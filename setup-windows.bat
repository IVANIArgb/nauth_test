@echo off
REM =============================================================================
REM  Установка / обновление LearningSite (nauth_test) под Windows.
REM  - Если каталог уже репозиторий: git pull, venv, pip, .env.
REM  - Если каталога нет: git clone с веткой, затем то же самое.
REM
REM  Запуск из корня репозитория (двойной щелчок по bat):
REM    setup-windows.bat
REM
REM  Клон в другой каталог + ветка:
REM    setup-windows.bat D:\Apps\LearnSite main
REM
REM  Переменные (перед вызовом в cmd: set NAUTH_BRANCH=develop):
REM    NAUTH_REPO           URL (по умолчанию https://github.com/IVANIArgb/nauth_test.git)
REM    NAUTH_BRANCH         ветка (по умолчанию tests)
REM    NAUTH_INSTALL_DIR    каталог (если не задан — папка, где лежит этот bat)
REM    SETUP_USE_PROD_DEPS  1 — requirements-prod.txt
REM    NAUTH_USE_DOCKER     1 — после настройки поднять Docker Compose
REM =============================================================================
chcp 65001 >nul
setlocal EnableExtensions
cd /d "%~dp0"

if not defined NAUTH_BRANCH set "NAUTH_BRANCH=tests"

set "PS1=%~dp0scripts\setup-project.ps1"
if not exist "%PS1%" (
  echo Не найден: %PS1%
  exit /b 1
)

powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%PS1%" %*
set "ERR=%ERRORLEVEL%"
if not "%ERR%"=="0" (
  echo.
  echo Ошибка: код %ERR%
  pause
  exit /b %ERR%
)
echo.
pause
exit /b 0
