# Frontend — DermAI

Aplicación web en **React 19 + TypeScript**, construida con **Vite**. Consume la API REST descrita en [api.md](api.md).

> La interfaz muestra en todas las vistas el aviso de uso educativo y no diagnóstico. Los análisis devueltos por la API incluyen además su propio campo `disclaimer`, que se muestra junto al resultado.

## 1. Vistas

| Ruta | Vista | Qué hace |
|---|---|---|
| `/` | Analizar | Elegir o arrastrar una imagen, validarla en el cliente, previsualizarla, confirmar que no contiene datos identificables y enviarla. Si hay modelos activos (`GET /model-versions?active_only=true`), permite elegir entre la heurística y un modelo. Sube la imagen (`POST /images`), solicita el análisis (`POST /images/{id}/analyses`), que se procesa en esa misma petición, y abre el resultado. |
| `/analyses/:analysisId` | Resultado | Imagen procesada u original (selector con leyenda), estado y proporción de la lesión con color compatible con tejido necrótico. También muestra la composición por color, los avisos de calidad, las características extraídas, el JSON completo, los datos de la imagen y el aviso. Permite actualizar, analizar de nuevo y eliminar la imagen con sus análisis. |
| `/history` | Historial | Análisis paginados (10 por página), del más reciente al más antiguo, con filtro por estado. El filtro y la página se guardan en la URL (`?status=pending&offset=10`). |
| `/about` | Acerca de | Qué hace y qué no, métodos, privacidad, limitaciones principales, créditos y licencias (incluida la atribución obligatoria del dataset WoundTissue). |
| `*` | No encontrada | Página para rutas desconocidas. |

El pie de página indica si la API responde (`GET /health`).

## 2. Validación en el cliente

Sirve para dar respuesta inmediata; el backend sigue siendo la autoridad y comprueba el contenido real con Pillow.

- Extensión `jpg`, `jpeg` o `png`, y tipo MIME `image/jpeg` o `image/png` cuando el navegador lo informa.
- Archivo no vacío y de como máximo `VITE_MAX_UPLOAD_SIZE_MB` (10 MB por defecto, igual que `MAX_UPLOAD_SIZE_MB` del backend).
- Casilla obligatoria confirmando que la imagen no identifica a una persona y que se tiene derecho a usarla.

Si la subida funciona pero el registro del análisis falla, el reintento no vuelve a subir la imagen.

## 3. Modos: API o navegador

`VITE_ANALYSIS_MODE` decide, al compilar, de dónde salen los datos (`src/services/api.ts`):

- **`api`** (por defecto): llama a la API REST del backend (§4).
- **`browser`**: usa `src/services/localBackend.ts`, que implementa las mismas operaciones sin servidor.
  - Permite elegir el modelo entrenado ONNX Runtime Web (`src/analysis/model.ts`, en worker) o la heurística OpenCV.js. Cada resultado e historial identifican el método; los fallos del modelo no ejecutan la heurística.
  - Imágenes, análisis e imágenes procesadas se guardan en **IndexedDB** (`src/services/localStore.ts`).
  - Las imágenes se muestran con URLs `blob:` (`useImageSource`).
  - Es el modo de la demo en GitHub Pages; ver [deployment.md](deployment.md).

## 4. Conexión con la API

En desarrollo, el servidor de Vite (`127.0.0.1:5173`) reenvía `/api` al backend, así que el navegador trabaja con un solo origen y no depende de CORS. Si el backend no responde, el proxy devuelve un `502` con un `detail` explicativo, y la interfaz lo muestra.

| Variable | Dónde | Por defecto | Uso |
|---|---|---|---|
| `DERMAI_API_PROXY` | entorno al lanzar `npm run dev` | `http://127.0.0.1:8000` | Destino del proxy de desarrollo. |
| `VITE_API_BASE_URL` | `frontend/.env.local` (opcional) | `/api/v1` | Base de la API si se sirve desde otro origen. Ese origen debe estar en `CORS_ORIGINS` del backend. |
| `VITE_MAX_UPLOAD_SIZE_MB` | `frontend/.env.local` (opcional) | `10` | Límite de tamaño en el cliente. |

Los errores de la API (`{"detail": ...}`) se convierten en `ApiError` con el código HTTP y un mensaje en español listo para mostrar. Los fallos de red tienen `status = 0`.

## 5. Organización del código

```
frontend/
├── index.html
├── vite.config.ts        # servidor de desarrollo, proxy /api y configuración de Vitest
├── tsconfig*.json
└── src/
    ├── main.tsx          # punto de entrada (router del navegador)
    ├── App.tsx           # definición de rutas
    ├── styles.css        # estilos y tokens (tema claro y oscuro)
    ├── components/       # Layout, Disclaimer, ImageDropzone, AnalysisImage, TissueComposition,
    │                     # FeatureSummary, StatusBadge, Pagination, ApiStatus, Feedback
    ├── pages/            # UploadPage, AnalysisPage, HistoryPage, NotFoundPage
    ├── hooks/            # useAsync (peticiones con recarga), useObjectUrl (vista previa)
    ├── services/         # api.ts (cliente HTTP), analysisResult.ts (lectura del `result`),
    │                     # imageValidation.ts, format.ts
    ├── types/            # api.ts (tipos que reflejan los esquemas Pydantic)
    └── test/             # configuración y utilidades de las pruebas
```

Las pruebas (`*.test.ts(x)`) están junto al código que prueban. Usan Vitest, Testing Library y jsdom. Las de páginas renderizan la aplicación completa con un router en memoria y sustituyen el cliente de la API por dobles.

## 6. Comandos

Desde `frontend/`:

| Comando | Qué hace |
|---|---|
| `npm install` | Instala las dependencias (una sola vez). |
| `npm run dev` | Servidor de desarrollo en <http://127.0.0.1:5173>. Requiere el backend en marcha. |
| `npm test` | Ejecuta las pruebas. |
| `npm run coverage` | Ejecuta las pruebas con informe de cobertura. |
| `npm run typecheck` | Comprueba los tipos. |
| `npm run build` | Genera la versión de producción en `frontend/dist/`. |

## 7. Accesibilidad y diseño

- Navegación por teclado (enlace para saltar al contenido, foco visible, zona de carga accesible como `<label>`).
- Roles ARIA para avisos (`note`), errores (`alert`) y estados de carga (`status`).
- Tema claro u oscuro según la preferencia del sistema.
- Diseño adaptable hasta 375 px de ancho sin desplazamiento horizontal.
