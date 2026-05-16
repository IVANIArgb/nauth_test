#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

echo "============================================================"
echo " Автонастройка окружения для LearningSiteSV (Unix‑подобные ОС)"
echo " Корень проекта: ${PROJECT_ROOT}"
echo "============================================================"

PY_BIN="${PY_BIN:-python3}"

if ! command -v "${PY_BIN}" >/dev/null 2>&1; then
  echo "ОШИБКА: не найден интерпретатор Python3 (команда ${PY_BIN})."
  echo "Установите Python 3.10+ и повторите запуск."
  exit 1
fi

echo "Запуск проверки окружения..."
"${SCRIPT_DIR}/check_env.sh"

echo
echo "Запуск Python‑скрипта автонастройки..."
"${PY_BIN}" "${SCRIPT_DIR}/setup_env.py"
