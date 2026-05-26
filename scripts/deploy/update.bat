@echo off
REM Обновление из git + pip + запуск (без Docker).
chcp 65001 >nul
setlocal EnableExtensions
cd /d "%~dp0..\.."
if not defined NAUTH_BRANCH set "NAUTH_BRANCH=tests"

git fetch origin %NAUTH_BRANCH% || goto :gitfail
git checkout -B %NAUTH_BRANCH% origin/%NAUTH_BRANCH% || goto :gitfail
git pull --ff-only origin %NAUTH_BRANCH% || goto :gitfail

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
