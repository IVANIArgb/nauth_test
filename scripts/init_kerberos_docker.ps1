# Подготовка файлов Kerberos для docker-compose.kerberos.yml (Windows).
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $root

$krb = Join-Path $root "kerberos\krb5.conf"
$ex = Join-Path $root "kerberos\krb5.conf.example"
if (-not (Test-Path $krb)) {
    Copy-Item $ex $krb
    Write-Host "Создан kerberos\krb5.conf из примера — отредактируйте realm и KDC."
}

$kt = Join-Path $root "kerberos\http.keytab"
if (-not (Test-Path $kt)) {
    New-Item -ItemType File -Path $kt -Force | Out-Null
    Write-Host "Создан пустой kerberos\http.keytab — замените на реальный keytab от AD (HTTP/<hostname>@REALM)."
}

Write-Host "Готово. Заполните .env (см. kerberos\env.kerberos.example), затем:"
Write-Host "  docker compose -f docker-compose.yml -f docker-compose.kerberos.yml --env-file .env up -d --build"
