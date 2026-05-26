# Скрипты развёртывания (без Docker)

| Файл | Назначение |
|------|------------|
| `setup-ubuntu.sh` | Первая установка на Ubuntu (apt, git, venv, `.env`) |
| `run-server.sh` | Запуск приложения |
| `update.sh` | `git pull` + pip + синхронизация `.env` |
| `update.bat` | То же на Windows |

Из корня репозитория: `update.bat` вызывает `scripts\deploy\update.bat`.

Авто `.env`: `TEST_MODE=true`, `TEST_MODE_AUTH_BYPASS=false` (функции тест-режима без подмены логина).
