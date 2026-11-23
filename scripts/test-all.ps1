# DermAI - Verificacion completa: lint, pruebas (backend, IA y frontend) y build.
#
# Uso (desde la raiz del proyecto):
#   powershell -ExecutionPolicy Bypass -File scripts\test-all.ps1
#   powershell -ExecutionPolicy Bypass -File scripts\test-all.ps1 -SkipFrontend
#
# Las pruebas de integracion con PostgreSQL se ejecutan si el contenedor dermai-db esta
# en marcha (scripts\db-init.ps1); si no, pytest las omite y lo indica.

param([switch]$SkipFrontend)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$python = Join-Path $root "backend\.venv\Scripts\python.exe"

function Invoke-Step([string]$Name, [scriptblock]$Action) {
    Write-Host ""
    Write-Host "==> $Name" -ForegroundColor Cyan
    & $Action
    if ($LASTEXITCODE -ne 0) {
        Write-Host "FALLO: $Name" -ForegroundColor Red
        exit $LASTEXITCODE
    }
}

if (-not (Test-Path $python)) {
    Write-Host "No se encuentra backend\.venv. Sigue la guia de instalacion (docs/installation.md)." -ForegroundColor Red
    exit 1
}

Push-Location $root
try {
    Invoke-Step "Ruff: lint de Python" { & $python -m ruff check . }
    Invoke-Step "Pytest: backend e IA, con cobertura" {
        & $python -m pytest -rs --cov=backend/app --cov=ai --cov-report=term:skip-covered
    }

    if (-not $SkipFrontend) {
        Push-Location (Join-Path $root "frontend")
        try {
            Invoke-Step "TypeScript: comprobacion de tipos" { npm run typecheck }
            Invoke-Step "Vitest: pruebas del frontend, con cobertura" { npm run coverage }
            Invoke-Step "Vite: build de produccion" { npm run build }
        }
        finally {
            Pop-Location
        }
    }

    Write-Host ""
    Write-Host "Todo correcto." -ForegroundColor Green
}
finally {
    Pop-Location
}
