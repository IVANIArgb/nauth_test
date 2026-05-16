"""SSO через доверенный прокси (без keytab) и кириллический логин."""
import base64

import pytest


@pytest.fixture
def app_trusted_proxy(app_config):
    from backend import create_app

    cfg = dict(app_config)
    cfg.update(
        {
            "TRUST_REMOTE_USER": True,
            "DOCKER_AUTH_FALLBACK": False,
            "KERBEROS_GSSAPI_ENABLED": False,
            "LDAP_ENABLED": False,
            "DOCKER": "1",
        }
    )
    return create_app(env_or_config=cfg)


@pytest.fixture
def client_trusted(app_trusted_proxy):
    return app_trusted_proxy.test_client()


def test_trusted_proxy_cyrillic_b64_login(client_trusted):
    b64 = base64.b64encode("Пользователь".encode("utf-8")).decode("ascii")
    resp = client_trusted.get(
        "/user/info-test",
        headers={"X-Remote-User-B64": b64},
    )
    assert resp.status_code == 200
    assert resp.get_json().get("username") == "пользователь"


def test_trusted_proxy_cyrillic_login(client_trusted):
    resp = client_trusted.get(
        "/user/info-test",
        headers={"X-Remote-User": "Пользователь"},
    )
    assert resp.status_code == 200
    data = resp.get_json()
    assert data.get("username") == "пользователь"
    assert data.get("auth_method") == "trusted_proxy"


def test_negotiate_without_gssapi_is_not_kerberos(client_trusted):
  """Поддельный Negotiate не должен давать kerberos без GSSAPI."""
  resp = client_trusted.get(
      "/api/current-user",
      headers={"Authorization": "Negotiate FAKE_TOKEN_USER"},
  )
  assert resp.status_code == 401


def test_proxy_login_overrides_fake_negotiate(client_trusted):
  resp = client_trusted.get(
      "/api/current-user",
      headers={
          "X-Remote-User": "testadmin",
          "Authorization": "Negotiate FAKE_TOKEN_USER",
      },
  )
  assert resp.status_code == 200
  assert resp.get_json().get("username") == "testadmin"
