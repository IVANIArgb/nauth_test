# Запуск LearningSite с SSO-прокси (без keytab).
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

if (-not (Test-Path ".env")) {
    Copy-Item "docker.env.sso.example" ".env"
    Write-Host "Создан .env из docker.env.sso.example — при необходимости задайте SSO_DEFAULT_USER"
}

docker compose -f docker-compose.yml -f docker-compose.sso.yml up -d --build
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

$port = (Get-Content .env | Where-Object { $_ -match '^WEB_PORT=' } | ForEach-Object { $_ -replace '^WEB_PORT=', '' })
if (-not $port) { $port = "8080" }

Write-Host ""
Write-Host "SSO URL:  http://localhost:$port/user/info-test"
Write-Host "API:      http://localhost:$port/api/current-user"
Write-Host "Прямой:   http://localhost:8000/healthz (без прокси — guest/fallback)"
Write-Host ""
Write-Host "Логин задаётся SSO_DEFAULT_USER в .env (кириллица допустима)."
