#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Создает (или обновляет) полигон для тестирования тестов:
- Категория
- Курс
- Урок
- Несколько test-блоков с разными настройками и типами вопросов

Запуск:
  python scripts/create_tests_showcase.py
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from sqlalchemy import func

from database.models import (
    db_manager,
    Category,
    Course,
    Lesson,
    LessonContentBlock,
)
from backend.utils.categories_data_sync import (
    sync_category,
    sync_course,
    sync_lesson,
    get_lesson_path,
    save_text_content,
)
from backend.utils.lesson_blocks_fs import write_blocks as fs_write_blocks
from backend.utils.test_fs import (
    FsTestConfig,
    ensure_test_dirs,
    write_test_config,
    write_questions_to_dir,
)


CATEGORY_TITLE = "Категория тестирования тестов"
COURSE_TITLE = "Курс: Полигон тестов"
LESSON_TITLE = "Урок: Все виды тестов"


def _now_iso_local(delta_minutes: int = 0) -> str:
    dt = datetime.now() + timedelta(minutes=delta_minutes)
    return dt.replace(microsecond=0).isoformat()


def _upsert_category(session) -> Category:
    cat = session.query(Category).filter(Category.title == CATEGORY_TITLE).first()
    if not cat:
        max_order = session.query(func.max(Category.order)).scalar() or 0
        cat = Category(
            title=CATEGORY_TITLE,
            description="Полигон для ручного и авто тестирования всех видов тестов.",
            order=int(max_order) + 1,
            sequential_progression=False,
            is_active=True,
        )
        session.add(cat)
        session.flush()
    else:
        cat.description = "Полигон для ручного и авто тестирования всех видов тестов."
        cat.is_active = True

    cat.path_identifier = sync_category(
        cat.id,
        cat.title,
        settings={
            "description": cat.description,
            "order": cat.order,
            "sequential_progression": bool(cat.sequential_progression),
            "is_active": bool(cat.is_active),
        },
    )
    return cat


def _upsert_course(session, cat: Category) -> Course:
    course = session.query(Course).filter(
        Course.category_id == cat.id,
        Course.title == COURSE_TITLE,
    ).first()
    if not course:
        max_order = (
            session.query(func.max(Course.order))
            .filter(Course.category_id == cat.id)
            .scalar()
            or 0
        )
        course = Course(
            category_id=cat.id,
            title=COURSE_TITLE,
            description="Курс со всеми вариациями тестов и их настроек.",
            order=int(max_order) + 1,
            sequential_progression=False,
            total_lessons=1,
            is_active=True,
        )
        session.add(course)
        session.flush()
    else:
        course.description = "Курс со всеми вариациями тестов и их настроек."
        course.is_active = True

    course.path_identifier = sync_course(
        cat.title,
        course.id,
        course.title,
        settings={
            "description": course.description,
            "order": course.order,
            "sequential_progression": bool(course.sequential_progression),
            "total_lessons": int(course.total_lessons or 0),
            "is_active": bool(course.is_active),
        },
    )
    return course


def _upsert_lesson(session, cat: Category, course: Course) -> Lesson:
    lesson = session.query(Lesson).filter(
        Lesson.course_id == course.id,
        Lesson.title == LESSON_TITLE,
    ).first()
    if not lesson:
        max_num = (
            session.query(func.max(Lesson.lesson_number))
            .filter(Lesson.course_id == course.id)
            .scalar()
            or 0
        )
        lesson = Lesson(
            course_id=course.id,
            title=LESSON_TITLE,
            description="Урок-полигон: single/multiple/input + попытки/таймер/временное окно/перемешивание.",
            lesson_number=int(max_num) + 1,
            is_active=True,
        )
        session.add(lesson)
        session.flush()
    else:
        lesson.description = "Урок-полигон: single/multiple/input + попытки/таймер/временное окно/перемешивание."
        lesson.is_active = True

    lesson.path_identifier = sync_lesson(
        cat.title,
        course.title,
        lesson.id,
        lesson.title,
        settings={
            "lesson_number": int(lesson.lesson_number or 1),
            "is_active": bool(lesson.is_active),
        },
    )
    return lesson


def _test_questions_mix() -> list[dict]:
    return [
        {
            "text": "Какой HTTP-метод обычно используется для получения данных?",
            "answer_type": "single",
            "multiple": False,
            "options": ["GET", "POST", "PUT", "PATCH"],
            "correct_answer": 0,
            "points": 1,
        },
        {
            "text": "Какие из перечисленных являются SQL-командами?",
            "answer_type": "multiple",
            "multiple": True,
            "options": ["SELECT", "UPDATE", "COMMIT", "CENTER"],
            "correct_answer": [0, 1, 2],
            "points": 2,
        },
        {
            "text": "Введите расширение Python-файла без точки",
            "answer_type": "input",
            "multiple": False,
            "accepted_answers": ["py", "python"],
            "points": 1,
        },
    ]


def _build_blocks() -> list[dict]:
    now_from = _now_iso_local(-30)
    now_until = _now_iso_local(60 * 24)  # на сутки вперед

    return [
        {
            "block_type": "heading",
            "content": {"text": "Полигон тестирования тестов", "level": 2},
        },
        {
            "block_type": "text",
            "content": {
                "text": (
                    "В этом уроке собраны разные конфигурации тестов: "
                    "без ограничений, с лимитом попыток, с таймером, "
                    "с временным окном, с перемешиванием вопросов и ответов."
                )
            },
        },
        {
            "block_type": "test",
            "content": {
                "title": "Тест 1: Базовый (single/multiple/input)",
                "settings": {
                    "pass_percent": 70,
                    "limit_attempts": False,
                    "max_attempts": None,
                    "shuffle_questions": False,
                    "shuffle_options": False,
                    "time_limit_seconds": 0,
                },
                "questions": _test_questions_mix(),
            },
        },
        {
            "block_type": "test",
            "content": {
                "title": "Тест 2: Ограничение попыток",
                "settings": {
                    "pass_percent": 80,
                    "limit_attempts": True,
                    "max_attempts": 2,
                    "shuffle_questions": False,
                    "shuffle_options": False,
                    "time_limit_seconds": 0,
                },
                "questions": _test_questions_mix(),
            },
        },
        {
            "block_type": "test",
            "content": {
                "title": "Тест 3: Лимит времени",
                "settings": {
                    "pass_percent": 70,
                    "limit_attempts": False,
                    "max_attempts": None,
                    "shuffle_questions": False,
                    "shuffle_options": False,
                    "time_limit_seconds": 90,
                },
                "questions": _test_questions_mix(),
            },
        },
        {
            "block_type": "test",
            "content": {
                "title": "Тест 4: Временное окно доступности",
                "settings": {
                    "pass_percent": 70,
                    "limit_attempts": True,
                    "max_attempts": 3,
                    "available_from": now_from,
                    "available_until": now_until,
                    "shuffle_questions": False,
                    "shuffle_options": False,
                    "time_limit_seconds": 0,
                },
                "questions": _test_questions_mix(),
            },
        },
        {
            "block_type": "test",
            "content": {
                "title": "Тест 5: Перемешивание + строгий порог",
                "settings": {
                    "pass_percent": 90,
                    "limit_attempts": True,
                    "max_attempts": 5,
                    "shuffle_questions": True,
                    "shuffle_options": True,
                    "time_limit_seconds": 180,
                },
                "questions": _test_questions_mix(),
            },
        },
    ]


def _sync_lesson_fs(lesson_path: str, lesson_id: int, db_blocks: list[LessonContentBlock]) -> None:
    blocks_for_fs: list[dict] = []

    # Чистим старые test-папки block-* чтобы не оставались артефакты
    tests_root = Path(lesson_path) / "tests"
    tests_root.mkdir(parents=True, exist_ok=True)
    for entry in tests_root.iterdir():
        if entry.is_dir() and entry.name.startswith("block-"):
            for sub in entry.rglob("*"):
                if sub.is_file():
                    sub.unlink(missing_ok=True)
            for sub in sorted(entry.rglob("*"), reverse=True):
                if sub.is_dir():
                    try:
                        sub.rmdir()
                    except OSError:
                        pass
            try:
                entry.rmdir()
            except OSError:
                pass

    for b in db_blocks:
        try:
            content = json.loads(b.content or "{}")
        except Exception:
            content = {}

        if b.block_type in ("heading", "text"):
            txt = str(content.get("text") or content.get("html") or "")
            save_text_content(lesson_path, b.id, txt)

        if b.block_type == "test":
            title = str(content.get("title") or "Тест")
            settings = content.get("settings") if isinstance(content.get("settings"), dict) else {}
            questions = content.get("questions") if isinstance(content.get("questions"), list) else []

            tests_dir = ensure_test_dirs(lesson_path)
            test_dir = os.path.join(tests_dir, f"block-{b.id}")
            os.makedirs(os.path.join(test_dir, "questions"), exist_ok=True)

            cfg = FsTestConfig(
                title=title,
                enabled=True,
                pass_percent=int(settings.get("pass_percent") or 70),
                limit_attempts=bool(settings.get("limit_attempts")),
                max_attempts=int(settings.get("max_attempts")) if settings.get("max_attempts") else None,
                test_type="temporary" if (settings.get("available_from") or settings.get("available_until")) else "permanent",
                available_from=settings.get("available_from") if isinstance(settings.get("available_from"), str) else None,
                available_until=settings.get("available_until") if isinstance(settings.get("available_until"), str) else None,
                shuffle_questions=bool(settings.get("shuffle_questions")),
                shuffle_options=bool(settings.get("shuffle_options")),
                time_limit_seconds=int(settings.get("time_limit_seconds")) if settings.get("time_limit_seconds") else None,
            )
            write_test_config(test_dir, cfg)
            write_questions_to_dir(os.path.join(test_dir, "questions"), [q for q in questions if isinstance(q, dict)])

        fs_content = {"title": str(content.get("title") or "Тест")} if b.block_type == "test" else (content if isinstance(content, dict) else {})
        blocks_for_fs.append(
            {
                "id": b.id,
                "lesson_id": lesson_id,
                "block_type": b.block_type,
                "order": b.order,
                "content": fs_content,
            }
        )

    fs_write_blocks(Path(lesson_path), blocks_for_fs)


def main() -> None:
    session = db_manager.get_session()
    try:
        cat = _upsert_category(session)
        course = _upsert_course(session, cat)
        lesson = _upsert_lesson(session, cat, course)

        # Пересобираем блоки урока детерминированно
        session.query(LessonContentBlock).filter(LessonContentBlock.lesson_id == lesson.id).delete()
        session.flush()

        blocks_spec = _build_blocks()
        created_blocks: list[LessonContentBlock] = []
        for idx, spec in enumerate(blocks_spec):
            block = LessonContentBlock(
                lesson_id=lesson.id,
                block_type=spec["block_type"],
                content=json.dumps(spec["content"], ensure_ascii=False),
                order=idx,
            )
            session.add(block)
            session.flush()
            created_blocks.append(block)

        course.total_lessons = (
            session.query(func.count(Lesson.id))
            .filter(Lesson.course_id == course.id, Lesson.is_active == True)
            .scalar()
            or 1
        )

        lesson_path = get_lesson_path(cat.title, course.title, lesson.title)
        _sync_lesson_fs(lesson_path, lesson.id, created_blocks)

        session.commit()
        print("OK: создан/обновлен полигон тестов")
        print(f"Категория: {cat.title} (id={cat.id})")
        print(f"Курс: {course.title} (id={course.id})")
        print(f"Урок: {lesson.title} (id={lesson.id})")
        print(f"Путь: {lesson_path}")
    except Exception as e:
        session.rollback()
        raise
    finally:
        session.close()


if __name__ == "__main__":
    main()
