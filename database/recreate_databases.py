#!/usr/bin/env python3
"""
Скрипт для безопасного пересоздания базы данных.
Сохраняет структуру таблиц, типы данных, ограничения и индексы.
"""

import os
import sys
import shutil
from datetime import datetime

# Добавляем корневую директорию проекта в путь
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
sys.path.insert(0, project_root)

from sqlalchemy import inspect, text
from database.models import (
    Base, db_manager, User, Category, Course, Lesson,
    UserCourseProgress, UserLessonProgress, LessonContentBlock,
    Question, Answer, QuestionAttachment, AnswerAttachment,
    KerberosSession
)


def backup_database():
    """Создает резервную копию существующей БД"""
    db_path = os.path.join(os.path.dirname(__file__), 'users_courses.db')
    if os.path.exists(db_path):
        backup_path = f"{db_path}.backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        shutil.copy2(db_path, backup_path)
        print(f"Backup created: {backup_path}")
        return backup_path
    return None


def get_table_schema(engine, table_name):
    """Получает схему таблицы"""
    inspector = inspect(engine)
    columns = inspector.get_columns(table_name)
    indexes = inspector.get_indexes(table_name)
    foreign_keys = inspector.get_foreign_keys(table_name)
    
    return {
        'columns': columns,
        'indexes': indexes,
        'foreign_keys': foreign_keys
    }


def recreate_database():
    """Безопасно пересоздает базу данных"""
    print("Начинаем пересоздание базы данных...")
    
    # Создаем резервную копию
    backup_path = backup_database()
    
    try:
        # Получаем информацию о существующих таблицах
        inspector = inspect(db_manager.engine)
        existing_tables = inspector.get_table_names()
        
        print(f"Найдено таблиц: {len(existing_tables)}")
        for table in existing_tables:
            print(f"   - {table}")
        
        # Удаляем все таблицы
        print("\nУдаление существующих таблиц...")
        with db_manager.engine.begin() as conn:
            # Удаляем в обратном порядке зависимостей
            tables_to_drop = [
                'answer_attachments',
                'question_attachments',
                'answers',
                'questions',
                'lesson_content_blocks',
                'user_lesson_progress',
                'user_course_progress',
                'lessons',
                'courses',
                'categories',
                'kerberos_sessions',
                'users'
            ]
            
            for table in tables_to_drop:
                try:
                    conn.execute(text(f"DROP TABLE IF EXISTS {table}"))
                    print(f"   OK: удалена таблица: {table}")
                except Exception as e:
                    print(f"   WARN: ошибка при удалении {table}: {e}")
            
            # Очищаем последовательности SQLite
            # sqlite_sequence может отсутствовать, если в текущей БД не использовались
            # AUTOINCREMENT/SEQUENCE (или таблицы уже были удалены).
            # Для пересоздания это не критично, поэтому безопасно игнорируем ошибку.
            try:
                conn.execute(text("DELETE FROM sqlite_sequence"))
            except Exception:
                pass
        
        # Создаем все таблицы заново
        print("\nСоздание таблиц...")
        db_manager.create_tables()
        
        # Проверяем созданные таблицы
        inspector = inspect(db_manager.engine)
        created_tables = inspector.get_table_names()
        
        print(f"\nСоздано таблиц: {len(created_tables)}")
        for table in created_tables:
            columns = inspector.get_columns(table)
            print(f"   - {table} ({len(columns)} колонок)")
            for col in columns:
                nullable = "NULL" if col['nullable'] else "NOT NULL"
                default = f" DEFAULT {col['default']}" if col.get('default') else ""
                print(f"     • {col['name']}: {col['type']} {nullable}{default}")
        
        print("\nБаза данных успешно пересоздана.")
        print(f"Backup: {backup_path}" if backup_path else "")
        
    except Exception as e:
        print(f"\nERROR: Ошибка при пересоздании БД: {e}")
        if backup_path:
            print(f"Restore from backup: {backup_path}")
        raise


if __name__ == "__main__":
    try:
        recreate_database()
    except KeyboardInterrupt:
        print("\nОперация прервана пользователем")
        sys.exit(1)
    except Exception as e:
        print(f"\nCRITICAL: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)



