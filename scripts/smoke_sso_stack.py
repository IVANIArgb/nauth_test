#!/usr/bin/env python3
"""Проверка SSO-логики без Docker (Flask test client)."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend import create_app


def main() -> int:
    app = create_app(
        env_or_config={
            "TESTING": True,
            "FLASK_ENV": "testing",
            "SECRET_KEY": "smoke",
            "TRUST_REMOTE_USER": True,
            "DOCKER_AUTH_FALLBACK": False,
            "KERBEROS_GSSAPI_ENABLED": False,
            "LDAP_ENABLED": False,
            "DOCKER": "1",
            "PROJECT_ROOT": str(ROOT),
            "ALLOWED_PAGE_DIRS": ["main-pg"],
            "ADMIN_TEMPLATE_DIR": "frontend/admin-pages",
            "USER_TEMPLATE_DIR": "frontend/user-pages",
            "SHARED_TEMPLATE_DIR": "frontend/shared-pages",
            "ADMIN_TEMPLATES_DIR": "frontend/admin-pages/templates",
            "USER_TEMPLATES_DIR": "frontend/user-pages/templates",
        }
    )
    client = app.test_client()

    r = client.get("/api/current-user", headers={"X-Remote-User": "Пользователь"})
    if r.status_code != 200:
        print("FAIL: trusted proxy cyrillic", r.status_code, r.get_data(as_text=True))
        return 1
    j = r.get_json() or {}
    if j.get("username") != "пользователь":
        print("FAIL: username", j)
        return 1

    r2 = client.get("/api/current-user", headers={"Authorization": "Negotiate FAKE"})
    if r2.status_code != 401:
        print("FAIL: negotiate should not auth", r2.status_code)
        return 1

    print("OK: SSO proxy auth smoke passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
