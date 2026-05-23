@echo off
chcp 65001 >nul
cd /d "%~dp0"
set "DC=-f docker-compose.yml -f docker-compose.hosting.yml"
echo === docker compose ps ===
docker compose %DC% ps
echo.
echo === learnsite-web logs (last 60 lines) ===
docker compose %DC% logs web --tail 60
echo.
pause
