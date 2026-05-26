import os


def _project_root() -> str:
    """Return absolute path to the site root used for templates and static pages.

    This backend now runs from the `site` folder. We anchor PROJECT_ROOT to
    the directory that contains the page directories and the `templates` folder.
    """
    # <repo_root>/site/backend/config.py -> <repo_root>/site
    return os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))


class BaseConfig:
    # ВАЖНО: безопасные дефолты. Dev/Testing включаются ТОЛЬКО в своих конфигах ниже.
    DEBUG = False
    TESTING = False
    # Кириллица в JSON как «Иванов», не \\u0418...
    JSON_AS_ASCII = False
    
    # SECRET_KEY должен быть установлен через переменную окружения
    # В production это ОБЯЗАТЕЛЬНО, иначе приложение не запустится
    _default_secret = os.environ.get("SECRET_KEY")
    if not _default_secret:
        import sys
        # В production не запускаемся без SECRET_KEY
        if os.environ.get("FLASK_ENV", "").lower() == "production":
            sys.exit(1)
        # В development генерируем предупреждение, но позволяем запуск
        import secrets
        import warnings
        warnings.warn(
            "SECRET_KEY не установлен! Используется временный ключ только для разработки. "
            "Установите SECRET_KEY через переменную окружения для production.",
            UserWarning
        )
        _default_secret = secrets.token_hex(32)
    SECRET_KEY = _default_secret
    
    # Максимальный размер загружаемых файлов (по умолчанию 1GB, можно увеличить через переменную окружения)
    # Для больших видео можно установить MAX_CONTENT_LENGTH=10737418240 (10GB) или больше
    # ВАЖНО: Убедитесь, что у вас достаточно дискового пространства
    # По умолчанию 100 MB; для больших видео задайте MAX_CONTENT_LENGTH в .env (например 1–10 GB).
    MAX_CONTENT_LENGTH = int(os.environ.get("MAX_CONTENT_LENGTH", 100 * 1024 * 1024))
    
    # Разрешенные MIME типы для загрузки файлов
    # ВАЖНО: список для 'files' умышленно более широкий, чтобы позволять
    # загружать не только офисные документы, но и архивы/тексты/исходники
    # (например, text/x-python), при этом безопасность обеспечивается
    # через FORBIDDEN_EXTENSIONS.
    ALLOWED_MIME_TYPES = {
        'images': [
            'image/jpeg', 'image/jpg', 'image/png', 'image/gif', 'image/webp', 'image/svg+xml'
        ],
        'videos': [
            'video/mp4', 'video/mpeg', 'video/quicktime', 'video/x-msvideo',
            'video/webm', 'video/x-ms-wmv'
        ],
        'files': [
            # Документы
            'application/pdf',
            'application/msword',
            'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            'application/vnd.ms-excel',
            'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            'application/vnd.ms-powerpoint',
            'application/vnd.openxmlformats-officedocument.presentationml.presentation',
            # Текстовые форматы
            'text/plain',
            'text/csv',
            'text/x-python',
            'text/x-c',
            'text/x-c++src',
            'text/x-java-source',
            'text/markdown',
            'application/json',
            # Архивы и "непонятные" бинарники (часто браузер шлёт application/octet-stream)
            'application/zip',
            'application/x-zip-compressed',
            'application/x-rar-compressed',
            'application/x-7z-compressed',
            'application/octet-stream',
        ]
    }
    
    # Запрещенные расширения файлов (исполняемые файлы)
    FORBIDDEN_EXTENSIONS = {'.exe', '.bat', '.cmd', '.com', '.pif', '.scr', '.vbs', '.js', '.jar', '.sh', '.app', '.deb', '.rpm', '.msi'}

    # Root where the existing frontend directories live
    PROJECT_ROOT = _project_root()

    # Explicitly enumerate the allowed frontend page directories
    ALLOWED_PAGE_DIRS = [
        "main-pg",
        "all-categories-pg",
        "all-courses-pg",
        "all-lessons-pg",
        "lessons-content-pg",
        "questions-pg",
        "users-info-pg",
        "user-profile-pg",
        "tests-analytics-pg",
        "bin",
        "bin-pg",  # директория корзины (CSS/JS для /bin)
        "terminal-pg",
    ]
    
    # Frontend directories
    FRONTEND_ROOT_DIR = "frontend"
    ADMIN_TEMPLATE_DIR = "frontend/admin-pages"
    USER_TEMPLATE_DIR = "frontend/user-pages"
    SHARED_TEMPLATE_DIR = "frontend/shared-pages"

    # Template directories for headers/footers based on role
    ADMIN_TEMPLATES_DIR = "frontend/admin-pages/templates"
    USER_TEMPLATES_DIR = "frontend/user-pages/templates"

    # Kerberos realm configuration
    KERBEROS_DEFAULT_REALM = "EXAMPLE.COM"

    # Logging
    LOG_DIR = os.path.join(PROJECT_ROOT, "backend", "logs")
    LOG_FILE = os.path.join(LOG_DIR, "app.log")
    LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO")
    
    # Kerberos Authentication settings (ONLY)
    KERBEROS_AUTH_ENABLED = os.environ.get("KERBEROS_AUTH_ENABLED", "true").lower() == "true"
    KERBEROS_SERVICE_NAME = os.environ.get("KERBEROS_SERVICE_NAME", "HTTP")
    KERBEROS_REALM = os.environ.get("KERBEROS_REALM", "EXAMPLE.COM")
    # Путь к keytab файлу (по умолчанию для Windows, для Linux установите через переменную окружения)
    _default_keytab = os.path.join(os.path.expanduser("~"), "kerberos", "http.keytab") if os.name == "nt" else "/etc/krb5.keytab"
    KERBEROS_KEYTAB = os.environ.get("KERBEROS_KEYTAB", _default_keytab)
    KERBEROS_KDC_HOST = os.environ.get("KERBEROS_KDC_HOST", "localhost")
    KERBEROS_KDC_PORT = int(os.environ.get("KERBEROS_KDC_PORT", "88"))
    # Реальный Kerberos в Linux/контейнере (pyspnego + GSSAPI): нужны krb5.conf, keytab, FQDN как в SPN.
    KERBEROS_GSSAPI_ENABLED = os.environ.get("KERBEROS_GSSAPI_ENABLED", "false").lower() in ("true", "1", "yes")
    KERBEROS_HOSTNAME = os.environ.get("KERBEROS_HOSTNAME", "").strip()

    # Active Directory по LDAP (контейнер/Linux; на Windows по умолчанию PowerShell Get-ADUser).
    LDAP_ENABLED = os.environ.get("LDAP_ENABLED", "false").lower() in ("true", "1", "yes")
    LDAP_SERVER = os.environ.get("LDAP_SERVER", "").strip()
    LDAP_BASE_DN = os.environ.get("LDAP_BASE_DN", "").strip()
    LDAP_USER = os.environ.get("LDAP_USER", "").strip()
    LDAP_BIND_DN = os.environ.get("LDAP_BIND_DN", "").strip()
    LDAP_PASSWORD = os.environ.get("LDAP_PASSWORD", "").strip()
    LDAP_USE_SSL = os.environ.get("LDAP_USE_SSL", "false").lower() in ("true", "1", "yes")
    
    # Database settings (единый путь: project_root/database/users_courses.db, как в database.models)
    _db_path = os.path.abspath(os.path.join(_project_root(), "database", "users_courses.db"))
    DATABASE_URL = os.environ.get("DATABASE_URL", f"sqlite:///{_db_path}")
    DATABASE_INIT_SAMPLE_DATA = os.environ.get("DATABASE_INIT_SAMPLE_DATA", "false").lower() == "true"

    # Static files caching: разумный кеш по умолчанию для статики (CSS/JS/изображения)
    # Flask использует это значение для send_file/send_from_directory, в том числе для frontend/*.
    # 7 дней кеша достаточно для ускорения, но не превращает обновление фронтенда в пытку.
    SEND_FILE_MAX_AGE_DEFAULT = int(os.environ.get("SEND_FILE_MAX_AGE_DEFAULT", 60 * 60 * 24 * 7))  # 7 days

    # Тестовый режим: функции демо (роли admin в API, seed БД, терминал)
    TEST_MODE = os.environ.get("TEST_MODE", "false").lower() in ("true", "1", "yes")
    # Подмена логина без Kerberos при TEST_MODE (отключите для реальной аутентификации)
    TEST_MODE_AUTH_BYPASS = os.environ.get("TEST_MODE_AUTH_BYPASS", "true").lower() in ("true", "1", "yes")

    # Docker без Kerberos/AD: подставить логин по умолчанию (не путать с TEST_MODE — роли из БД, без «все админы»).
    # В production запрещён в backend/__init__.py (fail-fast).
    DOCKER_AUTH_FALLBACK = os.environ.get("DOCKER_AUTH_FALLBACK", "false").lower() in ("true", "1", "yes")
    DOCKER_DEFAULT_USER = (os.environ.get("DOCKER_DEFAULT_USER") or "testadmin").strip()

    # За reverse-proxy (nginx/IIS/oauth2-proxy): доверять логину из заголовка после SSO.
    # ВАЖНО: прокси должен удалять/перезаписывать заголовок от клиента, иначе возможна подмена личности.
    TRUST_REMOTE_USER = os.environ.get("TRUST_REMOTE_USER", "false").lower() in ("true", "1", "yes")
    # IP/CIDR reverse-proxy, которым доверяем SSO-заголовки (см. auth/trusted_proxy.py). '*' — только dev.
    TRUSTED_PROXY_IPS = os.environ.get("TRUSTED_PROXY_IPS", "").strip()
    REMOTE_USER_HEADERS = [
        h.strip()
        for h in os.environ.get(
            "REMOTE_USER_HEADERS",
            "X-Remote-User,X-Forwarded-User,Remote-User,Cf-Access-Authenticated-User-Email",
        ).split(",")
        if h.strip()
    ]

    # В Linux-контейнере getpass.getuser() часто root/www-data — не считать это логином пользователя сайта.
    ACCEPT_CONTAINER_OS_USER = os.environ.get("ACCEPT_CONTAINER_OS_USER", "false").lower() in (
        "true",
        "1",
        "yes",
    )

    # Страница «Терминал»: команды смены своей роли (только явное включение — опасно для production).
    TERMINAL_ROLE_COMMANDS_ENABLED = os.environ.get(
        "TERMINAL_ROLE_COMMANDS_ENABLED", "false"
    ).lower() in ("true", "1", "yes")

    # ---------------- Security defaults (не меняют Kerberos/auth) ----------------
    # Cookie настройки: безопасные значения включаем в ProductionConfig ниже.
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = os.environ.get("SESSION_COOKIE_SAMESITE", "Lax")
    SESSION_COOKIE_SECURE = os.environ.get("SESSION_COOKIE_SECURE", "false").lower() in ("true", "1", "yes")

    # Security headers
    SECURITY_HEADERS_ENABLED = os.environ.get("SECURITY_HEADERS_ENABLED", "true").lower() in ("true", "1", "yes")
    # HSTS включаем только если приложение реально работает по HTTPS.
    SECURITY_HSTS_ENABLED = os.environ.get("SECURITY_HSTS_ENABLED", "false").lower() in ("true", "1", "yes")
    SECURITY_HSTS_MAX_AGE = int(os.environ.get("SECURITY_HSTS_MAX_AGE", str(60 * 60 * 24 * 180)))  # 180 days
    SECURITY_HSTS_INCLUDE_SUBDOMAINS = os.environ.get("SECURITY_HSTS_INCLUDE_SUBDOMAINS", "false").lower() in (
        "true",
        "1",
        "yes",
    )
    SECURITY_HSTS_PRELOAD = os.environ.get("SECURITY_HSTS_PRELOAD", "false").lower() in ("true", "1", "yes")

    # CSP: по умолчанию report-only, чтобы не ломать текущий фронт.
    CSP_ENABLED = os.environ.get("CSP_ENABLED", "true").lower() in ("true", "1", "yes")
    CSP_REPORT_ONLY = os.environ.get("CSP_REPORT_ONLY", "true").lower() in ("true", "1", "yes")
    CSP_POLICY = os.environ.get(
        "CSP_POLICY",
        # Базовый безопасный policy для SSR/статики; допускает inline, т.к. на страницах часто есть inline-скрипты/стили.
        "default-src 'self'; "
        "base-uri 'self'; "
        "object-src 'none'; "
        "frame-ancestors 'self'; "
        "img-src 'self' data: blob:; "
        "font-src 'self' data:; "
        "style-src 'self' 'unsafe-inline'; "
        "script-src 'self' 'unsafe-inline'; "
        "connect-src 'self';",
    )


class DevelopmentConfig(BaseConfig):
    DEBUG = True
    TESTING = False
    # Иначе браузер держит /templates/js/*.js до 7 дней — после git pull кажется, что «ничего не изменилось».
    SEND_FILE_MAX_AGE_DEFAULT = 0


class TestingConfig(BaseConfig):
    TESTING = True
    DEBUG = True


class ProductionConfig(BaseConfig):
    DEBUG = False
    TESTING = False

    # В production ожидаем HTTPS за proxy → делаем cookies Secure по умолчанию.
    SESSION_COOKIE_SECURE = True
    SESSION_COOKIE_SAMESITE = os.environ.get("SESSION_COOKIE_SAMESITE", "Strict")
    SECURITY_HSTS_ENABLED = os.environ.get("SECURITY_HSTS_ENABLED", "true").lower() in ("true", "1", "yes")
    # CSP в enforcing-режиме; без unsafe-inline в script-src (inline-стили по-прежнему допустимы).
    CSP_REPORT_ONLY = os.environ.get("CSP_REPORT_ONLY", "false").lower() in ("true", "1", "yes")
    CSP_POLICY = os.environ.get(
        "CSP_POLICY",
        "default-src 'self'; "
        "base-uri 'self'; "
        "object-src 'none'; "
        "frame-ancestors 'self'; "
        "img-src 'self' data: blob:; "
        "font-src 'self' data:; "
        "style-src 'self' 'unsafe-inline'; "
        "script-src 'self'; "
        "connect-src 'self';",
    )


CONFIG_MAP = {
    "development": DevelopmentConfig,
    "testing": TestingConfig,
    "production": ProductionConfig,
}


def get_config(env_name: str = None):
    env = (env_name or os.environ.get("FLASK_ENV") or "production").lower()
    return CONFIG_MAP.get(env, ProductionConfig)








