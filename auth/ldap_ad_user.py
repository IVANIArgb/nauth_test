"""
Чтение атрибутов пользователя из Active Directory через LDAP (Linux / контейнер).
На Windows по умолчанию используется PowerShell (ad_user_info.ADUserInfo).
"""
from __future__ import annotations

import logging
import os
from typing import Any, Dict, Optional

from auth.encoding_utils import normalize_ad_text

logger = logging.getLogger(__name__)

_ERR = {
    "first_name": "Ошибка",
    "second_name": "Ошибка",
    "sur_name": "Ошибка",
    "department": "Ошибка",
    "position": "Ошибка",
}


def _cfg(config: Optional[Dict[str, Any]], key: str, default: str = "") -> str:
    if config and config.get(key) is not None and str(config.get(key)).strip() != "":
        return str(config.get(key)).strip()
    v = os.environ.get(key)
    return (v or default).strip()


def get_user_info_ldap(login: str, config: Optional[Dict[str, Any]] = None) -> dict:
    """
    Возвращает тот же формат полей, что ADUserInfo.get_user_info() (first_name, sur_name, …).
    """
    try:
        from ldap3 import ALL, Connection, Server
    except ImportError:
        logger.warning("ldap3 не установлен — установите пакет ldap3 для LDAP.")
        return dict(_ERR)

    server_uri = _cfg(config, "LDAP_SERVER")
    base_dn = _cfg(config, "LDAP_BASE_DN")
    bind_user = _cfg(config, "LDAP_USER") or _cfg(config, "LDAP_BIND_DN")
    bind_pass = _cfg(config, "LDAP_PASSWORD")

    if not server_uri or not base_dn:
        logger.warning("LDAP_SERVER или LDAP_BASE_DN не заданы.")
        return {}

    if not bind_user or not bind_pass:
        logger.debug("LDAP bind не настроен — пропуск (используйте host cache или Windows AD).")
        return {}

    login_safe = "".join(c for c in (login or "") if c.isalnum() or c in "._-")
    if not login_safe:
        return dict(_ERR)

    try:
        use_ssl = _cfg(config, "LDAP_USE_SSL", "false").lower() in ("true", "1", "yes")
        server = Server(server_uri, get_info=ALL, use_ssl=use_ssl)
        if bind_user and bind_pass:
            conn = Connection(server, user=bind_user, password=bind_pass, auto_bind=True)
        else:
            conn = Connection(server, auto_bind=True)  # anonymous — часто запрещено в AD

        flt = f"(&(objectClass=user)(sAMAccountName={login_safe}))"
        conn.search(
            base_dn,
            flt,
            attributes=[
                "givenName",
                "sn",
                "middleName",
                "department",
                "title",
                "displayName",
                "mail",
            ],
        )
        if not conn.entries:
            return {}

        e = conn.entries[0]

        def _attr(name: str) -> str:
            try:
                v = e[name].value
                if v is None:
                    return ""
                return normalize_ad_text(v)
            except Exception:
                return ""

        gn = _attr("givenName")
        sn = _attr("sn")
        mid = _attr("middleName")
        dept = _attr("department")
        pos = _attr("title")
        if not gn and not sn:
            disp = _attr("displayName")
            if disp:
                parts = disp.split()
                if len(parts) >= 2:
                    gn, sn = parts[0], parts[-1]
                elif len(parts) == 1:
                    gn = parts[0]

        mail = _attr("mail")
        out = {
            "first_name": gn,
            "second_name": mid,
            "sur_name": sn,
            "department": dept,
            "position": pos,
        }
        if mail:
            out["email"] = mail
        return out
    except Exception as ex:
        logger.exception("LDAP get_user_info: %s", ex)
        return {}
