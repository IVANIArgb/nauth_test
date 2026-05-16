#!/usr/bin/env python
"""
CLI‑утилита для проверки совместимости окружения:
- ОС (фокус на Windows 10/11)
- версии Python
- наличия pip
- базовой установки ключевых библиотек из requirements.txt.

Выходной код:
 0 — всё ОК / можно продолжать установку
 1 — найдены критичные проблемы
"""

from __future__ import annotations

import sys
import platform
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent
REQUIREMENTS = BASE_DIR / "requirements.txt"


def print_section(title: str) -> None:
    print("\n" + "=" * 60)
    print(title)
    print("=" * 60)


def check_os() -> bool:
    print_section("ПРОВЕРКА ОПЕРАЦИОННОЙ СИСТЕМЫ")
    system = platform.system()
    release = platform.release()
    version = platform.version()

    print(f"Обнаружена ОС: {system} {release} (build: {version})")

    if system != "Windows":
        print(
            "ВНИМАНИЕ: автоматические .bat‑скрипты рассчитаны на Windows 10/11.\n"
            "Проект, скорее всего, запустится и на других ОС, "
            "но настройку окружения придётся делать вручную или через .sh‑скрипты."
        )
        return False

    # На Windows 10 и 11 номер версии — 10.0.x, различается только сборка.
    # Для наших целей считаем, что 10.0.x — совместимо.
    try:
        major_version_str = version.split(".")[0]
        major_version = int(major_version_str)
    except Exception:
        major_version = 10

    if major_version < 10:
        print(
            "ОШИБКА: обнаружена Windows версии ниже 10.\n"
            "Автонастройка поддерживается только на Windows 10 и 11."
        )
        return False

    print("ОС совместима: Windows 10/11 или новее на базе ядра 10.0.x.")
    return True


def check_python() -> bool:
    print_section("ПРОВЕРКА PYTHON")
    vi = sys.version_info
    version_str = f"{vi.major}.{vi.minor}.{vi.micro}"
    print(f"Обнаружен Python: {version_str}")

    # Ориентируемся на тот же диапазон, что используется в Docker‑образе (3.12),
    # но допускаем и 3.10+.
    if vi.major != 3 or vi.minor < 10:
        print(
            "ОШИБКА: требуется Python версии 3.10 или новее.\n"
            "Установите актуальную версию Python 3.10+ и повторите запуск."
        )
        return False

    try:
        import pip  # noqa: F401  # type: ignore
    except Exception:
        print(
            "ОШИБКА: модуль pip не найден.\n"
            "Установите/включите pip для текущей установки Python "
            "(при установке Python отметьте 'Add pip' / 'Add Python to PATH')."
        )
        return False

    print("Python и pip выглядят корректно установленными.")
    return True


def check_requirements() -> bool:
    print_section("ПРОВЕРКА ФАЙЛА ЗАВИСИМОСТЕЙ")

    if not REQUIREMENTS.exists():
        print(
            f"ОШИБКА: не найден файл зависимостей: {REQUIREMENTS}\n"
            "Без него автоматическая установка библиотек невозможна."
        )
        return False

    print(f"Найден файл зависимостей: {REQUIREMENTS}")

    # Лёгкая проверка наличия базовых пакетов (если уже установлены)
    missing_core: list[str] = []
    for pkg, import_name in [
        ("Flask", "flask"),
        ("SQLAlchemy", "sqlalchemy"),
    ]:
        try:
            __import__(import_name)
        except Exception:
            missing_core.append(pkg)

    if missing_core:
        print(
            "Базовые библиотеки пока не установлены или недоступны в текущем Python:\n"
            f"  - {', '.join(missing_core)}\n"
            "Это не ошибка для первого запуска setup‑скрипта, "
            "но после установки зависимости должны появиться."
        )
    else:
        print("Ключевые библиотеки Flask/SQLAlchemy уже доступны в текущем окружении.")

    return True


def main() -> int:
    print_section("ПРОВЕРКА ОКРУЖЕНИЯ ДЛЯ LearningSiteSV")
    print(f"Корень проекта: {BASE_DIR}")

    ok_os = check_os()
    ok_py = check_python()
    ok_req = check_requirements()

    all_ok = ok_os and ok_py and ok_req

    print("\n" + "=" * 60)
    if all_ok:
        print("РЕЗУЛЬТАТ: окружение выглядит совместимым. Можно запускать автонастройку.")
        return 0

    print(
        "РЕЗУЛЬТАТ: обнаружены проблемы с окружением.\n"
        "Исправьте замечания выше и запустите проверку ещё раз."
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

