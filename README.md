# DermAI

**DermAI** es un prototipo web de investigación experimental para analizar fotografías de lesiones cutáneas, con especial interés en las características visuales asociadas al **tejido necrótico**. Es un proyecto de portafolio que combina Ingeniería de Sistemas y Medicina.

> ⚠️ **Advertencia:** DermAI es un prototipo con fines **educativos y experimentales**. **No es una herramienta de diagnóstico médico**, no ha sido validado clínicamente y no sustituye la evaluación de profesionales sanitarios. Ningún resultado generado por el sistema debe usarse para tomar decisiones clínicas.

**Demo en línea** (gratuita, puede tardar 1–2 minutos en despertar): <https://wilmer-fp.github.io/dermai/> · API: <https://huggingface.co/spaces/Wilmer-FP/dermai>

---

## Problema a investigar

La valoración visual de lesiones cutáneas, en particular la identificación de tejido necrótico en heridas, depende en gran medida de la experiencia del observador y puede variar entre evaluadores. DermAI explora si el procesamiento de imágenes y el aprendizaje profundo pueden extraer de forma reproducible características visuales (color, textura, bordes, proporción de áreas) que ayuden a **estudiar** estos patrones en un entorno controlado de investigación.

## Qué hace

- **Subida segura de fotografías JPG/PNG.**
  - Se valida el contenido real del archivo, no solo su extensión.
  - Se eliminan sus metadatos (EXIF, ubicación GPS).
- **Dos métodos de análisis:**
  - **Heurística de OpenCV:** normaliza tamaño y color, separa la lesión de la piel circundante y clasifica sus píxeles por color (negro, amarillo y rojo).
  - **Modelo experimental de PyTorch:** U-Net con encoder ResNet-18 que segmenta 6 tipos de tejido de herida. Es una **prueba de concepto** entrenada con 13 imágenes públicas.
- **Resultados explicados:**
  - Proporción de la lesión compatible con tejido necrótico y composición por tejido.
  - Imagen procesada con leyenda y aviso incrustado.
  - Características de color, textura (GLCM), bordes y forma, y avisos de calidad de la foto.
- **Historial** paginado y filtrable, reanálisis y borrado completo de una imagen con sus análisis.
- **Entrenamiento reproducible:**
  - Se registran configuración, versiones, semilla y hashes de los datos.
  - Validación cruzada y comparación con la heurística.
  - Ficha del modelo y registro de versiones en la base de datos.

## Resultados del modelo (prueba de concepto)

| Validación cruzada de 5 particiones (13 imágenes) | Modelo | Heurística |
|---|---|---|
| Dice sin fondo, media por partición | 0,69 ± 0,18 | — |
| Dice sin fondo, agregado | 0,87 | 0,20 |
| Error medio en la proporción necrótica | 0,017 | 0,139 |

Con 13 imágenes, estas cifras **no son representativas**. El modelo falla con fotos que incluyen piel sana y su confianza no está calibrada. Ver [docs/model.md](docs/model.md).

## Tecnologías

| Capa | Tecnología |
|---|---|
| Frontend | React 19, TypeScript, Vite 7, React Router 7 |
| Backend | Python 3.12, FastAPI, SQLAlchemy 2, Alembic, Pydantic |
| Base de datos | PostgreSQL 16 (Docker) |
| Procesamiento de imágenes | OpenCV 5, NumPy, Pillow |
| Inteligencia artificial | PyTorch 2.11 + CUDA 12.8, torchvision |
| Calidad | pytest, Vitest + Testing Library, ruff, cobertura con pytest-cov y v8 |

## Arquitectura

```
┌──────────────────┐  HTTP/JSON (proxy /api)  ┌──────────────────────┐   SQL   ┌──────────────┐
│ Frontend         │ ───────────────────────▶ │ Backend FastAPI      │ ──────▶ │ PostgreSQL   │
│ React + TS (Vite)│ ◀─────────────────────── │ api · services       │ ◀────── │ (Docker)     │
└──────────────────┘                          └──────────┬───────────┘         └──────────────┘
                                                         │ módulo Python
                                     ┌───────────────────┼────────────────────┐
                                     ▼                   ▼                    ▼
                           ┌──────────────────┐ ┌──────────────────┐ ┌────────────────┐
                           │ ai/preprocessing │ │ ai/models        │ │ storage/       │
                           │ OpenCV           │ │ PyTorch (U-Net)  │ │ imágenes       │
                           └──────────────────┘ └──────────────────┘ └────────────────┘
```

Detalle en [docs/architecture.md](docs/architecture.md).

## Estructura del repositorio

```
dermai/
├── backend/        # API REST: app/ (api, core, models, schemas, services, cli), alembic/
├── frontend/       # Aplicación React + TypeScript (src/: pages, components, hooks, services, types)
├── ai/
│   ├── preprocessing/  # Pipeline de OpenCV (heurística)
│   ├── models/         # U-Net, datos, aumento, inferencia
│   ├── evaluation/     # Métricas de segmentación
│   ├── experiments/    # train.py y configuraciones (ejecuciones en runs/, no versionadas)
│   └── datasets/       # README del dataset (los datos no se versionan)
├── tests/          # backend/ y ai/ (las pruebas del frontend están junto a su código)
├── deploy/         # Space de Hugging Face (Dockerfile, arranque, publicación)
├── .github/        # GitHub Actions: CI y despliegue del frontend en Pages
├── scripts/        # db-init.ps1, test-all.ps1, build-space.ps1
├── storage/        # Imágenes subidas (no versionado)
└── docs/           # Documentación
```

## Inicio rápido (Windows)

Requisitos: Python 3.12, Node.js 20+ y Docker Desktop. Guía completa, con PyTorch, modelo y problemas frecuentes, en **[docs/installation.md](docs/installation.md)**.

```powershell
# 1. Backend y base de datos
cd backend; py -3.12 -m venv .venv; .\.venv\Scripts\python -m pip install -r requirements-dev.txt; cd ..
powershell -ExecutionPolicy Bypass -File scripts\db-init.ps1
cd backend; .\.venv\Scripts\python -m alembic upgrade head; cd ..

# 2. Frontend
npm install --prefix frontend
```

```powershell
# Terminal 1: API en http://127.0.0.1:8000 (documentación en /docs)
.\backend\.venv\Scripts\python -m uvicorn app.main:app --app-dir backend --reload
```

```powershell
# Terminal 2: interfaz en http://127.0.0.1:5173
npm run dev --prefix frontend
```

## Pruebas

```powershell
powershell -ExecutionPolicy Bypass -File scripts\test-all.ps1
```

**213 pruebas automáticas** (104 del backend, 42 de procesamiento y modelo, 67 del frontend), con cobertura de líneas del 96 %. Incluyen:
- integración con PostgreSQL;
- un entrenamiento completo en miniatura;
- privacidad (eliminación de EXIF y GPS), robustez y el modo demo.

En GitHub se ejecutan automáticamente en cada `push` (GitHub Actions).

Ver [docs/testing.md](docs/testing.md).

## Documentación

| Documento | Contenido |
|---|---|
| [Instalación](docs/installation.md) | Puesta en marcha paso a paso y problemas frecuentes |
| [Despliegue](docs/deployment.md) | Demo gratuita: GitHub Pages y Hugging Face Spaces, modo demo |
| [Arquitectura](docs/architecture.md) | Componentes, comunicación y flujo |
| [Base de datos](docs/database.md) | Modelo entidad-relación, migraciones y PostgreSQL en Docker |
| [API REST](docs/api.md) | Endpoints, validaciones, respuestas y errores |
| [Frontend](docs/frontend.md) | Vistas, conexión con la API y organización |
| [Procesamiento de imágenes](docs/image-processing.md) | Pipeline de OpenCV, clasificación por color y características |
| [Modelo experimental](docs/model.md) | Revisión de datos, U-Net, entrenamiento, resultados y limitaciones |
| [Pruebas](docs/testing.md) | Estrategia, cobertura y lo que no está cubierto |
| [Limitaciones](docs/limitations.md) | Limitaciones clínicas, técnicas, de sesgo y de privacidad |
| [Consideraciones éticas](docs/ethics.md) | Uso no diagnóstico, privacidad, licencias, equidad y seguridad |
| [Alcance](docs/project-scope.md) · [Hoja de ruta](docs/development-roadmap.md) | Objetivos, criterios de éxito y etapas |

## Consideraciones éticas

- **Uso no diagnóstico.** El aviso está siempre visible en la interfaz, en cada respuesta de la API y en la imagen procesada.
- **Privacidad.** No se piden datos personales, se eliminan los metadatos de las fotos y el usuario puede borrar sus imágenes.
- **Datos de entrenamiento.** Son públicos y con licencia explícita, citados en la aplicación; no hay imágenes clínicas en el repositorio.
- **Métricas honestas.** Se documentan los fallos conocidos y la falta de evaluación de sesgos por tono de piel.
- **Sin autenticación.** La versión local no debe exponerse a internet. La demo pública usa un **modo demo**: cada navegador solo ve sus imágenes, que se borran a las 6 horas, y hay un límite de uso.

Detalle en [docs/ethics.md](docs/ethics.md) y [docs/limitations.md](docs/limitations.md).

## Licencia

- **Código:** [MIT](LICENSE).
- **Dataset WoundTissue y pesos del modelo:** quedan fuera; se rigen por CC BY-NC-SA 4.0 (uso no comercial) y no están en este repositorio.

## Créditos

- Dataset **WoundTissue**: M. A. Kabir, N. Roy, M. E. Hossain, J. Featherston y S. Ahmed, *Deep Learning for Wound Tissue Segmentation: A Comprehensive Evaluation using A Novel Dataset*, arXiv:2502.10652, 2025. Licencia CC BY-NC-SA 4.0: el modelo entrenado con él solo puede usarse con fines no comerciales.
- Pesos de ResNet-18 en ImageNet (torchvision, BSD-3-Clause). PyTorch (BSD-3-Clause), OpenCV (Apache 2.0), FastAPI (MIT), React (MIT).
