@echo off
REM =============================================================================
REM  Обновление с GitHub (ветка tests) + сборка и запуск Docker.
REM  Из корня проекта:  update.bat
REM
REM  Не использует "git checkout tests" — в проекте есть папка tests\.
REM =============================================================================
chcp 65001 >nul
setlocal EnableExtensions
cd /d "%~dp0"

echo [1/3] Git: fetch и переключение на origin/tests ...
git fetch origin tests
if errorlevel 1 goto :gitfail

git rev-parse --verify tests >nul 2>&1
if errorlevel 1 (
  git checkout -B tests origin/tests
) else (
  git checkout -B tests origin/tests
)
if errorlevel 1 goto :gitfail

git pull --ff-only origin tests
if errorlevel 1 goto :gitfail

echo [2/3] Git: OK, ветка tests
echo [3/3] Docker: сборка и запуск ...
call "%~dp0run-server.bat"
exit /b %ERRORLEVEL%

:gitfail
echo.
echo Ошибка Git. Попробуйте вручную:
echo   git fetch origin tests
echo   git checkout -B tests origin/tests
echo   git pull --ff-only origin tests
pause
exit /b 1
