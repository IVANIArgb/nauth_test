# Выполните ОДИН РАЗ на этом ПК (после создания пустого repo nauth_test на GitHub).
Start-Process "https://github.com/new?name=nauth_test&description=SSO+without+keytab"
Write-Host "1) На открывшейся странице: Create repository (БЕЗ README/gitignore)"
Write-Host "2) Нажмите Enter здесь, когда репозиторий создан..."
Read-Host
Set-Location $PSScriptRoot
git remote set-url origin https://github.com/IVANIArgb/nauth_test.git
git push -u origin main
if ($LASTEXITCODE -eq 0) {
    Write-Host ""
    Write-Host "Готово. Команда для удалённого ПК — см. REMOTE-INSTALL.ps1 или:"
    Write-Host 'irm https://raw.githubusercontent.com/IVANIArgb/nauth_test/main/scripts/install-nauth_test.ps1 | iex'
}
