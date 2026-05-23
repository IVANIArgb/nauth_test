"""HOSTING_STRICT_SSO: без заголовка SSO — 401, не guest."""
from unittest.mock import patch

import pytest

from backend import create_app


@pytest.fixture
def hosting_client():
    app = create_app(
        {
            "TESTING": True,
            "HOSTING_MODE": True,
            "HOSTING_STRICT_SSO": True,
            "TRUST_REMOTE_USER": True,
            "TRUST_REMOTE_USER_CONFIRM": True,
            "TRUSTED_PROXY_IPS": "*",
            "LDAP_ENABLED": True,
            "LDAP_SERVER": "ldap://dc.example.com",
            "LDAP_BASE_DN": "DC=example,DC=com",
            "LDAP_USER": "svc",
            "LDAP_PASSWORD": "secret",
            "DOCKER_AUTH_FALLBACK": False,
            "TEST_MODE": False,
        }
    )
    return app.test_client()


def test_no_sso_header_returns_401(hosting_client):
    with patch("auth.new_auth.get_username_from_kerberos", return_value=None):
        with patch(
            "auth.new_auth.NewAuth._username_from_trusted_proxy",
            return_value=None,
        ):
            with patch(
                "auth.new_auth.NewAuth._username_from_docker_fallback",
                return_value=None,
            ):
                r = hosting_client.get("/user/info-test")
    assert r.status_code == 401
