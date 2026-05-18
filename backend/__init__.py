from __future__ import annotations

from typing import Any, Dict, Optional
import logging
import os
import sys
from pathlib import Path

from flask import Flask
from flask_wtf.csrf import CSRFProtect
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_compress import Compress

# Загружаем переменные окружения из .env файла (если есть)
try:
    from dotenv import load_dotenv
    # Ищем .env файл в корне проекта (на уровень выше backend)
    project_root = Path(__file__).parent.parent
    env_path = project_root / '.env'
    if env_path.exists():
        load_dotenv(env_path)
except ImportError:
    # python-dotenv не установлен, пропускаем
    pass

from .config import get_config
from .errors import register_error_handlers
from .routes import register_routes
from .utils.logging_config import configure_logging
# Try to import from auth module (could be in root or backend)
try:
    from auth.new_auth import init_new_auth
except ImportError:
    try:
        from backend.new_auth import init_new_auth
    except ImportError:
        def init_new_auth(app):
            pass
from .api import init_api


def create_app(env_or_config: Optional[str | Dict[str, Any]] = None) -> Flask:
    # Flask будет искать шаблоны в корневой папке site
    # Это позволит использовать пути типа "frontend/admin-pages/templates/base_static_page.html"
    site_root = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))

    # Недоступный CONTENT_ROOT_DIR из .env (часто после копирования с другого ПК) — убрать из os.environ до конфига.
    try:
        from backend.utils.categories_data_sync import ensure_content_root_env_matches_process

        ensure_content_root_env_matches_process()
    except Exception:
        pass

    app = Flask(__name__, template_folder=site_root)

    if isinstance(env_or_config, dict):
        # Сначала базовый конфиг (REMOTE_USER_HEADERS и др.), затем переопределения из тестов/.env dict.
        _env_name = env_or_config.get("FLASK_ENV") or os.environ.get("FLASK_ENV")
        config_cls = get_config(_env_name if isinstance(_env_name, str) else None)
        app.config.from_object(config_cls)
        app.config.update(env_or_config)
    else:
        config_cls = get_config(env_or_config)
        app.config.from_object(config_cls)
        # TERMINAL_ROLE_COMMANDS_ENABLED: брать из окружения после load_dotenv / Docker,
        # иначе значение в BaseConfig фиксируется при первом импорте config и может не совпасть с .env
        _tr = os.environ.get("TERMINAL_ROLE_COMMANDS_ENABLED")
        if _tr is not None and str(_tr).strip() != "":
            app.config["TERMINAL_ROLE_COMMANDS_ENABLED"] = str(_tr).strip().lower() in (
                "true",
                "1",
                "yes",
                "y",
                "on",
            )

        # Kerberos GSS / LDAP: подтянуть из .env после load_dotenv (как TERMINAL_*).
        _gss = os.environ.get("KERBEROS_GSSAPI_ENABLED")
        if _gss is not None and str(_gss).strip() != "":
            app.config["KERBEROS_GSSAPI_ENABLED"] = str(_gss).strip().lower() in (
                "true",
                "1",
                "yes",
                "y",
                "on",
            )
        _kh = os.environ.get("KERBEROS_HOSTNAME")
        if _kh is not None and str(_kh).strip() != "":
            app.config["KERBEROS_HOSTNAME"] = str(_kh).strip()

        for _ldap_key in (
            "LDAP_ENABLED",
            "LDAP_SERVER",
            "LDAP_BASE_DN",
            "LDAP_USER",
            "LDAP_BIND_DN",
            "LDAP_PASSWORD",
            "LDAP_USE_SSL",
        ):
            _lv = os.environ.get(_ldap_key)
            if _lv is None or str(_lv).strip() == "":
                continue
            if _ldap_key in ("LDAP_ENABLED", "LDAP_USE_SSL"):
                app.config[_ldap_key] = str(_lv).strip().lower() in ("true", "1", "yes", "y", "on")
            else:
                app.config[_ldap_key] = str(_lv).strip()

    def _validate_production_safety():
        """
        Fail-fast предохранители для production.
        Не трогает Kerberos/аутентификацию, только запрещает опасные флаги.
        """
        env = (os.environ.get("FLASK_ENV") or "").strip().lower()
        if env != "production":
            return

        if app.config.get("DEBUG") or app.config.get("TESTING"):
            raise RuntimeError("Security: DEBUG/TESTING запрещены в production.")

        # TEST_MODE эскалирует права в UI/логике — в production это недопустимо.
        if app.config.get("TEST_MODE"):
            raise RuntimeError("Security: TEST_MODE запрещён в production.")

        if app.config.get("DOCKER_AUTH_FALLBACK"):
            raise RuntimeError("Security: DOCKER_AUTH_FALLBACK запрещён в production.")

        # Root-test режим (подмена пользователя) в production недопустим
        root_test_enabled = (os.environ.get("ROOT_TEST_AUTH_ENABLED") or "").strip().lower() in (
            "true",
            "1",
            "yes",
            "on",
        )
        if root_test_enabled:
            raise RuntimeError(
                "Security: ROOT_TEST_AUTH_ENABLED запрещён в production. "
                "Включайте только в dev/test."
            )

        # Терминал-команды в production должны включаться только осознанно.
        allow_terminal = (os.environ.get("ALLOW_TERMINAL_IN_PROD") or "").strip().lower() in ("true", "1", "yes")
        if app.config.get("TERMINAL_ROLE_COMMANDS_ENABLED") and not allow_terminal:
            raise RuntimeError(
                "Security: TERMINAL_ROLE_COMMANDS_ENABLED включён в production. "
                "Отключите или установите ALLOW_TERMINAL_IN_PROD=true осознанно."
            )

        # TRUST_REMOTE_USER — опасная штука, если прокси не перезаписывает заголовки.
        # Требуем явного подтверждения, чтобы нельзя было случайно включить в production.
        if app.config.get("TRUST_REMOTE_USER"):
            confirm = (os.environ.get("TRUST_REMOTE_USER_CONFIRM") or "").strip().lower() in ("true", "1", "yes")
            headers = app.config.get("REMOTE_USER_HEADERS") or []
            if not headers:
                raise RuntimeError("Security: TRUST_REMOTE_USER=true, но REMOTE_USER_HEADERS пуст.")
            if not confirm:
                raise RuntimeError(
                    "Security: TRUST_REMOTE_USER=true в production требует TRUST_REMOTE_USER_CONFIRM=true "
                    "(защита от случайного включения)."
                )

        # Запрещаем явно учебные/плейсхолдер ключи в production.
        sk = (app.config.get("SECRET_KEY") or "").strip()
        sk_low = sk.lower()
        if (not sk) or ("not-for-production" in sk_low) or ("замените" in sk_low) or ("dev-key" in sk_low):
            raise RuntimeError("Security: SECRET_KEY выглядит как небезопасный/учебный. Установите нормальный SECRET_KEY.")

    _validate_production_safety()

    configure_logging(app)
    register_error_handlers(app)

    # Security headers (не трогает Kerberos/auth)
    @app.after_request
    def _apply_security_headers(resp):
        try:
            if not app.config.get("SECURITY_HEADERS_ENABLED", True):
                return resp

            # MIME sniffing protection
            resp.headers.setdefault("X-Content-Type-Options", "nosniff")
            # Clickjacking protection
            resp.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
            # Reduce referrer leakage
            resp.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
            # Disable powerful APIs by default
            resp.headers.setdefault(
                "Permissions-Policy",
                "geolocation=(), microphone=(), camera=(), payment=(), usb=(), serial=(), bluetooth=()",
            )

            # CSP (по умолчанию Report-Only, чтобы не ломать текущий фронт)
            if app.config.get("CSP_ENABLED", True):
                csp_policy = (app.config.get("CSP_POLICY") or "").strip()
                if csp_policy:
                    hdr = "Content-Security-Policy-Report-Only" if app.config.get("CSP_REPORT_ONLY", True) else "Content-Security-Policy"
                    resp.headers.setdefault(hdr, csp_policy)

            # HSTS включаем только при HTTPS (или если включено принудительно через конфиг)
            hsts_enabled = bool(app.config.get("SECURITY_HSTS_ENABLED"))
            if hsts_enabled:
                # не полагаемся на request.is_secure (может быть False за proxy),
                # поэтому даём возможность включить HSTS только осознанно через конфиг.
                max_age = int(app.config.get("SECURITY_HSTS_MAX_AGE", 0) or 0)
                if max_age > 0:
                    parts = [f"max-age={max_age}"]
                    if app.config.get("SECURITY_HSTS_INCLUDE_SUBDOMAINS"):
                        parts.append("includeSubDomains")
                    if app.config.get("SECURITY_HSTS_PRELOAD"):
                        parts.append("preload")
                    resp.headers.setdefault("Strict-Transport-Security", "; ".join(parts))
        except Exception:
            # Не ломаем ответы из-за заголовков.
            pass
        return resp
    
    # Initialize CSRF Protection (will exempt API routes after registration)
    csrf = CSRFProtect(app)
    
    # Initialize HTTP compression for text/JSON/HTML/CSS/JS responses
    # Снижает трафик и ускоряет загрузку страниц/JSON под высокой нагрузкой.
    app.config.setdefault("COMPRESS_ALGORITHM", "gzip")
    app.config.setdefault("COMPRESS_LEVEL", 6)
    app.config.setdefault("COMPRESS_MIN_SIZE", 512)
    Compress(app)
    
    # Initialize Rate Limiting for all routes (API + страницы)
    # Цель: защититься от DDoS одним клиентом, но не душить нормальную нагрузку.
    # Базовый лимит: 1000 запросов в минуту с одного IP, остальные ограничения задаются точечно в api.py.
    limiter = Limiter(
        app=app,
        key_func=get_remote_address,
        default_limits=["1000 per minute"],  # >= 1000 запросов в минуту на IP
        storage_uri="memory://",
        swallow_errors=True,  # Не роняем приложение, если хранилище лимитов недоступно
    )
    app.limiter = limiter  # Make limiter available for decorators
    
    # Initialize New Authentication (based on auth_script.py)
    if app.config.get('KERBEROS_AUTH_ENABLED', True):
        init_new_auth(app)
    
    # Initialize API and Database
    api_bp = init_api(app)
    # Exempt API blueprint from CSRF (REST APIs typically don't use CSRF tokens)
    csrf.exempt(api_bp)
    
    register_routes(app)

    def _log_deployment_profile() -> None:
        """Один раз при старте: среда, контент, auth — чтобы корпоративный и домашний ПК было проще сравнить."""
        try:
            from backend.utils.categories_data_sync import get_base_categories_data_path

            eff = get_base_categories_data_path()
        except Exception as ex:
            eff = f"(ошибка: {ex})"
        log = logging.getLogger("learningsite.startup")
        log.info(
            "Старт: FLASK_ENV=%s platform=%s docker=%s | контент=%s | "
            "TEST_MODE=%s TRUST_REMOTE_USER=%s KERBEROS_GSSAPI_ENABLED=%s",
            (os.environ.get("FLASK_ENV") or "").strip() or "?",
            sys.platform,
            bool((os.environ.get("DOCKER") or "").strip()),
            eff,
            bool(app.config.get("TEST_MODE")),
            bool(app.config.get("TRUST_REMOTE_USER")),
            bool(app.config.get("KERBEROS_GSSAPI_ENABLED")),
        )

    _log_deployment_profile()

    return app
