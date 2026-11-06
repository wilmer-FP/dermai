# Despliegue gratuito — DermAI

Demo pública sin coste:

- **Frontend** en **GitHub Pages**: <https://wilmer-fp.github.io/dermai/>
- **API** en **Hugging Face Spaces** (Docker, CPU gratuita): <https://huggingface.co/spaces/Wilmer-FP/dermai>, accesible en `https://wilmer-fp-dermai.hf.space`.

```
GitHub Pages                                 Hugging Face Spaces (Docker)
┌──────────────────────────┐  HTTPS + CORS   ┌──────────────────────────────────────┐
│ React (build estático)   │ ──────────────▶ │ FastAPI + OpenCV + PyTorch (CPU)      │
│ /dermai/ · sesión anónima│                 │ SQLite y archivos en /tmp (efímeros)  │
└──────────────────────────┘                 └──────────────────────────────────────┘
```

> La demo es un prototipo educativo, **no diagnóstico**. No tiene cuentas de usuario: la protegen el modo demo y el borrado automático, no una autenticación.

## 1. Modo demo

Se activa con `DEMO_MODE=true` (el `Dockerfile` del Space ya lo hace).

| Variable | Valor en el Space | Efecto |
|---|---|---|
| `DEMO_MODE` | `true` | Cada petición necesita un identificador anónimo de sesión (cabecera `X-DermAI-Session` o parámetro `?session=`). Cada navegador solo ve sus imágenes y análisis; los de otra sesión responden 404. |
| `DEMO_RETENTION_HOURS` | `6` | Una tarea en segundo plano borra cada 10 minutos las imágenes más antiguas, con sus análisis y archivos. |
| `DEMO_RATE_LIMIT_PER_HOUR` | `30` | Subidas y análisis por dirección IP y hora; al superarlo, la respuesta es 429. |
| `DATABASE_URL` | `sqlite:////tmp/dermai/dermai.db` | SQLite: no hace falta un servidor de base de datos. Se pierde al reiniciar el Space. |
| `STORAGE_PATH` | `/tmp/dermai/storage` | Imágenes efímeras. |
| `CORS_ORIGINS` | `https://wilmer-fp.github.io` | Solo el frontend publicado puede llamar a la API desde un navegador. |
| `AI_DEVICE` | `cpu` | Inferencia en CPU: menos de 1 s por análisis una vez cargado el modelo. |

**Frontend:**
- genera el identificador de sesión al azar (`crypto.randomUUID`), lo guarda en `localStorage` y lo envía en cada petición;
- muestra el aviso «Demo pública» cuando `GET /health` indica `demo_mode`;
- reintenta durante 3 minutos si el Space está dormido (tarda 1–2 minutos en despertar).

## 2. Archivos

| Archivo | Para qué |
|---|---|
| `deploy/huggingface/Dockerfile` | Imagen del Space: Python 3.12, PyTorch para CPU, usuario 1000 y configuración del modo demo |
| `deploy/huggingface/start.sh` | Arranque: migraciones, registro del modelo y `uvicorn` en el puerto 7860 |
| `deploy/huggingface/README.md` | Ficha del Space: metadatos, licencia CC BY-NC-SA 4.0 de los pesos y atribución |
| `scripts/build-space.ps1` | Prepara `deploy/huggingface/build/` (no versionado), con solo el código necesario y el modelo de la última ejecución de entrenamiento |
| `deploy/huggingface/publish.py` | Sube esa carpeta al Space |
| `.github/workflows/deploy-frontend.yml` | Compila el frontend con la ruta `/dermai/` y la URL de la API, y lo publica en GitHub Pages |
| `.github/workflows/ci.yml` | Integración continua: `ruff`, pytest (con PyTorch para CPU) y las pruebas, tipos y build del frontend |

## 3. Probar en local como en producción

```powershell
# API: la misma imagen del Space, en http://127.0.0.1:7860
powershell -ExecutionPolicy Bypass -File scripts\build-space.ps1
docker build -t dermai-space:local deploy\huggingface\build
docker run --rm -p 127.0.0.1:7860:7860 -e CORS_ORIGINS=http://127.0.0.1:4173 dermai-space:local
```

```powershell
# Frontend: build de producción en http://127.0.0.1:4173/dermai/
cd frontend
$env:VITE_BASE_PATH = "/dermai/"; $env:VITE_API_BASE_URL = "http://127.0.0.1:7860/api/v1"
npm run build
npm run preview -- --base /dermai/
```

## 4. Publicar

### GitHub (código y frontend)

1. Crea el repositorio `dermai` en tu cuenta y sube el proyecto (rama `main`).
2. En **Settings → Pages → Source**, elige **GitHub Actions**.
3. Cada `push` a `main` que cambie `frontend/` publica la web. También puedes lanzarlo a mano desde **Actions → Desplegar frontend → Run workflow**.
4. Opcional: si la API cambia de dirección, crea la variable `DERMAI_API_URL` en **Settings → Secrets and variables → Actions → Variables**.

### Hugging Face (API)

```powershell
# Una vez: herramienta de publicación e inicio de sesión con un token de permiso "write"
.\backend\.venv\Scripts\python -m pip install huggingface_hub==2.4.0
.\backend\.venv\Scripts\hf auth login

# En cada publicación
powershell -ExecutionPolicy Bypass -File scripts\build-space.ps1
.\backend\.venv\Scripts\python deploy\huggingface\publish.py
```

- El token se crea en <https://huggingface.co/settings/tokens>.
- El script crea el Space `Wilmer-FP/dermai` si no existe y sube la carpeta (unos 55 MB, incluido el modelo).
- Hugging Face construye la imagen en unos 5–10 minutos. El estado se ve en la pestaña **Logs** del Space.

## 5. Límites del plan gratuito

| Límite | Consecuencia |
|---|---|
| El Space duerme tras un tiempo sin uso | La primera visita espera 1–2 minutos; la web lo indica y reintenta. |
| Disco efímero | Al reiniciarse se pierden imágenes y análisis. Es intencionado en una demo con fotos de salud. |
| CPU compartida (2 vCPU) | Suficiente para una demo; no para mucho tráfico. |
| Límite en memoria | El límite de peticiones vive en un solo proceso y se reinicia con el Space. |

## 6. Seguridad y licencias

- **Sin cuentas.** El identificador de sesión separa a los visitantes, pero no es una contraseña: quien lo copiara vería esas imágenes durante unas horas. Por eso se borran pronto y se pide no subir fotos identificables.
- **Pesos del modelo.** Se publican en el Space con la licencia del dataset (CC BY-NC-SA 4.0, uso no comercial) y su atribución.
- **Licencia del código.** Elígela antes de hacer público el repositorio.
- **Secretos.** `.env` no se versiona y el Space no necesita secretos: toda su configuración es pública.
