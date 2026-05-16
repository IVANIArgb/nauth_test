#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

echo "============================================================"
echo " Запуск dev‑сервера LearningSiteSV (Unix‑подобные ОС)"
echo " Корень проекта: ${PROJECT_ROOT}"
echo "============================================================"

if [ ! -d "${PROJECT_ROOT}/venv" ]; then
  echo "Виртуальное окружение venv не найдено. Запускаю автонастройку..."
  "${SCRIPT_DIR}/setup_env.sh"
fi

VENV_PY="${PROJECT_ROOT}/venv/bin/python"
if [ -x "${VENV_PY}" ]; then
  PY_DEV="${VENV_PY}"
else
  PY_DEV="${PY_BIN:-python3}"
fi

echo "Используется интерпретатор: ${PY_DEV}"
echo "Запуск: python run.py"
echo
cd "${PROJECT_ROOT}"
"${PY_DEV}" run.py
