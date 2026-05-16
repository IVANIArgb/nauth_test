import json
from pathlib import Path

import pytest

from database.models import LESSON_STATUS_COMPLETED, UserLessonProgress


def _write_json(p: Path, data: dict) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


def _create_sequential_fs(base: Path) -> None:
    # Структура expected by backend/utils/content_fs.py:
    # categories-data/category-*/course-*/lesson-*/config.json
    cat_dir = base / "category-test"
    course_dir = cat_dir / "course-test"
    lesson1_dir = course_dir / "lesson-1"
    lesson2_dir = course_dir / "lesson-2"

    _write_json(cat_dir / "config.json", {"id": 1, "title": "Cat", "order": 0, "is_active": True})
    _write_json(
        course_dir / "config.json",
        {
            "id": 1,
            "title": "Course",
            "order": 0,
            "sequential_progression": True,
            "is_active": True,
            "description": "",
            "total_lessons": 2,
        },
    )

    _write_json(lesson1_dir / "config.json", {"id": 1, "title": "Lesson 1", "lesson_number": 1, "is_active": True})
    _write_json(lesson2_dir / "config.json", {"id": 2, "title": "Lesson 2", "lesson_number": 2, "is_active": True})

    # Контент тестов на lesson 2 (question содержит CORRECT для утечки, но мы не парсим это — только проверяем доступ)
    q1_path = lesson2_dir / "tests" / "block-1" / "questions" / "q001.txt"
    q1_path.parent.mkdir(parents=True, exist_ok=True)
    q1_path.write_text(
        "Q: Тест\nA) A\nB) B\nPOINTS: 1\nTYPE: single\nCORRECT: A\n",
        encoding="utf-8",
    )


@pytest.mark.parametrize(
    "url",
    ["/categories-data/category-test/course-test/lesson-2/tests/block-1/questions/q001.txt"],
)
def test_categories_data_tests_requires_auth(client, mock_no_auth, monkeypatch, tmp_path, url):
    # Подменяем базовый путь categories-data на временный.
    from backend.utils import categories_data_sync as cds

    base = tmp_path / "categories-data"
    monkeypatch.setattr(cds, "BASE_CATEGORIES_DATA_PATH", str(base), raising=False)

    _create_sequential_fs(base)

    resp = client.get(url)
    assert resp.status_code == 401


def test_categories_data_tests_sequential_gate_user_denied(
    client,
    mock_kerberos_and_ad,
    sample_user,
    monkeypatch,
    tmp_path,
):
    from backend.utils import categories_data_sync as cds

    base = tmp_path / "categories-data"
    monkeypatch.setattr(cds, "BASE_CATEGORIES_DATA_PATH", str(base), raising=False)
    _create_sequential_fs(base)

    # User без прогресса по Lesson 1 не должен видеть tests Lesson 2.
    resp = client.get(
        "/categories-data/category-test/course-test/lesson-2/tests/block-1/questions/q001.txt",
        headers={"Authorization": "Negotiate FAKE_TOKEN_USER"},
    )
    assert resp.status_code == 403


def test_categories_data_tests_sequential_gate_user_allowed(
    client,
    mock_kerberos_and_ad,
    sample_user,
    db_session,
    monkeypatch,
    tmp_path,
):
    from backend.utils import categories_data_sync as cds

    base = tmp_path / "categories-data"
    monkeypatch.setattr(cds, "BASE_CATEGORIES_DATA_PATH", str(base), raising=False)
    _create_sequential_fs(base)

    # Отмечаем Lesson 1 как завершенный — тогда Lesson 2 становится доступным по последовательности.
    p = UserLessonProgress(
        user_id=sample_user.id,
        lesson_id=1,
        lesson_status=LESSON_STATUS_COMPLETED,
        is_completed=False,
    )
    db_session.add(p)
    db_session.commit()

    resp = client.get(
        "/categories-data/category-test/course-test/lesson-2/tests/block-1/questions/q001.txt",
        headers={"Authorization": "Negotiate FAKE_TOKEN_USER"},
    )
    assert resp.status_code == 200

