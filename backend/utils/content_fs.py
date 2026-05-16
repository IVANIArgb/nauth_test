import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

from backend.utils.categories_data_sync import get_base_categories_data_path, ensure_categories_data_directory


def _read_json(path: Path) -> Optional[dict]:
    try:
        with open(path, "r", encoding="utf-8") as f:
            v = json.load(f)
        return v if isinstance(v, dict) else None
    except Exception:
        return None


def _is_active(cfg: dict) -> bool:
    # По умолчанию считаем активным, если ключа нет
    v = cfg.get("is_active")
    if isinstance(v, bool):
        return v
    if isinstance(v, (int, float)):
        return v != 0
    return True


@dataclass
class FsCategory:
    id: int
    title: str
    path: Path
    cfg: dict


@dataclass
class FsCourse:
    id: int
    title: str
    category_id: int
    path: Path
    cfg: dict


@dataclass
class FsLesson:
    id: int
    title: str
    category_id: int
    course_id: int
    path: Path
    cfg: dict


def iter_category_dirs() -> list[Path]:
    ensure_categories_data_directory()
    base = Path(get_base_categories_data_path())
    if not base.exists():
        return []
    out: list[Path] = []
    for entry in base.iterdir():
        if entry.is_dir() and entry.name.startswith("category-"):
            out.append(entry)
    return out


def load_categories() -> list[FsCategory]:
    cats: list[FsCategory] = []
    for cat_dir in iter_category_dirs():
        cfg = _read_json(cat_dir / "config.json")
        if not cfg:
            continue
        cid = cfg.get("id")
        title = cfg.get("title")
        if not isinstance(cid, int) or not isinstance(title, str):
            continue
        if not _is_active(cfg):
            continue
        cats.append(FsCategory(id=cid, title=title, path=cat_dir, cfg=cfg))
    # order: by explicit order then title
    def key(c: FsCategory):
        o = c.cfg.get("order")
        return (o if isinstance(o, (int, float)) else 10**9, c.title.lower())
    cats.sort(key=key)
    return cats


def find_category(category_id: int) -> Optional[FsCategory]:
    for c in load_categories():
        if c.id == category_id:
            return c
    return None


def load_courses(category: FsCategory) -> list[FsCourse]:
    courses: list[FsCourse] = []
    for entry in category.path.iterdir():
        if not entry.is_dir() or not entry.name.startswith("course-"):
            continue
        cfg = _read_json(entry / "config.json")
        if not cfg:
            continue
        cid = cfg.get("id")
        title = cfg.get("title")
        if not isinstance(cid, int) or not isinstance(title, str):
            continue
        if not _is_active(cfg):
            continue
        courses.append(FsCourse(id=cid, title=title, category_id=category.id, path=entry, cfg=cfg))
    def key(crs: FsCourse):
        o = crs.cfg.get("order")
        return (o if isinstance(o, (int, float)) else 10**9, crs.title.lower())
    courses.sort(key=key)
    return courses


def find_course(course_id: int) -> Optional[FsCourse]:
    for cat in load_categories():
        for course in load_courses(cat):
            if course.id == course_id:
                return course
    return None


def load_lessons(course: FsCourse) -> list[FsLesson]:
    lessons: list[FsLesson] = []
    for entry in course.path.iterdir():
        if not entry.is_dir() or not entry.name.startswith("lesson-"):
            continue
        cfg = _read_json(entry / "config.json")
        if not cfg:
            continue
        lid = cfg.get("id")
        title = cfg.get("title")
        if not isinstance(lid, int) or not isinstance(title, str):
            continue
        if not _is_active(cfg):
            continue
        lessons.append(FsLesson(id=lid, title=title, category_id=course.category_id, course_id=course.id, path=entry, cfg=cfg))
    # Prefer lesson_number if present, else order, else title
    def key(ls: FsLesson):
        ln = ls.cfg.get("lesson_number")
        o = ls.cfg.get("order")
        if isinstance(ln, (int, float)):
            return (0, int(ln))
        if isinstance(o, (int, float)):
            return (1, int(o))
        return (2, ls.title.lower())
    lessons.sort(key=key)
    return lessons


def find_lesson(lesson_id: int) -> Optional[FsLesson]:
    for cat in load_categories():
        for course in load_courses(cat):
            for lesson in load_lessons(course):
                if lesson.id == lesson_id:
                    return lesson
    return None


def to_public_dict(cfg: dict, extra: Optional[dict] = None) -> dict:
    """Отдаём cfg как есть + extra. Используем для совместимости с фронтом."""
    d = dict(cfg)
    if extra:
        d.update(extra)
    return d

