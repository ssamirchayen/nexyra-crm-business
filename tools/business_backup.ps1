param(
    [ValidateSet("backup", "verify")]
    [string]$Action = "backup",
    [string]$BackupFile = ""
)
$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $ProjectRoot
if (!(Test-Path ".env.docker")) { throw "Configure .env.docker antes de continuar." }
$ComposeArgs = @("compose", "--env-file", ".env.docker", "-f", "docker-compose.business.yml")
function Invoke-BackupCompose {
    & docker @ComposeArgs @args
    if ($LASTEXITCODE -ne 0) { throw "Falha no Docker durante o backup. Confira a mensagem acima." }
}

if ($Action -eq "verify") {
    if (!$BackupFile) { throw "Informe -BackupFile com o caminho do arquivo .dump." }
    $Archive = Get-Item -LiteralPath $BackupFile
    if ($Archive.PSIsContainer -or $Archive.Extension -ne ".dump") { throw "Selecione um arquivo .dump." }
    $Mount = $Archive.DirectoryName + ":/backup:ro"
    Invoke-BackupCompose run --rm --no-deps --entrypoint python --volume $Mount api tools/business_backup.py verify ("/backup/" + $Archive.Name)
    Write-Host "Arquivo e manifesto conferidos. Esta verificacao nao substitui um teste de restauracao."
    exit 0
}

$BackupDirectory = Join-Path $ProjectRoot "backups"
New-Item -ItemType Directory -Path $BackupDirectory -Force | Out-Null
$BackupId = (Get-Date -Format "yyyyMMdd_HHmmss") + "_" + [guid]::NewGuid().ToString("N")
$FileName = "nexyra_business_" + $BackupId + ".dump"
$RemoteFile = "/tmp/" + $FileName
$PartialFile = Join-Path $BackupDirectory ($FileName + ".partial")
$Mount = $BackupDirectory + ":/backup"
try {
    # Write binary data to a file inside PostgreSQL, never through PowerShell >.
    # The database's existing environment provides its name/user; no password is printed.
    # Disable field splitting/globbing; avoid nested quotes in Windows native arguments.
    $DumpCommand = 'set -efu; IFS=; umask 077; pg_dump --username=$POSTGRES_USER --dbname=$POSTGRES_DB --format=custom --file=$1; pg_restore --list $1 >/dev/null'
    Invoke-BackupCompose exec -T db sh -c $DumpCommand sh $RemoteFile
    Invoke-BackupCompose cp ("db:" + $RemoteFile) $PartialFile
    Invoke-BackupCompose run --rm --no-deps --entrypoint python --volume $Mount api tools/business_backup.py seal ("/backup/" + $FileName + ".partial")
    Invoke-BackupCompose run --rm --no-deps --entrypoint python --volume ($BackupDirectory + ":/backup:ro") api tools/business_backup.py verify ("/backup/" + $FileName)
    Write-Host ("Backup salvo: " + (Join-Path $BackupDirectory $FileName))
    Write-Host "Guarde o .dump e o .dump.sha256.json juntos. Copie-os tambem para outro local."
} finally {
    & docker @ComposeArgs exec -T db rm -f -- $RemoteFile
    if ($LASTEXITCODE -ne 0) { Write-Warning "Nao foi possivel remover o arquivo temporario do container." }
}
