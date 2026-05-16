"""
Тесты моделей БД: User, Category, Course, сериализация to_dict, хелперы.
"""
import pytest
from datetime import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Импорт после добавления пути в conftest не нужен в каждом файле при запуске pytest
# Модели импортируются внутри тестов с учётом PROJECT_ROOT в conftest


@pytest.fixture
def model_session():
    """Отдельная сессия для тестов моделей (in-memory)."""
    import os
    import sys
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)

    from database.models import Base, DatabaseManager
    manager = DatabaseManager("sqlite:///:memory:")
    Base.metadata.create_all(bind=manager.engine)
    session = manager.get_session()
    try:
        yield session
    finally:
        session.close()


class TestUserModel:
    """Модель User."""

    def test_to_dict_contains_required_fields(self, model_session):
        """to_dict() содержит id, username, role, department."""
        from database.models import User
        user = User(
            username="modeltest",
            full_name="Full Name",
            department="IT",
            role="user",
        )
        model_session.add(user)
        model_session.commit()
        model_session.refresh(user)
        d = user.to_dict()
        assert d["username"] == "modeltest"
        assert d["role"] == "user"
        assert d["department"] == "IT"
        assert "id" in d
        assert "created_at" in d or "last_login" in d

    def test_get_full_name_from_parts(self, model_session):
        """_get_full_name_from_parts собирает ФИО из surname, fst_name, sec_name."""
        from database.models import User
        user = User(
            username="parts",
            surname="Иванов",
            fst_name="Иван",
            sec_name="Иванович",
            department="IT",
            role="user",
        )
        full = user._get_full_name_from_parts()
        assert "Иванов" in full
        assert "Иван" in full
        assert "Иванович" in full

    def test_get_full_name_from_parts_empty(self, model_session):
        """_get_full_name_from_parts возвращает пустую строку если части пустые."""
        from database.models import User
        user = User(username="empty", department="IT", role="user")
        full = user._get_full_name_from_parts()
        assert full == ""


class TestCategoryModel:
    """Модель Category."""

    def test_to_dict_contains_title_and_order(self, model_session):
        """to_dict() содержит title, order, is_active."""
        from database.models import Category
        cat = Category(title="Test Category", order=1, is_active=True)
        model_session.add(cat)
        model_session.commit()
        model_session.refresh(cat)
        d = cat.to_dict()
        assert d["title"] == "Test Category"
        assert d["order"] == 1
        assert d["is_active"] is True


class TestCourseModel:
    """Модель Course."""

    def test_to_dict_contains_title_and_category(self, model_session):
        """to_dict() содержит title, category_id."""
        from database.models import Category, Course
        cat = Category(title="Cat", order=0)
        model_session.add(cat)
        model_session.commit()
        model_session.refresh(cat)
        course = Course(title="Test Course", category_id=cat.id, order=0)
        model_session.add(course)
        model_session.commit()
        model_session.refresh(course)
        d = course.to_dict()
        assert d["title"] == "Test Course"
        assert d["category_id"] == cat.id


class TestUserCourseProgress:
    """Модель UserCourseProgress."""

    def test_get_progress_percentage(self, model_session):
        """get_progress_percentage считает процент по total_lessons курса."""
        from database.models import Category, Course, User, UserCourseProgress
        cat = Category(title="C", order=0)
        model_session.add(cat)
        model_session.commit()
        model_session.refresh(cat)
        course = Course(title="Course", category_id=cat.id, total_lessons=10, order=0)
        model_session.add(course)
        user = User(username="u1", department="IT", role="user")
        model_session.add(user)
        model_session.commit()
        model_session.refresh(course)
        model_session.refresh(user)
        progress = UserCourseProgress(
            user_id=user.id,
            course_id=course.id,
            lessons_completed=5,
        )
        model_session.add(progress)
        model_session.commit()
        model_session.refresh(progress)
        pct = progress.get_progress_percentage()
        assert pct == 50.0
