@echo off
REM All-in-one: git pull, venv, .env (LDAP from domain), Docker hosting build+up.
chcp 65001 >nul
setlocal EnableExtensions
cd /d "%~dp0"

echo [1/7] git fetch + pull (tests)...
git fetch origin tests
if errorlevel 1 goto :gitfail
git checkout -B tests origin/tests
if errorlevel 1 goto :gitfail
git pull --ff-only origin tests
if errorlevel 1 goto :gitfail

echo [2/7] Python venv...
if not exist ".venv\Scripts\python.exe" (
  python -m venv .venv
  if errorlevel 1 (
    echo ERROR: python -m venv failed
    pause
    exit /b 1
  )
)
call ".venv\Scripts\activate.bat"
python -m pip install -q --upgrade pip
if exist "requirements-prod.txt" (
  pip install -q -r requirements-prod.txt
) else (
  pip install -q -r requirements.txt
)
if errorlevel 1 goto :fail

echo [3/7] sync .env (domain, SECRET_KEY, LDAP template)...
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "scripts\prepare-hosting-env.ps1"
if errorlevel 1 goto :fail

where docker >nul 2>&1
if errorlevel 1 (
  echo ERROR: Docker not found. Start Docker Desktop.
  pause
  exit /b 1
)

set "DC=-f docker-compose.yml -f docker-compose.hosting.yml"

echo [4/7] docker compose build...
docker compose %DC% build
if errorlevel 1 goto :fail

echo [5/7] docker compose down...
docker compose %DC% down

echo [6/7] docker compose up -d...
docker compose %DC% up -d
if errorlevel 1 goto :fail

echo [7/7] health check...
timeout /t 10 /nobreak >nul
docker compose %DC% ps | findstr /i "unhealthy exit"
if not errorlevel 1 (
  echo WARNING: unhealthy - run diagnose-hosting.bat
  call "%~dp0diagnose-hosting.bat"
  exit /b 1
)

echo.
echo OK
for /f "usebackq tokens=1,* delims==" %%a in (`findstr /b /i "WEB_PORT=" .env 2^>nul`) do set "SITE_PORT=%%b"
if not defined SITE_PORT set "SITE_PORT=8080"
echo   Docker: http://localhost:%SITE_PORT%/
echo   Native: .venv + python run.py  (port 8000, AD without LDAP bind)
docker compose %DC% ps
pause
exit /b 0

:gitfail
echo Git failed.
pause
exit /b 1

:fail
echo Failed. Run diagnose-hosting.bat  (often: LDAP_PASSWORD or Docker not running)
pause
exit /b 1
