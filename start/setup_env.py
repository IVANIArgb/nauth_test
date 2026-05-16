#!/usr/bin/env python
"""
CLI‑утилита для автоматической подготовки окружения проекта LearningSiteSV:
- создание виртуального окружения venv (если его ещё нет)
- установка/обновление pip
- установка зависимостей из requirements.txt
- создание базовых служебных директорий и минимального .env при необходимости.

Скрипт рассчитан на запуск из .bat/.sh‑обёрток или напрямую:
    python start/setup_env.py
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent
REQUIREMENTS = BASE_DIR / "requirements.txt"
VENV_DIR = BASE_DIR / "venv"
ENV_FILE = BASE_DIR / ".env"


def print_section(title: str) -> None:
    print("\n" + "=" * 60)
    print(title)
    print("=" * 60)


def run(cmd: list[str], cwd: Path | None = None) -> None:
    print(f"\n> {' '.join(cmd)}")
    subprocess.check_call(cmd, cwd=str(cwd) if cwd else None)


def ensure_venv() -> None:
    print_section("СОЗДАНИЕ ВИРТУАЛЬНОГО ОКРУЖЕНИЯ (venv)")
    if VENV_DIR.exists():
        print(f"Виртуальное окружение уже существует: {VENV_DIR}")
        return

    print(f"Создаю виртуальное окружение в: {VENV_DIR}")
    run([sys.executable, "-m", "venv", str(VENV_DIR)])
    print("venv успешно создан.")


def get_venv_python() -> Path:
    if os.name == "nt":
        candidate = VENV_DIR / "Scripts" / "python.exe"
    else:
        candidate = VENV_DIR / "bin" / "python"
    return candidate


def install_requirements() -> None:
    print_section("УСТАНОВКА ЗАВИСИМОСТЕЙ")

    if not REQUIREMENTS.exists():
        raise SystemExit(
            f"Файл зависимостей не найден: {REQUIREMENTS}\n"
            "Проверьте структуру проекта и наличие requirements.txt."
        )

    venv_python = get_venv_python()
    if not venv_python.exists():
        raise SystemExit(
            f"Не найден интерпретатор в venv: {venv_python}\n"
            "Проверьте, что виртуальное окружение успешно создано."
        )

    # Обновляем pip внутри venv и ставим зависимости.
    run([str(venv_python), "-m", "pip", "install", "--upgrade", "pip"])
    run([str(venv_python), "-m", "pip", "install", "-r", str(REQUIREMENTS)])

    print("Зависимости успешно установлены.")


def ensure_directories() -> None:
    print_section("СОЗДАНИЕ СЛУЖЕБНЫХ ДИРЕКТОРИЙ")
    for rel in ["backend/logs", "backend/uploads", "database/backups"]:
        path = BASE_DIR / rel
        if not path.exists():
            path.mkdir(parents=True, exist_ok=True)
            print(f"Создана директория: {path}")
        else:
            print(f"Директория уже существует: {path}")


def ensure_env_file() -> None:
    print_section("ПРОВЕРКА .env")

    if ENV_FILE.exists():
        print(f"Файл .env уже существует: {ENV_FILE}")
        return

    print(
        f"Файл .env не найден. Создаю минимальный шаблон по пути: {ENV_FILE}\n"
        "Обязательно отредактируйте его под свою среду (особенно SECRET_KEY и БД)."
    )

    content = """# Базовый .env, создан start/setup_env.py
FLASK_ENV=development
SECRET_KEY=change_me_please

# По умолчанию — SQLite в каталоге database
DATABASE_URL=sqlite:///database/users_courses.db

# Kerberos/SSO (по умолчанию выключен)
KERBEROS_AUTH_ENABLED=false

# Логирование
LOG_LEVEL=INFO
"""
    ENV_FILE.write_text(content, encoding="utf-8")
    print("Минимальный .env создан.")


def main() -> int:
    print_section("АВТОНАСТРОЙКА ОКРУЖЕНИЯ ДЛЯ LearningSiteSV")
    print(f"Корень проекта: {BASE_DIR}")

    try:
        ensure_venv()
        install_requirements()
        ensure_directories()
        ensure_env_file()
    except subprocess.CalledProcessError as exc:
        print(f"\nОШИБКА при выполнении команды: {exc}")
        return 1
    except SystemExit as exc:
        # Передаём читаемое сообщение наружу, но не стеками.
        if exc.code not in (0, None):
            print(exc)
        return int(exc.code) if isinstance(exc.code, int) else 1

    print("\n" + "=" * 60)
    print(
        "ОКРУЖЕНИЕ ПОДГОТОВЛЕНО.\n"
        "Для разработки на Windows вы можете запустить:\n"
        "  start\\run_dev.bat\n"
        "или вручную активировать venv и выполнить: python run.py"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

