"""
⚠️ УСТАРЕВШИЙ ФАЙЛ - НЕ ИСПОЛЬЗУЕТСЯ ⚠️

Этот файл устарел и больше не используется.
Все модели теперь находятся в database/models.py

Для обратной совместимости импортируем все из database.models
"""

# Импортируем все из database.models для обратной совместимости
from database.models import (
    Base,
    User,
    Category,
    Course,
    Lesson,
    UserCourseProgress,
    UserLessonProgress,
    LessonContentBlock,
    Question,
    Answer,
    QuestionAttachment,
    AnswerAttachment,
    DeletedObject,
    CourseDepartmentAccess,
    KerberosSession,
    DatabaseManager,
    db_manager
)

__all__ = [
    'Base',
    'User',
    'Category',
    'Course',
    'Lesson',
    'UserCourseProgress',
    'UserLessonProgress',
    'LessonContentBlock',
    'Question',
    'Answer',
    'QuestionAttachment',
    'AnswerAttachment',
    'DeletedObject',
    'CourseDepartmentAccess',
    'KerberosSession',
    'DatabaseManager',
    'db_manager'
]
