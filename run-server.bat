@echo off
REM Build and run LearningSite in Docker (SSO, no keytab).
REM From project root:  run-server.bat
REM Native Python:  set NAUTH_NATIVE=1  then run-server.bat
chcp 65001 >nul
setlocal EnableExtensions
cd /d "%~dp0"

if /I "%NAUTH_NATIVE%"=="1" (
  if not exist ".venv\Scripts\activate.bat" (
    echo Run setup-windows.bat first.
    pause
    exit /b 1
  )
  call ".venv\Scripts\activate.bat"
  python run.py
  pause
  exit /b %ERRORLEVEL%
)

where docker >nul 2>&1
if errorlevel 1 (
  echo Docker not found. Install Docker Desktop.
  pause
  exit /b 1
)

if not exist ".env" (
  if exist "docker.env.sso.example" copy /Y "docker.env.sso.example" ".env" >nul
  if not exist ".env" if exist "docker.env.example" copy /Y "docker.env.example" ".env" >nul
)

set "DC=-f docker-compose.yml"
if exist "docker-compose.sso.yml" set "DC=%DC% -f docker-compose.sso.yml"

echo.
echo [1/2] docker compose build ...
docker compose %DC% build
if errorlevel 1 goto :fail

echo [2/2] docker compose up -d ...
docker compose %DC% up -d
if errorlevel 1 goto :fail

echo.
echo OK. Open in browser:
if exist "docker-compose.sso.yml" (
  echo   http://localhost:8080/
  echo   http://localhost:8080/api/current-user
) else (
  echo   http://localhost:8000/
)
echo.
echo Logs:    docker compose %DC% logs -f web
echo Stop:    docker compose %DC% down
echo.
pause
exit /b 0

:fail
echo.
echo Docker failed. Check: docker version
pause
exit /b 1
