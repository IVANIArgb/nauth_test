"""Healthz must work with HOSTING_STRICT_SSO (Docker healthcheck)."""
from backend import create_app


def test_healthz_no_sso_header_ok():
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
        }
    )
    c = app.test_client()
    assert c.get("/healthz").status_code == 200
    assert c.get("/user/info-test").status_code == 401
