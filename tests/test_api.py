"""
Тесты API: 401 без аутентификации, 403 для user на admin-only эндпоинтах,
успешные ответы для admin и user на разрешённых эндпоинтах.
"""
import pytest


class TestAPIUnauthenticated:
    """Все запросы к /api без аутентификации возвращают 401."""

    @pytest.mark.parametrize("method,url", [
        ("GET", "/api/current-user"),
        ("GET", "/api/users"),
        ("GET", "/api/courses"),
        ("GET", "/api/categories"),
        ("GET", "/api/questions"),
    ])
    def test_api_returns_401_without_auth(self, client, mock_no_auth, method, url):
        """Без аутентификации API возвращает 401 (мок отключает Windows/Kerberos)."""
        if method == "GET":
            resp = client.get(url)
        else:
            resp = client.get(url)
        assert resp.status_code == 401, f"Expected 401 for {url}, got {resp.status_code}"
        data = resp.get_json()
        assert data.get("error") == "Unauthorized"


class TestAPIAdminOnly:
    """Эндпоинты только для admin: 403 для user, 200 для admin."""

    def test_get_users_requires_admin(
        self, client, mock_kerberos_and_ad, sample_user, sample_admin
    ):
        """GET /api/users доступен только admin."""
        resp_user = client.get(
            "/api/users",
            headers={"Authorization": "Negotiate FAKE_TOKEN_USER"},
        )
        assert resp_user.status_code == 403
        assert resp_user.get_json().get("error") == "Forbidden"

        resp_admin = client.get(
            "/api/users",
            headers={"Authorization": "Negotiate FAKE_TOKEN_ADMIN"},
        )
        assert resp_admin.status_code == 200
        data = resp_admin.get_json()
        assert "users" in data
        assert "pagination" in data

    def test_get_user_by_id_requires_admin(
        self, client, mock_kerberos_and_ad, sample_user, sample_admin
    ):
        """GET /api/users/<id> доступен только admin."""
        uid = sample_user.id
        resp_user = client.get(
            f"/api/users/{uid}",
            headers={"Authorization": "Negotiate FAKE_TOKEN_USER"},
        )
        assert resp_user.status_code == 403

        resp_admin = client.get(
            f"/api/users/{uid}",
            headers={"Authorization": "Negotiate FAKE_TOKEN_ADMIN"},
        )
        assert resp_admin.status_code == 200
        assert resp_admin.get_json().get("username") == "testuser"

    def test_get_user_progress_requires_admin(
        self, client, mock_kerberos_and_ad, sample_user, sample_admin
    ):
        """GET /api/users/<id>/progress доступен только admin."""
        uid = sample_user.id
        resp_user = client.get(
            f"/api/users/{uid}/progress",
            headers={"Authorization": "Negotiate FAKE_TOKEN_USER"},
        )
        assert resp_user.status_code == 403

        resp_admin = client.get(
            f"/api/users/{uid}/progress",
            headers={"Authorization": "Negotiate FAKE_TOKEN_ADMIN"},
        )
        assert resp_admin.status_code == 200
        data = resp_admin.get_json()
        assert "progress" in data or "username" in data


class TestAPIAllowedForUser:
    """Эндпоинты, доступные аутентифицированному user (не только admin)."""

    def test_current_user_returns_200_for_user(
        self, client, mock_kerberos_and_ad, sample_user
    ):
        """GET /api/current-user возвращает 200 для аутентифицированного user."""
        resp = client.get(
            "/api/current-user",
            headers={"Authorization": "Negotiate FAKE_TOKEN_USER"},
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert (data.get("username") or "").lower() == "testuser"
        assert data.get("role") == "user"

    def test_courses_list_returns_200_for_user(
        self, client, mock_kerberos_and_ad, sample_user
    ):
        """GET /api/courses возвращает 200 для user."""
        resp = client.get(
            "/api/courses",
            headers={"Authorization": "Negotiate FAKE_TOKEN_USER"},
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert "courses" in data or "pagination" in data or isinstance(data, list) or "items" in data

    def test_categories_list_returns_200_for_user(
        self, client, mock_kerberos_and_ad, sample_user
    ):
        """GET /api/categories возвращает 200 для user."""
        resp = client.get(
            "/api/categories",
            headers={"Authorization": "Negotiate FAKE_TOKEN_USER"},
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert isinstance(data, (list, dict))

    def test_questions_list_returns_200_for_user(
        self, client, mock_kerberos_and_ad, sample_user
    ):
        """GET /api/questions возвращает 200 для user."""
        resp = client.get(
            "/api/questions",
            headers={"Authorization": "Negotiate FAKE_TOKEN_USER"},
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert "questions" in data


class TestAPIBinAdminOnly:
    """Корзина: только admin."""

    def test_bin_list_requires_admin(
        self, client, mock_kerberos_and_ad, sample_user, sample_admin
    ):
        """GET /api/bin доступен только admin."""
        resp_user = client.get(
            "/api/bin",
            headers={"Authorization": "Negotiate FAKE_TOKEN_USER"},
        )
        assert resp_user.status_code == 403

        resp_admin = client.get(
            "/api/bin",
            headers={"Authorization": "Negotiate FAKE_TOKEN_ADMIN"},
        )
        assert resp_admin.status_code == 200
        data = resp_admin.get_json()
        assert "deleted_objects" in data or "pagination" in data

    def test_departments_requires_admin(
        self, client, mock_kerberos_and_ad, sample_user, sample_admin
    ):
        """GET /api/departments доступен только admin."""
        resp_user = client.get(
            "/api/departments",
            headers={"Authorization": "Negotiate FAKE_TOKEN_USER"},
        )
        assert resp_user.status_code == 403
        assert resp_user.get_json().get("error") == "Forbidden"

        resp_admin = client.get(
            "/api/departments",
            headers={"Authorization": "Negotiate FAKE_TOKEN_ADMIN"},
        )
        assert resp_admin.status_code == 200
        data = resp_admin.get_json()
        assert "departments" in data

    def test_course_users_requires_admin(
        self, client, mock_kerberos_and_ad, sample_user, sample_admin
    ):
        """GET /api/courses/<id>/users доступен только admin."""
        resp_user = client.get(
            "/api/courses/1/users",
            headers={"Authorization": "Negotiate FAKE_TOKEN_USER"},
        )
        assert resp_user.status_code == 403
        assert resp_user.get_json().get("error") == "Forbidden"


class TestUploadsAuth:
    """Маршрут /uploads/ доступен только аутентифицированным пользователям."""

    def test_uploads_returns_401_without_auth(self, client, mock_no_auth):
        """Без аутентификации /uploads/xxx возвращает 401."""
        resp = client.get("/uploads/somefile.pdf")
        assert resp.status_code == 401
        data = resp.get_json()
        assert "авторизация" in (data.get("error") or "").lower()


class TestTerminalRoleCommand:
    """Команды терминала смены роли (TERMINAL_ROLE_COMMANDS_ENABLED)."""

    def test_terminal_role_403_when_disabled(
        self, app, client, mock_kerberos_and_ad, sample_user
    ):
        """По умолчанию команды отключены."""
        assert not app.config.get("TERMINAL_ROLE_COMMANDS_ENABLED")
        resp = client.post(
            "/api/me/terminal-role-command",
            json={"command": "change-role-admin"},
            headers={"Authorization": "Negotiate FAKE_TOKEN_USER"},
        )
        assert resp.status_code == 403

    def test_terminal_role_admin_when_enabled(
        self, app, client, mock_kerberos_and_ad, sample_user, db_session
    ):
        """Включённый терминал: change-role-admin обновляет роль в БД."""
        app.config["TERMINAL_ROLE_COMMANDS_ENABLED"] = True
        resp = client.post(
            "/api/me/terminal-role-command",
            json={"command": "change-role-admin"},
            headers={"Authorization": "Negotiate FAKE_TOKEN_USER"},
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data.get("ok") is True
        assert data.get("role") == "admin"
        db_session.expire_all()
        from database.models import User

        u = db_session.query(User).filter(User.username == "testuser").first()
        assert u is not None
        assert u.role == "admin"

    def test_terminal_role_super_admin_when_enabled(
        self, app, client, mock_kerberos_and_ad, sample_user
    ):
        """change-role-super-admin назначает super_admin."""
        app.config["TERMINAL_ROLE_COMMANDS_ENABLED"] = True
        resp = client.post(
            "/api/me/terminal-role-command",
            json={"command": "change-role-super-admin"},
            headers={"Authorization": "Negotiate FAKE_TOKEN_USER"},
        )
        assert resp.status_code == 200
        assert resp.get_json().get("role") == "super_admin"

    def test_terminal_unknown_command_400(self, app, client, mock_kerberos_and_ad, sample_user):
        app.config["TERMINAL_ROLE_COMMANDS_ENABLED"] = True
        resp = client.post(
            "/api/me/terminal-role-command",
            json={"command": "hack"},
            headers={"Authorization": "Negotiate FAKE_TOKEN_USER"},
        )
        assert resp.status_code == 400
        names = resp.get_json().get("known_commands") or []
        assert "seed-test-data" in names
        assert "show-settings" in names

    def test_terminal_show_settings_forbidden_for_user(
        self, app, client, mock_kerberos_and_ad, sample_user
    ):
        app.config["TERMINAL_ROLE_COMMANDS_ENABLED"] = True
        resp = client.post(
            "/api/me/terminal-role-command",
            json={"command": "show-settings"},
            headers={"Authorization": "Negotiate FAKE_TOKEN_USER"},
        )
        assert resp.status_code == 403

    def test_terminal_show_settings_super_admin(
        self, app, client, mock_kerberos_and_ad, sample_admin, db_session
    ):
        app.config["TERMINAL_ROLE_COMMANDS_ENABLED"] = True
        sample_admin.role = "super_admin"
        db_session.commit()
        resp = client.post(
            "/api/me/terminal-role-command",
            json={"command": "show-settings"},
            headers={"Authorization": "Negotiate FAKE_TOKEN_ADMIN"},
        )
        assert resp.status_code == 200
        settings = resp.get_json().get("settings") or {}
        assert "TEST_MODE" in settings
        assert "content_path_resolved" in settings

    def test_terminal_list_commands(self, app, client, mock_kerberos_and_ad, sample_user):
        app.config["TERMINAL_ROLE_COMMANDS_ENABLED"] = True
        resp = client.post(
            "/api/me/terminal-role-command",
            json={"command": "list-commands"},
            headers={"Authorization": "Negotiate FAKE_TOKEN_USER"},
        )
        assert resp.status_code == 200
        cmds = resp.get_json().get("commands") or []
        assert any(c.get("command") == "seed-test-data" for c in cmds)

    def test_terminal_seed_test_data_mocked(
        self, app, client, mock_kerberos_and_ad, sample_user, monkeypatch
    ):
        app.config["TERMINAL_ROLE_COMMANDS_ENABLED"] = True
        called = []

        def fake_main():
            called.append(1)

        import seed_test_data

        monkeypatch.setattr(seed_test_data, "main", fake_main)
        resp = client.post(
            "/api/me/terminal-role-command",
            json={"command": "seed-test-data"},
            headers={"Authorization": "Negotiate FAKE_TOKEN_USER"},
        )
        assert resp.status_code == 200
        assert called == [1]
        assert resp.get_json().get("ok") is True

    def test_terminal_commands_enabled_flag(self, app, client, mock_kerberos_and_ad, sample_user):
        """GET /api/me/terminal-commands-enabled отражает конфиг."""
        app.config["TERMINAL_ROLE_COMMANDS_ENABLED"] = True
        resp = client.get(
            "/api/me/terminal-commands-enabled",
            headers={"Authorization": "Negotiate FAKE_TOKEN_USER"},
        )
        assert resp.status_code == 200
        assert resp.get_json().get("enabled") is True
