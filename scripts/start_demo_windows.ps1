param(
    [switch]$NoDaemon,
    [switch]$SkipSeed,
    [switch]$RebuildSeed,
    [switch]$NoBootstrap,
    [switch]$UseSQLite,
    [switch]$Reinstall,
    [string]$Address = '127.0.0.1:8000'
)

$ErrorActionPreference = 'Stop'
$ProjectDir = Split-Path -Parent $PSScriptRoot
$AppDisplayName = 'SaldoFlow(WIN)'
Set-Location $ProjectDir

function Write-Info($Message) { Write-Host "[INFO] $Message" -ForegroundColor Cyan }
function Write-Ok($Message) { Write-Host "[OK] $Message" -ForegroundColor Green }
function Write-Warn($Message) { Write-Host "[UWAGA] $Message" -ForegroundColor Yellow }
function Write-Fail($Message) { Write-Host "[BŁĄD] $Message" -ForegroundColor Red }

function Get-PythonCommand {
    if (Get-Command py -ErrorAction SilentlyContinue) { return 'py -3' }
    if (Get-Command python -ErrorAction SilentlyContinue) { return 'python' }
    throw 'Nie znaleziono Python 3.'
}

function Invoke-Py($CommandText) {
    $psi = New-Object System.Diagnostics.ProcessStartInfo
    $psi.FileName = 'cmd.exe'
    $psi.Arguments = "/c $CommandText"
    $psi.WorkingDirectory = $ProjectDir
    $psi.UseShellExecute = $false
    $psi.RedirectStandardOutput = $false
    $psi.RedirectStandardError = $false
    $process = [System.Diagnostics.Process]::Start($psi)
    $process.WaitForExit()
    if ($process.ExitCode -ne 0) { throw "Polecenie nie powiodło się: $CommandText" }
}

function Ensure-Oracle {
    if ($UseSQLite) { return }
    if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
        throw 'Nie znaleziono Dockera.'
    }

    $exists = docker inspect saldoflow-oracle 2>$null
    if ($LASTEXITCODE -eq 0) {
        $image = docker inspect --format '{{.Config.Image}}' saldoflow-oracle
        if ($image -notmatch 'oracle-free') {
            throw "Kontener saldoflow-oracle istnieje, ale nie wygląda na Oracle Free: $image"
        }
        Write-Info 'Używam istniejącego kontenera saldoflow-oracle.'
        docker start saldoflow-oracle | Out-Null
    }
    else {
        Write-Info 'Uruchamiam Oracle przez compose.oracle.yml'
        docker compose -f compose.oracle.yml up -d
        if ($LASTEXITCODE -ne 0) { throw 'docker compose up -d zakończyło się błędem.' }
    }

    Write-Info 'Czekam aż Oracle będzie gotowe...'
    for ($i = 0; $i -lt 120; $i++) {
        $status = docker inspect --format "{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}" saldoflow-oracle 2>$null
        if ($status -eq 'healthy' -or $status -eq 'running') {
            Write-Ok "Oracle gotowe ($status)."
            return
        }
        Start-Sleep -Seconds 5
    }
    docker logs saldoflow-oracle --tail 80
    throw 'Oracle nie osiągnęło stanu healthy/running.'
}

function Ensure-PythonEnv {
    $py = Get-PythonCommand
    if (-not (Test-Path .venv)) {
        Write-Info 'Tworzę virtualenv .venv'
        Invoke-Py "$py -m venv .venv"
    }
    if ($Reinstall -or -not (Test-Path .venv\.deps_installed)) {
        Write-Info 'Instaluję zależności Python'
        Invoke-Py ".venv\Scripts\python.exe -m pip install --upgrade pip"
        Invoke-Py ".venv\Scripts\python.exe -m pip install -r requirements.txt"
        New-Item -ItemType File -Path .venv\.deps_installed -Force | Out-Null
    }
}

function Prepare-Common {
    New-Item -ItemType Directory -Force -Path runtime\watch\dom | Out-Null
    New-Item -ItemType Directory -Force -Path runtime\watch\firma | Out-Null
    New-Item -ItemType Directory -Force -Path runtime\daemon_status | Out-Null
    New-Item -ItemType Directory -Force -Path runtime\emails | Out-Null

    $env:APP_NAME = $AppDisplayName
    $env:DJANGO_DEBUG = '1'
    $env:DJANGO_ALLOWED_HOSTS = '127.0.0.1,localhost'
    $env:DJANGO_CSRF_TRUSTED_ORIGINS = 'http://127.0.0.1,http://localhost'
    $env:EMAIL_FILE_PATH = "$ProjectDir\runtime\emails"
}

function Run-App {
    $pythonExe = Join-Path $ProjectDir '.venv\Scripts\python.exe'

    if ($UseSQLite) {
        $env:DB_ENGINE = 'sqlite'
    }
    else {
        $env:DB_ENGINE = 'oracle'
        $env:ORACLE_HOST = '127.0.0.1'
        $env:ORACLE_PORT = '1521'
        $env:ORACLE_SERVICE_NAME = 'FREEPDB1'
        $env:ORACLE_USER = 'SALDOFLOW_APP'
        $env:ORACLE_PASSWORD = 'change-me'
    }

    Write-Info 'Wykonuję migracje'
    & $pythonExe manage.py migrate
    if ($LASTEXITCODE -ne 0) { throw 'Migracje nie powiodły się.' }

    if (-not $NoBootstrap) {
        Write-Info 'Tworzę/aktualizuję konta pokazowe marcin/test'
        & $pythonExe manage.py bootstrap_demo_security
        if ($LASTEXITCODE -ne 0) { throw 'bootstrap_demo_security nie powiodło się.' }
    }

    if (-not $SkipSeed) {
        Write-Info 'Przygotowuję duży zestaw danych demonstracyjnych'
        if ($RebuildSeed) {
            & $pythonExe manage.py seed_showcase_data --force
        }
        else {
            & $pythonExe manage.py seed_showcase_data
        }
        if ($LASTEXITCODE -ne 0) { throw 'seed_showcase_data nie powiodło się.' }
    }

    if (-not $NoDaemon) {
        Write-Warn 'Ten demon jest natywnie linuksowy (POSIX C). Na Windows uruchamiam aplikację bez demona.'
        Write-Warn 'Do pełnej prezentacji z demonem użyj WSL albo Linux i skryptu scripts/start_demo_linux.sh.'
    }

    Write-Ok "Aplikacja będzie dostępna pod: http://$Address"
    Write-Ok "Nazwa projektu w interfejsie: $AppDisplayName"
    Write-Ok 'Login demo admina: marcin / danzel12'
    Write-Ok 'Konto testowe: test / test'
    Write-Ok 'Konta z dużymi danymi: 20 (test + user01..user19), po 1000 operacji na konto, zakres 2020-01 do 2026-06'
    & $pythonExe manage.py runserver $Address
}

try {
    if (-not $NoDaemon) {
        $NoDaemon = $true
    }
    Ensure-Oracle
    Ensure-PythonEnv
    Prepare-Common
    Run-App
}
catch {
    Write-Fail $_.Exception.Message
    exit 1
}
