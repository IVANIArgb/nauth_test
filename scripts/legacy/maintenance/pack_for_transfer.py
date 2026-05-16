#!/usr/bin/env python3
"""
Упаковка проекта в один ZIP-файл для передачи на другой ПК.
Исключает лишнее: кэш, venv, логи, большие бэкапы и т.д.
"""

import os
import zipfile
import sys
from pathlib import Path
from datetime import datetime

# Корень проекта = папка, где лежит этот скрипт
PROJECT_ROOT = Path(__file__).resolve().parent
OUTPUT_NAME = "LN_StabelVer.zip"

# Что не класть в архив
EXCLUDE_DIRS = {
    "__pycache__",
    ".git",
    "venv",
    ".venv",
    "env",
    "node_modules",
    ".idea",
    ".vscode",
    "dist",
    "build",
}
EXCLUDE_FILES = {
    ".env",
    ".env.local",
    ".env.*",
}
EXCLUDE_SUFFIXES = (
    ".pyc",
    ".pyo",
    ".pyd",
    ".log",
    ".rar",
    ".zip",
)
# Папки/файлы, которые полностью игнорируем (путь от корня)
EXCLUDE_PATHS = {
    "backend/logs",
    "backend/uploads",
    "docker image",
}
# Не включать файлы БД и бэкапы (на удалённом ПК БД создастся заново или скопируйте отдельно)
EXCLUDE_PATTERNS = (
)


def should_exclude(path: Path, is_dir: bool) -> bool:
    rel = path.relative_to(PROJECT_ROOT)
    parts = set(rel.parts)
    if is_dir and parts & EXCLUDE_DIRS:
        return True
    for ex in EXCLUDE_PATHS:
        if ex in rel.as_posix() or rel.as_posix().startswith(ex + "/"):
            return True
    if not is_dir:
        if rel.name in EXCLUDE_FILES:
            return True
        if rel.name.startswith(".env.") and rel.name != ".env.example":
            return True
        if rel.suffix in EXCLUDE_SUFFIXES:
            return True
        for pat in EXCLUDE_PATTERNS:
            if pat in rel.name:
                return True
    return False


def main():
    os.chdir(PROJECT_ROOT)
    zip_path = PROJECT_ROOT / OUTPUT_NAME
    # Удаляем старый архив, если есть
    if zip_path.exists():
        zip_path.unlink()
    print(f"Упаковка проекта в {zip_path.name} ...")
    count = 0
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk(PROJECT_ROOT):
            root_path = Path(root)
            if PROJECT_ROOT / ".git" in root_path.parents or root_path == PROJECT_ROOT / ".git":
                dirs.clear()
                continue
            # Не заходить в исключённые каталоги
            dirs[:] = [d for d in dirs if not should_exclude(root_path / d, True)]
            for f in files:
                full = root_path / f
                if should_exclude(full, False):
                    continue
                try:
                    arcname = full.relative_to(PROJECT_ROOT)
                    zf.write(full, arcname)
                    count += 1
                except Exception as e:
                    print(f"  пропуск {full}: {e}")
    print(f"Готово. Добавлено файлов: {count}. Архив: {zip_path.resolve()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
