# API REST — DermAI

Base: `http://127.0.0.1:8000/api/v1` · Documentación interactiva (OpenAPI): `http://127.0.0.1:8000/docs`

> Todas las salidas de análisis son **experimentales** e incluyen el campo `disclaimer`. DermAI no realiza diagnósticos médicos.

## 1. Endpoints

| Método | Ruta | Descripción | Respuestas |
|---|---|---|---|
| GET | `/health` | Estado del servicio | 200 |
| POST | `/images` | Subir una imagen (`multipart/form-data`, campo `file`) | 201, 413, 415, 422 |
| GET | `/images` | Listar imágenes (paginado, más recientes primero) | 200 |
| GET | `/images/{image_id}` | Metadatos de una imagen | 200, 404 |
| GET | `/images/{image_id}/file` | Descargar el archivo de la imagen | 200, 404 |
| DELETE | `/images/{image_id}` | Eliminar la imagen, sus análisis y sus archivos | 204, 404 |
| POST | `/images/{image_id}/analyses` | Solicitar y procesar un análisis | 201, 404 |
| GET | `/images/{image_id}/analyses` | Análisis de una imagen (paginado) | 200, 404 |
| GET | `/analyses` | Historial de análisis; filtro opcional `status` | 200, 422 |
| GET | `/analyses/{analysis_id}` | Detalle de un análisis | 200, 404 |
| GET | `/analyses/{analysis_id}/processed-image` | Imagen procesada (PNG) con la región y los tejidos marcados, y el aviso de uso no diagnóstico en una franja inferior | 200, 404 |
| GET | `/model-versions` | Versiones de modelo; filtro opcional `active_only` | 200 |

**Paginación:** parámetros `limit` (1–100, por defecto 20) y `offset` (≥ 0). Las respuestas paginadas tienen la forma:

```json
{ "items": [ ... ], "total": 42, "limit": 20, "offset": 0 }
```

## 2. Subida de imágenes

```powershell
curl.exe -F "file=@lesion.jpg" http://127.0.0.1:8000/api/v1/images
```

Validaciones, en este orden:

1. El archivo no puede estar vacío → **422**.
2. Tamaño máximo `MAX_UPLOAD_SIZE_MB` (10 MB por defecto) → **413**.
3. La extensión debe estar en `ALLOWED_IMAGE_EXTENSIONS` (`jpg`, `jpeg`, `png`) → **415**.
4. El contenido se abre con Pillow: si no es una imagen válida → **422**.
5. El formato **real** detectado (JPEG o PNG) debe estar permitido → **415**. El `content_type` guardado es el detectado, no el que declara el cliente.

El nombre original se conserva sin rutas. El archivo se guarda como `STORAGE_PATH/images/<uuid>.<ext>`, y el nombre interno nunca se expone en la API.

**Metadatos.** Antes de guardar se eliminan los metadatos de la foto:
- JPEG: EXIF, GPS, XMP, IPTC y comentarios, **sin recomprimir**. Si la orientación EXIF no es la normal, la imagen se gira físicamente.
- PNG: bloques de texto y fecha.

Por eso `file_size_bytes`, `width`, `height` y `checksum_sha256` corresponden al archivo **guardado**, que puede diferir del enviado.

Respuesta `201`:

```json
{
  "id": "e201c49a-4a85-402f-9b84-84eafa7eafb6",
  "original_filename": "lesion.jpg",
  "content_type": "image/jpeg",
  "file_size_bytes": 677,
  "width": 64,
  "height": 48,
  "checksum_sha256": "…",
  "created_at": "2026-11-05T16:30:00Z"
}
```

## 3. Análisis

`POST /images/{image_id}/analyses` acepta un cuerpo JSON opcional:

```json
{ "model_version_id": "uuid-de-una-version-de-modelo" }
```

Sin `model_version_id`, el análisis se procesa en la misma petición con el pipeline heurístico de OpenCV (ver [image-processing.md](image-processing.md)):

- `status` queda en `completed`, o en `failed` con `error_message` si la imagen no pudo procesarse.
- `necrotic_area_ratio` es la proporción de la lesión con color compatible con tejido necrótico.
- `result` contiene la composición por color, las características visuales y los avisos de calidad.
- `confidence` queda en `null`, porque el método no produce una probabilidad.
- La imagen procesada se obtiene en `GET /analyses/{id}/processed-image` cuando `has_processed_image` es `true`.

Con `model_version_id`, el análisis usa ese modelo de PyTorch (ver [model.md](model.md)):

- `result.method.type` es `"model"`.
- `confidence` es la probabilidad media, **no calibrada**, que el modelo asigna a la clase predicha en los píxeles de herida. Su definición viaja en `result.confidence_definition`.
- `necrotic_area_ratio` es la proporción de la herida predicha como necrosis.
- `result.class_composition` contiene la proporción de las 6 clases de tejido.
- Si el modelo no puede usarse (PyTorch no instalado, pesos ausentes o dañados), el análisis queda en `failed` con el motivo en `error_message`.

Los modelos disponibles se consultan en `GET /model-versions?active_only=true`.

Respuesta (resumida):

```json
{
  "id": "a4110c1d-4268-4835-8200-515ada72e12b",
  "image_id": "e201c49a-4a85-402f-9b84-84eafa7eafb6",
  "model_version_id": null,
  "status": "completed",
  "necrotic_area_ratio": 0.1264,
  "confidence": null,
  "result": {
    "method": { "name": "dermai-opencv-heuristic", "version": "0.1.0", "description": "…" },
    "tissue_composition": { "necrotic": 0.1264, "slough": 0.2948, "granulation": 0.5781, "other": 0.0008 },
    "segmentation": { "roi_area_ratio": 0.2866, "fallback_full_image": false, "border_contact": 0.0, "threshold_delta_e": 20.7 },
    "color": { "…": "…" }, "texture": { "…": "…" }, "edges": { "…": "…" }, "shape": { "…": "…" },
    "quality": { "…": "…" },
    "warnings": [],
    "config": { "…": "…" }
  },
  "error_message": null,
  "created_at": "2026-11-05T16:30:01Z",
  "completed_at": "2026-11-05T16:30:01Z",
  "has_processed_image": true,
  "disclaimer": "Prototipo experimental con fines educativos. No es una herramienta de diagnóstico médico."
}
```

Valores de `status`: `pending`, `processing`, `completed`, `failed`.

## 4. Modo demo (despliegue público)

Con `DEMO_MODE=true` (ver [deployment.md](deployment.md)):

- **Identificador de sesión obligatorio.** Todas las rutas de imágenes y análisis exigen un identificador anónimo de sesión, de 16 a 64 caracteres alfanuméricos o guiones. Va en la cabecera `X-DermAI-Session` o en el parámetro `?session=`; el parámetro existe para `<img src>`, que no envía cabeceras.
  - Si falta, la respuesta es **400**.
  - Los recursos de otra sesión responden **404**.
- **Límite de uso.** `POST /images` y `POST /images/{id}/analyses` están limitados por IP (`DEMO_RATE_LIMIT_PER_HOUR`). Al superarlo, la respuesta es **429**.
- **Borrado automático.** Las imágenes se borran pasadas `DEMO_RETENTION_HOURS`.
- **Estado.** `GET /health` incluye `demo_mode` y `demo_retention_hours`.
- **Raíz.** `GET /` describe la API (documentación, estado, frontend y aviso).

## 5. Errores

Todos los errores devuelven JSON con un campo `detail`:

| Código | Causa |
|---|---|
| 404 | Imagen, análisis o versión de modelo inexistente; archivo o imagen procesada ausente |
| 413 | Archivo mayor que `MAX_UPLOAD_SIZE_MB` |
| 415 | Extensión o formato real no permitido |
| 422 | Archivo vacío, imagen no válida, UUID mal formado o parámetros fuera de rango |
| 400 | Modo demo: falta el identificador de sesión o no es válido |
| 429 | Modo demo: límite de subidas y análisis alcanzado |
| 503 | `DATABASE_URL` no configurada |

```json
{ "detail": "Imagen no encontrada." }
```

## 6. Organización del código

| Capa | Archivos |
|---|---|
| Rutas | `backend/app/api/routes/` (`images.py`, `analyses.py`, `model_versions.py`, `health.py`) |
| Dependencias | `backend/app/api/deps.py` (sesión de BD, configuración, almacenamiento, paginación) |
| Esquemas | `backend/app/schemas/` (`ImageRead`, `AnalysisCreate`, `AnalysisRead`, `ModelVersionRead`, `Page`) |
| Servicios | `backend/app/services/` (`image_service.py`, `analysis_service.py`, `processing_service.py`, `storage.py`) |
| Procesamiento | `ai/preprocessing/` (pipeline de OpenCV) |
| Errores | `backend/app/core/exceptions.py` |
| Pruebas | `tests/backend/test_api_images.py`, `tests/backend/test_api_analyses.py`, `tests/ai/test_preprocessing.py` |
