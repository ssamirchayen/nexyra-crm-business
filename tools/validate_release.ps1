$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $ProjectRoot

$Python = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $Python)) {
    throw "Ambiente virtual não encontrado em $Python"
}

Write-Host "[1/6] Alembic upgrade head" -ForegroundColor Cyan
& $Python -m alembic upgrade head

Write-Host "[2/6] Ruff" -ForegroundColor Cyan
& $Python -m ruff check app tests alembic tools

Write-Host "[3/6] Pytest" -ForegroundColor Cyan
& $Python -m pytest -q

Write-Host "[4/6] Smoke test em banco temporário" -ForegroundColor Cyan
& $Python tools\smoke_release.py

Write-Host "[5/6] TypeScript + Vite" -ForegroundColor Cyan
Push-Location frontend
try {
    if (-not (Test-Path "node_modules")) {
        npm ci
    }
    npm run build
} finally {
    Pop-Location
}

Write-Host "[6/6] Release validada" -ForegroundColor Green
Write-Host "Nexyra CRM 1.0.0 passou no checklist técnico local." -ForegroundColor Green
