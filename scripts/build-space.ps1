# DermAI - Prepara la carpeta que se sube al Space de Hugging Face (deploy/huggingface/build).
#
# Uso (desde la raiz del proyecto):
#   powershell -ExecutionPolicy Bypass -File scripts\build-space.ps1
#   powershell -ExecutionPolicy Bypass -File scripts\build-space.ps1 -RunDir ai\experiments\runs\<ejecucion>
#
# Copia solo lo necesario para ejecutar la API: backend, el codigo de ai/ (sin datos ni
# entrenamiento), el modelo de la ejecucion indicada (por defecto, la mas reciente) y los
# archivos del Space (Dockerfile, start.sh, README.md).

param([string]$RunDir)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$space = Join-Path $root "deploy\huggingface"
$build = Join-Path $space "build"

if (-not $RunDir) {
    $runs = Join-Path $root "ai\experiments\runs"
    $latest = Get-ChildItem $runs -Directory -ErrorAction SilentlyContinue | Sort-Object Name | Select-Object -Last 1
    if (-not $latest) { throw "No hay ejecuciones de entrenamiento en $runs. Entrena el modelo primero (docs/model.md)." }
    $RunDir = $latest.FullName
}
$RunDir = (Resolve-Path $RunDir).Path
foreach ($file in "model.pt", "model_meta.json", "metrics.json", "model_card.md") {
    if (-not (Test-Path (Join-Path $RunDir $file))) { throw "Falta $file en $RunDir" }
}

if (Test-Path $build) { Remove-Item -Recurse -Force $build }
New-Item -ItemType Directory -Force "$build\backend", "$build\ai", "$build\model" | Out-Null

# Backend: aplicacion, migraciones y dependencias
Copy-Item -Recurse (Join-Path $root "backend\app") "$build\backend\app"
Copy-Item -Recurse (Join-Path $root "backend\alembic") "$build\backend\alembic"
Copy-Item (Join-Path $root "backend\alembic.ini"), (Join-Path $root "backend\requirements.txt") "$build\backend"

# Modulo de IA: solo codigo de ejecucion (sin datasets, experimentos, cache ni pesos)
Copy-Item (Join-Path $root "ai\__init__.py"), (Join-Path $root "ai\requirements.txt") "$build\ai"
foreach ($package in "preprocessing", "models", "evaluation") {
    New-Item -ItemType Directory -Force "$build\ai\$package" | Out-Null
    Copy-Item (Join-Path $root "ai\$package\*.py") "$build\ai\$package"
}

# Modelo entrenado y su ficha
foreach ($file in "model.pt", "model_meta.json", "metrics.json", "model_card.md") {
    Copy-Item (Join-Path $RunDir $file) "$build\model"
}

# Archivos del Space
Copy-Item (Join-Path $space "Dockerfile"), (Join-Path $space "start.sh"), (Join-Path $space "README.md") $build

Get-ChildItem $build -Recurse -Directory -Filter "__pycache__" | Remove-Item -Recurse -Force

$files = Get-ChildItem $build -Recurse -File
$sizeMb = [math]::Round(($files | Measure-Object Length -Sum).Sum / 1MB, 1)
Write-Host "Carpeta del Space lista: $build" -ForegroundColor Green
Write-Host "  $($files.Count) archivos, $sizeMb MB (modelo de $(Split-Path -Leaf $RunDir))"
Write-Host "Siguiente paso: docs/deployment.md (probar con Docker y publicar)."
