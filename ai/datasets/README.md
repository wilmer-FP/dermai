# Datasets

Los datos **no se versionan** (tamaño y licencias); solo este README. Cada dataset se descarga en su propia carpeta.

## WoundTissue (Kabir et al., 2025)

| | |
|---|---|
| Origen | <https://github.com/akabircs/WoundTissue> |
| Licencia | **CC BY-NC-SA 4.0**: solo investigación no comercial; atribución obligatoria; las obras derivadas que se distribuyan deben usar la misma licencia. El copyright de las imágenes es de sus titulares originales. |
| Contenido publicado | **13 pares** imagen/máscara de muestra (PNG cuadrados de 128 a 467 px). El artículo describe 147 imágenes, pero el repositorio público solo incluye estas 13. |
| Ruta local | `ai/datasets/woundtissue/raw/WoundTissue-main/{image,label}/` |

Clases (color RGB de la máscara → índice usado en DermAI):

| Índice | Clase | Color | En la muestra pública |
|---|---|---|---|
| 0 | Fondo | azul `(0, 0, 255)` | sí |
| 1 | Granulación | rojo `(255, 0, 0)` | sí |
| 2 | Esfacelo | amarillo `(255, 255, 0)` | sí |
| 3 | Necrosis | negro `(0, 0, 0)` | sí (2 imágenes) |
| 4 | Maceración | blanco `(255, 255, 255)` | sí |
| 5 | Tendón | azul cielo (supuesto `(135, 206, 235)`) | no |
| 6 | Hueso | crema `(255, 200, 124)` | sí |

Descarga (PowerShell, desde la raíz del proyecto):

```powershell
$dest = "ai\datasets\woundtissue"
New-Item -ItemType Directory -Force $dest | Out-Null
Invoke-WebRequest "https://github.com/akabircs/WoundTissue/archive/refs/heads/main.zip" -OutFile "$dest\WoundTissue-main.zip"
Expand-Archive "$dest\WoundTissue-main.zip" -DestinationPath "$dest\raw" -Force
Remove-Item "$dest\WoundTissue-main.zip"
```

Cita:

> M. A. Kabir, N. Roy, M. E. Hossain, J. Featherston y S. Ahmed. *Deep Learning for Wound Tissue Segmentation: A Comprehensive Evaluation using A Novel Dataset*. arXiv:2502.10652, 2025.

Para reentrenar con el dataset completo (si los autores lo facilitan), basta con dejar las carpetas `image/` y `label/` con el mismo formato y apuntar `data_root` de la configuración del experimento a ellas.
