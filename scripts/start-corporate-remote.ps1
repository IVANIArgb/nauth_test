<#
.SYNOPSIS
    Подготовка и запуск LearningSite на корпоративном Windows-ПК.
.DESCRIPTION
    - При отсутствии .env копирует env.corporate-remote.example → .env (один раз).
    - Активирует .venv при наличии.
    - Запускает python run.py из корня репозитория.
.EXAMPLE
    .\scripts\start-corporate-remote.ps1
#>
$ErrorActionPreference = "Stop"
$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $ProjectRoot

$envExample = Join-Path $ProjectRoot "env.corporate-remote.example"
$envFile = Join-Path $ProjectRoot ".env"

if (-not (Test-Path $envFile)) {
    if (-not (Test-Path $envExample)) {
        Write-Error "Не найден шаблон: $envExample"
    }
    Copy-Item -LiteralPath $envExample -Destination $envFile
    Write-Host "Создан файл .env из env.corporate-remote.example — отредактируйте SECRET_KEY, KERBEROS_REALM, пути." -ForegroundColor Yellow
}

$venvPy = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
if (Test-Path $venvPy) {
    & $venvPy (Join-Path $ProjectRoot "run.py")
} else {
    Write-Host "Виртуальное окружение не найдено (.venv). Рекомендуется: python -m venv .venv; .\.venv\Scripts\Activate.ps1; pip install -r requirements.txt" -ForegroundColor Yellow
    & python (Join-Path $ProjectRoot "run.py")
}
