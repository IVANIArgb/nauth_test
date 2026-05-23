"""Resolve user profile from AD: host cache (Docker), LDAP, or Windows Get-ADUser."""
from __future__ import annotations

import logging
import os
import sys
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


def _ldap_bind_configured(config: Optional[Dict[str, Any]] = None) -> bool:
    def _get(key: str) -> str:
        if config and config.get(key) is not None:
            return str(config.get(key) or "").strip()
        return (os.environ.get(key) or "").strip()

    if _get("LDAP_ENABLED").lower() not in ("true", "1", "yes"):
        return False
    if not _get("LDAP_SERVER") or not _get("LDAP_BASE_DN"):
        return False
    # Без учётки LDAP в контейнере запрос не сработает — только host cache / Windows.
    return bool(_get("LDAP_USER") or _get("LDAP_BIND_DN")) and bool(_get("LDAP_PASSWORD"))


def resolve_ad_profile(login: str, config: Optional[Dict[str, Any]] = None) -> Dict[str, str]:
    """
    Вернуть поля профиля из AD (пустой dict, если недоступно).
    Порядок: host cache -> LDAP (если есть bind) -> Get-ADUser (только Windows-хост).
    """
    login = (login or "").strip().lower()
    if not login:
        return {}

    try:
        from auth.ad_host_cache import get_user_info_from_host_cache

        cached = get_user_info_from_host_cache(login)
        if cached and any(cached.values()):
            logger.info("AD profile: host cache hit for %s", login)
            return cached
    except Exception as ex:
        logger.debug("host cache: %s", ex)

    if _ldap_bind_configured(config):
        try:
            from auth.ldap_ad_user import get_user_info_ldap

            info = get_user_info_ldap(login, config)
            if info and any(v for k, v in info.items() if k != "error" and v and v != "Ошибка"):
                logger.info("AD profile: LDAP hit for %s", login)
                return info
        except Exception as ex:
            logger.warning("LDAP profile failed for %s: %s", login, ex)

    if sys.platform == "win32":
        try:
            from auth.ad_user_info import get_user_info_by_login as win_ad

            info = win_ad(login)
            if info and any(info.values()):
                logger.info("AD profile: Get-ADUser hit for %s", login)
                return info
        except Exception as ex:
            logger.warning("Get-ADUser failed for %s: %s", login, ex)

    return {}
