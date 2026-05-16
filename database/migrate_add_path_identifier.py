"""
Миграция для добавления поля path_identifier в таблицы categories, courses и lessons.
"""

import os
import sys
from sqlalchemy import text, inspect
from sqlalchemy.exc import OperationalError

# Добавляем путь к корню проекта
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.models import db_manager


def column_exists(conn, table_name, column_name):
    """Проверить существование колонки в таблице."""
    inspector = inspect(db_manager.engine)
    columns = [col['name'] for col in inspector.get_columns(table_name)]
    return column_name in columns


def table_exists(conn, table_name):
    """Проверить существование таблицы."""
    inspector = inspect(db_manager.engine)
    return table_name in inspector.get_table_names()


def migrate_database():
    """Выполнить миграцию базы данных."""
    print("🔄 Начинаем миграцию базы данных для добавления path_identifier...")
    
    try:
        with db_manager.engine.begin() as conn:
            inspector = inspect(db_manager.engine)
            existing_tables = inspector.get_table_names()
            
            print(f"📋 Найдено таблиц: {len(existing_tables)}")
            
            # 1. Добавить path_identifier в categories
            print("\n📝 Шаг 1: Добавление path_identifier в таблицу categories...")
            if table_exists(conn, 'categories'):
                if not column_exists(conn, 'categories', 'path_identifier'):
                    print("   Добавляем колонку path_identifier...")
                    conn.execute(text("""
                        ALTER TABLE categories ADD COLUMN path_identifier VARCHAR(500)
                    """))
                    conn.execute(text("""
                        CREATE INDEX IF NOT EXISTS ix_categories_path_identifier ON categories(path_identifier)
                    """))
                    print("   ✅ Колонка path_identifier добавлена в categories")
                else:
                    print("   ℹ️  Колонка path_identifier уже существует в categories")
            else:
                print("   ⚠️  Таблица categories не найдена, пропускаем")
            
            # 2. Добавить path_identifier в courses
            print("\n📝 Шаг 2: Добавление path_identifier в таблицу courses...")
            if table_exists(conn, 'courses'):
                if not column_exists(conn, 'courses', 'path_identifier'):
                    print("   Добавляем колонку path_identifier...")
                    conn.execute(text("""
                        ALTER TABLE courses ADD COLUMN path_identifier VARCHAR(500)
                    """))
                    conn.execute(text("""
                        CREATE INDEX IF NOT EXISTS ix_courses_path_identifier ON courses(path_identifier)
                    """))
                    print("   ✅ Колонка path_identifier добавлена в courses")
                else:
                    print("   ℹ️  Колонка path_identifier уже существует в courses")
            else:
                print("   ⚠️  Таблица courses не найдена, пропускаем")
            
            # 3. Добавить path_identifier в lessons
            print("\n📝 Шаг 3: Добавление path_identifier в таблицу lessons...")
            if table_exists(conn, 'lessons'):
                if not column_exists(conn, 'lessons', 'path_identifier'):
                    print("   Добавляем колонку path_identifier...")
                    conn.execute(text("""
                        ALTER TABLE lessons ADD COLUMN path_identifier VARCHAR(500)
                    """))
                    conn.execute(text("""
                        CREATE INDEX IF NOT EXISTS ix_lessons_path_identifier ON lessons(path_identifier)
                    """))
                    print("   ✅ Колонка path_identifier добавлена в lessons")
                else:
                    print("   ℹ️  Колонка path_identifier уже существует в lessons")
            else:
                print("   ⚠️  Таблица lessons не найдена, пропускаем")
            
            print("\n✅ Миграция завершена успешно!")
            
    except Exception as e:
        print(f"\n❌ Ошибка при миграции: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    return True


if __name__ == '__main__':
    migrate_database()




