@echo off
REM =============================================================================
REM  Сборка Docker-образа и запуск контейнеров (SSO без keytab).
REM  Из корня проекта:  run-server.bat
REM
REM  Нативный Python (без Docker):  set NAUTH_NATIVE=1  и снова run-server.bat
REM =============================================================================
chcp 65001 >nul
setlocal EnableExtensions
cd /d "%~dp0"

if /I "%NAUTH_NATIVE%"=="1" (
  if not exist ".venv\Scripts\activate.bat" (
    echo Сначала выполните setup-windows.bat
    pause
    exit /b 1
  )
  call ".venv\Scripts\activate.bat"
  python run.py
  pause
  exit /b %ERRORLEVEL%
)

set "PS1=%~dp0scripts\run-docker-stack.ps1"
if not exist "%PS1%" (
  echo Не найден: %PS1%
  pause
  exit /b 1
)

powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%PS1%"
set "ERR=%ERRORLEVEL%"
if not "%ERR%"=="0" (
  echo.
  echo Ошибка Docker: код %ERR%
  pause
  exit /b %ERR%
)
echo.
pause
exit /b 0
