#Requires -Version 5.1
<#
.SYNOPSIS
    Диагностика и сброс типичных проблем на корпоративном ПК (путь Пользователь, кэш, ветка).
.EXAMPLE
    cd C:\Users\ManakovIV\nauth_test
    .\scripts\fix-corporate-install.ps1
#>
$ErrorActionPreference = "Stop"
$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $ProjectRoot

Write-Host "=== LearningSite: fix-corporate-install ===" -ForegroundColor Cyan
Write-Host "Каталог: $ProjectRoot"

# 1) Ветка
$branch = (git rev-parse --abbrev-ref HEAD 2>$null)
$commit = (git rev-parse --short HEAD 2>$null)
Write-Host "Git: ветка=$branch commit=$commit"
if ($branch -ne "nauth") {
    Write-Host "ВНИМАНИЕ: нужна ветка nauth. Выполните: git checkout nauth && git pull" -ForegroundColor Yellow
}

# 2) Override-файл (важнее .env!)
$override = Join-Path $ProjectRoot ".content_root_dir_override"
if (Test-Path $override) {
    $ov = (Get-Content $override -Raw -Encoding UTF8).Trim()
    Write-Host "Найден .content_root_dir_override: $ov" -ForegroundColor Yellow
    Remove-Item -LiteralPath $override -Force
    Write-Host "Удалён .content_root_dir_override" -ForegroundColor Green
} else {
    Write-Host "OK: .content_root_dir_override нет"
}

# 3) .env CONTENT_ROOT_DIR
$envPath = Join-Path $ProjectRoot ".env"
if (Test-Path $envPath) {
    $lines = Get-Content $envPath -Encoding UTF8
    $out = foreach ($line in $lines) {
        if ($line -match '^\s*CONTENT_ROOT_DIR\s*=') {
            "CONTENT_ROOT_DIR="
        } else { $line }
    }
    $out | Set-Content $envPath -Encoding UTF8
    Write-Host "OK: в .env установлено CONTENT_ROOT_DIR=" -ForegroundColor Green
} else {
    Write-Host "Нет .env — запустите setup-windows.bat" -ForegroundColor Yellow
}

# 4) Процесс на порту 5000
$port = 5000
if ($env:PORT) { try { $port = [int]$env:PORT } catch {} }
$listeners = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue
if ($listeners) {
    Write-Host "Порт $port занят — остановите старый сервер (закройте окно python или):" -ForegroundColor Yellow
    foreach ($c in $listeners) {
        $p = Get-Process -Id $c.OwningProcess -ErrorAction SilentlyContinue
        if ($p) { Write-Host "  PID $($p.Id) $($p.ProcessName) $($p.Path)" }
    }
} else {
    Write-Host "OK: порт $port свободен"
}

# 5) Проверка JS (должен быть IIFE, не let в начале)
$modal = Join-Path $ProjectRoot "frontend\admin-pages\templates\js\custom-modal.js"
if (Test-Path $modal) {
    $head = (Get-Content $modal -TotalCount 12 -Encoding UTF8) -join "`n"
    if ($head -match '__learnSiteCustomModalLoaded') {
        Write-Host "OK: custom-modal.js — новая версия (IIFE)" -ForegroundColor Green
    } else {
        Write-Host "ОШИБКА: custom-modal.js старый. git checkout nauth && git pull" -ForegroundColor Red
    }
}

Write-Host ""
Write-Host "Дальше:" -ForegroundColor Cyan
Write-Host "  1) Закройте все окна с python run.py"
Write-Host "  2) .\run-server.bat   (или: .\.venv\Scripts\python.exe run.py)"
Write-Host "  3) В браузере: Ctrl+Shift+R (жёсткое обновление)"
Write-Host "  4) Проверка: http://127.0.0.1:${port}/api/categories — должен быть JSON, не 500"
