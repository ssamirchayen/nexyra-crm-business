param(
    [switch]$SkipInstaller,
    [switch]$SkipTests
)

$ErrorActionPreference = "Stop"
$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$BuildVenv = Join-Path $Root ".venv-build"
$Python = Join-Path $BuildVenv "Scripts\python.exe"
$PyInstaller = Join-Path $BuildVenv "Scripts\pyinstaller.exe"
$SmokeData = Join-Path $env:TEMP "NexyraCRM-build-smoke"

function Step([string]$Message) {
    Write-Host "`n==> $Message" -ForegroundColor Cyan
}

Set-Location $Root

Step "Verificando Python e Node.js"
if (-not (Get-Command py -ErrorAction SilentlyContinue) -and -not (Get-Command python -ErrorAction SilentlyContinue)) {
    throw "Python 3 não encontrado no PATH."
}
if (-not (Get-Command npm -ErrorAction SilentlyContinue)) {
    throw "Node.js/npm não encontrado no PATH."
}

if (-not (Test-Path $BuildVenv)) {
    Step "Criando ambiente de build"
    if (Get-Command py -ErrorAction SilentlyContinue) {
        & py -3 -m venv $BuildVenv
    } else {
        & python -m venv $BuildVenv
    }
}

Step "Instalando dependências Python de build"
& $Python -m pip install --upgrade pip
& $Python -m pip install -r requirements.txt
& $Python -m pip install -r requirements-build.txt

if (-not $SkipTests) {
    & $Python -m pip install -r requirements-dev.txt
    if ($LASTEXITCODE -ne 0) { throw "Falha ao instalar dependencias de desenvolvimento." }
    Step "Executando Ruff e testes"
    & $Python -m ruff check app tests alembic tools
    if ($LASTEXITCODE -ne 0) { throw "Ruff falhou." }
    & $Python -m pytest -q
    if ($LASTEXITCODE -ne 0) { throw "Pytest falhou." }
}

Step "Compilando frontend React"
Push-Location (Join-Path $Root "frontend")
try {
    if (Test-Path "node_modules") {
        & npm run build
    } else {
        & npm ci
        if ($LASTEXITCODE -ne 0) { throw "npm ci falhou." }
        & npm run build
    }
    if ($LASTEXITCODE -ne 0) { throw "Build do frontend falhou." }
} finally {
    Pop-Location
}

Step "Gerando NexyraCRM Desktop.exe com PyInstaller"
Remove-Item -Recurse -Force (Join-Path $Root "build") -ErrorAction SilentlyContinue
Remove-Item -Recurse -Force (Join-Path $Root "dist") -ErrorAction SilentlyContinue
& $PyInstaller --noconfirm --clean (Join-Path $Root "packaging\nexyra_crm.spec")
if ($LASTEXITCODE -ne 0) { throw "PyInstaller falhou." }

$Exe = Join-Path $Root "dist\NexyraCRM.exe"
if (-not (Test-Path $Exe)) { throw "NexyraCRM.exe não foi criado." }

Step "Executando smoke test do executável"
Remove-Item -Recurse -Force $SmokeData -ErrorAction SilentlyContinue
& $Exe --smoke-test --data-dir $SmokeData
if ($LASTEXITCODE -ne 0) { throw "Smoke test do executável falhou." }
Remove-Item -Recurse -Force $SmokeData -ErrorAction SilentlyContinue

if (-not $SkipInstaller) {
    Step "Procurando Inno Setup"
    $ISCC = @(
        "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe",
        "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
        "$env:ProgramFiles\Inno Setup 6\ISCC.exe"
    ) | Where-Object { $_ -and (Test-Path $_) } | Select-Object -First 1

    if ($ISCC) {
        Step "Gerando instalador"
        & "$ISCC" (Join-Path $Root "packaging\NexyraCRM.iss")
        if ($LASTEXITCODE -ne 0) { throw "Inno Setup falhou." }
        Write-Host "`nInstalador criado em:" -ForegroundColor Green
        Write-Host (Join-Path $Root "release\NexyraCRM_Setup_1.0.0.exe")
    } else {
        Write-Warning "Inno Setup 6 não encontrado. O EXE portátil foi criado com sucesso."
        Write-Host "Para gerar o instalador, instale com:"
        Write-Host "  winget install -e --id JRSoftware.InnoSetup"
        Write-Host "e execute este script novamente."
    }
}

Write-Host "`nBuild concluído." -ForegroundColor Green
Write-Host "Executável portátil: $Exe"
