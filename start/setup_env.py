#!/usr/bin/env python
"""
Подготовка окружения LearningSiteSV: venv, pip, каталоги, .env.

  python start/setup_env.py           # venv + deps + .env (если нет)
  python start/setup_env.py --sync-auto  # дописать в .env ключи автонастройки (без перезаписи существующих)
"""

from __future__ import annotations

import argparse
import os
import secrets
import subprocess
import sys
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent
REQUIREMENTS = BASE_DIR / "requirements.txt"
REQ_PROD = BASE_DIR / "requirements-prod.txt"
VENV_DIR = BASE_DIR / "venv"
ENV_FILE = BASE_DIR / ".env"

# TEST_MODE=true: админ-права в API/UI, seed БД, терминал.
# TEST_MODE_AUTH_BYPASS=false: реальная Kerberos/Windows/LDAP-аутентификация (без подмены логина).
AUTO_ENV_DEFAULTS: dict[str, str] = {
    "FLASK_ENV": "development",
    "DEBUG": "true",
    "LOG_LEVEL": "INFO",
    "SECRET_KEY": "",  # подставляется при создании
    "INSECURE_DEV_SECRET": "true",
    "HOST": "0.0.0.0",
    "PORT": "8000",
    "RUN_WITH_GUNICORN": "true",
    "GUNICORN_WORKERS": "2",
    "GUNICORN_TIMEOUT": "120",
    "TEST_MODE": "true",
    "TEST_MODE_AUTH_BYPASS": "false",
    "TEST_MODE_DEFAULT_USER": "testadmin",
    "TEST_MODE_DEFAULT_FULL_NAME": "Тестовый Админ",
    "ROOT_TEST_AUTH_ENABLED": "false",
    "DOCKER_AUTH_FALLBACK": "false",
    "KERBEROS_AUTH_ENABLED": "true",
    "KERBEROS_GSSAPI_ENABLED": "false",
    "TRUST_REMOTE_USER": "false",
    "DB_SEED_ON_START": "true",
    "DB_RECREATE_ON_START": "false",
    "DATABASE_INIT_SAMPLE_DATA": "false",
    "TERMINAL_ROLE_COMMANDS_ENABLED": "true",
    "ALLOW_TERMINAL_IN_PROD": "false",
    "CONTENT_ROOT_DIR": "",
    "MAX_CONTENT_LENGTH": "104857600",
    "SESSION_COOKIE_SECURE": "false",
    "SECURITY_HEADERS_ENABLED": "true",
    "CSP_REPORT_ONLY": "true",
}


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


def get_venv_python() -> Path:
    if os.name == "nt":
        return VENV_DIR / "Scripts" / "python.exe"
    return VENV_DIR / "bin" / "python"


def install_requirements() -> None:
    print_section("УСТАНОВКА ЗАВИСИМОСТЕЙ")
    req = REQ_PROD if REQ_PROD.exists() else REQUIREMENTS
    if not req.exists():
        raise SystemExit(f"Не найден файл зависимостей: {req}")

    venv_python = get_venv_python()
    if not venv_python.exists():
        raise SystemExit(f"Не найден интерпретатор в venv: {venv_python}")

    run([str(venv_python), "-m", "pip", "install", "--upgrade", "pip", "wheel"])
    run([str(venv_python), "-m", "pip", "install", "-r", str(req)])


def ensure_directories() -> None:
    print_section("СОЗДАНИЕ СЛУЖЕБНЫХ ДИРЕКТОРИЙ")
    for rel in ["backend/logs", "backend/uploads", "database/backups", "categories-data"]:
        path = BASE_DIR / rel
        path.mkdir(parents=True, exist_ok=True)
        print(f"  {path}")


def _parse_env_lines(text: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for line in text.splitlines():
        s = line.strip()
        if not s or s.startswith("#") or "=" not in s:
            continue
        k, _, v = s.partition("=")
        out[k.strip()] = v.strip()
    return out


def _format_env_file(values: dict[str, str]) -> str:
    lines = [
        "# Автонастройка LearningSiteSV (start/setup_env.py)",
        "# TEST_MODE=true — функции демо/разработки (роли admin, seed БД, терминал).",
        "# TEST_MODE_AUTH_BYPASS=false — без подмены логина; нужен Kerberos/Windows/прокси.",
        "",
    ]
    for key, val in values.items():
        lines.append(f"{key}={val}")
    lines.append("")
    return "\n".join(lines)


def build_auto_env_values(existing: dict[str, str] | None = None) -> dict[str, str]:
    existing = existing or {}
    values = dict(AUTO_ENV_DEFAULTS)
    sk = (existing.get("SECRET_KEY") or "").strip()
    if not sk or sk in ("change_me_please", "замените-на-длинную-случайную-строку"):
        values["SECRET_KEY"] = secrets.token_hex(32)
    else:
        values["SECRET_KEY"] = sk
    return values


def ensure_env_file() -> None:
    print_section("ПРОВЕРКА .env")
    if ENV_FILE.exists():
        print(f"Файл .env уже существует: {ENV_FILE}")
        return
    existing: dict[str, str] = {}
    content = _format_env_file(build_auto_env_values(existing))
    ENV_FILE.write_text(content, encoding="utf-8")
    print("Создан .env с TEST_MODE=true и реальной аутентификацией (TEST_MODE_AUTH_BYPASS=false).")


def sync_auto_env_keys() -> None:
    print_section("СИНХРОНИЗАЦИЯ КЛЮЧЕЙ .env (автонастройка)")
    existing: dict[str, str] = {}
    if ENV_FILE.exists():
        existing = _parse_env_lines(ENV_FILE.read_text(encoding="utf-8"))
    merged = dict(existing)
    defaults = build_auto_env_values(existing)
    added = []
    for key, val in defaults.items():
        if key not in merged or not str(merged.get(key, "")).strip():
            merged[key] = val
            added.append(key)
    ENV_FILE.write_text(_format_env_file(merged), encoding="utf-8")
    if added:
        print("Добавлены ключи:", ", ".join(added))
    else:
        print("Все ключи автонастройки уже заданы.")


def main() -> int:
    parser = argparse.ArgumentParser(description="Настройка окружения LearningSiteSV")
    parser.add_argument(
        "--sync-auto",
        action="store_true",
        help="Дописать в .env ключи автонастройки (не перезаписывает существующие значения)",
    )
    parser.add_argument("--skip-venv", action="store_true", help="Не создавать venv и не ставить pip")
    args = parser.parse_args()

    print_section("АВТОНАСТРОЙКА ОКРУЖЕНИЯ")
    print(f"Корень проекта: {BASE_DIR}")

    try:
        if not args.skip_venv:
            ensure_venv()
            install_requirements()
        ensure_directories()
        if args.sync_auto:
            sync_auto_env_keys()
        else:
            ensure_env_file()
    except subprocess.CalledProcessError as exc:
        print(f"\nОШИБКА при выполнении команды: {exc}")
        return 1
    except SystemExit as exc:
        if exc.code not in (0, None):
            print(exc)
        return int(exc.code) if isinstance(exc.code, int) else 1

    print("\n" + "=" * 60)
    print(
        "ОКРУЖЕНИЕ ПОДГОТОВЛЕНО.\n"
        "Запуск: scripts/deploy/run-server.sh (Linux) или python run.py\n"
        "Обновление: scripts/deploy/update.sh | update.bat"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
