#!/usr/bin/env python3
"""
Создание курса «Основы Python» в новой категории «Программирование».
Первый урок наполнен текстовым контентом по мотивам NIC.ru (основы Python).
"""

import os
import sys
import json

project_root = os.path.abspath(os.path.join(os.path.dirname(__file__)))
sys.path.insert(0, project_root)

from database.models import (
    db_manager,
    Category,
    Course,
    Lesson,
    LessonContentBlock,
)
from backend.utils.categories_data_sync import sync_category, sync_course, sync_lesson


# Контент первого урока «Основы языка программирования Python» (по мотивам NIC.ru)
LESSON_BLOCKS = [
    {"block_type": "heading", "content": {"level": 1, "text": "Основы языка программирования Python"}},
    {"block_type": "text", "content": {"text": "Python — один из самых популярных языков программирования в мире. Он прост в изучении, имеет понятный синтаксис и широко используется в веб-разработке, анализе данных, автоматизации и машинном обучении."}},
    {"block_type": "heading", "content": {"level": 2, "text": "Почему стоит изучать Python"}},
    {"block_type": "text", "content": {"text": "Python читается почти как обычный текст, поэтому он отлично подходит для новичков. На нём можно быстро писать программы любой сложности — от простых скриптов до крупных приложений."}},
    {"block_type": "heading", "content": {"level": 2, "text": "Установка Python"}},
    {"block_type": "text", "content": {"text": "Скачайте установщик с официального сайта python.org. Выберите последнюю стабильную версию и следуйте инструкциям. После установки откройте командную строку (терминал) и выполните команду python --version, чтобы убедиться, что Python установлен корректно."}},
    {"block_type": "heading", "content": {"level": 2, "text": "Первая программа"}},
    {"block_type": "text", "content": {"text": "Традиционно первой программой на любом языке является вывод приветствия. В Python это делается одной строкой:\n\nprint(\"Привет, мир!\")\n\nСохраните код в файл с расширением .py и запустите его командой python имя_файла.py"}},
    {"block_type": "heading", "content": {"level": 2, "text": "Переменные и типы данных"}},
    {"block_type": "text", "content": {"text": "В Python не нужно объявлять тип переменной — интерпретатор определяет его автоматически.\n\nname = \"Алексей\"\nage = 25\nheight = 1.78\n\nПеременная name — строка, age — целое число, height — число с плавающей точкой. Python поддерживает строки, целые и дробные числа, списки, словари, кортежи и булевы значения (True/False)."}},
    {"block_type": "heading", "content": {"level": 2, "text": "Условные конструкции"}},
    {"block_type": "text", "content": {"text": "Условия в Python записываются с помощью if, elif и else. Отступы (пробелы или табуляция) определяют блок кода — это обязательная часть синтаксиса.\n\nif age >= 18:\n    print(\"Вы совершеннолетний\")\nelse:\n    print(\"Вы несовершеннолетний\")"}},
    {"block_type": "heading", "content": {"level": 2, "text": "Циклы"}},
    {"block_type": "text", "content": {"text": "Цикл for перебирает элементы последовательности. Цикл while выполняется, пока условие истинно.\n\nfor i in range(5):\n    print(i)\n\nЦикл выше выведет числа от 0 до 4. Функция range() создаёт последовательность чисел."}},
    {"block_type": "heading", "content": {"level": 2, "text": "Функции"}},
    {"block_type": "text", "content": {"text": "Функция объявляется ключевым словом def. Она может принимать аргументы и возвращать значение.\n\ndef greet(name):\n    return f\"Привет, {name}!\"\n\nprint(greet(\"Мир\"))  # Выведет: Привет, Мир!"}},
    {"block_type": "heading", "content": {"level": 2, "text": "Что дальше"}},
    {"block_type": "text", "content": {"text": "После освоения основ рекомендуется изучить: списки и словари, работу с файлами, обработку исключений, объектно-ориентированное программирование (классы) и модули. Python имеет богатую стандартную библиотеку и множество сторонних пакетов для решения самых разных задач."}},
]


def main():
    print("=" * 60)
    print("Создание курса «Основы Python»")
    print("=" * 60)

    session = db_manager.get_session()
    try:
        # 1. Категория
        category_title = "Программирование"
        existing_cat = session.query(Category).filter(
            Category.title == category_title,
            Category.is_active == True
        ).first()
        if existing_cat:
            category = existing_cat
            print(f"✓ Категория «{category_title}» уже существует (id={category.id})")
        else:
            category = Category(
                title=category_title,
                description="Курсы по программированию",
                order=999,
                is_active=True,
            )
            session.add(category)
            session.flush()
            path_id = sync_category(category.id, category.title)
            category.path_identifier = path_id
            session.commit()
            session.flush()
            print(f"✓ Создана категория «{category_title}» (id={category.id})")

        # 2. Курс
        course_title = "Основы Python"
        existing_course = session.query(Course).filter(
            Course.category_id == category.id,
            Course.title == course_title,
            Course.is_active == True
        ).first()
        if existing_course:
            course = existing_course
            print(f"✓ Курс «{course_title}» уже существует (id={course.id})")
        else:
            course = Course(
                category_id=category.id,
                title=course_title,
                description="Введение в язык программирования Python: переменные, циклы, функции и основы ООП.",
                total_lessons=1,
                order=0,
                sequential_progression=False,
                is_active=True,
            )
            session.add(course)
            session.flush()
            path_id = sync_course(category.title, course.id, course.title)
            course.path_identifier = path_id
            session.commit()
            session.flush()
            print(f"✓ Создан курс «{course_title}» (id={course.id})")

        # 3. Урок
        lesson_title = "Основы языка программирования Python"
        existing_lesson = session.query(Lesson).filter(
            Lesson.course_id == course.id,
            Lesson.title == lesson_title,
            Lesson.is_active == True
        ).first()
        if existing_lesson:
            lesson = existing_lesson
            print(f"✓ Урок «{lesson_title}» уже существует (id={lesson.id})")
        else:
            lesson = Lesson(
                course_id=course.id,
                title=lesson_title,
                description="Введение в Python: установка, первая программа, переменные, условия, циклы и функции.",
                lesson_number=1,
                content=None,
                is_active=True,
            )
            session.add(lesson)
            session.flush()
            path_id = sync_lesson(category.title, course.title, lesson.id, lesson.title)
            lesson.path_identifier = path_id
            session.commit()
            session.flush()
            print(f"✓ Создан урок «{lesson_title}» (id={lesson.id})")

        # 4. Блоки контента (только если урок только что создан — иначе не дублируем)
        blocks_count = session.query(LessonContentBlock).filter(
            LessonContentBlock.lesson_id == lesson.id
        ).count()
        if blocks_count > 0:
            print(f"✓ В уроке уже есть {blocks_count} блоков контента, пропускаем добавление")
        else:
            for i, block_data in enumerate(LESSON_BLOCKS):
                block = LessonContentBlock(
                    lesson_id=lesson.id,
                    block_type=block_data["block_type"],
                    content=json.dumps(block_data["content"], ensure_ascii=False),
                    order=i,
                )
                session.add(block)
            session.commit()
            print(f"✓ Добавлено {len(LESSON_BLOCKS)} блоков контента (заголовки и текст)")

        # Обновляем total_lessons в курсе
        total = session.query(Lesson).filter(
            Lesson.course_id == course.id,
            Lesson.is_active == True
        ).count()
        if course.total_lessons != total:
            course.total_lessons = total
            session.commit()
            print(f"✓ Обновлено total_lessons={total} в курсе")

        print()
        print("Готово! Откройте в браузере:")
        print(f"  http://127.0.0.1:5000/lessons-content-pg?lesson_id={lesson.id}")
        print()

    except Exception as e:
        session.rollback()
        print(f"Ошибка: {e}")
        raise
    finally:
        session.close()


if __name__ == "__main__":
    main()
