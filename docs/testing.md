# Pruebas — DermAI

## 1. Ejecutarlas

```powershell
# Todo: linting, pruebas de Python y del frontend, tipos y build
powershell -ExecutionPolicy Bypass -File scripts\test-all.ps1

# Por partes
.\backend\.venv\Scripts\python -m ruff check .
.\backend\.venv\Scripts\python -m pytest                       # backend e IA
.\backend\.venv\Scripts\python -m pytest -m "not integration"  # sin PostgreSQL
npm run coverage --prefix frontend                             # frontend, con cobertura
```

Las pruebas **no tocan los datos reales**:
- Usan SQLite en memoria o, en integración, transacciones de PostgreSQL que se revierten.
- Los archivos van a carpetas temporales.
- Las imágenes son sintéticas.

## 2. Resumen

| Conjunto | Pruebas | Cobertura de líneas |
|---|---|---|
| Backend (`tests/backend`) | 107 | 96 % entre backend e IA |
| Procesamiento y modelo (`tests/ai`) | 42 | (incluida arriba) |
| Frontend (`frontend/src/**/*.test.ts(x)`) | 94 | 90 %; las funciones que solo existen en un navegador real (canvas, `createImageBitmap`) se verificaron a mano |
| **Total** | **243** | |

En GitHub, el *workflow* `.github/workflows/ci.yml` ejecuta el linting y todas las pruebas, salvo las de PostgreSQL, en cada `push` y *pull request*.

## 3. Qué se prueba

### Backend

| Archivo | Pruebas | Contenido |
|---|---|---|
| `test_api_images.py` | 20 | Subida, validación (vacío, tamaño, extensión, contenido real, formato detectado), listado paginado, descarga y borrado de imágenes |
| `test_api_analyses.py` | 16 | Análisis con la heurística (herida sintética con proporción conocida), imagen procesada, fallos del procesamiento, historial y filtros, versiones de modelo |
| `test_model_inference.py` | 10 | Análisis con un modelo de PyTorch (confianza, imagen procesada), pesos ausentes o dañados, CLI de registro y activación de modelos |
| `test_privacy.py` | 13 | Eliminación de EXIF y GPS en JPEG sin recomprimir; giro físico según la orientación EXIF; bloques de texto en PNG; checksum del archivo guardado; aviso incrustado en la imagen procesada |
| `test_demo_mode.py` | 12 | Modo demo: sesión obligatoria, aislamiento entre sesiones en todas las rutas, sesión por parámetro para `<img>`, límite de peticiones (429), borrado de imágenes caducadas, `/health` y raíz, SQLite con claves foráneas |
| `test_robustness.py` | 11 | 503 sin base de datos (código real de conexión), borrado del archivo si falla el `commit`, protección contra *path traversal* |
| `test_models.py` | 10 | Modelos ORM: relaciones, cascadas, restricciones CHECK y valores por defecto |
| `test_migrations.py` | 4 | Subida y bajada de las migraciones (0001 y 0002); coinciden con los modelos; SQL de PostgreSQL |
| `test_config.py`, `test_health.py` | 6 | Configuración y `GET /health` |
| `test_postgres_integration.py` | 3 | **Integración con PostgreSQL**: esquema en la última versión, JSONB, enum nativo, restricciones |
| `test_postgres_api_integration.py` | 2 | **Integración con PostgreSQL**: flujo completo de la API (subida, análisis heurístico y con modelo, historial, imagen procesada, borrado en cascada) |

Las pruebas marcadas como `integration` se **omiten**, y pytest lo indica, si PostgreSQL no está en marcha.

### Procesamiento de imágenes y modelo

| Archivo | Pruebas | Contenido |
|---|---|---|
| `test_preprocessing.py` | 29 | Lectura (alfa, escala de grises, datos no válidos), redimensionado, constancia de color, segmentación de una elipse (IoU > 0,95), composición de una herida de tres anillos, fototipo oscuro, escara negra, vello, reflejos, descriptores GLCM y de forma, determinismo y avisos de calidad |
| `test_ml_models.py` | 13 | Máscaras de color a clases, métricas con valores conocidos, carga de datos, aumento determinista, U-Net con tamaños arbitrarios, guardado y carga del modelo, inferencia, y **un entrenamiento completo en miniatura** que comprueba todos los artefactos de la ejecución y la regeneración de informes |

Las imágenes de prueba son **sintéticas** (`tests/ai/synthetic.py`), con resultado geométrico conocido. Las pruebas de PyTorch se omiten si no está instalado.

### Frontend

| Archivo | Pruebas | Contenido |
|---|---|---|
| `analysis/heuristic.test.ts` | 18 | **Paridad con Python** del análisis en el navegador (OpenCV.js real, entorno `node`). Usa 4 imágenes de referencia generadas por `scripts/generate-browser-fixtures.py` y comprueba que coinciden el mapa de clases (≥ 99 % de píxeles; en la práctica 99,997–100 %), la composición, la segmentación, los avisos y las características. También prueba las utilidades. |
| `services/localBackend.test.ts` | 9 | Modo navegador con IndexedDB simulado (`fake-indexeddb`): subida, análisis, fallos, historial con filtro y paginación, 404 y borrado en cascada |
| `api.test.ts` | 17 | Cliente HTTP: URLs, multipart, JSON, mensajes de error de la API y genéricos por código, fallos de red |
| `AnalysisPage.test.tsx` | 13 | Resultados de la heurística y del modelo, selector de imagen procesada u original, ficha del modelo con atribución, reanálisis, borrado con confirmación y errores |
| `UploadPage.test.tsx` | 7 | Validación en el cliente, confirmación obligatoria, selector de método, flujo completo, reintento sin volver a subir la imagen |
| `HistoryPage.test.tsx` | 5 | Listado, estado vacío, filtro y paginación reflejados en la URL, reintento |
| `ImageDropzone.test.tsx` | 5 | Arrastrar y soltar, estado deshabilitado, descripción accesible |
| Otros | 20 | Validación de imágenes, formatos, lectura del resultado, sesión anónima (incluido almacenamiento bloqueado), diseño general (aviso siempre visible, aviso de demo, reintentos mientras el servidor despierta), página «Acerca de» con créditos |

Las páginas se prueban renderizando la aplicación completa con un router en memoria y dobles del cliente de la API (Vitest, Testing Library, jsdom). Las consultas usan roles y nombres accesibles.

## 4. Verificación manual realizada

En cada etapa se probó la aplicación real en el navegador (backend, PostgreSQL en Docker y Vite), en escritorio y en móvil (375 px), con tema claro y oscuro:
- subida y análisis con la heurística y con el modelo;
- imagen procesada y leyenda;
- historial, reanálisis y borrado;
- comportamiento con el backend apagado.

Al terminar se borraron los datos de prueba.

Para el despliegue se probó además la **imagen Docker del Space** en local:
- migraciones sobre SQLite y registro del modelo al arrancar;
- el frontend compilado para `/dermai/` contra esa API en otro origen (CORS), con el flujo completo con el modelo en CPU;
- aislamiento entre sesiones y rechazo de peticiones sin sesión.

El **modo navegador** se probó con el build de producción en un navegador real:
- el flujo completo dio el mismo resultado que Python (12,5 %, 29,5 %, 57,9 % y 0,1 %) en unos 3 s, incluida la primera descarga de OpenCV.js;
- la imagen procesada lleva el aviso incrustado;
- los datos persisten al recargar y el borrado vacía el historial;
- **no se hizo ninguna petición fuera del propio sitio**.

## 5. Lo que no está cubierto

- **Navegadores:** no hay pruebas automáticas en un navegador real (p. ej. Playwright); la interfaz se verificó a mano.
- **Rendimiento:** hay mediciones de PyTorch/ONNX CPU y WASM en Node y una prueba local en navegador; ver [deployment.md](deployment.md). No equivalen a mediciones de móviles, concurrencia o memoria aislada del navegador.
- **Validez clínica:** las pruebas comprueban que el software hace lo que dice, **no** que sus resultados sean clínicamente correctos. Ver [limitations.md](limitations.md).
## 6. Modelo entrenado en navegador (16-11-2026)

El frontend tiene ahora 100 pruebas: cuatro nuevas de paridad completa ONNX Runtime
Web/OpenCV.js contra referencias PyTorch y dos de identidad del modelo, historial,
borrado y fallo explícito sin heurística. El exportador prueba además ocho entradas
contra ONNX CPU, registra hashes y genera referencias sintéticas. El protocolo,
resultados medidos y límites de la comprobación visual están en [deployment.md](deployment.md).
Las referencias no contienen fotografías clínicas.
