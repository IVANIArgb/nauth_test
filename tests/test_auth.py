"""
Тесты аутентификации: Kerberos/AD моки, роли (admin/user), guest, ошибочные сценарии.
"""
import pytest


class TestAuthWithMocks:
    """Аутентификация с замоканными Kerberos и AD."""

    def test_guest_when_no_auth_header(self, client, mock_no_auth):
        """Без заголовка Authorization доступ к API возвращает 401 (неаутентифицированный пользователь)."""
        resp = client.get("/api/current-user")
        assert resp.status_code == 401
        assert resp.get_json().get("error") == "Unauthorized"

    def test_authenticated_user_with_mock(self, app, mock_kerberos_and_ad, sample_user, client):
        """С моком Kerberos при заголовке Negotiate USER возвращается user с ролью user."""
        resp = client.get(
            "/user/info-test",
            headers={"Authorization": "Negotiate FAKE_TOKEN_USER"},
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data.get("authenticated") is True
        assert (data.get("username") or "").lower() == "testuser"
        assert data.get("role") == "user"

    def test_authenticated_admin_with_mock(self, app, mock_kerberos_and_ad, sample_admin, client):
        """С моком Kerberos при заголовке Negotiate ADMIN возвращается пользователь с ролью admin."""
        resp = client.get(
            "/user/info-test",
            headers={"Authorization": "Negotiate FAKE_TOKEN_ADMIN"},
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data.get("authenticated") is True
        assert (data.get("username") or "").lower() == "testadmin"
        assert data.get("role") == "admin"

    def test_guest_gets_401_on_protected_api(self, app, client, mock_no_auth):
        """Без аутентификации запрос к /api возвращает 401."""
        resp = client.get("/api/current-user")
        assert resp.status_code == 401
        data = resp.get_json()
        assert data.get("error") == "Unauthorized"

    def test_authenticated_user_can_access_current_user_api(
        self, app, mock_kerberos_and_ad, sample_user, client
    ):
        """Аутентифицированный user может вызвать /api/current-user."""
        resp = client.get(
            "/api/current-user",
            headers={"Authorization": "Negotiate FAKE_TOKEN_USER"},
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert (data.get("username") or "").lower() == "testuser"

    def test_user_cannot_access_admin_only_users_list(
        self, app, mock_kerberos_and_ad, sample_user, client
    ):
        """Роль user не может получить список пользователей (admin only)."""
        resp = client.get(
            "/api/users",
            headers={"Authorization": "Negotiate FAKE_TOKEN_USER"},
        )
        assert resp.status_code == 403
        data = resp.get_json()
        assert data.get("error") == "Forbidden"

    def test_admin_can_access_users_list(
        self, app, mock_kerberos_and_ad, sample_admin, client
    ):
        """Роль admin может получить список пользователей."""
        resp = client.get(
            "/api/users",
            headers={"Authorization": "Negotiate FAKE_TOKEN_ADMIN"},
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert "users" in data
        assert "pagination" in data


class TestAuthEdgeCases:
    """Граничные и ошибочные сценарии аутентификации."""

    def test_user_info_test_without_auth(self, app, client, mock_no_auth):
        """Без аутентификации: /user/info-test либо 401, либо 200 с guest."""
        resp = client.get("/user/info-test")
        data = resp.get_json() or {}
        if resp.status_code == 401:
            assert "error" in data or "аутентифицирован" in (data.get("error") or "")
        else:
            assert resp.status_code == 200
            assert data.get("username") in ("guest", "user") or not data.get("authenticated")

    @pytest.mark.parametrize("header", [
        "Basic dXNlcjpwYXNz",
        "Bearer sometoken",
        "",
    ])
    def test_non_negotiate_auth_does_not_authenticate(self, app, client, mock_no_auth, header):
        """Заголовки Basic/Bearer или пустой не считаются Kerberos-аутентификацией (мок всегда None)."""
        headers = {"Authorization": header} if header else {}
        resp = client.get("/api/current-user", headers=headers)
        assert resp.status_code == 401

    def test_x_remote_user_ignored_when_trust_disabled(self, app, client, mock_no_auth):
        """Без TRUST_REMOTE_USER заголовок X-Remote-User не даёт сессию (защита от подделки с клиента)."""
        resp = client.get(
            "/api/current-user",
            headers={"X-Remote-User": "attacker"},
        )
        assert resp.status_code == 401

    def test_trusted_remote_user_header_authenticates(self, app, client, mock_no_auth, db_session):
        """С TRUST_REMOTE_USER логин берётся из заголовка прокси (Kerberos-мок возвращает None)."""
        from database.models import User

        app.config["TRUST_REMOTE_USER"] = True
        app.config["REMOTE_USER_HEADERS"] = ["X-Remote-User"]

        u = User(
            username="proxyuser",
            full_name="Proxy User",
            surname="User",
            fst_name="Proxy",
            sec_name="",
            department="IT",
            position="Dev",
            email="proxyuser@company.com",
            principal="proxyuser@EXAMPLE.COM",
            realm="EXAMPLE.COM",
            role="user",
            is_active=True,
        )
        db_session.add(u)
        db_session.commit()

        resp = client.get(
            "/api/current-user",
            headers={"X-Remote-User": "proxyuser"},
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert (data.get("username") or "").lower() == "proxyuser"

    def test_trusted_remote_user_email_form(self, app, client, mock_no_auth, db_session):
        """Заголовок с email: берётся локальная часть до @."""
        from database.models import User

        app.config["TRUST_REMOTE_USER"] = True
        app.config["REMOTE_USER_HEADERS"] = ["Cf-Access-Authenticated-User-Email"]

        u = User(
            username="clouduser",
            full_name="Cloud User",
            surname="User",
            fst_name="Cloud",
            sec_name="",
            department="IT",
            position="Dev",
            email="clouduser@company.com",
            principal="clouduser@EXAMPLE.COM",
            realm="EXAMPLE.COM",
            role="user",
            is_active=True,
        )
        db_session.add(u)
        db_session.commit()

        resp = client.get(
            "/api/current-user",
            headers={"Cf-Access-Authenticated-User-Email": "clouduser@example.com"},
        )
        assert resp.status_code == 200
        assert (resp.get_json().get("username") or "").lower() == "clouduser"
