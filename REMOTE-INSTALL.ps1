# Скопируйте и выполните на УДАЛЁННОМ ПК (PowerShell от администратора не обязателен).
# Нужны: Git, Docker Desktop.

# Логин SSO (латиница или кириллица) — измените при необходимости:
$env:NAUTH_SSO_USER = 'testadmin'

# Установка:
powershell -NoProfile -ExecutionPolicy Bypass -Command "[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; iex ((New-Object Net.WebClient).DownloadString('https://raw.githubusercontent.com/IVANIArgb/nauth_test/main/scripts/install-nauth_test.ps1'))"
