"""Checks for HOSTING_MODE (container on server)."""
from __future__ import annotations

import logging
import os
import re

logger = logging.getLogger(__name__)

_LDAP_PASS_PLACEHOLDER = re.compile(
    r"^(password|replace|example|parol|)$",
    re.IGNORECASE,
)


def hosting_mode_enabled() -> bool:
    return (os.environ.get("HOSTING_MODE") or "").strip().lower() in ("true", "1", "yes", "on")


def strict_sso_enabled() -> bool:
    return (os.environ.get("HOSTING_STRICT_SSO") or "").strip().lower() in ("true", "1", "yes", "on")


def _require_ldap_bind_at_startup() -> bool:
    return (os.environ.get("HOSTING_REQUIRE_LDAP_BIND") or "").strip().lower() in (
        "true",
        "1",
        "yes",
        "on",
    )


def _ldap_bind_ok(app) -> tuple[bool, list[str]]:
    issues: list[str] = []
    if not app.config.get("LDAP_ENABLED"):
        issues.append("LDAP_ENABLED is false")
        return False, issues

    if not (app.config.get("LDAP_SERVER") or "").strip():
        issues.append("LDAP_SERVER empty")
    if not (app.config.get("LDAP_BASE_DN") or "").strip():
        issues.append("LDAP_BASE_DN empty")

    ldap_pass = (app.config.get("LDAP_PASSWORD") or "").strip()
    ldap_user = (app.config.get("LDAP_USER") or app.config.get("LDAP_BIND_DN") or "").strip()
    if not ldap_user:
        issues.append("LDAP_USER empty")
    if not ldap_pass or _LDAP_PASS_PLACEHOLDER.match(ldap_pass):
        issues.append("LDAP_PASSWORD missing or placeholder")

    return len(issues) == 0, issues


def validate_hosting_config(app) -> None:
    if not hosting_mode_enabled():
        return

    fatal: list[str] = []

    if not app.config.get("TRUST_REMOTE_USER"):
        fatal.append("TRUST_REMOTE_USER must be true")
    if app.config.get("DOCKER_AUTH_FALLBACK"):
        fatal.append("DOCKER_AUTH_FALLBACK must be false on hosting")
    if app.config.get("TEST_MODE"):
        fatal.append("TEST_MODE must be false on hosting")

    ldap_ok, ldap_issues = _ldap_bind_ok(app)
    if not ldap_ok:
        msg = "LDAP not ready: " + "; ".join(ldap_issues)
        if _require_ldap_bind_at_startup():
            fatal.append(msg)
        else:
            logger.warning(
                "%s — container will start; set LDAP_USER/LDAP_PASSWORD in .env and restart for AD profiles",
                msg,
            )

    if fatal:
        text = "HOSTING_MODE config invalid: " + "; ".join(fatal)
        logger.error(text)
        raise RuntimeError(text)

    if ldap_ok:
        logger.info("HOSTING_MODE: SSO headers + LDAP AD profile per user (no keytab)")
    else:
        logger.info("HOSTING_MODE: SSO headers only until LDAP bind is configured")
