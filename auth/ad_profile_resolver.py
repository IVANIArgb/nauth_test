"""Resolve user profile from AD: LDAP (container/server), Get-ADUser (Windows), host cache (dev only)."""
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
    return bool(_get("LDAP_USER") or _get("LDAP_BIND_DN")) and bool(_get("LDAP_PASSWORD"))


def _running_in_docker() -> bool:
    return bool((os.environ.get("DOCKER") or "").strip())


def _host_cache_allowed() -> bool:
    """Файловый кэш с ПК — только явный dev-режим (не для мультиюзерного сервера)."""
    v = (os.environ.get("AD_HOST_PROFILE_CACHE_DEV") or "").strip().lower()
    return v in ("true", "1", "yes", "on")


def _try_ldap(login: str, config: Optional[Dict[str, Any]]) -> Dict[str, str]:
    if not _ldap_bind_configured(config):
        return {}
    try:
        from auth.ldap_ad_user import get_user_info_ldap

        info = get_user_info_ldap(login, config)
        if info and any(v for k, v in info.items() if k != "error" and v and v != "Ошибка"):
            logger.info("AD profile: LDAP hit for %s", login)
            return info
    except Exception as ex:
        logger.warning("LDAP profile failed for %s: %s", login, ex)
    return {}


def _try_host_cache(login: str) -> Dict[str, str]:
    if not _host_cache_allowed():
        return {}
    try:
        from auth.ad_host_cache import get_user_info_from_host_cache

        cached = get_user_info_from_host_cache(login)
        if cached and any(cached.values()):
            logger.info("AD profile: host cache (dev) hit for %s", login)
            return cached
    except Exception as ex:
        logger.debug("host cache: %s", ex)
    return {}


def _try_windows_ad(login: str) -> Dict[str, str]:
    if sys.platform != "win32":
        return {}
    try:
        from auth.ad_user_info import get_user_info_by_login as win_ad

        info = win_ad(login)
        if info and any(info.values()):
            logger.info("AD profile: Get-ADUser hit for %s", login)
            return info
    except Exception as ex:
        logger.warning("Get-ADUser failed for %s: %s", login, ex)
    return {}


def resolve_ad_profile(login: str, config: Optional[Dict[str, Any]] = None) -> Dict[str, str]:
    """
    Профиль из AD по логину (каждый запрос / каждый новый пользователь).

    Сервер в Docker (мультиюзер):
      1) LDAP в AD (основной путь)
      2) host cache только если AD_HOST_PROFILE_CACHE_DEV=true

    Windows без Docker:
      1) Get-ADUser
      2) LDAP (если настроен)
    """
    login = (login or "").strip().lower()
    if not login:
        return {}

    if _running_in_docker():
        info = _try_ldap(login, config)
        if info:
            return info
        info = _try_host_cache(login)
        if info:
            return info
        return _try_windows_ad(login)

    info = _try_windows_ad(login)
    if info:
        return info
    info = _try_ldap(login, config)
    if info:
        return info
    return _try_host_cache(login)
