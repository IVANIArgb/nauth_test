"""
Модели базы данных для системы управления пользователями и курсами.
"""

from datetime import datetime, timedelta
import os
import json
from typing import List, Optional
from sqlalchemy import create_engine, Column, Integer, String, DateTime, ForeignKey, Boolean, Text, UniqueConstraint
from sqlalchemy import text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from sqlalchemy.sql import func

Base = declarative_base()

# Срок хранения объектов в корзине до окончательного удаления (дней)
BIN_RETENTION_DAYS = 30


class User(Base):
    """Единая модель пользователя с данными из Active Directory и Kerberos."""
    __tablename__ = 'users'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(100), unique=True, nullable=False, index=True)
    
    # ФИО
    full_name = Column(String(200), nullable=True)
    surname = Column(String(100), nullable=True)  # Фамилия
    fst_name = Column(String(100), nullable=True)  # Имя
    sec_name = Column(String(100), nullable=True)  # Отчество
    
    # Рабочая информация
    department = Column(String(100), nullable=False, default='')
    position = Column(String(100), nullable=True)  # Должность
    email = Column(String(200), unique=True, nullable=True)
    
    # Kerberos информация
    principal = Column(String(200), nullable=True, index=True)  # username@REALM
    realm = Column(String(100), nullable=True, index=True)
    
    # Роль и активность
    # Возможные значения: 'user', 'admin', 'super_admin'
    role = Column(String(20), nullable=False, default='user')
    is_active = Column(Boolean, default=True)
    
    # Временные метки
    last_login = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    
    # Связи
    course_progress = relationship("UserCourseProgress", back_populates="user", cascade="all, delete-orphan")
    # Вопросы и ответы пользователя
    questions = relationship("Question", back_populates="author", cascade="all, delete-orphan")
    answers = relationship("Answer", back_populates="author", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<User(username='{self.username}', full_name='{self.full_name}', department='{self.department}')>"
    
    def to_dict(self):
        """Преобразование в словарь для JSON."""
        return {
            'id': self.id,
            'username': self.username,
            'full_name': self.full_name or self._get_full_name_from_parts(),
            'surname': self.surname or '',
            'fst_name': self.fst_name or '',
            'sec_name': self.sec_name or '',
            'department': self.department,
            'position': self.position or '',
            'email': self.email,
            'principal': self.principal or '',
            'realm': self.realm or '',
            'role': self.role,
            'is_active': self.is_active,
            'last_login': self.last_login.isoformat() if self.last_login else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'courses_completed': len([cp for cp in self.course_progress if cp.is_completed]),
            'total_lessons_completed': sum(cp.lessons_completed for cp in self.course_progress)
        }
    
    def _get_full_name_from_parts(self) -> str:
        """Собирает полное имя из частей."""
        parts = []
        if self.surname:
            parts.append(self.surname)
        if self.fst_name:
            parts.append(self.fst_name)
        if self.sec_name:
            parts.append(self.sec_name)
        return ' '.join(parts) if parts else ''


class Category(Base):
    """Модель категории курсов."""
    __tablename__ = 'categories'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    order = Column(Integer, default=0)
    sequential_progression = Column(Boolean, default=False)  # последовательное прохождение курсов внутри категории
    is_active = Column(Boolean, default=True)
    path_identifier = Column(String(500), nullable=True, index=True)  # Идентификатор пути, например: 'category-microsoft'
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    
    # Связи
    courses = relationship("Course", back_populates="category", cascade="all, delete-orphan", order_by="Course.order")
    
    def __repr__(self):
        return f"<Category(title='{self.title}', order={self.order})>"
    
    def to_dict(self):
        """Преобразование в словарь для JSON."""
        return {
            'id': self.id,
            'title': self.title,
            'description': self.description,
            'order': self.order,
            'sequential_progression': getattr(self, 'sequential_progression', False),
            'is_active': self.is_active,
            'path_identifier': getattr(self, 'path_identifier', None),
            'courses_count': len([c for c in self.courses if c.is_active]),
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }


class Course(Base):
    """Модель курса."""
    __tablename__ = 'courses'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    category_id = Column(Integer, ForeignKey('categories.id'), nullable=False, index=True)
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    total_lessons = Column(Integer, default=0)
    order = Column(Integer, default=0)
    sequential_progression = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)
    path_identifier = Column(String(500), nullable=True, index=True)  # Идентификатор пути, например: 'category-microsoft/course-word'
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    
    # Связи
    category = relationship("Category", back_populates="courses")
    user_progress = relationship("UserCourseProgress", back_populates="course", cascade="all, delete-orphan")
    lessons = relationship("Lesson", back_populates="course", cascade="all, delete-orphan", order_by="Lesson.lesson_number")
    department_access = relationship("CourseDepartmentAccess", back_populates="course", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<Course(title='{self.title}', category_id={self.category_id}, total_lessons={self.total_lessons})>"
    
    def to_dict(self):
        """Преобразование в словарь для JSON."""
        return {
            'id': self.id,
            'category_id': self.category_id,
            'category_title': self.category.title if self.category else None,
            'title': self.title,
            'description': self.description,
            'total_lessons': self.total_lessons,
            'order': self.order,
            'sequential_progression': self.sequential_progression,
            'is_active': self.is_active,
            'path_identifier': getattr(self, 'path_identifier', None),
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'users_enrolled': len(self.user_progress)
        }


class Lesson(Base):
    """Модель урока."""
    __tablename__ = 'lessons'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    course_id = Column(Integer, ForeignKey('courses.id'), nullable=False)
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    lesson_number = Column(Integer, nullable=False)
    content = Column(Text, nullable=True)
    file_path = Column(String(500), nullable=True)
    path_identifier = Column(String(500), nullable=True, index=True)  # Идентификатор пути, например: 'category-microsoft/course-word/lesson-5'
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    
    # Связи
    course = relationship("Course", back_populates="lessons")
    user_progress = relationship("UserLessonProgress", back_populates="lesson", cascade="all, delete-orphan")
    content_blocks = relationship("LessonContentBlock", back_populates="lesson", cascade="all, delete-orphan", order_by="LessonContentBlock.order")
    
    def __repr__(self):
        return f"<Lesson(title='{self.title}', course_id={self.course_id}, lesson_number={self.lesson_number})>"
    
    def to_dict(self):
        """Преобразование в словарь для JSON."""
        return {
            'id': self.id,
            'course_id': self.course_id,
            'title': self.title,
            'description': self.description,
            'lesson_number': self.lesson_number,
            'content': self.content,
            'file_path': self.file_path,
            'path_identifier': getattr(self, 'path_identifier', None),
            'is_active': self.is_active,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'content_blocks': [block.to_dict() for block in self.content_blocks]
        }


class UserCourseProgress(Base):
    """Модель прогресса пользователя по курсу."""
    __tablename__ = 'user_course_progress'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    course_id = Column(Integer, ForeignKey('courses.id'), nullable=False)
    lessons_completed = Column(Integer, default=0)
    is_completed = Column(Boolean, default=False)
    started_at = Column(DateTime, default=func.now())
    completed_at = Column(DateTime, nullable=True)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    
    # Связи
    user = relationship("User", back_populates="course_progress")
    course = relationship("Course", back_populates="user_progress")
    
    def __repr__(self):
        return f"<UserCourseProgress(user_id={self.user_id}, course_id={self.course_id}, lessons_completed={self.lessons_completed})>"
    
    def to_dict(self):
        """Преобразование в словарь для JSON."""
        return {
            'id': self.id,
            'user_id': self.user_id,
            'course_id': self.course_id,
            'lessons_completed': self.lessons_completed,
            'is_completed': self.is_completed,
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'progress_percentage': self.get_progress_percentage()
        }
    
    def get_progress_percentage(self):
        """Получить процент выполнения курса."""
        if not self.course or self.course.total_lessons == 0:
            return 0
        return round((self.lessons_completed / self.course.total_lessons) * 100, 2)


# Статусы урока для пользователя: 0=незаходил, 1=недопрошел, 2=прошел
LESSON_STATUS_NOT_VISITED = 0
LESSON_STATUS_IN_PROGRESS = 1
LESSON_STATUS_COMPLETED = 2


class UserLessonProgress(Base):
    """Модель прогресса пользователя по уроку."""
    __tablename__ = 'user_lesson_progress'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    lesson_id = Column(Integer, ForeignKey('lessons.id'), nullable=False)
    is_completed = Column(Boolean, default=False)  # deprecated, use lesson_status
    lesson_status = Column(Integer, default=LESSON_STATUS_IN_PROGRESS)  # 0=незаходил, 1=недопрошел, 2=прошел
    completed_at = Column(DateTime, nullable=True)
    time_spent = Column(Integer, default=0)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    
    # Связи
    user = relationship("User")
    lesson = relationship("Lesson", back_populates="user_progress")
    
    @property
    def is_completed_prop(self):
        """Совместимость: completed если lesson_status==2 или is_completed."""
        return self.lesson_status == LESSON_STATUS_COMPLETED or self.is_completed
    
    def __repr__(self):
        return f"<UserLessonProgress(user_id={self.user_id}, lesson_id={self.lesson_id}, lesson_status={self.lesson_status})>"
    
    def to_dict(self):
        """Преобразование в словарь для JSON."""
        return {
            'id': self.id,
            'user_id': self.user_id,
            'lesson_id': self.lesson_id,
            'is_completed': self.lesson_status == LESSON_STATUS_COMPLETED or self.is_completed,
            'lesson_status': getattr(self, 'lesson_status', LESSON_STATUS_COMPLETED if self.is_completed else LESSON_STATUS_IN_PROGRESS),
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'time_spent': self.time_spent,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }


class LessonContentBlock(Base):
    """Блок контента урока (текст, видео, файл, изображение, тест)."""
    __tablename__ = 'lesson_content_blocks'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    lesson_id = Column(Integer, ForeignKey('lessons.id'), nullable=False, index=True)
    block_type = Column(String(50), nullable=False)  # 'heading', 'text', 'video', 'file', 'image'
    content = Column(Text, nullable=True)  # JSON
    order = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    
    # Связи
    lesson = relationship("Lesson", back_populates="content_blocks")
    
    def __repr__(self):
        return f"<LessonContentBlock(lesson_id={self.lesson_id}, block_type='{self.block_type}', order={self.order})>"
    
    def to_dict(self):
        """Преобразование в словарь для JSON."""
        content = None
        if self.content:
            try:
                content = json.loads(self.content)
            except (json.JSONDecodeError, TypeError):
                content = None
        return {
            'id': self.id,
            'lesson_id': self.lesson_id,
            'block_type': self.block_type,
            'content': content,
            'order': self.order,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }


class LessonTestResult(Base):
    """Результаты прохождения теста в конкретном блоке урока."""
    __tablename__ = 'lesson_test_results'

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False, index=True)
    lesson_id = Column(Integer, ForeignKey('lessons.id'), nullable=False, index=True)
    block_id = Column(Integer, ForeignKey('lesson_content_blocks.id'), nullable=False, index=True)
    attempt_number = Column(Integer, nullable=False, default=1)
    score = Column(Integer, nullable=False, default=0)
    total = Column(Integer, nullable=False, default=0)
    score_percent = Column(Integer, nullable=False, default=0)
    passed = Column(Boolean, nullable=False, default=False)
    answers = Column(Text, nullable=True)  # JSON с ответами пользователя и подробным фидбеком
    created_at = Column(DateTime, default=func.now())

    def to_dict(self):
        details = None
        if self.answers:
            try:
                details = json.loads(self.answers)
            except (json.JSONDecodeError, TypeError):
                details = None
        return {
            'id': self.id,
            'user_id': self.user_id,
            'lesson_id': self.lesson_id,
            'block_id': self.block_id,
            'attempt_number': self.attempt_number,
            'score': self.score,
            'total': self.total,
            'score_percent': self.score_percent,
            'passed': self.passed,
            'details': details,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


class GlobalTest(Base):
    """Глобальный тест (не привязан к уроку)."""
    __tablename__ = 'global_tests'

    id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)
    settings = Column(Text, nullable=True)  # JSON: pass_percent, limit_attempts, max_attempts, time_limit_seconds, shuffle_*, available_*
    created_by = Column(Integer, ForeignKey('users.id'), nullable=False, index=True)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    author = relationship("User")
    questions = relationship("GlobalTestQuestion", back_populates="test", cascade="all, delete-orphan")

    def _settings_dict(self):
        if not self.settings:
            return {}
        try:
            v = json.loads(self.settings)
            return v if isinstance(v, dict) else {}
        except Exception:
            return {}

    def to_dict(self):
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "is_active": bool(self.is_active),
            "settings": self._settings_dict(),
            "created_by": self.created_by,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class GlobalTestQuestion(Base):
    """Вопрос глобального теста. Держим данные вопроса JSON-ом."""
    __tablename__ = 'global_test_questions'

    id = Column(Integer, primary_key=True, autoincrement=True)
    global_test_id = Column(Integer, ForeignKey('global_tests.id'), nullable=False, index=True)
    order = Column(Integer, nullable=False, default=0, index=True)
    content = Column(Text, nullable=False)  # JSON
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    test = relationship("GlobalTest", back_populates="questions")

    def _parse_content(self):
        if not self.content:
            return {}
        try:
            val = json.loads(self.content)
            return val if isinstance(val, dict) else {}
        except Exception:
            return {}

    def to_public_dict(self, include_correct: bool = False):
        c = self._parse_content()
        if not include_correct:
            c.pop("correct_answer", None)
            c.pop("accepted_answers", None)
        return {
            "id": self.id,
            "order": self.order,
            "content": c,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class GlobalTestResult(Base):
    """Результаты прохождения глобального теста."""
    __tablename__ = 'global_test_results'

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False, index=True)
    global_test_id = Column(Integer, ForeignKey('global_tests.id'), nullable=False, index=True)
    attempt_number = Column(Integer, nullable=False, default=1)
    score = Column(Integer, nullable=False, default=0)
    total = Column(Integer, nullable=False, default=0)
    score_percent = Column(Integer, nullable=False, default=0)
    passed = Column(Boolean, nullable=False, default=False)
    answers = Column(Text, nullable=True)  # JSON
    created_at = Column(DateTime, default=func.now(), index=True)

    user = relationship("User")
    test = relationship("GlobalTest")

    def to_dict(self):
        details = None
        if self.answers:
            try:
                details = json.loads(self.answers)
            except Exception:
                details = None
        return {
            "id": self.id,
            "user_id": self.user_id,
            "global_test_id": self.global_test_id,
            "attempt_number": self.attempt_number,
            "score": self.score,
            "total": self.total,
            "score_percent": self.score_percent,
            "passed": self.passed,
            "details": details,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class NewsEvent(Base):
    """Событие ленты новостей (обновления контента, новые тесты и т.д.)."""
    __tablename__ = 'news_events'

    id = Column(Integer, primary_key=True, autoincrement=True)
    event_type = Column(String(80), nullable=False, index=True)
    title = Column(String(255), nullable=False)
    body = Column(Text, nullable=True)
    meta = Column(Text, nullable=True)  # JSON
    created_by = Column(Integer, ForeignKey('users.id'), nullable=False, index=True)
    created_at = Column(DateTime, default=func.now(), index=True)

    author = relationship("User")

    def to_dict(self):
        meta_val = None
        if self.meta:
            try:
                meta_val = json.loads(self.meta)
            except Exception:
                meta_val = None
        return {
            "id": self.id,
            "event_type": self.event_type,
            "title": self.title,
            "body": self.body,
            "meta": meta_val,
            "created_by": self.created_by,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class Question(Base):
    """Модель вопроса пользователя для страницы вопросов."""
    __tablename__ = 'questions'

    id = Column(Integer, primary_key=True, autoincrement=True)
    author_id = Column(Integer, ForeignKey('users.id'), nullable=False, index=True)
    title = Column(String(255), nullable=False)
    body = Column(Text, nullable=False)
    tags = Column(String(500), nullable=True)  # строка тегов, разделённых запятой
    is_resolved = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    # Связи
    author = relationship("User", back_populates="questions")
    answers = relationship("Answer", back_populates="question", cascade="all, delete-orphan")
    attachments = relationship("QuestionAttachment", back_populates="question", cascade="all, delete-orphan")

    def to_dict(self, include_relations: bool = True):
        data = {
            'id': self.id,
            'author_id': self.author_id,
            'author_username': self.author.username if self.author else None,
            'author_full_name': self.author.full_name if self.author else None,
            'author_department': self.author.department if self.author else None,
            'title': self.title,
            'body': self.body,
            'tags': [t.strip() for t in (self.tags or '').split(',') if t.strip()],
            'is_resolved': self.is_resolved,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }
        if include_relations:
            data['attachments'] = [a.to_dict() for a in self.attachments]
            data['answers'] = [ans.to_dict() for ans in self.answers]
        return data


class Answer(Base):
    """Ответ администратора на вопрос."""
    __tablename__ = 'answers'

    id = Column(Integer, primary_key=True, autoincrement=True)
    question_id = Column(Integer, ForeignKey('questions.id'), nullable=False, index=True)
    author_id = Column(Integer, ForeignKey('users.id'), nullable=False, index=True)
    body = Column(Text, nullable=False)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    # Связи
    question = relationship("Question", back_populates="answers")
    author = relationship("User", back_populates="answers")
    attachments = relationship("AnswerAttachment", back_populates="answer", cascade="all, delete-orphan")

    def to_dict(self, include_relations: bool = True):
        data = {
            'id': self.id,
            'question_id': self.question_id,
            'author_id': self.author_id,
            'author_username': self.author.username if self.author else None,
            'author_full_name': self.author.full_name if self.author else None,
            'body': self.body,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }
        if include_relations:
            data['attachments'] = [a.to_dict() for a in self.attachments]
        return data


class QuestionAttachment(Base):
    """Прикреплённый файл к вопросу."""
    __tablename__ = 'question_attachments'

    id = Column(Integer, primary_key=True, autoincrement=True)
    question_id = Column(Integer, ForeignKey('questions.id'), nullable=False, index=True)
    stored_filename = Column(String(255), nullable=False)  # имя файла на диске
    original_filename = Column(String(255), nullable=False)  # исходное имя файла
    mime_type = Column(String(100), nullable=True)
    size_bytes = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=func.now())

    question = relationship("Question", back_populates="attachments")

    def to_dict(self):
        return {
            'id': self.id,
            'question_id': self.question_id,
            'stored_filename': self.stored_filename,
            'original_filename': self.original_filename,
            'mime_type': self.mime_type,
            'size_bytes': self.size_bytes,
            'url': f"/uploads/{self.stored_filename}",
        }


class AnswerAttachment(Base):
    """Прикреплённый файл к ответу."""
    __tablename__ = 'answer_attachments'

    id = Column(Integer, primary_key=True, autoincrement=True)
    answer_id = Column(Integer, ForeignKey('answers.id'), nullable=False, index=True)
    stored_filename = Column(String(255), nullable=False)
    original_filename = Column(String(255), nullable=False)
    mime_type = Column(String(100), nullable=True)
    size_bytes = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=func.now())

    answer = relationship("Answer", back_populates="attachments")

    def to_dict(self):
        return {
            'id': self.id,
            'answer_id': self.answer_id,
            'stored_filename': self.stored_filename,
            'original_filename': self.original_filename,
            'mime_type': self.mime_type,
            'size_bytes': self.size_bytes,
            'url': f"/uploads/{self.stored_filename}",
        }

class DatabaseManager:
    """Менеджер базы данных."""
    
    def __init__(self, database_url: str | None = None):
        # По умолчанию размещаем БД в папке database/users_courses.db (абсолютный путь)
        if not database_url:
            database_dir = os.path.dirname(__file__)
            db_path = os.path.abspath(os.path.join(database_dir, 'users_courses.db'))
            database_url = f"sqlite:///{db_path}"
        engine_kwargs = {"echo": False}
        if database_url.startswith("sqlite"):
            engine_kwargs["connect_args"] = {"check_same_thread": False}
        self.engine = create_engine(database_url, **engine_kwargs)
        if database_url.startswith("sqlite"):

            from sqlalchemy import event

            @event.listens_for(self.engine, "connect")
            def _sqlite_wal(dbapi_connection, connection_record):
                cursor = dbapi_connection.cursor()
                cursor.execute("PRAGMA journal_mode=WAL")
                cursor.close()
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
        
    def _ensure_qa_schema(self):
        """Проверить схему Q&A таблиц для SQLite.
        НЕ удаляет таблицы - только проверяет наличие обязательных колонок.
        Если колонок не хватает, таблица будет пересоздана при следующей миграции.
        """
        # Этот метод больше не удаляет таблицы автоматически
        # Удаление таблиц должно происходить только через явные миграции
        # или через скрипт recreate_databases.py
        pass

    def create_tables(self):
        """
        Создать все таблицы если их нет.
        БЕЗОПАСНО: не удаляет существующие таблицы и данные.
        SQLAlchemy create_all() создает таблицы только если их нет.
        """
        # Просто создаем таблицы - SQLAlchemy не перезапишет существующие
        Base.metadata.create_all(bind=self.engine)

    def cleanup_legacy_tables(self):
        """Удалить устаревшие таблицы (mac_users, kerberos_users)."""
        with self.engine.begin() as conn:
            try:
                # Удаляем таблицу mac_users, если она существует
                conn.execute(text("DROP TABLE IF EXISTS mac_users"))
            except Exception:
                pass
            try:
                # Удаляем старую таблицу kerberos_users (теперь все в users)
                conn.execute(text("DROP TABLE IF EXISTS kerberos_users"))
                conn.execute(text("DELETE FROM sqlite_sequence WHERE name='kerberos_users'"))
            except Exception:
                pass
    
    def get_session(self):
        """Получить сессию базы данных."""
        return self.SessionLocal()
    
    def init_sample_data(self):
        """
        Инициализация БД только реальными пользователями из AD.
        Тестовые данные (курсы, уроки, прогресс, вопросы) не создаются.
        Пользователи создаются автоматически при аутентификации через Kerberos/Windows Auth.
        
        ВАЖНО: Этот метод НЕ удаляет существующие данные!
        Пользователи добавляются только при их первой аутентификации.
        """
        # Метод оставлен для обратной совместимости, но не создает никаких данных
        # Все пользователи создаются автоматически при аутентификации через
        # auth/new_auth.py или simplified_real_kerberos_auth._auto_register_user()


class KerberosSession(Base):
    """Модель для Kerberos сессий"""
    __tablename__ = 'kerberos_sessions'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String(255), nullable=False, unique=True, index=True)
    username = Column(String(100), nullable=False, index=True)
    principal = Column(String(200), nullable=False)
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(Text, nullable=True)
    created_at = Column(DateTime, default=func.now())
    expires_at = Column(DateTime, nullable=False)
    is_active = Column(Boolean, default=True)
    
    def __repr__(self):
        return f"<KerberosSession(session_id='{self.session_id}', username='{self.username}')>"


class DeletedObject(Base):
    """Модель для хранения удаленных объектов (корзина)"""
    __tablename__ = 'deleted_objects'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    object_type = Column(String(50), nullable=False, index=True)  # 'category', 'course', 'lesson'
    object_id = Column(Integer, nullable=False, index=True)
    object_data = Column(Text, nullable=False)  # JSON с данными объекта
    deleted_at = Column(DateTime, default=func.now(), nullable=False, index=True)
    deleted_by = Column(Integer, ForeignKey('users.id'), nullable=True)
    parent_type = Column(String(50), nullable=True)  # тип родительского объекта
    parent_id = Column(Integer, nullable=True)  # ID родительского объекта
    
    def __repr__(self):
        return f"<DeletedObject(type='{self.object_type}', id={self.object_id}, deleted_at='{self.deleted_at}')>"
    
    def to_dict(self):
        """Преобразование в словарь для JSON."""
        object_data = None
        if self.object_data:
            try:
                object_data = json.loads(self.object_data)
            except (json.JSONDecodeError, TypeError):
                object_data = None
        days_left = BIN_RETENTION_DAYS
        if self.deleted_at:
            days_left = max(0, BIN_RETENTION_DAYS - (datetime.now() - self.deleted_at).days)
        return {
            'id': self.id,
            'object_type': self.object_type,
            'object_id': self.object_id,
            'object_data': object_data,
            'deleted_at': self.deleted_at.isoformat() if self.deleted_at else None,
            'deleted_by': self.deleted_by,
            'parent_type': self.parent_type,
            'parent_id': self.parent_id,
            'days_until_permanent_delete': days_left
        }


class CourseDepartmentAccess(Base):
    """Модель для настройки доступа курсов по отделам"""
    __tablename__ = 'course_department_access'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    course_id = Column(Integer, ForeignKey('courses.id'), nullable=False, index=True)
    department = Column(String(100), nullable=False, index=True)
    created_at = Column(DateTime, default=func.now())
    
    # Связи
    course = relationship("Course", back_populates="department_access")
    
    __table_args__ = (
        UniqueConstraint('course_id', 'department', name='uq_course_department'),
    )
    
    def __repr__(self):
        return f"<CourseDepartmentAccess(course_id={self.course_id}, department='{self.department}')>"
    
    def to_dict(self):
        """Преобразование в словарь для JSON."""
        return {
            'id': self.id,
            'course_id': self.course_id,
            'department': self.department,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }


# Глобальный экземпляр менеджера базы данных
# Создается с правильным путем к БД в папке database
db_manager = DatabaseManager()

