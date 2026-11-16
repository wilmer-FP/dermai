# Despliegue gratuito de DermAI

Destino: https://wilmer-fp.github.io/dermai/. Frontend estático con el modelo real
mediante ONNX Runtime Web y una heurística OpenCV.js seleccionable por separado.
FastAPI y PostgreSQL no se despliegan. Las fotos se procesan y guardan en el dispositivo.
Un fallo del modelo queda como fallo, sin sustitución automática por la heurística.

## Modelo y reproducción

Modelo: `unet-resnet18-woundtissue` v0.1.0, U-Net/ResNet-18, entrenado con 13
imágenes. Se encontraron `model.pt`, `model_meta.json`, `metrics.json` y
`model_card.md` en `ai/experiments/runs/20261105T231652Z_unet-resnet18-woundtissue/`.
No es el checkpoint genérico `ai/models/cache/hub/checkpoints/resnet18-f37072fd.pth`.
El exportador usa `torch.load(weights_only=True)`, carga el estado estrictamente,
no descarga un encoder y exige igualdad entre metadatos internos/externos,
arquitectura, normalización, clases y cantidad de imágenes. No entrena.

Desde la raíz, con las dependencias normales de backend e IA instaladas:

```powershell
.\backend\.venv\Scripts\python -m pip install -r ai/requirements-export.txt
.\backend\.venv\Scripts\python scripts/export-browser-model.py --run ai/experiments/runs/20261105T231652Z_unet-resnet18-woundtissue
npm ci --prefix frontend
npm test --prefix frontend
$env:VITE_ANALYSIS_MODE = 'browser'
$env:VITE_BASE_PATH = '/dermai/'
npm run build --prefix frontend
npm run preview --prefix frontend -- --base /dermai/
```

Salida: `frontend/public/models/dermai/model.onnx`, manifiesto, ficha, métricas y
`validation.json`. Conservar `LICENSE.txt` y `NOTICE.md` con cada distribución.
`prebuild` verifica tamaño y SHA-256 del ONNX y presencia de documentación.
No se usa Git LFS ni alojamiento externo de pesos.

Contrato numérico conservado:

1. RGB original recodificado como PNG sin EXIF, aplicando orientación del navegador.
   Límite de archivo 10 MB; se rechazan imágenes superiores a 24 megapíxeles.
2. Lado mayor 512: INTER_AREA al reducir, INTER_CUBIC al ampliar; redondeo al par.
3. El modelo recibe la imagen **sin corrección de color ni filtro bilateral**, igual
   que `ai/models/inference.py`: lado mayor 256, INTER_LINEAR, proporción conservada.
   La corrección de color se utiliza para las características auxiliares.
4. Float32 NCHW, RGB/255, medias `[0.485,0.456,0.406]`, desviaciones
   `[0.229,0.224,0.225]`. ONNX opset 17, alto/ancho dinámicos, sin cuantización.
5. Softmax sobre siete clases, interpolación bilineal de cada probabilidad a 512 y
   después argmax. Orden: fondo, granulación, esfacelo, necrosis, maceración, tendón, hueso.
6. Composición sobre píxeles no fondo. Confianza media sobre herida si ocupa al menos
   0,002 de la imagen, o sobre toda la imagen en caso contrario. No está calibrada.

WASM usa un hilo: Pages no proporciona COOP/COEP. Un worker dedicado termina tras
cada análisis, fallo o límite de tres minutos, liberando memorias WASM. La caché HTTP
puede evitar descargas posteriores; no se promete funcionamiento offline. Motores y
modelo se sirven desde el mismo origen. IndexedDB guarda imágenes y resultados;
borrar una imagen elimina todos sus análisis y archivos procesados. Los archivos
anteriores a esta versión pueden conservar EXIF: eliminarlos desde el historial o
borrar los datos del sitio. Los decodificadores de navegador/Pillow pueden diferir
en perfiles de color: la equivalencia se verifica desde los mismos píxeles RGB.

## Pruebas del 16 de noviembre de 2026

- PyTorch CPU frente a ONNX CPU: ocho entradas sintéticas/aleatorias, incluyendo
  vertical, horizontal y dimensiones extremas. 100 % de etiquetas iguales; máximo
  error absoluto de logits `1.55e-5` y de probabilidades `2.15e-6`.
- Pipeline completo TypeScript + OpenCV.js + ONNX Runtime Web WASM: cuatro imágenes
  sintéticas, acuerdo de etiquetas 99,955–100 %. Se verifican composición por clase,
  confianza, avisos y ausencia de sustitución por heurística. Las pequeñas diferencias
  incluyen implementaciones OpenCV nativa/JS y aritmética float32.
- 100 pruebas frontend, TypeScript y build Vite: modelo real, fallo de ONNX sin fallback,
  historial, borrado en cascada, vistas y regresiones de heurística.
- Prueba visual local: cargar PNG sintético, elegir modelo, ejecutar, ver segmentación,
  leyenda y resultados, abrir historial y recargar conservando el registro.
  Borrado cubierto automáticamente; no se completó su verificación visual porque el
  control del navegador se detuvo al no poder identificar la URL de forma segura.
- Chromium integrado, 320×240: carga 2.505 s, inferencia 0.231 s, total 3.340 s.
  Medición con servidor local; no representa la descarga por internet.
- WASM en Node: inferencia 204–289 ms; proceso completo 402–465 MiB RSS frente a
  65,5 MiB iniciales, muestreado tras cada caso. **No es pico garantizado ni memoria
  aislada del navegador.** Python PyTorch+ORT: pico del proceso 911 MiB.
- ONNX: 57.285.761 bytes (54,63 MiB). Runtime WASM: 14,85 MB sin comprimir;
  OpenCV.js: 15,51 MB. Se añaden JS/CSS. Transferencia real depende de compresión
  HTTP/caché. No se ha validado memoria/rendimiento en móviles con poca RAM.

Los fixtures son sintéticos, sin pacientes. Estas pruebas verifican equivalencia
técnica, no eficacia clínica. No se cuantizó ni se cambiaron los pesos entrenados.
Hashes y mediciones Python en `frontend/public/models/dermai/validation.json`.
Para repetir mediciones WASM en Node:

```powershell
$env:DERMAI_BENCHMARK_REPORT = "$PWD\wasm-report.json"
npm test --prefix frontend -- --run src/analysis/model.test.ts
Remove-Item Env:DERMAI_BENCHMARK_REPORT
```

## Publicar y verificar

El workflow fija modo `browser` y base `/dermai/`, verifica hash, ejecuta pruebas y
build, añade `404.html` y `.nojekyll` y publica solo `frontend/dist`. Acciones fijadas
por SHA. Solo funciona en repositorio público; no entrena/exporta dentro de Actions.
Con los cambios revisados y confirmados en un commit, desde una terminal autenticada:

```powershell
gh auth login --hostname github.com --git-protocol https --web
gh auth setup-git
powershell -ExecutionPolicy Bypass -File scripts\publish-pages.ps1
```

El script comprueba visibilidad pública, pruebas y build; exige que `origin/main`
sea ancestro, configura Pages `build_type=workflow`, hace push sin forzar, inicia
Actions y espera el resultado. Verifica HTTP 200 y manifiesto público. No modifica
facturación, planes, secretos ni permisos de Actions. Si un entorno aislado no puede
leer el token del almacén de Windows, ejecutar el script desde la terminal ya autenticada;
no copiar tokens al chat ni al repositorio.

Después abrir la URL, elegir **Modelo experimental**, cargar una imagen sintética y
comprobar método/hash en «Datos completos del resultado»; repetir historial y borrado.
HTTP 200 por sí solo no demuestra inferencia. Hasta completar estos pasos no debe
considerarse verificada la publicación pública.

## Coste, límites y licencias

Fuentes oficiales consultadas el 16-11-2026:

- [GitHub Pages](https://docs.github.com/en/pages/getting-started-with-github-pages/github-pages-limits):
  GitHub Free con repositorio público; sitio máximo 1 GB, ancho de banda orientativo
  100 GB/mes, timeout de despliegue de 10 minutos. El límite de diez builds/hora no
  aplica a workflows personalizados. Un modelo de 57 MB equivale a unas 1.700 descargas
  completas con 100 GB **antes de descontar los demás archivos**. Exceder límites
  puede restringir el servicio: no se contrata una ampliación. No es alojamiento para SaaS comercial.
- [Actions](https://docs.github.com/en/billing/concepts/product-billing/github-actions):
  runners estándar gratuitos para repositorios públicos; no usar runners grandes.
  Pages no requiere tarjeta ni prueba temporal. Este workflow no usa caché npm y
  retiene el artefacto un día. No hay servidor que duerma por inactividad. Publicar
  requiere cuenta GitHub; visitar la aplicación no requiere cuenta.
- Código MIT. Modelo CC BY-NC-SA 4.0 conforme a la política del proyecto y la
  [licencia de WoundTissue](https://github.com/akabircs/WoundTissue/blob/main/LICENSE):
  atribución, uso no comercial y misma licencia para adaptaciones distribuidas.
  Se conservan autores, fuente, cambios de formato y avisos; no se incluyen fotografías.
  La [licencia](https://creativecommons.org/licenses/by-nc-sa/4.0/) no otorga derechos
  de privacidad ni garantías sobre material de terceros.
- No se publican pesos ImageNet por separado. BSD de torchvision es licencia de
  código, no de las imágenes ImageNet: ver [aviso oficial](https://github.com/pytorch/vision#disclaimer-on-datasets-and-pre-trained-models).

El modelo sí es viable técnicamente en navegador; no hace falta contratar servidores.
Se retiran las afirmaciones anteriores no verificadas de que todos los servicios
alternativos gratuitos o los Spaces Docker requieran pago.

**Educativo y experimental, no validado para diagnóstico médico.** Solo 13 imágenes,
sin ejemplos de tendón y muy pocos de necrosis/hueso; generalización y sesgos no
validados. No usar resultados para decisiones clínicas.
