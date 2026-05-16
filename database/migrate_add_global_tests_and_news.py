"""
Миграция: добавление таблиц global_tests / global_test_questions / global_test_results / news_events.
"""

import os
import sys
from sqlalchemy import inspect

project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
sys.path.insert(0, project_root)

from database.models import db_manager, GlobalTest, GlobalTestQuestion, GlobalTestResult, NewsEvent  # noqa: E402


def migrate_database():
    print("🔄 Миграция: добавление global_tests и news_events...")
    engine = db_manager.engine
    inspector = inspect(engine)

    with engine.begin() as conn:
        for model in (GlobalTest, GlobalTestQuestion, GlobalTestResult, NewsEvent):
            table_name = model.__tablename__
            print(f"📝 Проверяем таблицу '{table_name}'...")
            if not inspector.has_table(table_name):
                model.__table__.create(conn)
                print(f"  ✅ Таблица '{table_name}' создана.")
            else:
                print(f"  ℹ️  Таблица '{table_name}' уже существует.")

    print("✅ Миграция завершена успешно!")


if __name__ == "__main__":
    migrate_database()

