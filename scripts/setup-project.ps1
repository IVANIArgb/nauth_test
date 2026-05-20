#Requires -Version 5.1
<#
.SYNOPSIS
    Клонирование (при необходимости), checkout ветки, venv, зависимости, .env под Windows.
.DESCRIPTION
    Переменные окружения (до запуска):
      NAUTH_REPO          URL git (по умолчанию https://github.com/IVANIArgb/nauth_test.git)
      NAUTH_BRANCH        ветка (по умолчанию main)
      NAUTH_INSTALL_DIR   каталог проекта; если не задан — родитель scripts/ (текущий репозиторий)
      SETUP_USE_PROD_DEPS true — pip install -r requirements-prod.txt, иначе requirements.txt
      NAUTH_USE_DOCKER    true — после настройки вызвать docker compose SSO (как install-nauth_test)
.PARAMETER InstallPath
    Каталог установки (перекрывает NAUTH_INSTALL_DIR). Не использовать имя Path — конфликт с $PATH в сессии.
.PARAMETER Branch
    Ветка git (перекрывает NAUTH_BRANCH).
.PARAMETER Repo
    URL репозитория (перекрывает NAUTH_REPO).
.PARAMETER Docker
    Запустить Docker SSO-стек после подготовки (нужен Docker Desktop).
.EXAMPLE
    .\scripts\setup-project.ps1
.EXAMPLE
    .\scripts\setup-project.ps1 -InstallPath "D:\work\nauth_test" -Branch "main"
#>
param(
    [Alias("InstallDir")]
    [string]$InstallPath = "",
    [string]$Branch = "",
    [string]$Repo = "",
    [switch]$Docker
)

$ErrorActionPreference = "Stop"
$ScriptRoot = $PSScriptRoot
$DefaultRepo = "https://github.com/IVANIArgb/nauth_test.git"
$DefaultBranch = "main"

$RepoUrl = if ($Repo) { $Repo.Trim() } elseif ($env:NAUTH_REPO) { $env:NAUTH_REPO.Trim() } else { $DefaultRepo }
$GitBranch = if ($Branch) { $Branch.Trim() } elseif ($env:NAUTH_BRANCH) { $env:NAUTH_BRANCH.Trim() } else { $DefaultBranch }

if ($InstallPath -and $InstallPath.Trim()) {
    $ProjectRoot = $InstallPath.Trim()
} elseif ($env:NAUTH_INSTALL_DIR -and $env:NAUTH_INSTALL_DIR.Trim()) {
    $ProjectRoot = $env:NAUTH_INSTALL_DIR.Trim()
} else {
    $ProjectRoot = (Resolve-Path (Join-Path $ScriptRoot "..")).Path
}

function Require-Command([string]$name, [string]$Hint) {
    if (-not (Get-Command $name -ErrorAction SilentlyContinue)) {
        throw "Не найдена команда '$name'. $Hint"
    }
}

Require-Command "git" "Установите Git: https://git-scm.com/download/win"

function Ensure-Repo {
    param([string]$Root, [string]$Url, [string]$Br)

    $gitDir = Join-Path $Root ".git"
    if (Test-Path $gitDir) {
        Write-Host "Репозиторий уже есть: $Root — fetch / checkout $Br"
        Push-Location $Root
        try {
            git fetch origin --prune
            git checkout $Br
            git pull --ff-only origin $Br
        } finally {
            Pop-Location
        }
        return
    }

    if (Test-Path $Root) {
        $children = @(Get-ChildItem -LiteralPath $Root -Force -ErrorAction SilentlyContinue)
        if ($children.Count -gt 0) {
            throw "Каталог существует и не пуст, но нет .git: $Root. Укажите другой NAUTH_INSTALL_DIR или удалите мусор."
        }
    }

    $parent = Split-Path -Parent $Root
    if ($parent -and -not (Test-Path $parent)) {
        New-Item -ItemType Directory -Force -Path $parent | Out-Null
    }
    Write-Host "Клонирование: $Url (ветка $Br) -> $Root"
    $parent = Split-Path -Parent $Root
    if ($parent -and -not (Test-Path $parent)) {
        New-Item -ItemType Directory -Force -Path $parent | Out-Null
    }
    git clone -b $Br --single-branch $Url $Root
}

Ensure-Repo -Root $ProjectRoot -Url $RepoUrl -Br $GitBranch
Set-Location $ProjectRoot

# --- Python ---
$py = $null
try {
    $o = & py -3 -c "import sys; print(sys.executable)" 2>$null
    if ($o) { $py = ($o | Out-String).Trim() }
} catch { }
if (-not $py) {
    try {
        $o = & python -c "import sys; print(sys.executable)" 2>$null
        if ($o) { $py = ($o | Out-String).Trim() }
    } catch { }
}
if (-not $py -or -not (Test-Path -LiteralPath $py)) {
    throw "Не найден Python 3 (команды py -3 / python). Установите с https://www.python.org/downloads/windows/"
}
Write-Host "Python: $py"

$venvPython = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $venvPython)) {
    Write-Host "Создание виртуального окружения .venv ..."
    & $py -m venv (Join-Path $ProjectRoot ".venv")
    $venvPython = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
    if (-not (Test-Path $venvPython)) {
        throw "Не удалось создать .venv"
    }
}

$req = "requirements.txt"
if (($env:SETUP_USE_PROD_DEPS -or "").Trim().ToLowerInvariant() -in @("1", "true", "yes", "y", "on")) {
    if (Test-Path (Join-Path $ProjectRoot "requirements-prod.txt")) {
        $req = "requirements-prod.txt"
    }
}
Write-Host "pip install -r $req ..."
& $venvPython -m pip install --upgrade pip
& $venvPython -m pip install -r (Join-Path $ProjectRoot $req)

# --- .env ---
$envFile = Join-Path $ProjectRoot ".env"
if (-not (Test-Path $envFile)) {
    $template = $null
    foreach ($t in @("env.corporate-remote.example", "env.example", "docker.env.sso.example", "docker.env.example")) {
        $p = Join-Path $ProjectRoot $t
        if (Test-Path $p) {
            $template = $p
            break
        }
    }
    if ($template) {
        Copy-Item -LiteralPath $template -Destination $envFile
        Write-Host "Создан .env из $(Split-Path -Leaf $template)"
    } else {
        Write-Host "Предупреждение: шаблон .env не найден — создайте .env вручную." -ForegroundColor Yellow
    }
}

function Set-EnvKey([string]$key, [string]$value) {
    $path = Join-Path $ProjectRoot ".env"
    if (-not (Test-Path $path)) { return }
    $lines = Get-Content $path -Encoding UTF8
    $found = $false
    $out = foreach ($line in $lines) {
        if ($line -match "^\s*#") { $line; continue }
        if ($line -match "^\s*$([regex]::Escape($key))\s*=") {
            $found = $true
            "$key=$value"
        } else { $line }
    }
    if (-not $found) { $out += "$key=$value" }
    $out | Set-Content $path -Encoding UTF8
}

if (Test-Path $envFile) {
    # Подстройка под Windows-хост без Docker: удобные дефолты, не затирая явные значения пользователя
    function Test-PlaceholderSecret([string]$raw) {
        if (-not $raw) { return $true }
        $s = $raw.ToLowerInvariant()
        return $s -match "замените|сгенерируйте|your_|example\.com|not-for-production|dev-key"
    }
    $sk = ""
    foreach ($line in (Get-Content $envFile -Encoding UTF8)) {
        if ($line -match '^\s*SECRET_KEY\s*=\s*(.*)$') {
            $sk = $matches[1].Trim()
            break
        }
    }
    if (Test-PlaceholderSecret $sk) {
        $rng = New-Object System.Security.Cryptography.RNGCryptoServiceProvider
        $bytes = New-Object byte[] 32
        $rng.GetBytes($bytes)
        $newKey = [BitConverter]::ToString($bytes).Replace("-", "").ToLowerInvariant()
        Set-EnvKey "SECRET_KEY" $newKey
        Write-Host "SECRET_KEY в .env заменён на случайный (64 hex-символа)."
    }

    $overrideFile = Join-Path $ProjectRoot ".content_root_dir_override"
    if (Test-Path $overrideFile) {
        Remove-Item -LiteralPath $overrideFile -Force
        Write-Host "Удалён .content_root_dir_override (мог указывать на чужой профиль Windows)."
    }

    if (-not ($env:NAUTH_SKIP_HOST_TUNING -eq "1")) {
        Set-EnvKey "DOCKER" "false"
        Set-EnvKey "CONTENT_ROOT_DIR" ""
    }
}

# --- Ярлык запуска (опционально) ---
$runBat = Join-Path $ProjectRoot "run-server.bat"
@"
@echo off
chcp 65001 >nul
cd /d "%~dp0"
call ".venv\Scripts\activate.bat"
python run.py
pause
"@ | Set-Content -Path $runBat -Encoding UTF8
Write-Host "Создан ярлык: run-server.bat"

$useDocker = $Docker -or (($env:NAUTH_USE_DOCKER -or "").Trim().ToLowerInvariant() -in @("1", "true", "yes", "y", "on"))
if ($useDocker) {
    Require-Command "docker" "Установите Docker Desktop: https://www.docker.com/products/docker-desktop/"
    Write-Host "Docker: сборка и запуск (docker-compose.yml + docker-compose.sso.yml при наличии)..."
    if ((Test-Path (Join-Path $ProjectRoot "docker-compose.sso.yml"))) {
        docker compose -f docker-compose.yml -f docker-compose.sso.yml up -d --build
    } else {
        docker compose -f docker-compose.yml up -d --build
    }
    if ($LASTEXITCODE -ne 0) { throw "docker compose завершился с кодом $LASTEXITCODE" }
    Write-Host "Готово (Docker). Сайт см. в выводе docker / README."
} else {
    Write-Host ""
    Write-Host "Готово (нативный Python)." -ForegroundColor Green
    Write-Host "  Каталог: $ProjectRoot"
    Write-Host "  Запуск:  .\run-server.bat   или   .\.venv\Scripts\Activate.ps1 ; python run.py"
    Write-Host "  В логе при старте ищите: learningsite.startup"
}
