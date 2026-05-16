"""
Миграция: добавление колонки settings в global_tests.
"""

import os
import sys
from sqlalchemy import inspect, text

project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
sys.path.insert(0, project_root)

from database.models import db_manager  # noqa: E402


def column_exists(conn, table_name, column_name):
    inspector = inspect(db_manager.engine)
    cols = [c["name"] for c in inspector.get_columns(table_name)]
    return column_name in cols


def migrate_database():
    print("Migration: adding settings to global_tests...")
    try:
        with db_manager.engine.begin() as conn:
            if not column_exists(conn, "global_tests", "settings"):
                conn.execute(text("ALTER TABLE global_tests ADD COLUMN settings TEXT"))
                print("  Column settings added.")
            else:
                print("  Column settings already exists.")
        print("Migration done.")
        return True
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    migrate_database()
