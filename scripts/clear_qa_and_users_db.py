from __future__ import annotations

import argparse
import os
import shutil
from datetime import datetime
from pathlib import Path


def _now_stamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _db_path() -> Path:
    # database/models.py places default DB at <repo>/database/users_courses.db
    repo_root = Path(__file__).resolve().parents[1]
    return repo_root / "database" / "users_courses.db"


def _uploads_dir() -> Path:
    repo_root = Path(__file__).resolve().parents[1]
    return repo_root / "backend" / "uploads"


def _backup_db(db: Path) -> Path | None:
    if not db.exists():
        return None
    backup_dir = db.parent / "_backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    backup_path = backup_dir / f"users_courses_{_now_stamp()}.db"
    shutil.copy2(db, backup_path)
    return backup_path


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Очистка БД пользователей и Q&A (вопросы/ответы/вложения). Делает бэкап sqlite перед удалением."
    )
    parser.add_argument("--no-backup", action="store_true", help="Не создавать бэкап sqlite файла перед очисткой")
    parser.add_argument(
        "--keep-super-admin",
        action="store_true",
        help="Оставить пользователей с ролью super_admin (остальные будут удалены)",
    )
    parser.add_argument(
        "--purge-uploads",
        action="store_true",
        help="Удалить ВСЕ файлы из backend/uploads (вложения вопросов/ответов)",
    )
    args = parser.parse_args()

    db_file = _db_path()
    if not db_file.exists():
        print(f"DB file not found: {db_file}")
        return 1

    if not args.no_backup:
        backup = _backup_db(db_file)
        print(f"DB backup created: {backup}")
    else:
        print("DB backup skipped (--no-backup).")

    # Import after path checks to keep script fast
    from database.models import db_manager, User, Question, Answer, QuestionAttachment, AnswerAttachment  # type: ignore

    session = db_manager.get_session()
    try:
        # 1) удалить вложения ответов/вопросов
        session.query(AnswerAttachment).delete(synchronize_session=False)
        session.query(QuestionAttachment).delete(synchronize_session=False)
        # 2) удалить ответы/вопросы
        session.query(Answer).delete(synchronize_session=False)
        session.query(Question).delete(synchronize_session=False)

        # 3) удалить пользователей (опционально сохраняя super_admin)
        if args.keep_super_admin:
            session.query(User).filter(User.role != "super_admin").delete(synchronize_session=False)
        else:
            session.query(User).delete(synchronize_session=False)

        session.commit()
        print("DB cleared: questions/answers/attachments + users.")
    except Exception as e:
        session.rollback()
        print(f"ERROR: failed to clear DB: {e}")
        return 2
    finally:
        session.close()

    if args.purge_uploads:
        up = _uploads_dir()
        if up.exists() and up.is_dir():
            removed = 0
            for p in up.glob("*"):
                try:
                    if p.is_file():
                        p.unlink(missing_ok=True)
                        removed += 1
                except Exception:
                    continue
            print(f"Uploads purged: {removed} files removed from {up}")
        else:
            print(f"Uploads dir not found: {up}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

