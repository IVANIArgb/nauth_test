#!/usr/bin/env python3
"""
Одноразовый/периодический скрипт для синхронизации файловой структуры
контента (categories-data) с текущей базой данных.

Запускать из корня проекта:

    python scripts/sync_content_fs_from_db.py

Результат:
    - создаются/обновляются папки категорий/курсов/уроков в CONTENT_ROOT_DIR
      (или в ./categories-data, если переменная не задана);
    - для каждой сущности пишутся config.json;
    - для всех текстовых/заголовочных блоков формируются .txt-файлы.
"""

import os
import sys

# Добавляем корень проекта в sys.path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from database.models import db_manager  # type: ignore
from backend.utils.categories_data_sync import sync_all_categories_from_db  # type: ignore


def main() -> None:
    session = db_manager.get_session()
    try:
        sync_all_categories_from_db(session)
    finally:
        session.close()


if __name__ == "__main__":
    main()

