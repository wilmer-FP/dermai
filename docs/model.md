# Modelo experimental — DermAI

Segmentación de tejidos de herida con **PyTorch**: una U-Net con encoder ResNet-18 preentrenado en ImageNet, entrenada con la muestra pública del dataset WoundTissue.

> **Prueba de concepto.** El modelo se entrenó con solo 13 imágenes. Sus métricas tienen una variabilidad enorme y no son representativas. No es una herramienta de diagnóstico médico, y sus resultados no deben usarse para tomar decisiones clínicas.

## 1. Revisión de datos y literatura

Hay pocos datasets públicos con máscaras **por tipo de tejido** (no solo de "herida sí/no"), y casi todos son de uso no comercial:

| Dataset | Contenido | Licencia | Decisión |
|---|---|---|---|
| WoundTissue (Kabir et al., 2025) | El artículo describe 147 imágenes con 7 clases (granulación, esfacelo, necrosis, maceración, tendón, hueso, fondo). El repositorio solo publica **13 pares**. | CC BY-NC-SA 4.0, explícita | **Elegido.** Licencia clara y clases que incluyen necrosis. |
| DFUTissue (UWM BigData) | 110 úlceras de pie diabético etiquetadas y 600 sin etiquetar | Sin archivo de licencia; solo pide citar | Descartado por licencia ambigua. |
| ComplexWoundDB | 2727 imágenes con 5 clases (incluida necrosis seca) | No indicada | Descartado por licencia no indicada. |
| LUTSeg | 141 úlceras de lepra con 5 clases | Contradictoria (CC BY vs. CC BY-NC-ND) | Descartado. |
| FUSeg y otras de Kaggle | Máscaras binarias de herida | Variable | No sirven: no distinguen tejidos. |

En la literatura reciente (Kabir et al., 2025; trabajos con DFUTissue), las U-Net con encoder preentrenado son la referencia habitual para segmentar tejidos con pocos datos. Con datasets pequeños, el preentrenamiento en ImageNet es la mejora más importante. Esa es la elección aquí: ResNet-18, pequeño y rápido de entrenar en una GPU doméstica.

Detalles del dataset y cómo descargarlo: [`ai/datasets/README.md`](../ai/datasets/README.md).

## 2. Modelo

| Elemento | Elección |
|---|---|
| Arquitectura | U-Net: encoder ResNet-18 (torchvision, ImageNet) y decoder con conexiones de salto a 1/2, 1/4, 1/8 y 1/16 |
| Clases | 7: fondo, granulación, esfacelo, necrosis, maceración, tendón, hueso |
| Entrada | Recortes de 256 px; en inferencia, lado mayor de 256 px y salida al tamaño de la imagen |
| Aumento de datos | Recorte aleatorio (50–100 % del área), volteos, rotaciones de 90° y variaciones leves de brillo, contraste, saturación y tono. Las variaciones son pequeñas porque el color es informativo. |
| Pérdida | Entropía cruzada ponderada (1/√frecuencia de clase) + pérdida Dice |
| Optimización | AdamW (lr 3·10⁻⁴, *weight decay* 10⁻⁴), coseno, 40 épocas, lotes de 8, 20 recortes por imagen y época |

Código: `ai/models/` (`unet.py`, `classes.py`, `data.py`, `transforms.py`, `inference.py`) y `ai/evaluation/metrics.py`.

## 3. Entrenamiento reproducible

```powershell
# Desde la raíz del proyecto
.\backend\.venv\Scripts\python -m ai.experiments.train --config ai/experiments/configs/unet_resnet18_woundtissue.json
```

Cada ejecución crea `ai/experiments/runs/<fecha>_<nombre>/` (no versionado) con:

| Archivo | Contenido |
|---|---|
| `config.json` | Configuración exacta |
| `environment.json` | Versiones de Python, PyTorch, NumPy y OpenCV; GPU; ajustes deterministas; SHA-256 de cada imagen y máscara |
| `history.csv` | Pérdidas por época de cada partición y del modelo final |
| `metrics.json` | Validación cruzada, comparación con la heurística y resumen |
| `model.pt`, `model_meta.json` | Modelo final (entrenado con todas las imágenes) y sus metadatos |
| `model_card.md` | Ficha del modelo con métricas y limitaciones |

**Evaluación.** Se usa validación cruzada de 5 particiones, porque con 13 imágenes no hay datos para un conjunto de prueba aparte. El número de épocas es fijo, sin selección por validación, para no sobreajustar a las particiones.

Las métricas se calculan sobre la matriz de confusión acumulada de todas las particiones:
- Dice, IoU, precisión, sensibilidad y especificidad por clase.
- El error absoluto medio de la proporción necrótica por imagen.

**Comparación con la heurística.** La heurística de la Etapa 6 se evalúa sobre las mismas imágenes, agrupando las clases en fondo, granulación, esfacelo, necrosis y otros.

Los pesos de ImageNet se guardan en `ai/models/cache/` (no versionado), no en la caché global del usuario.

## 4. Registro y uso en la aplicación

```powershell
# Desde backend/: copia model.pt a ai/models/weights/<nombre>-<versión>.pt y crea la fila en model_versions
.\.venv\Scripts\python -m app.cli register-model ..\ai\experiments\runs\<ejecución> --activate
.\.venv\Scripts\python -m app.cli deactivate-model <nombre> <versión>
```

- La versión registrada guarda su ruta de pesos, su descripción y el resumen de métricas.
- El frontend ofrece los modelos **activos** como método de análisis, junto a la heurística.
- La página de resultado muestra:
  - la composición de tejidos;
  - la confianza (no calibrada) y su definición;
  - la imagen con las clases coloreadas;
  - la ficha del modelo, con sus métricas frente a la heurística.
- La inferencia usa el dispositivo de `AI_DEVICE` (`cpu` por defecto; `cuda` o `auto` para la GPU). El modelo se carga una vez y se reutiliza mientras el archivo no cambie.

**Confianza.** Es la media, sobre los píxeles de herida, de la probabilidad *softmax* de la clase predicha. No está calibrada: un modelo sobreajustado puede dar valores altos y equivocarse.

## 5. Resultados

Ejecución `20261105T231652Z_unet-resnet18-woundtissue`:
- **Hardware y duración:** RTX 5060, PyTorch 2.11 + CUDA 12.8, 11,4 minutos en total (5 particiones y el modelo final).
- **Datos:** 13 imágenes. Imágenes que contienen cada clase: granulación 8, esfacelo 5, maceración 5, necrosis 2, hueso 1 y tendón 0.

**Validación cruzada de 5 particiones** (Dice por grupo, 1 = perfecto):

| Grupo | Modelo | Heurística OpenCV (Etapa 6) |
|---|---|---|
| Granulación | 0,954 | 0,000 |
| Esfacelo | 0,817 | 0,551 |
| Necrosis | 0,958 | 0,142 |
| Otros (maceración, tendón, hueso) | 0,754 | 0,102 |
| **Media sin fondo, agregada** | **0,870** | **0,199** |
| **Media sin fondo por partición** | **0,694 ± 0,179** (0,83, 0,58, 0,59, 0,50, 0,98) | — |

| Otra métrica | Modelo | Heurística |
|---|---|---|
| Error absoluto medio de la proporción necrótica por imagen | 0,017 | 0,139 |
| Exactitud por píxel (5 grupos) | 0,963 | 0,620 |

**Cómo leer estas cifras:**

- **La cifra agregada exagera.** Suma los píxeles de todas las particiones y la dominan las clases grandes. La media **por partición (0,69 ± 0,18)** es más representativa, y su dispersión muestra lo inestable que es la estimación con tan pocas imágenes. La interfaz muestra primero esta cifra.
- **El Dice de necrosis (0,96) no es fiable.** Solo 2 imágenes tienen necrosis, y en ambas ocupa el 96–100 % del encuadre. Basta con reconocer "toda la imagen es oscura".
- **El hueso no se detecta (Dice 0):** aparece en una sola imagen.
- **La heurística falla en este dataset**, y la causa es conocida: son recortes de herida sin piel alrededor, así que el borde que usa como "piel de referencia" es la propia herida. Es la limitación documentada en [image-processing.md](image-processing.md), ahora medida.

**Prueba fuera de distribución.** Con una herida sintética sobre piel clara, el modelo marcó como herida casi toda la imagen: clasificó la piel sana como esfacelo, maceración o hueso, con una confianza del 87 %. Nunca vio piel sana, porque las imágenes de entrenamiento son recortes de herida. Es una demostración práctica de por qué la confianza no está calibrada y del riesgo de usar el modelo fuera de su distribución.

## 6. Limitaciones

- **Datos insuficientes.** Con 13 imágenes (solo 2 con necrosis), cualquier métrica tiene intervalos de confianza enormes. El modelo es una demostración técnica del flujo completo, no un modelo útil.
- **Cambio de dominio.** Las imágenes de WoundTissue son recortes ajustados de heridas; fotos con mucha piel sana, fondo o lesiones que no son heridas (p. ej. eritemas) quedan fuera de su distribución.
- **Sin evaluación de sesgos** por tono de piel, cámara o iluminación.
- **Licencia.** WoundTissue es CC BY-NC-SA 4.0. El modelo derivado solo puede usarse con fines no comerciales y, si se distribuye, con la misma licencia. Por eso los pesos no se versionan.
- **Para reentrenar con más datos** (por ejemplo, el dataset completo si los autores lo facilitan), basta con apuntar `data_root` a carpetas `image/` y `label/` con el mismo formato y cambiar `version` en la configuración.

## 7. Referencias

- M. A. Kabir, N. Roy, M. E. Hossain, J. Featherston y S. Ahmed. *Deep Learning for Wound Tissue Segmentation: A Comprehensive Evaluation using A Novel Dataset*. arXiv:2502.10652, 2025.
- O. Ronneberger, P. Fischer y T. Brox. *U-Net: Convolutional Networks for Biomedical Image Segmentation*. MICCAI, 2015.
- K. He, X. Zhang, S. Ren y J. Sun. *Deep Residual Learning for Image Recognition*. CVPR, 2016.
- Repositorios consultados: [WoundTissue](https://github.com/akabircs/WoundTissue), [DFUTissueSegNet](https://github.com/uwm-bigdata/DFUTissueSegNet), [ComplexWoundDB](https://github.com/recogna-lab/datasets/tree/master/ComplexWoundDB).
