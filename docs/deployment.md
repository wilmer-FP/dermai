# Despliegue gratuito — DermAI

La demo pública es **solo frontend**: <https://wilmer-fp.github.io/dermai/>, publicada en GitHub Pages sin coste y sin servidor.

```
GitHub Pages (archivos estáticos)
┌──────────────────────────────────────────────────────────────┐
│ React + heurística de OpenCV.js (port de ai/preprocessing)   │
│ Imágenes, análisis e historial en IndexedDB (este navegador) │
└──────────────────────────────────────────────────────────────┘
        Las fotos no salen del dispositivo del visitante.
```

> La demo es un prototipo educativo, **no diagnóstico**.

## 1. Modo navegador

El frontend tiene dos modos, que se eligen al compilar con `VITE_ANALYSIS_MODE`:

| Modo | Dónde se analiza | Dónde se guardan los datos | Uso |
|---|---|---|---|
| `api` (por defecto) | Backend FastAPI (heurística y modelo) | PostgreSQL o SQLite y `storage/` | Desarrollo local y despliegues con servidor |
| `browser` | En el navegador, con **OpenCV.js 5.0** | **IndexedDB** del propio navegador | Demo pública en GitHub Pages |

En modo navegador:

- **Heurística.** `frontend/src/analysis/heuristic.ts` es un port de `ai/preprocessing` con los mismos pasos y parámetros. Las pruebas lo comparan con Python sobre imágenes de referencia: el **99,997–100 %** de los píxeles recibe la misma clase y la composición difiere como mucho en 0,0001. El análisis tarda unos 0,1–0,4 s.
- **Descarga de OpenCV.js.** Ocupa unos 4 MB comprimido y se descarga solo la primera vez que se analiza una imagen; la página inicial sigue pesando unos 110 KB.
- **Privacidad.** Las imágenes, los análisis y las imágenes procesadas (con el aviso incrustado) se guardan en IndexedDB y **no se envían a ningún servidor**. Cada visitante solo ve lo suyo, y lo borra desde la propia aplicación o borrando los datos del sitio.
- **Sin modelo.** El modelo de PyTorch no está disponible en este modo; el selector de método no aparece.

## 2. Publicación

El *workflow* `.github/workflows/deploy-frontend.yml` compila en modo navegador con la ruta `/dermai/` y publica en Pages en cada `push` a `main` que cambie `frontend/`. Requisito único: **Settings → Pages → Source = GitHub Actions**, ya configurado.

Variables opcionales del repositorio (**Settings → Secrets and variables → Actions → Variables**):

| Variable | Efecto |
|---|---|
| `DERMAI_ANALYSIS_MODE=api` | Compilar en modo API, para usar un backend desplegado |
| `DERMAI_API_URL` | URL de ese backend, p. ej. `https://…/api/v1` |

`.github/workflows/ci.yml` ejecuta el linting y todas las pruebas, incluidas las de paridad con Python, en cada `push` y *pull request*.

### Probar en local como en Pages

```powershell
cd frontend
$env:VITE_BASE_PATH = "/dermai/"; $env:VITE_ANALYSIS_MODE = "browser"
npm run build
npm run preview -- --base /dermai/   # http://127.0.0.1:4173/dermai/
```

### Regenerar las referencias de paridad

Si cambia la heurística de Python, hay que regenerar las referencias y ajustar el port hasta que las pruebas vuelvan a pasar:

```powershell
.\backend\.venv\Scripts\python scripts\generate-browser-fixtures.py
```

## 3. Desplegar también la API (opcional, no gratuito)

El repositorio incluye todo lo necesario para desplegar el backend completo (heurística y modelo) como contenedor Docker:

- **Imagen:** `deploy/huggingface/Dockerfile` y `start.sh`.
- **Modo demo:** sesiones anónimas, borrado a las 6 h y límite de uso; ver [api.md](api.md).
- **Scripts:** `scripts/build-space.ps1` y `deploy/huggingface/publish.py`.

Ya **no hay una opción gratuita adecuada**:
- Hugging Face exige desde 2026 una suscripción PRO para Spaces Docker.
- Los planes gratuitos de otros proveedores ofrecen unos 512 MB de RAM, y PyTorch no cabe.

Con PRO, o en un proveedor como Google Cloud Run (con tarjeta), se publica así:

```powershell
.\backend\.venv\Scripts\hf auth login
powershell -ExecutionPolicy Bypass -File scripts\build-space.ps1
.\backend\.venv\Scripts\python deploy\huggingface\publish.py
```

Después, define `DERMAI_ANALYSIS_MODE=api` y `DERMAI_API_URL` en el repositorio.

Para probar la imagen en local:

```powershell
docker build -t dermai-space:local deploy\huggingface\build
docker run --rm -p 127.0.0.1:7860:7860 -e CORS_ORIGINS=http://127.0.0.1:4173 dermai-space:local
```

## 4. Licencias

- **Código:** MIT.
- **OpenCV.js:** Apache 2.0; se distribuye como dependencia en el build.
- **Pesos del modelo:** no se publican en la demo de Pages. Si se despliega la API, van con la licencia CC BY-NC-SA 4.0 del dataset y su atribución (`deploy/huggingface/README.md`).
