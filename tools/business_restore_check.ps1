param(
    [Parameter(Mandatory = $true)]
    [string]$BackupFile,
    [switch]$TestApplication
)
$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $ProjectRoot
if (!(Test-Path ".env.docker")) { throw "Configure .env.docker antes de continuar." }
$Archive = Get-Item -LiteralPath $BackupFile
if ($Archive.PSIsContainer -or $Archive.Extension -ne ".dump") { throw "Selecione um arquivo .dump." }
$ComposeArgs = @("compose", "--env-file", ".env.docker", "-f", "docker-compose.business.yml")
function Invoke-CheckedDocker {
    & docker @args
    if ($LASTEXITCODE -ne 0) { throw "Falha no Docker durante o teste de restauracao." }
}

# Verify before creating any database. The input folder is mounted read-only.
Invoke-CheckedDocker @ComposeArgs run --rm --no-deps --entrypoint python --volume ($Archive.DirectoryName + ":/backup:ro") api tools/business_backup.py verify ("/backup/" + $Archive.Name)
$Manifest = Get-Content -LiteralPath ($Archive.FullName + ".sha256.json") -Raw | ConvertFrom-Json
$ExpectedHash = [string]$Manifest.sha256
if ($ExpectedHash -notmatch '^[a-f0-9]{64}$') { throw "SHA-256 invalido no manifesto." }

$TestId = [guid]::NewGuid().ToString("N")
$ContainerName = "nexyra-restore-check-" + $TestId
$TestPassword = [guid]::NewGuid().ToString("N") + [guid]::NewGuid().ToString("N")
$ReportDirectory = Join-Path $ProjectRoot ("backups\restore-checks\" + $TestId)
$ContainerId = ""
$ApiContainerId = ""
$NetworkId = ""
$CheckPassed = $false
try {
    $DatabaseNetworkArgs = @("--network", "none")
    if ($TestApplication) {
        $NetworkId = ([string](Invoke-CheckedDocker network create --internal ("nexyra-restore-check-" + $TestId))).Trim()
        if ($NetworkId -notmatch '^[a-f0-9]{64}$') { throw "ID invalido para a rede temporaria." }
        $DatabaseNetworkArgs = @("--network", $NetworkId, "--network-alias", "restore-db")
    }
    # No published ports, no project network, no production volumes.
    # PostgreSQL's anonymous data volume is removed with this exact container ID.
    $Created = Invoke-CheckedDocker create --name $ContainerName @DatabaseNetworkArgs --label ("nexyra.restore-check=" + $TestId) --env ("POSTGRES_PASSWORD=" + $TestPassword) --env POSTGRES_USER=nexyra_restore --env POSTGRES_DB=nexyra_restore_check postgres:16-alpine
    $ContainerId = ([string]($Created | Select-Object -Last 1)).Trim()
    if ($ContainerId -notmatch '^[a-f0-9]{64}$') { throw "Docker nao retornou um ID valido para o container temporario." }
    Invoke-CheckedDocker start $ContainerId | Out-Null
    $Ready = $false
    for ($Attempt = 0; $Attempt -lt 60; $Attempt++) {
        & docker exec $ContainerId pg_isready --host=127.0.0.1 --username=nexyra_restore --dbname=nexyra_restore_check *> $null
        if ($LASTEXITCODE -eq 0) { $Ready = $true; break }
        Start-Sleep -Seconds 1
    }
    if (!$Ready) { throw "PostgreSQL temporario nao ficou pronto em 60 segundos." }
    Invoke-CheckedDocker cp $Archive.FullName ($ContainerId + ":/tmp/backup.dump")
    $HashOutput = Invoke-CheckedDocker exec $ContainerId sha256sum /tmp/backup.dump
    $CopiedHash = (([string]$HashOutput).Trim() -split '\s+')[0]
    if ($CopiedHash -ne $ExpectedHash) { throw "A copia do backup nao corresponde ao manifesto verificado." }
    Invoke-CheckedDocker exec $ContainerId pg_restore --exit-on-error --single-transaction --no-owner --no-privileges --username=nexyra_restore --dbname=nexyra_restore_check /tmp/backup.dump
    Invoke-CheckedDocker cp (Join-Path $PSScriptRoot "business_restore_check.sql") ($ContainerId + ":/tmp/check.sql")
    Invoke-CheckedDocker exec $ContainerId psql --no-psqlrc --tuples-only --no-align --set ON_ERROR_STOP=1 --username=nexyra_restore --dbname=nexyra_restore_check --file=/tmp/check.sql --output=/tmp/check.json
    New-Item -ItemType Directory -Path $ReportDirectory -Force | Out-Null
    Invoke-CheckedDocker cp ($ContainerId + ":/tmp/check.json") (Join-Path $ReportDirectory "database-check.json")
    $ApplicationReportArgs = @()
    if ($TestApplication) {
        $ImageRef = Invoke-CheckedDocker @ComposeArgs images --quiet api | Select-Object -First 1
        if (!$ImageRef) { throw "Imagem da API ausente. Execute business.ps1 start antes do teste." }
        $ApiImage = ([string](Invoke-CheckedDocker image inspect --format '{{.Id}}' $ImageRef)).Trim()
        if ($ApiImage -notmatch '^sha256:[a-f0-9]{64}$') { throw "ID invalido para a imagem da API." }
        $ApiEnvironment = @(
            "--env", "NEXYRA_DB_HOST=restore-db",
            "--env", "NEXYRA_DB_PORT=5432",
            "--env", "NEXYRA_DB_NAME=nexyra_restore_check",
            "--env", "NEXYRA_DB_USER=nexyra_restore",
            "--env", ("NEXYRA_DB_PASSWORD=" + $TestPassword),
            "--env", ("NEXYRA_RESTORE_CHECK_ID=" + $TestId),
            "--env", "DATABASE_REQUIRE_POSTGRESQL=true",
            "--env", "DEPLOYMENT_MODE=business",
            "--env", "ENVIRONMENT=development",
            "--env", "SQL_ECHO=false",
            "--env", "SECURITY_RATE_LIMIT_ENABLED=false",
            "--env", "SECURITY_ALLOWED_HOSTS=127.0.0.1,localhost",
            "--env", ("INTEGRATION_SECRET_MASTER_KEY=restore-only-" + $TestId),
            "--env", ("ATLAS_INTEGRATION_TOKEN=restore-only-" + $TestId)
        )
        $ApiCreated = Invoke-CheckedDocker create --name ("nexyra-restore-api-" + $TestId) --network $NetworkId --label ("nexyra.restore-check=" + $TestId) @ApiEnvironment --entrypoint python $ApiImage -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --no-access-log
        $ApiContainerId = ([string]($ApiCreated | Select-Object -Last 1)).Trim()
        if ($ApiContainerId -notmatch '^[a-f0-9]{64}$') { throw "ID invalido para a API temporaria." }
        Invoke-CheckedDocker start $ApiContainerId | Out-Null
        Invoke-CheckedDocker exec $ApiContainerId python -m tools.business_restore_smoke
        Invoke-CheckedDocker cp ($ApiContainerId + ":/tmp/application-check.json") (Join-Path $ReportDirectory "application-check.json")
        $ApplicationReportArgs = @("--application-check", "/report/application-check.json", "--check-id", $TestId)
    }
    Invoke-CheckedDocker @ComposeArgs run --rm --no-deps --entrypoint python --volume ($ReportDirectory + ":/report") api tools/business_restore_report.py /report/database-check.json /report/restore-report.json --backup-name $Archive.Name --sha256 $CopiedHash @ApplicationReportArgs
    $CheckPassed = $true
} finally {
    if ($ApiContainerId -match '^[a-f0-9]{64}$') {
        & docker rm --force --volumes $ApiContainerId | Out-Null
        if ($LASTEXITCODE -ne 0) {
            Write-Warning ("Limpeza pendente da API temporaria: " + $ApiContainerId)
            $CheckPassed = $false
        }
    }
    if ($ContainerId -match '^[a-f0-9]{64}$') {
        & docker rm --force --volumes $ContainerId | Out-Null
        if ($LASTEXITCODE -ne 0) {
            Write-Warning ("Limpeza pendente do container temporario: " + $ContainerId)
            Write-Warning "Remova apenas esse container com docker rm --force --volumes ID."
            $CheckPassed = $false
        }
    }
    if ($NetworkId -match '^[a-f0-9]{64}$') {
        & docker network rm $NetworkId | Out-Null
        if ($LASTEXITCODE -ne 0) {
            Write-Warning ("Limpeza pendente da rede temporaria: " + $NetworkId)
            $CheckPassed = $false
        }
    }
    $TestPassword = $null
}
if (!$CheckPassed) { throw "O teste ou a limpeza do ambiente temporario nao foi concluido." }
Write-Host ("Teste concluido. Relatorio: " + (Join-Path $ReportDirectory "restore-report.json"))
if ($TestApplication) {
    Write-Host "Banco, API e login com conta temporaria conferidos. Usuarios reais e integracoes externas nao foram testados."
} else {
    Write-Host "O banco em uso foi preservado. Este teste nao inclui login ou integracoes externas."
}
