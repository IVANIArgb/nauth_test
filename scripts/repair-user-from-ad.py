"""One-shot: refresh SQLite user row from live AD (run on domain Windows PC)."""
from __future__ import annotations

import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
sys.path.insert(0, ROOT)

from backend import create_app
from auth.auth_script import get_user_info_by_login
from auth.new_auth import NewAuth
from database.models import db_manager, User


def main() -> int:
    create_app(os.environ.get("FLASK_ENV", "development"))
    login = (sys.argv[1] if len(sys.argv) > 1 else os.environ.get("USERNAME") or "").strip().lower()
    if not login:
        print("Usage: python scripts/repair-user-from-ad.py [login]")
        return 2
    raw = get_user_info_by_login(login)
    auth = NewAuth()
    auth.realm = auth._effective_realm()
    cleaned = auth._validate_and_clean_ad_info(raw)
    auth._auto_register_user(login, cleaned, force_from_ad=True)
    session = db_manager.get_session()
    try:
        u = session.query(User).filter(User.username == login).first()
        if u:
            print(
                f"OK {u.username}: {u.full_name!r} dept={u.department!r} "
                f"realm={u.realm!r} principal={u.principal!r}"
            )
        else:
            print("User not in DB after register")
            return 1
    finally:
        session.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
