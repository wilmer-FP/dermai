# Procesamiento de imágenes — DermAI

Módulo `ai/preprocessing`: pipeline de **OpenCV** que normaliza la imagen, separa la lesión de la piel circundante, clasifica sus píxeles por color y extrae características visuales.

> **Método heurístico y experimental.** No usa aprendizaje automático ni ha sido validado clínicamente. Mide **color**, no identifica tejidos: "compatible con tejido necrótico" significa "de color negro o marrón oscuro". No es un diagnóstico médico.

## 1. Uso

```python
from ai.preprocessing import analyze_image_bytes, PipelineConfig

output = analyze_image_bytes(open("lesion.jpg", "rb").read())
output.necrotic_area_ratio  # proporción 0–1 de la lesión con color compatible con necrosis
output.result               # dict JSON: composición, características, avisos y configuración
output.overlay              # imagen BGR con la región y los tejidos marcados
output.roi_mask             # máscara booleana de la región analizada
output.tissue_labels        # mapa de clases por píxel (0 fuera, 1 necrótico, 2 esfacelo, 3 granulación, 4 otro)
```

`analyze_image(image_bgr, config)` recibe una matriz BGR de OpenCV. Todos los parámetros están en `PipelineConfig` y `TissueThresholds`, y se guardan en `result["config"]` para poder reproducir cada análisis.

## 2. Etapas

```
imagen ─▶ redimensionado ─▶ reflejos ─▶ constancia de color ─▶ filtro bilateral ─▶ CIELAB
                                                                                    │
            visualización ◀── características ◀── clasificación por color ◀── segmentación
```

| Etapa | Archivo | Qué hace |
|---|---|---|
| Lectura | `io.py` | Decodifica JPG/PNG a BGR de 8 bits. Aplica la orientación EXIF, descarta el canal alfa y convierte escala de grises a color. |
| Redimensionado | `enhancement.py` | Lado mayor a 512 px (`target_size`), conservando la proporción, para que las medidas sean comparables. |
| Reflejos | `segmentation.py` | Marca los píxeles casi blancos y sin saturación (brillo especular) y los excluye de la estimación de color y de la clasificación. |
| Constancia de color | `enhancement.py` | *Shades of Gray* con p = 6 (Finlayson y Trezzi, 2004; uso en dermatología: Barata et al., 2015), aplicada al 50 % (`color_constancy_strength`). La corrección completa vuelve gris la propia piel en fotos dominadas por ella. |
| Reducción de ruido | `enhancement.py` | Filtro bilateral: suaviza el ruido y conserva los bordes. |
| Segmentación | `segmentation.py` | Toma como piel de referencia la mediana CIELAB de una franja del 8 % junto al borde. Calcula la distancia de color de cada píxel a esa referencia (ΔE con L* a mitad de peso, para tolerar sombras) y la umbraliza con Otsu, con un mínimo de ΔE 8. Después aplica apertura y cierre morfológicos, elige la componente conexa más grande y central y rellena sus huecos. |
| Clasificación por color | `tissue.py` | Esquema negro / amarillo / rojo de heridas en CIELAB (ver §3). |
| Características | `features.py` | Color, textura, bordes, forma y calidad (ver §4). |
| Visualización | `visualization.py` | Contorno verde de la región, negro/marrón en magenta y amarillo en amarillo, sobre la foto redimensionada. |

Si no se distingue ninguna lesión (diferencia de color insuficiente, o región por debajo del 0,5 % o por encima del 95 % de la imagen), se analiza la imagen completa y se avisa (`fallback_full_image`).

## 3. Clasificación por color

Los umbrales combinan valores absolutos y diferencias respecto a la piel de referencia (L\* 0–100, tono en grados).

| Clase | Criterio por defecto |
|---|---|
| Negro / marrón oscuro (compatible con necrosis) | L\* < mín(40, L\*piel − 25) y croma < 35. Se eliminan las estructuras finas (vello) con una apertura de 5 px. |
| Amarillo (compatible con esfacelo) | L\* ≥ 50, tono 50–115° y b\* ≥ máx(18, b\*piel + 8) |
| Rojo (compatible con granulación o inflamación) | Tono −30–45° y a\* ≥ máx(15, a\*piel + 8) |
| Otros tonos | El resto de la región |

La condición **relativa** del tejido oscuro evita que una lesión pigmentada en piel de fototipo oscuro se marque entera como "necrótica". Hay una prueba que lo comprueba en ambos sentidos: con la regla relativa no se marca, y solo con el umbral absoluto sí. Aun así, los umbrales de color dependen de la iluminación, la cámara y el tono de piel, y su sesgo no está evaluado.

La clase roja no distingue granulación de eritema o inflamación. Por eso la interfaz nombra las clases por su color.

## 4. Características extraídas (`result`)

| Sección | Contenido |
|---|---|
| `tissue_composition` | Proporción de cada clase sobre los píxeles válidos de la región (suman 1). |
| `segmentation` | Área relativa de la región, uso del respaldo de imagen completa, contacto con el borde y umbral ΔE. |
| `color` | L\*a\*b\* medio y desviación de la lesión, croma medio, piel de referencia y ΔE medio lesión–piel. |
| `texture` | Descriptores de Haralick de la GLCM (distancia 1, cuatro orientaciones, 32 niveles): contraste, homogeneidad, energía, correlación y entropía. Además, varianza del laplaciano. |
| `edges` | Densidad de bordes Canny (umbrales automáticos por mediana), gradiente medio y gradiente medio en el contorno (nitidez del borde). |
| `shape` | Área relativa, perímetro, circularidad (4πA/P²), solidez, excentricidad por momentos y relación de aspecto. Es `null` si se usó la imagen completa. |
| `quality` | Luminosidad media y desviación, nitidez y proporción de reflejos. |
| `warnings` | Avisos en español: sin lesión distinguible, lesión que toca el borde, resolución baja, desenfoque, imagen oscura o sobreexpuesta, reflejos. |
| `method`, `preprocessing`, `config` | Nombre y versión del método (`dermai-opencv-heuristic` 0.1.0), tamaños, constancia de color y configuración completa. |

## 5. Integración en el backend

- `POST /images/{id}/analyses` ejecuta el pipeline de forma síncrona: `pending → processing → completed` (o `failed`), en unos 50–200 ms por imagen.
  - Guarda `necrotic_area_ratio`, `result` y la imagen procesada (`<id>_processed.png` en `storage/images`).
  - `confidence` queda vacía, porque un umbral no produce una probabilidad calibrada.
- Si se indica `model_version_id`, el análisis queda en `pending` hasta la integración de modelos (Etapa 7). Así no se atribuyen a un modelo valores de la heurística.
- `GET /analyses/{id}/processed-image` devuelve la visualización. Al borrar la imagen se borran también las procesadas.
- El backend importa el paquete `ai` añadiendo la raíz del repositorio a `sys.path` (`backend/app/services/processing_service.py`).

## 6. Versión para el navegador

`frontend/src/analysis/heuristic.ts` es un port del pipeline a **TypeScript + OpenCV.js 5.0**. Es el que usa la demo pública en GitHub Pages, sin servidor (ver [deployment.md](deployment.md)).

Reproduce los mismos pasos, parámetros y redondeos:
- `round()` de Python con redondeo al par;
- truncamiento de `astype(uint8)`;
- percentiles lineales de NumPy;
- relleno de huecos con conectividad 4.

**Paridad con Python.** `scripts/generate-browser-fixtures.py` genera imágenes de referencia con los resultados exactos de Python, y `heuristic.test.ts` las compara:

| Imagen | Píxeles con la misma clase | Mayor diferencia en la composición |
|---|---|---|
| Herida de tres anillos | 99,998 % | 0,0001 |
| Lesión pigmentada en piel oscura | 99,997 % | 0,0000 |
| Lesión roja con vello y reflejos | 99,998 % | 0,0001 |
| Imagen uniforme (respaldo) | 100 % | 0,0000 |

Las pequeñas diferencias vienen de cálculos en coma flotante de 32 frente a 64 bits. Al decodificar la foto, el navegador aplica la orientación EXIF y reduce las imágenes de más de 2048 px antes del análisis.

## 7. Pruebas

`tests/ai/test_preprocessing.py` usa imágenes **sintéticas** de resultado conocido (`tests/ai/synthetic.py`), no imágenes clínicas:

- Lectura de PNG con alfa y en escala de grises; rechazo de datos no válidos.
- Redimensionado, corrección de una dominante de color y formas coherentes de las salidas.
- Segmentación de una elipse (IoU > 0,95) y respaldo de imagen completa en una imagen uniforme.
- Composición de una herida de tres anillos (±3 % del valor geométrico).
- Fototipo oscuro, escara negra, vello fino y reflejos.
- Descriptores GLCM y de forma, resultado JSON serializable y finito, visualización, determinismo y avisos.

```powershell
.\backend\.venv\Scripts\python -m pytest tests/ai
```

## 8. Limitaciones

- Supone una lesión aproximadamente centrada y rodeada de piel. Las fotos muy cercanas, en las que la herida llena el encuadre, dan una referencia de piel poco fiable; en ese caso se emite un aviso.
- Sombras, vendajes, marcadores, tatuajes o fondos que no son piel pueden segmentarse como lesión.
- La calibración se hizo con imágenes sintéticas y una sola foto real. Validar los umbrales exigiría un dataset anotado (Etapa 7).
