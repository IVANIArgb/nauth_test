"""
Миграция для добавления таблиц корзины и доступа курсов по отделам
"""
import os
import sys
from sqlalchemy import text, inspect
from database.models import db_manager, Base, DeletedObject, CourseDepartmentAccess

project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
sys.path.insert(0, project_root)

def migrate_database():
    print("🔄 Начинаем миграцию базы данных для корзины и доступа по отделам...")
    
    engine = db_manager.engine
    inspector = inspect(engine)
    
    with engine.begin() as conn:
        # 1. Создание таблицы deleted_objects
        print("📝 Проверяем и создаем таблицу 'deleted_objects'...")
        if not inspector.has_table(DeletedObject.__tablename__):
            DeletedObject.__table__.create(conn)
            print(f"  ✅ Таблица '{DeletedObject.__tablename__}' создана.")
        else:
            print(f"  ℹ️  Таблица '{DeletedObject.__tablename__}' уже существует.")
        
        # 2. Создание таблицы course_department_access
        print("📝 Проверяем и создаем таблицу 'course_department_access'...")
        if not inspector.has_table(CourseDepartmentAccess.__tablename__):
            CourseDepartmentAccess.__table__.create(conn)
            print(f"  ✅ Таблица '{CourseDepartmentAccess.__tablename__}' создана.")
        else:
            print(f"  ℹ️  Таблица '{CourseDepartmentAccess.__tablename__}' уже существует.")
        
        print("✅ Миграция завершена успешно!")

if __name__ == "__main__":
    migrate_database()




