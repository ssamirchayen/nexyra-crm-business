param()
$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $ProjectRoot
function Invoke-DockerChecked {
    & docker @args
    if ($LASTEXITCODE -ne 0) { throw "Validacao interrompida: etapa Docker falhou." }
}
Invoke-DockerChecked info | Out-Null

Write-Host "[1/7] Build, pytest, Ruff e dependencias de desenvolvimento"
Invoke-DockerChecked compose -f docker-compose.tests.yml build tests
Invoke-DockerChecked compose -f docker-compose.tests.yml run --rm tests
Invoke-DockerChecked compose -f docker-compose.tests.yml run --rm tests ruff check app tests tools alembic
Invoke-DockerChecked compose -f docker-compose.tests.yml run --rm tests pip check

Write-Host "[2/7] Redis real em ambiente temporario"
$CheckProject = "nexyra-final-check-" + [guid]::NewGuid().ToString("N")
try {
    Invoke-DockerChecked compose -p $CheckProject -f docker-compose.redis-check.yml build check
    Invoke-DockerChecked compose -p $CheckProject -f docker-compose.redis-check.yml run --rm check
} finally {
    # Only the unique project created above; never the Business project.
    Invoke-DockerChecked compose -p $CheckProject -f docker-compose.redis-check.yml down --volumes
}

Write-Host "[3/7] Auditoria online de Python e frontend"
Invoke-DockerChecked compose -f docker-compose.audit.yml build audit frontend-audit
Invoke-DockerChecked compose -f docker-compose.audit.yml run --rm audit
Invoke-DockerChecked compose -f docker-compose.audit.yml run --rm audit -r requirements-dev.txt --no-deps --disable-pip
Invoke-DockerChecked compose -f docker-compose.audit.yml run --rm frontend-audit

Write-Host "[4/7] Build e inicializacao do Business"
& powershell.exe -NoProfile -ExecutionPolicy Bypass -File (Join-Path $PSScriptRoot "business.ps1") start
if ($LASTEXITCODE -ne 0) { throw "Falha ao iniciar o Business." }
$BusinessArgs = @("compose", "--env-file", ".env.docker", "-f", "docker-compose.business.yml")

Write-Host "[5/7] Imagem de producao sem ferramentas de desenvolvimento"
Invoke-DockerChecked @BusinessArgs run --rm --no-deps --entrypoint python api tools/business_dependency_check.py
Invoke-DockerChecked @BusinessArgs run --rm --no-deps --entrypoint python api -m pip check

Write-Host "[6/7] Backup atual com integridade SHA-256"
& powershell.exe -NoProfile -ExecutionPolicy Bypass -File (Join-Path $PSScriptRoot "business.ps1") backup
if ($LASTEXITCODE -ne 0) { throw "Falha no backup." }
$LatestBackup = Get-ChildItem -LiteralPath (Join-Path $ProjectRoot "backups") -Filter *.dump |
    Sort-Object LastWriteTime -Descending | Select-Object -First 1
if (!$LatestBackup) { throw "Nenhum backup encontrado." }

Write-Host "[7/7] Restauracao isolada com login e logout"
& powershell.exe -NoProfile -ExecutionPolicy Bypass -File (Join-Path $PSScriptRoot "business_restore_check.ps1") -BackupFile $LatestBackup.FullName -TestApplication
if ($LASTEXITCODE -ne 0) { throw "Falha no teste da restauracao." }
Write-Host "Validacao final concluida. Banco restaurado e Redis de teste foram isolados do ambiente em uso."
