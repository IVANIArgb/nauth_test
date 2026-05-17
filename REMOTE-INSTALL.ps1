# ========== УДАЛЁННЫЙ ПК: скопируйте в PowerShell (по порядку) ==========
# Нужны: Git + Docker Desktop (docker version в консоли должен работать).

# 1) Ваш логин для SSO (латиница или кириллица):
$env:NAUTH_SSO_USER = 'ManakovIV'

# 2) Установка (одна строка, БЕЗ вложенного powershell -Command):
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
irm https://raw.githubusercontent.com/IVANIArgb/nauth_test/main/scripts/install-nauth_test.ps1 | iex

# Проверка: http://localhost:8080/user/info-test
