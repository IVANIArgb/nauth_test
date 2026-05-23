@echo off
REM Полное обновление + сборка + запуск продакшен Docker (hosting, без keytab).
chcp 65001 >nul
setlocal EnableExtensions
cd /d "%~dp0"

echo [1/5] git fetch + pull (branch tests)...
git fetch origin tests
if errorlevel 1 goto :gitfail
git checkout -B tests origin/tests
if errorlevel 1 goto :gitfail
git pull --ff-only origin tests
if errorlevel 1 goto :gitfail

if not exist ".env" (
  echo [2/5] .env not found - copy docker.env.hosting.example
  copy /Y "docker.env.hosting.example" ".env"
  echo       Edit .env: LDAP_*, SECRET_KEY, TRUSTED_PROXY_IPS
) else (
  echo [2/5] .env OK
)

where docker >nul 2>&1
if errorlevel 1 (
  echo ERROR: Docker not found. Start Docker Desktop.
  pause
  exit /b 1
)

set "DC=-f docker-compose.yml -f docker-compose.hosting.yml"

echo [3/5] docker compose build...
docker compose %DC% build
if errorlevel 1 goto :fail

echo [4/5] docker compose down...
docker compose %DC% down

echo [5/5] docker compose up -d...
docker compose %DC% up -d
if errorlevel 1 goto :fail

echo.
echo OK — production hosting stack
echo   http://localhost:8080/
echo   http://localhost:8080/user/info-test
docker compose %DC% ps
echo.
pause
exit /b 0

:gitfail
echo Git failed.
pause
exit /b 1

:fail
echo Docker failed. Is Docker Desktop running?
pause
exit /b 1
