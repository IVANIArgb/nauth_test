#!/usr/bin/env python3
"""
Скрипт для автоматического удаления всех данных из БД:
- Категории (Category)
- Курсы (Course)
- Уроки (Lesson)
- Корзина (DeletedObject)
- Связанные данные (прогресс, блоки контента, доступы)

Запуск: python clear_categories_courses_lessons_bin_auto.py
"""

import os
import sys
import shutil
from datetime import datetime

# Добавляем корневую директорию проекта в путь
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__)))
sys.path.insert(0, project_root)

from database.models import (
    db_manager,
    Category, Course, Lesson,
    UserCourseProgress, UserLessonProgress,
    LessonContentBlock, DeletedObject,
    CourseDepartmentAccess
)


def backup_database():
    """Создать резервную копию базы данных."""
    # Путь к БД относительно корня проекта
    script_dir = os.path.dirname(os.path.abspath(__file__))
    db_path = os.path.join(script_dir, 'database', 'users_courses.db')
    if os.path.exists(db_path):
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_path = f"{db_path}.backup_{timestamp}"
        shutil.copy2(db_path, backup_path)
        print(f"✅ Резервная копия создана: {backup_path}")
        return backup_path
    else:
        print(f"⚠️  База данных не найдена по пути: {db_path}")
    return None


def clear_all_data():
    """Удалить все данные из категорий, курсов, уроков и корзины."""
    session = db_manager.get_session()
    
    try:
        print("🗑️  Начинаем удаление данных...\n")
        
        # Статистика до удаления
        stats_before = {
            'UserLessonProgress': session.query(UserLessonProgress).count(),
            'UserCourseProgress': session.query(UserCourseProgress).count(),
            'LessonContentBlock': session.query(LessonContentBlock).count(),
            'CourseDepartmentAccess': session.query(CourseDepartmentAccess).count(),
            'Lesson': session.query(Lesson).count(),
            'Course': session.query(Course).count(),
            'Category': session.query(Category).count(),
            'DeletedObject': session.query(DeletedObject).count(),
        }
        
        print("📊 Статистика ДО удаления:")
        for table, count in stats_before.items():
            print(f"   {table}: {count} записей")
        print()
        
        # Удаляем в правильном порядке (с учетом внешних ключей)
        print("🗑️  Удаление данных...")
        
        # 1. Удаляем прогресс пользователей по урокам
        deleted = session.query(UserLessonProgress).delete()
        print(f"   ✅ Удалено UserLessonProgress: {deleted} записей")
        
        # 2. Удаляем прогресс пользователей по курсам
        deleted = session.query(UserCourseProgress).delete()
        print(f"   ✅ Удалено UserCourseProgress: {deleted} записей")
        
        # 3. Удаляем блоки контента уроков
        deleted = session.query(LessonContentBlock).delete()
        print(f"   ✅ Удалено LessonContentBlock: {deleted} записей")
        
        # 4. Удаляем доступы к курсам по отделам
        deleted = session.query(CourseDepartmentAccess).delete()
        print(f"   ✅ Удалено CourseDepartmentAccess: {deleted} записей")
        
        # 5. Удаляем уроки
        deleted = session.query(Lesson).delete()
        print(f"   ✅ Удалено Lesson: {deleted} записей")
        
        # 6. Удаляем курсы
        deleted = session.query(Course).delete()
        print(f"   ✅ Удалено Course: {deleted} записей")
        
        # 7. Удаляем категории
        deleted = session.query(Category).delete()
        print(f"   ✅ Удалено Category: {deleted} записей")
        
        # 8. Удаляем корзину (удаленные объекты)
        deleted = session.query(DeletedObject).delete()
        print(f"   ✅ Удалено DeletedObject: {deleted} записей")
        
        # Коммитим изменения
        session.commit()
        print("\n✅ Все данные успешно удалены!")
        
        # Статистика после удаления
        print("\n📊 Статистика ПОСЛЕ удаления:")
        stats_after = {
            'UserLessonProgress': session.query(UserLessonProgress).count(),
            'UserCourseProgress': session.query(UserCourseProgress).count(),
            'LessonContentBlock': session.query(LessonContentBlock).count(),
            'CourseDepartmentAccess': session.query(CourseDepartmentAccess).count(),
            'Lesson': session.query(Lesson).count(),
            'Course': session.query(Course).count(),
            'Category': session.query(Category).count(),
            'DeletedObject': session.query(DeletedObject).count(),
        }
        for table, count in stats_after.items():
            print(f"   {table}: {count} записей")
        
        # Итоговая статистика
        print("\n📈 Итого удалено:")
        total_deleted = 0
        for table in stats_before.keys():
            deleted_count = stats_before[table] - stats_after[table]
            if deleted_count > 0:
                print(f"   {table}: {deleted_count} записей")
                total_deleted += deleted_count
        
        print(f"\n🎯 Всего удалено записей: {total_deleted}")
        
    except Exception as e:
        session.rollback()
        print(f"\n❌ Ошибка при удалении данных: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        session.close()
    
    return True


def main():
    """Главная функция."""
    print("=" * 60)
    print("ОЧИСТКА БАЗЫ ДАННЫХ (АВТОМАТИЧЕСКИЙ РЕЖИМ)")
    print("=" * 60)
    print()
    print("⚠️  Будут удалены ВСЕ данные из:")
    print("   - Категории (Category)")
    print("   - Курсы (Course)")
    print("   - Уроки (Lesson)")
    print("   - Корзина (DeletedObject)")
    print("   - Прогресс пользователей (UserCourseProgress, UserLessonProgress)")
    print("   - Блоки контента (LessonContentBlock)")
    print("   - Доступы к курсам (CourseDepartmentAccess)")
    print()
    print("⚠️  Пользователи (User) и вопросы/ответы (Question/Answer) НЕ будут удалены!")
    print()
    
    # Создаем резервную копию
    backup_path = backup_database()
    if not backup_path:
        print("⚠️  База данных не найдена или уже пуста")
    
    print()
    print("🚀 Запуск автоматического удаления...")
    print()
    
    success = clear_all_data()
    
    if success:
        print("\n" + "=" * 60)
        print("✅ ОЧИСТКА ЗАВЕРШЕНА УСПЕШНО")
        print("=" * 60)
        if backup_path:
            print(f"\n💾 Резервная копия сохранена: {backup_path}")
    else:
        print("\n" + "=" * 60)
        print("❌ ОЧИСТКА ЗАВЕРШИЛАСЬ С ОШИБКАМИ")
        print("=" * 60)
        if backup_path:
            print(f"\n💾 Резервная копия сохранена: {backup_path}")
            print("   Вы можете восстановить данные из резервной копии")


if __name__ == '__main__':
    main()
