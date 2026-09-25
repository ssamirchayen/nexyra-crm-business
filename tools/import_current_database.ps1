param(
    [string]$Source = ""
)

$ErrorActionPreference = "Stop"
$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
if (-not $Source) {
    $Source = Join-Path $Root "nexyra_crm.db"
}

if (-not (Test-Path $Source)) {
    throw "Banco de origem não encontrado: $Source"
}

$DataDir = Join-Path $env:LOCALAPPDATA "Nexyra CRM"
$Destination = Join-Path $DataDir "nexyra_crm.db"
New-Item -ItemType Directory -Force -Path $DataDir | Out-Null

if (Test-Path $Destination) {
    $Stamp = Get-Date -Format "yyyyMMdd-HHmmss"
    Copy-Item $Destination "$Destination.backup-$Stamp" -Force
}

Copy-Item $Source $Destination -Force
Write-Host "Banco importado para: $Destination" -ForegroundColor Green
Write-Host "Na próxima abertura, o Nexyra aplicará migrations pendentes automaticamente."
