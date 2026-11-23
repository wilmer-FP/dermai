<#
.SYNOPSIS
    Prepara y arranca el PostgreSQL de DESARROLLO de DermAI en Docker.

.DESCRIPTION
    - Crea .env a partir de .env.example si no existe.
    - Si POSTGRES_PASSWORD sigue con el valor de ejemplo, genera una contrasena
      aleatoria y actualiza POSTGRES_PASSWORD y DATABASE_URL en .env.
    - Levanta el contenedor (docker compose up -d --wait).
    Es seguro ejecutarlo varias veces: no cambia una contrasena ya generada.
    Solo para desarrollo local. No usar en produccion.

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File scripts\db-init.ps1
#>
$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $PSScriptRoot
$EnvFile = Join-Path $Root '.env'
$EnvExample = Join-Path $Root '.env.example'
$PlaceholderPassword = 'your_password'

function New-RandomSecret([int]$Length = 24) {
    $chars = 'ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz23456789'.ToCharArray()
    $bytes = New-Object byte[] $Length
    [System.Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($bytes)
    -join ($bytes | ForEach-Object { $chars[$_ % $chars.Length] })
}

function Get-EnvValues([string]$Path) {
    $values = @{}
    foreach ($line in Get-Content -Path $Path -Encoding UTF8) {
        if ($line -match '^\s*([A-Za-z_][A-Za-z0-9_]*)=(.*)$') { $values[$Matches[1]] = $Matches[2].Trim() }
    }
    $values
}

function Set-EnvValue([string]$Path, [string]$Key, [string]$Value) {
    $lines = @(Get-Content -Path $Path -Encoding UTF8)
    $pattern = "^\s*$([regex]::Escape($Key))="
    if ($lines | Where-Object { $_ -match $pattern }) {
        $lines = $lines | ForEach-Object { if ($_ -match $pattern) { "$Key=$Value" } else { $_ } }
    } else {
        $lines += "$Key=$Value"
    }
    [System.IO.File]::WriteAllLines($Path, [string[]]$lines, (New-Object System.Text.UTF8Encoding $false))
}

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) { throw 'Docker no esta instalado o no esta en el PATH.' }

if (-not (Test-Path $EnvFile)) {
    Copy-Item $EnvExample $EnvFile
    Write-Host 'Creado .env a partir de .env.example.'
}

$envValues = Get-EnvValues $EnvFile
foreach ($key in 'POSTGRES_USER', 'POSTGRES_DB', 'POSTGRES_PORT') {
    if (-not $envValues[$key]) { throw "Falta $key en .env." }
}

if (-not $envValues['POSTGRES_PASSWORD'] -or $envValues['POSTGRES_PASSWORD'] -eq $PlaceholderPassword) {
    $password = New-RandomSecret
    Set-EnvValue $EnvFile 'POSTGRES_PASSWORD' $password
    $url = "postgresql+psycopg://$($envValues['POSTGRES_USER']):$password@127.0.0.1:$($envValues['POSTGRES_PORT'])/$($envValues['POSTGRES_DB'])"
    Set-EnvValue $EnvFile 'DATABASE_URL' $url
    Write-Host 'Contrasena generada y guardada en .env (no versionado).'
} else {
    Write-Host 'Se mantiene la contrasena existente de .env.'
}

Push-Location $Root
try {
    docker compose up -d --wait
    if ($LASTEXITCODE -ne 0) { throw 'docker compose up fallo.' }
} finally {
    Pop-Location
}

Write-Host "PostgreSQL listo en 127.0.0.1:$($envValues['POSTGRES_PORT']) (base '$($envValues['POSTGRES_DB'])')."
