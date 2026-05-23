"""Profile from AD read on Windows host (Get-ADUser/ADSI) for Docker Linux container."""
from __future__ import annotations

import json
import os
import re
from typing import Any, Dict, Optional

from auth.encoding_utils import normalize_ad_text

_CACHE_RE = re.compile(r"^[a-z0-9._-]{1,128}$")


def _enabled() -> bool:
    v = (os.environ.get("AD_HOST_PROFILE_CACHE_ENABLED") or "true").strip().lower()
    return v in ("true", "1", "yes", "y", "on")


def _cache_dir() -> str:
    return (os.environ.get("AD_HOST_PROFILE_CACHE_DIR") or "/app/runtime/ad-cache").strip()


def _normalize_login(login: str) -> Optional[str]:
    s = (login or "").strip().lower()
    if not s or not _CACHE_RE.fullmatch(s):
        return None
    return s


def _clean_field(value: Any) -> str:
    if value is None:
        return ""
    s = normalize_ad_text(value)
    if s.lower() in ("не указано", "ошибка", "error", "none", "null", ""):
        return ""
    return s


def get_user_info_from_host_cache(login: str) -> Optional[Dict[str, str]]:
    """
    JSON from scripts/refresh-ad-profile-cache.ps1 (Windows host before docker up).
    """
    if not _enabled():
        return None
    key = _normalize_login(login)
    if not key:
        return None
    path = os.path.join(_cache_dir(), f"{key}.json")
    if not os.path.isfile(path):
        return None
    try:
        with open(path, "r", encoding="utf-8-sig") as f:
            raw = json.load(f)
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(raw, dict):
        return None
    out = {
        "first_name": _clean_field(raw.get("first_name")),
        "second_name": _clean_field(raw.get("second_name")),
        "sur_name": _clean_field(raw.get("sur_name")),
        "department": _clean_field(raw.get("department")),
        "position": _clean_field(raw.get("position")),
        "email": _clean_field(raw.get("email") or raw.get("mail")),
    }
    if not any(out.values()):
        return None
    return out
