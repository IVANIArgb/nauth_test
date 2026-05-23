#Requires -Version 5.1
# Собрать образ для передачи на хостинг: learnsite-web.tar
$ErrorActionPreference = "Stop"
$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $Root

$out = Join-Path $Root "dist\learnsite-web.tar"
New-Item -ItemType Directory -Force -Path (Split-Path $out) | Out-Null

Write-Host "[1/2] docker compose build (hosting)..."
docker compose -f docker-compose.yml -f docker-compose.hosting.yml build
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "[2/2] docker save -> $out"
docker save learnsite:web -o $out
Write-Host "OK. Transfer to hosting:"
Write-Host "  docker load -i learnsite-web.tar"
Write-Host "  copy docker.env.hosting.example .env"
Write-Host "  docker compose -f docker-compose.yml -f docker-compose.hosting.yml up -d"
