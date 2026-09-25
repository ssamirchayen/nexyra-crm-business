param(
    [string]$HostAddress = "0.0.0.0",
    [int]$Port = 8000,
    [int]$Workers = 2
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $Root

$Python = Join-Path $Root ".venv\\Scripts\\python.exe"
if (-not (Test-Path $Python)) {
    throw "Ambiente .venv não encontrado em $Root. Crie-o e instale requirements.txt."
}
if (-not (Test-Path (Join-Path $Root ".env"))) {
    throw "Arquivo .env não encontrado. Copie .env.business.example para .env e configure PostgreSQL."
}

& $Python -m alembic upgrade head
if ($LASTEXITCODE -ne 0) { throw "Falha ao aplicar migrations." }

& $Python -m uvicorn app.main:app --host $HostAddress --port $Port --workers $Workers
