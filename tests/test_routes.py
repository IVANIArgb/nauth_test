"""
Тесты маршрутов: healthz, debug/auth, ролевые страницы, /user/info-test, ошибки.
"""
import pytest


class TestHealthAndDebug:
    """Системные и отладочные эндпоинты."""

    def test_healthz_returns_200(self, client):
        """Эндпоинт /healthz доступен без аутентификации и возвращает status ok."""
        resp = client.get("/healthz")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data.get("status") == "ok"

    def test_debug_auth_available_in_testing(self, app, client, mock_kerberos_and_ad, sample_user):
        """В режиме TESTING эндпоинт /debug/auth доступен и возвращает JSON."""
        assert app.config.get("TESTING") is True
        resp = client.get(
            "/debug/auth",
            headers={"Authorization": "Negotiate FAKE_TOKEN_USER"},
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert "user_info" in data
        assert "config" in data

    def test_root_redirects_to_main(self, client):
        """Корневой URL перенаправляет на /main-pg/."""
        resp = client.get("/", follow_redirects=False)
        assert resp.status_code == 302
        assert "main-pg" in (resp.headers.get("Location") or "")


class TestRoleBasedPages:
    """Доступ к страницам в зависимости от роли (admin vs user)."""

    def test_main_page_as_user(self, app, client, mock_kerberos_and_ad, sample_user):
        """Роль user видит страницы из frontend/user-pages (главная страница отдаётся)."""
        resp = client.get(
            "/main-pg/",
            headers={"Authorization": "Negotiate FAKE_TOKEN_USER"},
        )
        assert resp.status_code == 200

    def test_main_page_as_admin(self, app, client, mock_kerberos_and_ad, sample_admin):
        """Роль admin видит страницы из frontend/admin-pages."""
        resp = client.get(
            "/main-pg/",
            headers={"Authorization": "Negotiate FAKE_TOKEN_ADMIN"},
        )
        assert resp.status_code == 200

    def test_bin_page_returns_200_for_authenticated(self, client, mock_kerberos_and_ad, sample_user):
        """Страница корзины доступна аутентифицированному пользователю."""
        resp = client.get(
            "/bin",
            headers={"Authorization": "Negotiate FAKE_TOKEN_USER"},
        )
        assert resp.status_code == 200

    def test_terminal_page_returns_200_for_authenticated(self, client, mock_kerberos_and_ad, sample_user):
        """Страница терминала отдаётся аутентифицированному пользователю."""
        resp = client.get(
            "/terminal",
            headers={"Authorization": "Negotiate FAKE_TOKEN_USER"},
        )
        assert resp.status_code == 200
        assert b"terminal-input" in resp.data


class TestUserInfoEndpoint:
    """Эндпоинт /user/info-test."""

    def test_returns_json_with_role_and_username(
        self, client, mock_kerberos_and_ad, sample_user
    ):
        """Ответ содержит username, role, authenticated."""
        resp = client.get(
            "/user/info-test",
            headers={"Authorization": "Negotiate FAKE_TOKEN_USER"},
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert "username" in data
        assert "role" in data
        assert data.get("authenticated") is True


class TestErrorHandling:
    """Обработка ошибок (404, 500 в тестовом режиме)."""

    def test_404_returns_json(self, client):
        """Несуществующий маршрут возвращает JSON с ошибкой."""
        resp = client.get("/nonexistent-page-route-xyz")
        assert resp.status_code == 404
        data = resp.get_json()
        assert data is not None
        assert "error" in data or "message" in data

    def test_trigger_error_500_in_testing(self, app, client):
        """В режиме TESTING эндпоинт __trigger_error вызывает 500 с traceback."""
        if not app.config.get("TESTING"):
            pytest.skip("Only in TESTING")
        resp = client.get("/__trigger_error")
        assert resp.status_code == 500
        data = resp.get_json()
        assert data is not None
        if app.config.get("TESTING"):
            assert "traceback" in data or "message" in data
