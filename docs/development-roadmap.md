# Hoja de ruta de desarrollo — DermAI

Cada etapa se revisa y aprueba antes de avanzar a la siguiente.

| # | Etapa | Estado |
|---|-------|--------|
| 1 | Estructura inicial | ✅ Completada |
| 2 | Configuración del backend | ✅ Completada |
| 3 | Diseño de base de datos | ✅ Completada |
| 4 | Desarrollo de API REST | ✅ Completada |
| 5 | Desarrollo del frontend | ✅ Completada |
| 6 | Procesamiento de imágenes | ✅ Completada |
| 7 | Investigación e integración del modelo experimental | ✅ Completada |
| 8 | Pruebas y documentación | ✅ Completada |
| 9 | Despliegue gratuito (demo pública) | 🟡 En revisión |

Las 8 etapas del plan original se cerraron el 5 de noviembre de 2026. La Etapa 9 se añadió después para publicar una demo.

---

## Etapa 1 — Estructura inicial
- Crear la estructura de carpetas del repositorio.
- Redactar la documentación base (README, arquitectura, alcance, hoja de ruta).
- Definir `.gitignore` y `.env.example`.
- **Entregable:** esqueleto del proyecto listo para revisión.

## Etapa 2 — Configuración del backend
- Crear entorno virtual y archivo de dependencias.
- Configurar FastAPI, carga de variables de entorno y logging.
- Endpoint de verificación de estado (`/health`).
- **Entregable:** servidor FastAPI ejecutándose localmente.
- **Resultado:** entorno virtual en `backend/.venv` (Python 3.12), `requirements.txt` y `requirements-dev.txt`, configuración con `pydantic-settings` (`core/config.py`), logging centralizado (`core/logging.py`), CORS, endpoint `GET /api/v1/health` y 6 pruebas con pytest.

## Etapa 3 — Diseño de base de datos
- Modelo entidad-relación (imágenes, análisis, versiones de modelo).
- Configuración del ORM y sistema de migraciones.
- **Entregable:** esquema inicial de PostgreSQL documentado y migrado.
- **Resultado:** tablas `images`, `model_versions` y `analyses` con SQLAlchemy 2.0, migración inicial `0001` de Alembic, conexión y sesiones en `core/database.py`, documentación en [database.md](database.md) y 16 pruebas nuevas (modelos, migraciones e integración con PostgreSQL). PostgreSQL 16 de desarrollo en Docker (`docker-compose.yml`, puerto 5433) con la migración `0001` aplicada.

## Etapa 4 — Desarrollo de API REST
- Endpoints de carga de imágenes, consulta de análisis e historial.
- Esquemas Pydantic de validación y manejo de errores.
- Documentación automática con OpenAPI.
- **Entregable:** API funcional con pruebas básicas.
- **Resultado:** 10 endpoints nuevos (imágenes, análisis, historial y versiones de modelo) con capa de servicios, almacenamiento local en `storage/images`, validación del contenido real de las imágenes con Pillow, errores homogéneos (`{"detail": ...}`), documentación en [api.md](api.md) y 31 pruebas nuevas (53 en total). Probada también contra el servidor real con PostgreSQL. Los análisis se registran en `pending`; el procesamiento llegará en las Etapas 6 y 7.

## Etapa 5 — Desarrollo del frontend
- Inicializar proyecto React + TypeScript.
- Vistas de carga, resultados e historial.
- Cliente HTTP hacia la API y aviso de uso no diagnóstico.
- **Entregable:** interfaz web conectada al backend.
- **Resultado:** aplicación React 19 + TypeScript con Vite, con tres vistas (analizar, resultado e historial), aviso de uso no diagnóstico en todas ellas, validación en el cliente y confirmación de que la imagen no contiene datos identificables. Cliente HTTP tipado, proxy de desarrollo hacia el backend, tema claro y oscuro, y diseño adaptable a móvil. Documentación en [frontend.md](frontend.md) y 33 pruebas con Vitest y Testing Library. Probada también contra el backend real con PostgreSQL.

## Etapa 6 — Procesamiento de imágenes
- Pipeline OpenCV: redimensionado, normalización de color, reducción de ruido, segmentación de la región de interés.
- Extracción de características visuales (color, textura, bordes).
- **Entregable:** módulo de preprocesamiento reutilizable y probado.
- **Resultado:** paquete `ai/preprocessing` con OpenCV 5 y NumPy:
  - Preprocesamiento: redimensionado a 512 px, exclusión de reflejos, constancia de color *Shades of Gray* parcial y filtro bilateral.
  - Segmentación de la lesión por diferencia de color con la piel circundante (Otsu y morfología).
  - Clasificación heurística por color (negro / amarillo / rojo) con reglas relativas a la piel.
  - Características de color, textura (GLCM), bordes, forma y calidad, con avisos.
  - El backend ejecuta el pipeline al solicitar un análisis y sirve la imagen procesada (`GET /analyses/{id}/processed-image`).
  - El frontend muestra la imagen procesada, la composición por color, las características y los avisos.
  - Documentación en [image-processing.md](image-processing.md). 26 pruebas nuevas del módulo con imágenes sintéticas y 5 nuevas del backend.

## Etapa 7 — Investigación e integración del modelo experimental
- Revisión de literatura y selección de datasets públicos con licencia adecuada.
- Diseño, entrenamiento y evaluación de modelos en PyTorch.
- Registro reproducible de experimentos y versionado de modelos.
- Integración de la inferencia en el backend.
- **Entregable:** modelo experimental integrado con métricas documentadas.
- **Resultado:** prueba de concepto documentada en [model.md](model.md).
  - **Datos:** revisión de datasets públicos con máscaras de tejido; se eligió WoundTissue (CC BY-NC-SA 4.0), cuyo repositorio solo publica 13 de sus 147 imágenes.
  - **Modelo:** U-Net con encoder ResNet-18 de ImageNet (PyTorch 2.11, CUDA 12.8).
  - **Entrenamiento reproducible** (`ai/experiments/train.py`): configuración, entorno y hashes de datos; validación cruzada de 5 particiones; comparación con la heurística; ficha del modelo.
  - **Resultado:** Dice sin fondo de 0,69 ± 0,18 por partición, frente a 0,20 agregado de la heurística. No es representativo con 13 imágenes.
  - **Integración:** registro de versiones con `python -m app.cli register-model`, inferencia en el backend con confianza no calibrada, y selector de método y ficha del modelo en el frontend.
  - **Pruebas:** 23 nuevas de Python (13 del modelo, 10 del backend y la CLI) y 3 nuevas del frontend.

## Etapa 8 — Pruebas y documentación
- Pruebas unitarias y de integración (backend y módulo de IA).
- Documentación técnica final, guía de instalación y limitaciones conocidas.
- Revisión de consideraciones éticas y avisos.
- **Entregable:** prototipo documentado listo para portafolio.
- **Resultado:**
  - **Pruebas:** 194 automáticas (91 del backend, 42 de IA y 61 del frontend), con cobertura de líneas del 97 % en Python y en el frontend. Incluyen nuevas pruebas de integración del flujo completo de la API con PostgreSQL, robustez (503, reversión al fallar el guardado, *path traversal*) y arrastrar y soltar.
  - **Calidad:** linting con `ruff` y un script único de verificación (`scripts/test-all.ps1`).
  - **Ética:** eliminación de metadatos EXIF y GPS al subir, aviso incrustado en la imagen procesada, y página «Acerca de» con atribución del dataset y licencias.
  - **Documentación:** [installation.md](installation.md), [testing.md](testing.md), [limitations.md](limitations.md) y [ethics.md](ethics.md); README final.

## Etapa 9 — Despliegue gratuito (demo pública)
- Frontend en GitHub Pages y API en Hugging Face Spaces, sin coste.
- Modo demo para publicar sin cuentas de usuario.
- **Entregable:** demo pública documentada en [deployment.md](deployment.md).
- **Preparado y probado en local:**
  - **Modo demo:** sesión anónima por navegador, aislamiento entre visitantes, borrado automático a las 6 h y límite de 30 operaciones por hora e IP. Migración `0002`.
  - **Base de datos:** soporte de SQLite.
  - **Space:** imagen Docker con PyTorch para CPU, arranque con migraciones y registro del modelo, y scripts de montaje y publicación.
  - **Frontend:** ruta base `/dermai/` y reintentos mientras el servidor despierta.
  - **GitHub Actions:** CI y despliegue en Pages.
  - **Pruebas:** 19 nuevas (213 en total).
- **Publicado:** repositorio <https://github.com/wilmer-FP/dermai> (MIT) y web <https://wilmer-fp.github.io/dermai/>.
- **Cambio de plan.** Hugging Face pasó a exigir PRO para Spaces Docker, así que la API no se publicó. En su lugar, la demo analiza **en el navegador**:
  - la heurística se portó a TypeScript + OpenCV.js, con paridad del 99,997–100 % de píxeles frente a Python;
  - los datos van en IndexedDB y las fotos no salen del dispositivo;
  - 30 pruebas nuevas, 243 en total.
- El despliegue de la API (Docker, modo demo) queda preparado como opción de pago.
