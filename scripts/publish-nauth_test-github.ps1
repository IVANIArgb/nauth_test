# Публикация локального репозитория на GitHub (один раз).
# 1) Создайте пустой репозиторий: https://github.com/new  имя: nauth_test
# 2) Запустите этот скрипт с вашим логином GitHub.

param(
    [string]$GithubUser = "IVANIArgh",
    [string]$RepoName = "nauth_test"
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

if (-not (Test-Path ".git")) {
    throw "Нет .git в $Root — сначала выполните git init и commit."
}

$remote = "https://github.com/${GithubUser}/${RepoName}.git"
git remote remove origin 2>$null
git remote add origin $remote

Write-Host "Пуш в $remote ..."
git push -u origin main
if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Host "Если 'Repository not found':"
    Write-Host "  1. Создайте репозиторий $RepoName на https://github.com/new (без README)"
    Write-Host "  2. Повторите: .\scripts\publish-nauth_test-github.ps1 -GithubUser ВАШ_ЛОГИН"
    exit 1
}

Write-Host ""
Write-Host "Готово. Установка на другом ПК:"
Write-Host "  irm https://raw.githubusercontent.com/${GithubUser}/${RepoName}/main/scripts/install-nauth_test.ps1 | iex"
Write-Host "  (или: git clone $remote)"
