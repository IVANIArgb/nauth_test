@echo off
REM Обновление из git + pip + запуск (без Docker).
chcp 65001 >nul
setlocal EnableExtensions
cd /d "%~dp0..\.."

if not defined LSITE_BRANCH (
  if defined NAUTH_BRANCH (set "LSITE_BRANCH=%NAUTH_BRANCH%") else (set "LSITE_BRANCH=main")
)

git fetch origin %LSITE_BRANCH% || goto :gitfail
git checkout -B %LSITE_BRANCH% origin/%LSITE_BRANCH% || goto :gitfail
git pull --ff-only origin %LSITE_BRANCH% || goto :gitfail

if not exist "venv\Scripts\python.exe" python -m venv venv
set "PY=venv\Scripts\python.exe"
"%PY%" -m pip install -q --upgrade pip
if exist requirements-prod.txt ("%PY%" -m pip install -q -r requirements-prod.txt) else ("%PY%" -m pip install -q -r requirements.txt)
"%PY%" start\setup_env.py --sync-auto --skip-venv

echo.
echo Запуск сервера...
"%PY%" run.py
exit /b %ERRORLEVEL%

:gitfail
echo Git failed.
pause
exit /b 1
