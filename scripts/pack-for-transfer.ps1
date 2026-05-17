# Упаковать проект для переноса на другой ПК (без .env, venv, docker-образов, uploads).
$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $PSScriptRoot
$OutDir = Join-Path $env:USERPROFILE 'Desktop'
$Zip = Join-Path $OutDir 'nauth_test-transfer.zip'

$exclude = @(
    '.git', '.venv', 'venv', '__pycache__', '.pytest_cache', '.cursor', '.idea',
    'backend\uploads', 'backend\logs', 'docker_export', 'LNSVImage',
    'categories-data', 'database\*.db', '.env'
)

Push-Location $Root
$items = Get-ChildItem -Force | Where-Object { $exclude -notcontains $_.Name }
Compress-Archive -Path ($items | ForEach-Object { $_.FullName }) -DestinationPath $Zip -Force
Pop-Location

Write-Host "Архив: $Zip"
Write-Host "На другом ПК: распакуйте и откройте папку."
