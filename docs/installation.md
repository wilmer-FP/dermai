# Guía de instalación — DermAI (Windows)

Instrucciones para poner en marcha DermAI desde cero en un equipo Windows. Todos los comandos son de **PowerShell** y se ejecutan desde la raíz del proyecto, salvo que se indique otra cosa.

## 1. Requisitos

| Herramienta | Versión probada | Para qué |
|---|---|---|
| Python | 3.12 | Backend, procesamiento de imágenes y modelo |
| Node.js | 20 o superior (probado con 24) | Frontend |
| Docker Desktop | Cualquiera reciente | PostgreSQL 16 de desarrollo |
| GPU NVIDIA (opcional) | Probado con RTX 5060 (CUDA 12.8) | Entrenar el modelo; la inferencia funciona en CPU |

Espacio en disco: unos 500 MB sin PyTorch y unos 4 GB con PyTorch y CUDA.

## 2. Backend

```powershell
cd backend
py -3.12 -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements-dev.txt
cd ..
```

`requirements-dev.txt` incluye las dependencias de ejecución (FastAPI, SQLAlchemy, Pillow, OpenCV, NumPy…) y las de pruebas y linting.

### PyTorch (opcional)

Solo hace falta para **entrenar** o **usar** el modelo experimental; la heurística de OpenCV funciona sin él.

```powershell
# Con GPU NVIDIA (CUDA 12.8; necesario para tarjetas RTX 50xx)
.\backend\.venv\Scripts\python -m pip install -r ai\requirements.txt --index-url https://download.pytorch.org/whl/cu128
# Sin GPU NVIDIA
.\backend\.venv\Scripts\python -m pip install -r ai\requirements.txt --index-url https://download.pytorch.org/whl/cpu
```

## 3. Base de datos

```powershell
powershell -ExecutionPolicy Bypass -File scripts\db-init.ps1
```

El script:
- Crea `.env` a partir de `.env.example`, con una contraseña aleatoria, si no existe.
- Levanta PostgreSQL 16 en Docker (contenedor `dermai-db`) en `127.0.0.1:5433`.
- Espera a que esté listo. Es idempotente: se puede ejecutar varias veces.

Después, aplica las migraciones:

```powershell
cd backend
.\.venv\Scripts\python -m alembic upgrade head
cd ..
```

> `.env` contiene credenciales: no se versiona ni debe compartirse.

## 4. Frontend

```powershell
cd frontend
npm install
cd ..
```

## 5. Ejecutar

Hacen falta dos terminales:

```powershell
# Terminal 1: API en http://127.0.0.1:8000 (documentación interactiva en /docs)
.\backend\.venv\Scripts\python -m uvicorn app.main:app --app-dir backend --reload
```

```powershell
# Terminal 2: interfaz en http://127.0.0.1:5173
npm run dev --prefix frontend
```

Abre <http://127.0.0.1:5173>. El pie de página debe indicar «API conectada».

## 6. Modelo experimental (opcional)

Requiere PyTorch (§2). Descarga el dataset (ver [`ai/datasets/README.md`](../ai/datasets/README.md)), entrena el modelo y regístralo:

```powershell
.\backend\.venv\Scripts\python -m ai.experiments.train --config ai/experiments/configs/unet_resnet18_woundtissue.json
cd backend
.\.venv\Scripts\python -m app.cli register-model ..\ai\experiments\runs\<ejecución> --activate
cd ..
```

El entrenamiento tarda unos 11 minutos en una RTX 5060. La primera vez descarga los pesos de ResNet-18 de ImageNet (45 MB) en `ai/models/cache/`. Con el modelo activo, la página «Analizar» ofrece elegir entre la heurística y el modelo. Para usar la GPU también en la inferencia, pon `AI_DEVICE=auto` en `.env`.

Más detalles en [model.md](model.md).

## 7. Comprobar la instalación

```powershell
powershell -ExecutionPolicy Bypass -File scripts\test-all.ps1
```

Ejecuta el linting de Python, todas las pruebas (con PostgreSQL si está en marcha), la comprobación de tipos y las pruebas del frontend, y el build de producción. Debe terminar con «Todo correcto.». Ver [testing.md](testing.md).

## 8. Problemas frecuentes

| Síntoma | Causa y solución |
|---|---|
| `npm error enoent Could not read package.json` | `npm run dev` se ejecutó en la raíz. Usa `npm run dev --prefix frontend` o entra en `frontend/`. |
| En Vite: `http proxy error … ECONNREFUSED 127.0.0.1:8000`. En la interfaz: «API no disponible». | El backend no está en marcha (§5, terminal 1). |
| Error 503 «La base de datos no está configurada» | Falta `.env` o `DATABASE_URL`. Ejecuta `scripts\db-init.ps1`. |
| El backend se queda colgado al conectar con la base de datos | Usa `127.0.0.1` y no `localhost` en `DATABASE_URL`: en Windows con Docker Desktop, `localhost` puede intentar IPv6 primero. |
| El puerto 5433 está ocupado | Cambia `POSTGRES_PORT` y el puerto de `DATABASE_URL` en `.env` y vuelve a ejecutar `db-init.ps1`. |
| No se pueden ejecutar los scripts `.ps1` | Ejecútalos con `powershell -ExecutionPolicy Bypass -File …`, como en los ejemplos. |
| Análisis con modelo en `failed`: «PyTorch no está instalado» | Instala PyTorch (§2) en el mismo entorno del backend y reinícialo. |
| Análisis con modelo en `failed`: «No se encuentra el archivo de pesos» | Los pesos (`ai/models/weights/`) no se versionan. Entrena y registra el modelo de nuevo (§6). |
