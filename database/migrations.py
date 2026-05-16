from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, List

from sqlalchemy import text, inspect


@dataclass(frozen=True)
class Migration:
    id: str
    run: Callable


def _ensure_migrations_table(conn) -> None:
    conn.execute(
        text(
            """
            CREATE TABLE IF NOT EXISTS schema_migrations (
              id TEXT PRIMARY KEY,
              applied_at TEXT NOT NULL DEFAULT (datetime('now'))
            )
            """
        )
    )


def _already_applied(conn, migration_id: str) -> bool:
    row = conn.execute(
        text("SELECT 1 FROM schema_migrations WHERE id = :id LIMIT 1"),
        {"id": migration_id},
    ).fetchone()
    return bool(row)


def _mark_applied(conn, migration_id: str) -> None:
    conn.execute(
        text("INSERT INTO schema_migrations (id) VALUES (:id)"),
        {"id": migration_id},
    )


def _sqlite_has_column(inspector, table: str, column: str) -> bool:
    try:
        cols = [c.get("name") for c in inspector.get_columns(table)]
        return column in cols
    except Exception:
        return False


def _m_0001_qa_indexes(conn, inspector) -> None:
    if inspector.bind.dialect.name != "sqlite":
        return
    # Индексы для Q&A (ускоряют сортировку и фильтры на /api/questions).
    conn.execute(text("CREATE INDEX IF NOT EXISTS ix_questions_created_at ON questions(created_at DESC)"))
    conn.execute(text("CREATE INDEX IF NOT EXISTS ix_questions_author_created_at ON questions(author_id, created_at DESC)"))
    conn.execute(text("CREATE INDEX IF NOT EXISTS ix_questions_is_resolved_created_at ON questions(is_resolved, created_at DESC)"))
    conn.execute(text("CREATE INDEX IF NOT EXISTS ix_answers_question_created_at ON answers(question_id, created_at ASC)"))
    conn.execute(text("CREATE INDEX IF NOT EXISTS ix_question_attachments_question_id ON question_attachments(question_id)"))
    conn.execute(text("CREATE INDEX IF NOT EXISTS ix_answer_attachments_answer_id ON answer_attachments(answer_id)"))


def _m_0002_add_lesson_status(conn, inspector) -> None:
    if inspector.bind.dialect.name != "sqlite":
        return
    if not _sqlite_has_column(inspector, "user_lesson_progress", "lesson_status"):
        conn.execute(text("ALTER TABLE user_lesson_progress ADD COLUMN lesson_status INTEGER DEFAULT 1"))
        conn.execute(text("UPDATE user_lesson_progress SET lesson_status = 2 WHERE is_completed = 1"))


def _m_0003_add_sequential_progression(conn, inspector) -> None:
    if inspector.bind.dialect.name != "sqlite":
        return
    if not _sqlite_has_column(inspector, "categories", "sequential_progression"):
        conn.execute(text("ALTER TABLE categories ADD COLUMN sequential_progression BOOLEAN DEFAULT 0"))


def _migrations() -> List[Migration]:
    return [
        Migration("0001_qa_indexes", _m_0001_qa_indexes),
        Migration("0002_add_lesson_status", _m_0002_add_lesson_status),
        Migration("0003_add_sequential_progression", _m_0003_add_sequential_progression),
    ]


def apply_soft_migrations(engine) -> None:
    """
    Безопасные "мягкие" миграции.

    - идемпотентно (можно запускать много раз)
    - защищено от конкуренции в SQLite через транзакцию BEGIN IMMEDIATE
    - фиксируем применённые миграции в schema_migrations
    """
    with engine.connect() as conn:
        # Для SQLite берём write-lock сразу, чтобы 2 воркера не делали ALTER одновременно.
        if engine.dialect.name == "sqlite":
            conn.execute(text("BEGIN IMMEDIATE"))
        else:
            conn.execute(text("BEGIN"))
        try:
            _ensure_migrations_table(conn)
            inspector = inspect(conn)
            for m in _migrations():
                if _already_applied(conn, m.id):
                    continue
                m.run(conn, inspector)
                _mark_applied(conn, m.id)
            conn.execute(text("COMMIT"))
        except Exception:
            conn.execute(text("ROLLBACK"))
            raise
