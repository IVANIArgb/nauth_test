@echo off
REM Update from GitHub (branch tests) + Docker build/up. From project root: update.bat
chcp 65001 >nul
setlocal EnableExtensions
cd /d "%~dp0"

echo [1/3] git fetch ...
git fetch origin tests
if errorlevel 1 goto :gitfail

echo [2/3] git checkout tests (from origin/tests) ...
git checkout -B tests origin/tests
if errorlevel 1 goto :gitfail

echo [3/3] git pull ...
git pull --ff-only origin tests
if errorlevel 1 goto :gitfail

echo.
echo Git OK. Starting Docker ...
call "%~dp0run-server.bat"
exit /b %ERRORLEVEL%

:gitfail
echo.
echo Git failed. Try:
echo   git fetch origin tests
echo   git checkout -B tests origin/tests
echo   git pull --ff-only origin tests
pause
exit /b 1
