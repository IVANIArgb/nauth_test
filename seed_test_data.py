#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Скрипт: удаление всех категорий/курсов/уроков и создание тестовых данных.
- 2 категории: свободная и последовательная
- В каждой по 2 курса: один последовательный, один свободный
- По 10 уроков в каждом курсе со всеми типами контента
Запуск: python seed_test_data.py  или  python run.py seed
"""

import os
import sys
import json
from sqlalchemy import func

_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _root)

from database.models import (
    db_manager, Category, Course, Lesson, LessonContentBlock,
    UserCourseProgress, UserLessonProgress, CourseDepartmentAccess, DeletedObject
)
from backend.utils.categories_data_sync import sync_category, sync_course, sync_lesson


def create_content_block(session, lesson_id, block_type, content, order):
    block = LessonContentBlock(
        lesson_id=lesson_id,
        block_type=block_type,
        content=json.dumps(content, ensure_ascii=False),
        order=order
    )
    session.add(block)
    return block


def get_lesson_blocks(lesson_num):
    """Генерирует блоки контента для урока: заголовки, текст разных стилей, видео, фото."""
    videos = [
        ("https://www.youtube.com/embed/_uQrJ0TkZlc", "Python для начинающих"),
        ("https://www.youtube.com/embed/DKH7VMbj4YM", "HTML и CSS"),
        ("https://www.youtube.com/embed/bbp_849-RZ4", "Pytest"),
        ("https://www.youtube.com/embed/dQw4w9WgXcQ", "Демо видео"),
    ]
    colors = ["#333333", "#2563eb", "#059669", "#dc2626", "#7c3aed", "#ea580c"]
    sizes = ["xs", "sm", "md", "lg", "xl"]
    aligns = ["left", "center", "right"]
    levels = [1, 2, 3, 4]

    v = videos[(lesson_num - 1) % len(videos)]
    c = colors[(lesson_num - 1) % len(colors)]
    s = sizes[(lesson_num - 1) % len(sizes)]
    a = aligns[(lesson_num - 1) % len(aligns)]
    lvl = levels[(lesson_num - 1) % len(levels)]

    blocks = [
        {"type": "heading", "content": {"text": f"Урок {lesson_num}: Введение", "level": min(lvl, 2)}},
        {"type": "text", "content": {"text": f"Это содержимое урока {lesson_num}. Основные понятия и теория.", "size": "md", "align": "left"}},
        {"type": "heading", "content": {"text": "Ключевые моменты", "level": 3}},
        {"type": "text", "content": {"text": f"Текст размера {s}, выравнивание {a}.", "size": s, "align": a, "color": c}},
        {"type": "text", "content": {"text": "Дополнительный абзац с важной информацией.", "size": "sm", "align": "left"}},
        {"type": "video", "content": {"url": v[0], "title": v[1]}},
        {"type": "image", "content": {"url": f"https://via.placeholder.com/600x250/{c[1:]}/ffffff?text=Урок+{lesson_num}", "alt": f"Иллюстрация урока {lesson_num}"}},
        {"type": "text", "content": {"text": "Подпись под изображением.", "size": "xs", "align": "center"}},
    ]
    if lesson_num == 1:
        blocks.append({
            "type": "test",
            "content": {
                "title": "Проверочный тест",
                "questions": [
                    {"text": "Python — это интерпретируемый язык?", "options": ["Да", "Нет"], "correct_answer": 0, "multiple": False},
                    {"text": "Какие из перечисленных являются типами данных в Python?", "options": ["list", "dict", "array", "tuple"], "correct_answer": [0, 1, 3], "multiple": True},
                ]
            }
        })
    if lesson_num % 2 == 0:
        blocks.append({"type": "file", "content": {"filename": f"материалы_урок_{lesson_num}.pdf", "url": ""}})
    return blocks


def clear_all(session):
    """Удаление всех категорий, курсов, уроков и связанных данных."""
    session.query(UserLessonProgress).delete()
    session.query(UserCourseProgress).delete()
    session.query(LessonContentBlock).delete()
    session.query(CourseDepartmentAccess).delete()
    session.query(Lesson).delete()
    session.query(Course).delete()
    session.query(Category).delete()
    session.query(DeletedObject).delete()
    session.commit()


def main():
    print("=" * 60)
    print("Очистка и создание тестовых данных")
    print("=" * 60)

    session = db_manager.get_session()
    try:
        # 1. Очистка
        print("\n🗑️  Удаление всех категорий, курсов, уроков...")
        clear_all(session)
        print("   ✅ Данные удалены\n")

        # 2. Категории: свободная и последовательная
        categories_data = [
            {"title": "Свободная категория", "desc": "Курсы можно проходить в любом порядке.", "order": 0, "seq": False},
            {"title": "Последовательная категория", "desc": "Курсы доступны по порядку.", "order": 1, "seq": True},
        ]
        created_categories = []
        for c in categories_data:
            cat = Category(title=c["title"], description=c["desc"], order=c["order"],
                           sequential_progression=c["seq"], is_active=True)
            session.add(cat)
            session.flush()
            cat.path_identifier = sync_category(cat.id, cat.title)
            created_categories.append(cat)
            print(f"  ✓ Категория: {cat.title} (sequential={cat.sequential_progression})")

        session.commit()

        # 3. Курсы: в каждой категории по 2 — один sequential, один free
        courses_data = [
            {"cat": "Свободная категория", "title": "Свободный курс 1", "desc": "Уроки в любом порядке.", "order": 0, "seq": False},
            {"cat": "Свободная категория", "title": "Последовательный курс 1", "desc": "Уроки по порядку.", "order": 1, "seq": True},
            {"cat": "Последовательная категория", "title": "Свободный курс 2", "desc": "Уроки в любом порядке.", "order": 0, "seq": False},
            {"cat": "Последовательная категория", "title": "Последовательный курс 2", "desc": "Уроки по порядку.", "order": 1, "seq": True},
        ]
        created_courses = {}
        for c in courses_data:
            cat = next((x for x in created_categories if x.title == c["cat"]), None)
            if not cat:
                continue
            course = Course(category_id=cat.id, title=c["title"], description=c["desc"],
                           order=c["order"], sequential_progression=c["seq"], is_active=True)
            session.add(course)
            session.flush()
            course.path_identifier = sync_course(cat.title, course.id, course.title)
            created_courses[f"{cat.title}|{course.title}"] = (course, cat)
            print(f"  ✓ Курс: {cat.title} / {course.title} (sequential={course.sequential_progression})")

        session.commit()

        # 4. По 10 уроков в каждом курсе
        for key, (course, cat) in created_courses.items():
            for i in range(1, 11):
                max_num = session.query(func.max(Lesson.lesson_number)).filter(Lesson.course_id == course.id).scalar()
                lesson_number = (max_num or 0) + 1

                lesson = Lesson(
                    course_id=course.id,
                    title=f"Урок {i}",
                    description=f"Описание урока {i} курса {course.title}",
                    lesson_number=lesson_number,
                    is_active=True,
                )
                session.add(lesson)
                session.flush()
                lesson.path_identifier = sync_lesson(cat.title, course.title, lesson.id, lesson.title)

                blocks = get_lesson_blocks(i)
                for j, blk in enumerate(blocks):
                    create_content_block(session, lesson.id, blk["type"], blk["content"], j)

            print(f"  ✓ Курс {course.title}: 10 уроков")

        # Обновить total_lessons
        for (course, _) in created_courses.values():
            count = session.query(Lesson).filter(Lesson.course_id == course.id, Lesson.is_active == True).count()
            course.total_lessons = count

        session.commit()
        print("\n" + "=" * 60)
        print("✅ Готово: 2 категории, 4 курса, 40 уроков")
        print("=" * 60)

    except Exception as e:
        session.rollback()
        print(f"\n❌ Ошибка: {e}")
        raise
    finally:
        session.close()


if __name__ == "__main__":
    main()
