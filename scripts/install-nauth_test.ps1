#Requires -Version 5.1
<#
.SYNOPSIS
  Установка nauth_test (LearningSite + SSO без keytab) на удалённый ПК.

.EXAMPLE
  irm https://raw.githubusercontent.com/IVANIArgh/nauth_test/main/scripts/install-nauth_test.ps1 | iex

.EXAMPLE
  $env:NAUTH_REPO='https://github.com/IVANIArgh/nauth_test.git'
  $env:NAUTH_SSO_USER='Пользователь'
  .\scripts\install-nauth_test.ps1
#>
$ErrorActionPreference = 'Stop'

$RepoUrl = if ($env:NAUTH_REPO) { $env:NAUTH_REPO } else { 'https://github.com/IVANIArgh/nauth_test.git' }
$InstallDir = if ($env:NAUTH_INSTALL_DIR) { $env:NAUTH_INSTALL_DIR } else { Join-Path $env:USERPROFILE 'nauth_test' }
$SsoUser = if ($env:NAUTH_SSO_USER) { $env:NAUTH_SSO_USER } else { 'testadmin' }
$WebPort = if ($env:NAUTH_WEB_PORT) { $env:NAUTH_WEB_PORT } else { '8080' }

function Require-Command($name) {
    if (-not (Get-Command $name -ErrorAction SilentlyContinue)) {
        throw "Не найдена команда '$name'. Установите её и повторите."
    }
}

Require-Command git
Require-Command docker

Write-Host "nauth_test: клонирование в $InstallDir"
if (-not (Test-Path $InstallDir)) {
    git clone $RepoUrl $InstallDir
} else {
    Write-Host "Каталог уже есть — git pull"
    Set-Location $InstallDir
    git pull --ff-only
}
Set-Location $InstallDir

if (-not (Test-Path '.env')) {
    if (Test-Path 'docker.env.sso.example') {
        Copy-Item 'docker.env.sso.example' '.env'
    } elseif (Test-Path 'docker.env.example') {
        Copy-Item 'docker.env.example' '.env'
    }
}

function Set-EnvLine($key, $value) {
    $path = Join-Path (Get-Location) '.env'
    $lines = @()
    if (Test-Path $path) { $lines = Get-Content $path -Encoding UTF8 }
    $found = $false
    $out = foreach ($line in $lines) {
        if ($line -match "^\s*$([regex]::Escape($key))\s*=") {
            $found = $true
            "$key=$value"
        } else { $line }
    }
    if (-not $found) { $out += "$key=$value" }
    $out | Set-Content $path -Encoding UTF8
}

if (Test-Path '.env') {
    Set-EnvLine 'SSO_DEFAULT_USER' $SsoUser
    Set-EnvLine 'WEB_PORT' $WebPort
    Set-EnvLine 'TRUST_REMOTE_USER' 'true'
    Set-EnvLine 'DOCKER_AUTH_FALLBACK' 'false'
}

Write-Host "Docker: сборка и запуск SSO-стека..."
docker compose -f docker-compose.yml -f docker-compose.sso.yml up -d --build
if ($LASTEXITCODE -ne 0) { throw "docker compose завершился с кодом $LASTEXITCODE" }

Write-Host ""
Write-Host "Готово."
Write-Host "  SSO:  http://localhost:${WebPort}/user/info-test"
Write-Host "  Сайт: http://localhost:${WebPort}/"
Write-Host "  Логин (SSO_DEFAULT_USER): $SsoUser"
Write-Host "  Остановка: docker compose -f docker-compose.yml -f docker-compose.sso.yml down"
