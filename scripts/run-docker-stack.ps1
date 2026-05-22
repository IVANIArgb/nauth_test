#Requires -Version 5.1
<#
.SYNOPSIS
  Сборка образа и запуск LearningSite в Docker (SSO-прокси без keytab).
.EXAMPLE
  .\scripts\run-docker-stack.ps1
#>
$ErrorActionPreference = "Stop"
$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $ProjectRoot

function Require-Command([string]$name, [string]$hint) {
    if (-not (Get-Command $name -ErrorAction SilentlyContinue)) {
        throw "Не найдена команда '$name'. $hint"
    }
}

Require-Command "docker" "Установите Docker Desktop и убедитесь, что docker version работает."

$envFile = Join-Path $ProjectRoot ".env"
if (-not (Test-Path $envFile)) {
    foreach ($t in @("docker.env.sso.example", "docker.env.example", "env.example")) {
        $src = Join-Path $ProjectRoot $t
        if (Test-Path $src) {
            Copy-Item -LiteralPath $src -Destination $envFile
            Write-Host "Создан .env из $t"
            break
        }
    }
}

$composeFiles = @("-f", "docker-compose.yml")
if (Test-Path (Join-Path $ProjectRoot "docker-compose.sso.yml")) {
    $composeFiles += @("-f", "docker-compose.sso.yml")
}

Write-Host "Docker: сборка образа и запуск контейнеров..."
& docker compose @composeFiles build
if ($LASTEXITCODE -ne 0) { throw "docker compose build: код $LASTEXITCODE" }

& docker compose @composeFiles up -d
if ($LASTEXITCODE -ne 0) { throw "docker compose up: код $LASTEXITCODE" }

$webPort = "8080"
if (Test-Path $envFile) {
    foreach ($line in Get-Content $envFile -Encoding UTF8) {
        if ($line -match '^\s*WEB_PORT\s*=\s*(\d+)\s*$') {
            $webPort = $matches[1]
            break
        }
    }
}

Write-Host ""
Write-Host "Готово (Docker)." -ForegroundColor Green
if ($composeFiles -contains "docker-compose.sso.yml") {
    Write-Host "  Сайт (SSO):  http://localhost:${webPort}/"
    Write-Host "  API:         http://localhost:${webPort}/api/current-user"
    Write-Host "  Прямой web:  http://localhost:8000/healthz"
} else {
    Write-Host "  Сайт:        http://localhost:8000/"
}
Write-Host "  Логи:        docker compose $($composeFiles -join ' ') logs -f web"
Write-Host "  Остановка:   docker compose $($composeFiles -join ' ') down"
