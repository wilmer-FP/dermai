# Arquitectura de DermAI

> Arquitectura **implementada** al cierre de la Etapa 8. El módulo de IA se integra como paquete Python dentro del proceso del backend (no como servicio HTTP separado).

## 1. Visión general

DermAI sigue una arquitectura modular por capas, con separación clara entre la interfaz de usuario, la lógica de negocio, la persistencia y el análisis de imágenes. El módulo de inteligencia artificial se concibe como un **servicio independiente**, de modo que pueda evolucionar, reentrenarse o sustituirse sin afectar al resto del sistema.

```
┌───────────────────────────┐
│ Frontend (React + TS)     │
└────────────┬──────────────┘
             │ REST (JSON / multipart)
┌────────────▼──────────────┐        ┌─────────────────────┐
│ Backend (FastAPI)         │──SQL──▶│ PostgreSQL          │
│  api · services · models  │        └─────────────────────┘
└──────┬─────────────┬──────┘
       │             │ lectura/escritura de archivos
       │             ▼
       │      ┌─────────────────────┐
       │      │ storage/ (imágenes) │
       │      └─────────────────────┘
       │ llamada interna (HTTP o módulo Python)
┌──────▼────────────────────┐
│ Servicio de IA            │
│  OpenCV (preprocesamiento)│
│  PyTorch (inferencia)     │
└───────────────────────────┘
```

## 2. Componentes y responsabilidades

### 2.1 Frontend — React + TypeScript (`frontend/`)
- Interfaz para cargar fotografías y visualizar resultados experimentales.
- Validación básica en cliente (tipo y tamaño de archivo).
- Mostrar de forma visible el aviso de uso no diagnóstico.
- Organización:
  - `components/`: componentes reutilizables de UI.
  - `pages/`: vistas principales (carga, resultados, historial).
  - `hooks/`: lógica reutilizable de estado y efectos.
  - `services/`: cliente HTTP hacia la API.
  - `types/`: tipos e interfaces TypeScript compartidos.
  - `assets/`: recursos estáticos.
- En desarrollo, el servidor de Vite reenvía `/api` al backend (un solo origen para el navegador).
- Detalle en [frontend.md](frontend.md).

### 2.2 Backend — Python + FastAPI (`backend/app/`)
- Exponer la API REST consumida por el frontend.
- Validar entradas, gestionar la carga de imágenes y orquestar el análisis.
- Persistir metadatos y resultados en PostgreSQL.
- Organización prevista:
  - `api/`: routers y definición de endpoints.
  - `core/`: configuración, variables de entorno, seguridad, logging.
  - `models/`: modelos ORM de base de datos.
  - `schemas/`: esquemas Pydantic de entrada/salida.
  - `services/`: lógica de negocio y comunicación con el servicio de IA.
  - `main.py`: punto de entrada de la aplicación.
  - Endpoints documentados en [api.md](api.md).

### 2.3 Base de datos — PostgreSQL
- Almacenar metadatos de imágenes (ruta, formato, dimensiones, fecha de carga).
- Almacenar resultados de análisis (versión del modelo, métricas, salidas).
- Mantener trazabilidad entre imagen, análisis y versión del modelo.
- Las imágenes **no** se guardan en la base de datos; solo su referencia.
- Esquema detallado en [database.md](database.md).

### 2.4 Servicio de inteligencia artificial (`ai/`)
- **Preprocesamiento (OpenCV), implementado en `ai/preprocessing`:** normalización de tamaño y color, reducción de ruido, segmentación de la región de interés, clasificación heurística por color y extracción de características visuales (color, textura, bordes, forma). El backend lo importa como módulo Python y lo ejecuta al solicitar un análisis. Detalle en [image-processing.md](image-processing.md).
- **Modelos (PyTorch), implementado en `ai/models`:** U-Net con encoder ResNet-18 para segmentar tejidos de herida. Las versiones entrenadas se registran en `model_versions` y el backend las usa cuando un análisis indica `model_version_id`. Detalle en [model.md](model.md).
- **Evaluación (`ai/evaluation`):** métricas por clase (precisión, sensibilidad, especificidad, IoU/Dice) a partir de matrices de confusión.
- **Experimentos (`ai/experiments`):** configuraciones versionadas en `configs/` y ejecuciones reproducibles en `runs/` (no versionadas).
- Se mantiene desacoplado del backend mediante una interfaz bien definida (función de inferencia o API interna).

### 2.5 Almacenamiento (`storage/`)
- Directorio local para imágenes cargadas y artefactos generados durante el desarrollo.
- Excluido del control de versiones.
- Podrá migrarse a almacenamiento de objetos en etapas futuras.

## 3. Comunicación entre módulos

| Origen | Destino | Mecanismo | Contenido |
|--------|---------|-----------|-----------|
| Frontend | Backend | HTTP REST | JSON y `multipart/form-data` para imágenes |
| Backend | PostgreSQL | SQL vía ORM | Metadatos y resultados |
| Backend | Storage | Sistema de archivos | Imágenes originales y procesadas |
| Backend | Servicio de IA | Llamada interna (módulo Python o HTTP interno) | Ruta de imagen → resultado del análisis |

### Flujo implementado
1. El usuario elige una fotografía en el frontend, que valida su formato y tamaño.
2. El backend comprueba el contenido real con Pillow y elimina sus metadatos (EXIF, GPS). Después guarda el archivo en `storage/` y sus datos en PostgreSQL.
3. Al solicitar el análisis, el backend ejecuta en la misma petición la heurística de OpenCV (`ai/preprocessing`) o, si se indica una versión de modelo, la inferencia de PyTorch (`ai/models`).
4. El backend guarda en PostgreSQL la proporción necrótica, la confianza (solo con modelo) y el resultado JSON. La imagen procesada, con el aviso incrustado, se guarda en `storage/`.
5. El frontend muestra el resultado, la imagen procesada, las características y el aviso de uso experimental.

## 4. Principios de diseño
- **Separación de responsabilidades** entre capas.
- **Desacoplamiento** del módulo de IA.
- **Configuración por variables de entorno** (ver `.env.example`).
- **Reproducibilidad** de experimentos (versionado de modelos y configuraciones).
- **Privacidad por diseño:** sin datos personales identificables.
