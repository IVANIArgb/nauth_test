"""
Новый модуль аутентификации и получения данных из Active Directory.
Заменяет старый механизм simplified_real_kerberos_auth.

Kerberos в Linux/контейнере (проверка билета в приложении):
  KERBEROS_GSSAPI_ENABLED=true, krb5.conf и keytab (или эквивалент SPN), KERBEROS_HOSTNAME.

Без keytab в контейнере Kerberos проверяется только на reverse-proxy (IIS Windows Auth,
nginx с SPNEGO и т.п.); приложение принимает логин из доверенных заголовков
(TRUST_REMOTE_USER + REMOTE_USER_HEADERS). Эвристика разбора Negotiate без GSSAPI
по умолчанию отключена (см. ALLOW_INSECURE_NEGOTIATE_HEURISTIC).
"""
import logging
import os
import sys
import subprocess
import json
import base64
import re
import getpass
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

# Учётки ОС контейнера / сервиса — не путать с пользователем портала (иначе все «входят» как root).
_SERVICE_OS_USERS = frozenset(
    {
        "root",
        "www-data",
        "nginx",
        "apache",
        "apache2",
        "daemon",
        "nobody",
        "bin",
        "systemd-network",
        "messagebus",
        "_apt",
        "news",
        "man",
    }
)


def _config_str(key: str, default: str = "") -> str:
    try:
        from flask import has_app_context, current_app

        if has_app_context() and current_app.config.get(key) is not None:
            v = current_app.config.get(key)
            if v is not None and str(v).strip() != "":
                return str(v).strip()
    except Exception:
        pass
    return (os.environ.get(key) or default).strip()


def _gssapi_enabled() -> bool:
    v = _config_str("KERBEROS_GSSAPI_ENABLED", "false").lower()
    return v in ("true", "1", "yes", "y", "on")


def _negotiate_heuristic_allowed() -> bool:
    """
    Разбор AP-REQ эвристикой без keytab/GSSAPI НЕ является проверкой Kerberos — любой
    может подставить заголовок. Разрешено только явно и только вне Docker/production.
    """
    if os.environ.get("ALLOW_INSECURE_NEGOTIATE_HEURISTIC", "").strip().lower() not in (
        "true",
        "1",
        "yes",
        "y",
        "on",
    ):
        return False
    if (os.environ.get("DOCKER") or "").strip():
        return False
    if (os.environ.get("FLASK_ENV") or "").strip().lower() == "production":
        return False
    return True


def _username_from_spnego_negotiate(auth_header: str) -> Optional[str]:
    """
    Реальная проверка AP-REQ через GSSAPI (pyspnego). Нужны krb5.conf, keytab, верный SPN.
    """
    try:
        import spnego
        from spnego import KerberosKeytab
    except ImportError:
        logger.warning("pyspnego не установлен — Kerberos GSSAPI недоступен.")
        return None

    try:
        in_token = auth_header.split(" ", 1)[1].strip()
    except IndexError:
        return None

    hostname = _config_str("KERBEROS_HOSTNAME", "")
    service = _config_str("KERBEROS_SERVICE_NAME", "HTTP")
    keytab_path = _config_str("KERBEROS_KEYTAB", "/etc/krb5.keytab")

    if not hostname:
        logger.warning("KERBEROS_HOSTNAME не задан — SPN для Kerberos неоднозначен.")
        return None

    kwargs: Dict[str, Any] = {"hostname": hostname, "service": service, "protocol": "negotiate"}
    if os.path.isfile(keytab_path):
        try:
            kwargs["credentials"] = KerberosKeytab(keytab_path)
        except Exception as ex:
            logger.warning("Keytab %s: %s — пробуем KRB5_KTNAME", keytab_path, ex)
            os.environ.setdefault("KRB5_KTNAME", keytab_path)

    try:
        ctx = spnego.server(**kwargs)
        ctx.step(in_token)
        if not ctx.complete:
            return None
    except Exception as ex:
        logger.debug("spnego.server step: %s", ex)
        return None

    principal = getattr(ctx, "username", None) or getattr(ctx, "client_principal", None)
    if not principal:
        return None
    s = str(principal).strip()
    if "@" in s:
        return s.split("@", 1)[0].lower()
    return s.lower() if s else None


def _ignore_os_username_for_portal(username: str) -> bool:
    if not username or username.strip().lower() == "guest":
        return True
    if os.environ.get("ACCEPT_CONTAINER_OS_USER", "").strip().lower() in ("true", "1", "yes"):
        return False
    return username.strip().lower() in _SERVICE_OS_USERS


def _hosting_strict_sso_active() -> bool:
    try:
        from flask import has_app_context, current_app

        if has_app_context():
            v = current_app.config.get("HOSTING_STRICT_SSO")
            if v is not None:
                return str(v).strip().lower() in ("true", "1", "yes", "y", "on")
    except Exception:
        pass
    return (os.environ.get("HOSTING_STRICT_SSO") or "").strip().lower() in (
        "true",
        "1",
        "yes",
        "y",
        "on",
    )


def get_username_from_kerberos(auth_header: Optional[str] = None, token: Optional[str] = None) -> Optional[str]:
    """
    Извлекает имя пользователя из Kerberos токена или использует Windows Auth как fallback.

    Без KERBEROS_GSSAPI (keytab) заголовок Negotiate по умолчанию игнорируется — используйте
    reverse-proxy с проверкой Kerberos и TRUST_REMOTE_USER.

    Args:
        auth_header: HTTP заголовок Authorization
        token: Base64-encoded Kerberos токен (только вместе с ALLOW_INSECURE_NEGOTIATE_HEURISTIC)

    Returns:
        Логин пользователя или None
    """
    token_to_parse = (token or "").strip() or None

    def _extract_username_from_kerberos_token(raw: str) -> Optional[str]:
        """
        Извлекает имя пользователя из Kerberos токена.

        Args:
            token: Base64-encoded Kerberos токен

        Returns:
            Логин пользователя или None
        """
        try:
            # Декодируем base64 токен
            token_bytes = base64.b64decode(raw)

            # Пробуем декодировать как строку (упрощенный подход)
            try:
                token_str = token_bytes.decode('utf-8', errors='ignore')
            except Exception:
                token_str = token_bytes.decode('latin-1', errors='ignore')

            # Поиск паттернов имени пользователя в токене
            patterns = [
                r'([a-zA-Z0-9._-]+)@([a-zA-Z0-9._-]+)',  # username@realm
                r'([a-zA-Z0-9._-]+)/',  # username/
                r'([a-zA-Z0-9._-]+)',  # username
            ]

            for pattern in patterns:
                match = re.search(pattern, token_str)
                if match:
                    username = match.group(1)
                    if 3 <= len(username) <= 50:
                        return username

            # Альтернативный подход: поиск в бинарных данных
            username_candidates = re.findall(rb'[a-zA-Z0-9._-]{3,20}', token_bytes)
            for candidate in username_candidates:
                try:
                    candidate_str = candidate.decode('ascii')
                    if candidate_str.lower() not in ['http', 'negotiate', 'kerberos', 'ntlm']:
                        return candidate_str
                except Exception:
                    continue

            return None

        except Exception as e:
            return None

    # Вариант 1a: Реальный Kerberos (GSSAPI) — единственный безопасный разбор Negotiate в приложении
    if auth_header and auth_header.startswith("Negotiate ") and _gssapi_enabled():
        u = _username_from_spnego_negotiate(auth_header)
        if u:
            return u
        return None

    # Negotiate без GSSAPI: не доверяем (контейнер / production) — см. trusted proxy + REMOTE_USER
    if auth_header and auth_header.startswith("Negotiate ") and not _gssapi_enabled():
        if _negotiate_heuristic_allowed():
            token_to_parse = auth_header[10:].strip() or None
        else:
            logger.info(
                "Negotiate без KERBEROS_GSSAPI: логин не извлекается (нет keytab / "
                "включите прокси с Kerberos и TRUST_REMOTE_USER)."
            )
            return None

    if auth_header:
        if auth_header.startswith("Basic "):
            return None

    # Эвристика только при ALLOW_INSECURE_NEGOTIATE_HEURISTIC (не Docker / не production)
    if token_to_parse and _negotiate_heuristic_allowed():
        username = _extract_username_from_kerberos_token(token_to_parse)
        if username:
            return username

    # Вариант 3: Windows — учётная запись сессии (кириллица, без keytab); не в контейнере и не в TESTING
    _flask_env = (os.environ.get("FLASK_ENV") or "").strip().lower()
    _testing = _flask_env == "testing"
    try:
        from flask import has_app_context, current_app

        if has_app_context() and current_app.config.get("TESTING"):
            _testing = True
    except Exception:
        pass
    if (
        sys.platform == "win32"
        and not (os.environ.get("DOCKER") or "").strip()
        and not _testing
        and not _hosting_strict_sso_active()
    ):
        try:
            from auth.windows_identity import sam_account_name

            u = sam_account_name()
            if u and not _ignore_os_username_for_portal(u):
                return u.lower()
        except Exception:
            pass

    # Хостинг: только SSO-заголовки с прокси, не getpass/ОС
    if _hosting_strict_sso_active():
        return None

    # Вариант 4: getpass (Linux dev; в контейнере часто root — отбрасываем)
    try:
        username = getpass.getuser()
        if username and not _ignore_os_username_for_portal(username):
            return username
    except Exception:
        pass

    return None


def get_user_info_by_login(login: str) -> dict:
    """
    Профиль из AD: host cache (Docker) -> LDAP (если bind) -> Get-ADUser (Windows).
    """
    cfg: Optional[Dict[str, Any]] = None
    try:
        from flask import has_app_context, current_app

        if has_app_context():
            cfg = current_app.config
    except Exception:
        pass
    from auth.ad_profile_resolver import resolve_ad_profile

    return resolve_ad_profile(login, cfg)



