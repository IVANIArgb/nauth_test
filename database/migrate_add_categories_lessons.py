#!/usr/bin/env python3
"""
Миграция базы данных: добавление категорий, обновление курсов и уроков.
Безопасно добавляет новые таблицы и поля без удаления существующих данных.
"""

import os
import sys
import shutil
from datetime import datetime

# Добавляем корневую директорию проекта в путь
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
sys.path.insert(0, project_root)

from sqlalchemy import inspect, text
from database.models import db_manager, Base, Category, LessonContentBlock


def backup_database():
    """Создает резервную копию существующей БД"""
    db_path = os.path.join(os.path.dirname(__file__), 'users_courses.db')
    if os.path.exists(db_path):
        backup_path = f"{db_path}.backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        shutil.copy2(db_path, backup_path)
        print(f"✅ Резервная копия создана: {backup_path}")
        return backup_path
    return None


def table_exists(conn, table_name):
    """Проверить существование таблицы"""
    result = conn.execute(text(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=:name"
    ), {"name": table_name})
    return result.fetchone() is not None


def column_exists(conn, table_name, column_name):
    """Проверить существование колонки"""
    result = conn.execute(text(f"PRAGMA table_info({table_name})"))
    columns = result.fetchall()
    return any(col[1] == column_name for col in columns)


def migrate_database():
    """Выполнить миграцию базы данных"""
    print("🔄 Начинаем миграцию базы данных...")
    
    # Создаем резервную копию
    backup_path = backup_database()
    
    try:
        with db_manager.engine.begin() as conn:
            inspector = inspect(db_manager.engine)
            existing_tables = inspector.get_table_names()
            
            print(f"📋 Найдено таблиц: {len(existing_tables)}")
            
            # 1. Создать таблицу categories, если не существует
            print("\n📝 Шаг 1: Создание таблицы categories...")
            if not table_exists(conn, 'categories'):
                print("   Создаем таблицу categories...")
                conn.execute(text("""
                    CREATE TABLE categories (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        title VARCHAR(200) NOT NULL,
                        description TEXT,
                        "order" INTEGER DEFAULT 0,
                        is_active BOOLEAN DEFAULT 1,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                    )
                """))
                print("   ✅ Таблица categories создана")
            else:
                print("   ℹ️  Таблица categories уже существует")
            
            # 2. Обновить таблицу courses: добавить category_id, order, sequential_progression
            print("\n📝 Шаг 2: Обновление таблицы courses...")
            if not column_exists(conn, 'courses', 'category_id'):
                print("   Добавляем колонку category_id...")
                # Сначала создаем категорию по умолчанию, если курсы существуют
                result = conn.execute(text("SELECT COUNT(*) FROM courses"))
                course_count = result.fetchone()[0]
                
                if course_count > 0:
                    # Создаем категорию "Без категории"
                    conn.execute(text("""
                        INSERT INTO categories (title, description, "order", is_active)
                        VALUES ('Без категории', 'Категория по умолчанию для существующих курсов', 0, 1)
                    """))
                    default_category_id = conn.execute(text("SELECT last_insert_rowid()")).fetchone()[0]
                    print(f"   ✅ Создана категория по умолчанию (ID: {default_category_id})")
                else:
                    default_category_id = 1
                
                # Добавляем колонку category_id
                conn.execute(text(f"""
                    ALTER TABLE courses ADD COLUMN category_id INTEGER DEFAULT {default_category_id}
                """))
                
                # Устанавливаем category_id для всех существующих курсов
                if course_count > 0:
                    conn.execute(text(f"""
                        UPDATE courses SET category_id = {default_category_id} WHERE category_id IS NULL
                    """))
                
                # Добавляем индекс
                conn.execute(text("""
                    CREATE INDEX IF NOT EXISTS ix_courses_category_id ON courses(category_id)
                """))
                print("   ✅ Колонка category_id добавлена")
            else:
                print("   ℹ️  Колонка category_id уже существует")
            
            if not column_exists(conn, 'courses', 'order'):
                print("   Добавляем колонку order...")
                conn.execute(text("""
                    ALTER TABLE courses ADD COLUMN "order" INTEGER DEFAULT 0
                """))
                print("   ✅ Колонка order добавлена")
            else:
                print("   ℹ️  Колонка order уже существует")
            
            if not column_exists(conn, 'courses', 'sequential_progression'):
                print("   Добавляем колонку sequential_progression...")
                conn.execute(text("""
                    ALTER TABLE courses ADD COLUMN sequential_progression BOOLEAN DEFAULT 0
                """))
                print("   ✅ Колонка sequential_progression добавлена")
            else:
                print("   ℹ️  Колонка sequential_progression уже существует")
            
            # 3. Обновить таблицу lessons: добавить file_path
            print("\n📝 Шаг 3: Обновление таблицы lessons...")
            if not column_exists(conn, 'lessons', 'file_path'):
                print("   Добавляем колонку file_path...")
                conn.execute(text("""
                    ALTER TABLE lessons ADD COLUMN file_path VARCHAR(500)
                """))
                print("   ✅ Колонка file_path добавлена")
            else:
                print("   ℹ️  Колонка file_path уже существует")
            
            # 4. Создать таблицу lesson_content_blocks, если не существует
            print("\n📝 Шаг 4: Создание таблицы lesson_content_blocks...")
            if not table_exists(conn, 'lesson_content_blocks'):
                print("   Создаем таблицу lesson_content_blocks...")
                conn.execute(text("""
                    CREATE TABLE lesson_content_blocks (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        lesson_id INTEGER NOT NULL,
                        block_type VARCHAR(50) NOT NULL,
                        content TEXT,
                        "order" INTEGER NOT NULL DEFAULT 0,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (lesson_id) REFERENCES lessons(id)
                    )
                """))
                # Добавляем индекс
                conn.execute(text("""
                    CREATE INDEX IF NOT EXISTS ix_lesson_content_blocks_lesson_id 
                    ON lesson_content_blocks(lesson_id)
                """))
                print("   ✅ Таблица lesson_content_blocks создана")
            else:
                print("   ℹ️  Таблица lesson_content_blocks уже существует")
            
            # 5. Обновить таблицу user_lesson_progress: добавить time_spent
            print("\n📝 Шаг 5: Обновление таблицы user_lesson_progress...")
            if not column_exists(conn, 'user_lesson_progress', 'time_spent'):
                print("   Добавляем колонку time_spent...")
                conn.execute(text("""
                    ALTER TABLE user_lesson_progress ADD COLUMN time_spent INTEGER DEFAULT 0
                """))
                print("   ✅ Колонка time_spent добавлена")
            else:
                print("   ℹ️  Колонка time_spent уже существует")
            
            # Проверяем результат
            inspector = inspect(db_manager.engine)
            final_tables = inspector.get_table_names()
            
            print(f"\n✅ Миграция завершена успешно!")
            print(f"📋 Всего таблиц: {len(final_tables)}")
            for table in sorted(final_tables):
                columns = inspector.get_columns(table)
                print(f"   - {table} ({len(columns)} колонок)")
            
            if backup_path:
                print(f"\n📦 Резервная копия: {backup_path}")
            
    except Exception as e:
        print(f"\n❌ Ошибка при миграции БД: {e}")
        if backup_path:
            print(f"💾 Восстановите из резервной копии: {backup_path}")
        raise


if __name__ == "__main__":
    try:
        migrate_database()
        print("\n✅ Миграция выполнена успешно!")
    except KeyboardInterrupt:
        print("\n⚠️  Операция прервана пользователем")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Критическая ошибка: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)




