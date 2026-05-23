"""Проверки конфигурации для режима HOSTING_MODE (контейнер на сервере)."""
from __future__ import annotations

import logging
import os

logger = logging.getLogger(__name__)


def hosting_mode_enabled() -> bool:
    return (os.environ.get("HOSTING_MODE") or "").strip().lower() in ("true", "1", "yes", "on")


def strict_sso_enabled() -> bool:
    return (os.environ.get("HOSTING_STRICT_SSO") or "").strip().lower() in ("true", "1", "yes", "on")


def validate_hosting_config(app) -> None:
    if not hosting_mode_enabled():
        return

    errors: list[str] = []

    if not app.config.get("TRUST_REMOTE_USER"):
        errors.append("TRUST_REMOTE_USER must be true")

    ldap_on = app.config.get("LDAP_ENABLED")
    has_server = bool((app.config.get("LDAP_SERVER") or "").strip())
    has_base = bool((app.config.get("LDAP_BASE_DN") or "").strip())
    ldap_pass = (app.config.get("LDAP_PASSWORD") or "").strip()
    ldap_pass_bad = not ldap_pass or ldap_pass.lower() in (
        "пароль_службы",
        "password",
        "replace",
        "example",
    ) or "пароль" in ldap_pass.lower() and "служб" in ldap_pass.lower()
    has_bind = bool(
        (app.config.get("LDAP_USER") or app.config.get("LDAP_BIND_DN") or "").strip()
        and ldap_pass
        and not ldap_pass_bad
    )
    if not (ldap_on and has_server and has_base and has_bind):
        errors.append(
            "LDAP_ENABLED, LDAP_SERVER, LDAP_BASE_DN, LDAP_USER/LDAP_BIND_DN, LDAP_PASSWORD required"
        )

    if app.config.get("DOCKER_AUTH_FALLBACK"):
        errors.append("DOCKER_AUTH_FALLBACK must be false on hosting")

    if app.config.get("TEST_MODE"):
        errors.append("TEST_MODE must be false on hosting")

    if errors:
        msg = "HOSTING_MODE config invalid: " + "; ".join(errors)
        logger.error(msg)
        raise RuntimeError(msg)

    logger.info(
        "HOSTING_MODE: SSO headers + LDAP profile per user (no keytab, no host AD cache)"
    )
