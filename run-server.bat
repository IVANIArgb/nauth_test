@echo off
REM Auto AD profile (no manual DB). Domain PC: native Flask+Get-ADUser by default.
REM Docker: set NAUTH_FORCE_DOCKER=1  (reads AD from host cache + optional LDAP).
chcp 65001 >nul
setlocal EnableExtensions
cd /d "%~dp0"

REM --- Native Windows (best: full AD automatic, no .env login) ---
if /I not "%NAUTH_FORCE_DOCKER%"=="1" (
  if not "%USERDNSDOMAIN%"=="" (
    if exist ".venv\Scripts\activate.bat" (
      echo [mode] Domain PC - native Python + Active Directory
      call ".venv\Scripts\activate.bat"
      python run.py
      pause
      exit /b %ERRORLEVEL%
    )
  )
)

where docker >nul 2>&1
if errorlevel 1 (
  echo Docker not found. Install Docker Desktop or run setup-windows.bat
  pause
  exit /b 1
)

echo [mode] Docker SSO + AD from Windows host

if not exist "runtime\ad-cache" mkdir "runtime\ad-cache"

powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "scripts\sync-docker-env-from-windows.ps1"
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "scripts\refresh-ad-profile-cache.ps1" -Login "%USERNAME%"
if errorlevel 1 (
  if not "%USERDNSDOMAIN%"=="" (
    echo ERROR: AD profile cache failed. Run on domain PC as %USERNAME%.
    pause
    exit /b 1
  )
  echo WARNING: AD cache skipped - not domain PC.
)

set "DC=-f docker-compose.yml"
if exist "docker-compose.sso.yml" set "DC=%DC% -f docker-compose.sso.yml"

echo.
echo [1/2] docker compose build ...
docker compose %DC% build
if errorlevel 1 goto :fail

echo [2/2] docker compose down + up -d ...
docker compose %DC% down
docker compose %DC% up -d
if errorlevel 1 goto :fail

echo.
echo OK. User: %USERNAME%
if exist "docker-compose.sso.yml" (
  echo   http://localhost:8080/
  echo   http://localhost:8080/api/current-user
) else (
  echo   http://localhost:8000/
)
echo.
pause
exit /b 0

:fail
echo Docker failed. Is Docker Desktop running?
pause
exit /b 1
