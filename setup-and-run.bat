@echo off
REM =============================================================================
REM  Установка / обновление (ветка tests) + сборка и запуск Docker.
REM  Одна команда из корня проекта:  setup-and-run.bat
REM =============================================================================
chcp 65001 >nul
setlocal EnableExtensions
cd /d "%~dp0"

if not defined NAUTH_BRANCH set "NAUTH_BRANCH=tests"
if not defined NAUTH_USE_DOCKER set "NAUTH_USE_DOCKER=1"

powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\setup-project.ps1" -Docker %*
set "ERR=%ERRORLEVEL%"
if not "%ERR%"=="0" (
  echo Ошибка установки: %ERR%
  pause
  exit /b %ERR%
)

powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\run-docker-stack.ps1"
set "ERR=%ERRORLEVEL%"
if not "%ERR%"=="0" pause
exit /b %ERR%
