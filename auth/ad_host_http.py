"""Fetch AD profile from Windows host API (Docker -> host.docker.internal)."""
from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from typing import Any, Dict, Optional

_LOGIN_RE = re.compile(r"^[a-z0-9._-]{1,128}$")


def _api_base() -> str:
    return (os.environ.get("AD_HOST_PROFILE_URL") or "").strip().rstrip("/")


def _clean_field(value: Any) -> str:
    if value is None:
        return ""
    s = str(value).strip()
    if s.lower() in ("не указано", "ошибка", "error", "none", "null", ""):
        return ""
    return s


def get_user_info_from_host_http(login: str) -> Optional[Dict[str, str]]:
    base = _api_base()
    if not base:
        return None
    key = (login or "").strip().lower()
    if not key or not _LOGIN_RE.fullmatch(key):
        return None
    url = f"{base}/profile/{key}"
    try:
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=10) as resp:
            raw = json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, OSError, json.JSONDecodeError, TimeoutError):
        return None
    if not isinstance(raw, dict):
        return None
    out = {
        "first_name": _clean_field(raw.get("first_name")),
        "second_name": _clean_field(raw.get("second_name")),
        "sur_name": _clean_field(raw.get("sur_name")),
        "department": _clean_field(raw.get("department")),
        "position": _clean_field(raw.get("position")),
    }
    if not any(out.values()):
        return None
    return out
