"""
Миграция: добавление lesson_status (0=незаходил, 1=недопрошел, 2=прошел) в user_lesson_progress.
"""

import os
import sys
from sqlalchemy import text, inspect

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.models import db_manager


def column_exists(conn, table_name, column_name):
    inspector = inspect(db_manager.engine)
    columns = [col['name'] for col in inspector.get_columns(table_name)]
    return column_name in columns


def migrate_database():
    print("🔄 Миграция: добавление lesson_status в user_lesson_progress...")
    try:
        with db_manager.engine.begin() as conn:
            if not column_exists(conn, 'user_lesson_progress', 'lesson_status'):
                conn.execute(text("""
                    ALTER TABLE user_lesson_progress ADD COLUMN lesson_status INTEGER DEFAULT 1
                """))
                conn.execute(text("""
                    UPDATE user_lesson_progress SET lesson_status = 2 WHERE is_completed = 1
                """))
                conn.execute(text("""
                    UPDATE user_lesson_progress SET lesson_status = 1 WHERE is_completed = 0 OR lesson_status IS NULL
                """))
                print("   ✅ Колонка lesson_status добавлена и данные перенесены")
            else:
                print("   ℹ️  Колонка lesson_status уже существует")
        print("✅ Миграция завершена")
        return True
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == '__main__':
    migrate_database()
