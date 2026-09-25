param(
    [ValidateSet("start", "status", "logs", "first-access", "stop", "backup")]
    [string]$Action = "start"
)
$ErrorActionPreference = "Stop"
Set-Location (Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path))
if (!(Test-Path ".env.docker")) { throw "Configure .env.docker antes de iniciar." }
$ComposeArgs = @("compose", "--env-file", ".env.docker", "-f", "docker-compose.business.yml")
function Invoke-Compose {
    & docker @ComposeArgs @args
    if ($LASTEXITCODE -ne 0) { throw "Falha no Docker. Execute tools/business.ps1 logs para diagnosticar." }
}
switch ($Action) {
    "backup" { & (Join-Path $PSScriptRoot "business_backup.ps1") -Action backup }
    "start" {
        Invoke-Compose up -d --build --wait --wait-timeout 180
        # Refresh Nginx's cached upstream after API recreation.
        Invoke-Compose restart web
        Write-Host "Business iniciado. Abra http://localhost:8080 (ou a porta NEXYRA_WEB_PORT configurada)."
    }
    "status" { Invoke-Compose ps -a }
    "logs" { Invoke-Compose logs --tail 80 api web }
    "first-access" { Invoke-Compose exec api python tools/business_first_access.py }
    "stop" { Invoke-Compose stop }
}
