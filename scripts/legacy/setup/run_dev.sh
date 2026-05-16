#!/usr/bin/env bash
set -e
cd "$(dirname "$0")"

if [ ! -d "venv" ]; then
    echo "Создаю виртуальное окружение..."
    python3 -m venv venv
fi
source venv/bin/activate

pip install -q -r requirements.txt
mkdir -p backend/logs backend/uploads
[ -f .env ] || { echo "Создаю .env из .env.example..."; cp .env.example .env; }

echo "Запуск приложения на http://127.0.0.1:5000"
exec python run.py
