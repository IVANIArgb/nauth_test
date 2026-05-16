"""
Pytest fixtures для тестирования Flask-приложения с Kerberos/AD аутентификацией.
Настройка приложения, in-memory БД и моки для Kerberos/AD.
"""
import os
import sys
import pytest

# Добавляем корень проекта в PYTHONPATH до импорта приложения
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# Переменные окружения для тестов (до импорта backend)
os.environ.setdefault("SECRET_KEY", "test-secret-key-for-pytest")
os.environ.setdefault("FLASK_ENV", "testing")
os.environ["TEST_MODE"] = "false"  # чтобы 401-тесты работали
# Изоляция от окружения хоста (Docker / root-test иначе ломают сценарии guest/моков).
os.environ["DOCKER"] = ""
os.environ["DOCKER_AUTH_FALLBACK"] = "false"
os.environ["ROOT_TEST_AUTH_ENABLED"] = "false"
os.environ["KERBEROS_GSSAPI_ENABLED"] = "false"

# Путь к папке отчётов (внутри tests)
TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
REPORTS_DIR = os.path.join(TESTS_DIR, "reports")
COVERAGE_HTML_DIR = os.path.join(REPORTS_DIR, "coverage")


def pytest_configure(config):
    """При использовании --cov сохраняем HTML-отчёт в tests/reports/coverage."""
    try:
        cov = getattr(config.option, "cov", None)
        cov_report = getattr(config.option, "cov_report", None) or []
        if cov and not any(str(r).startswith("html:") for r in (cov_report if isinstance(cov_report, list) else [cov_report])):
            config.option.cov_report = list(cov_report) + [f"html:{COVERAGE_HTML_DIR}", "term-missing"]
    except Exception:
        pass


@pytest.fixture(scope="session")
def app_config():
    """Переопределения конфига для тестов. PROJECT_ROOT обязателен для register_routes."""
    return {
        "TESTING": True,
        "DEBUG": True,
        "TEST_MODE": False,  # иначе все считаются admin и 401-тесты падают
        "DOCKER_AUTH_FALLBACK": False,
        "TERMINAL_ROLE_COMMANDS_ENABLED": False,
        "SECRET_KEY": "test-secret-key",
        "KERBEROS_AUTH_ENABLED": True,
        "DATABASE_URL": "sqlite:///:memory:",
        "WTF_CSRF_ENABLED": False,
        "PROJECT_ROOT": PROJECT_ROOT,
        "ALLOWED_PAGE_DIRS": [
            "main-pg", "all-categories-pg", "all-courses-pg", "all-lessons-pg",
            "lessons-content-pg", "questions-pg", "users-info-pg", "bin-pg",
            "terminal-pg",
        ],
        "ADMIN_TEMPLATE_DIR": "frontend/admin-pages",
        "USER_TEMPLATE_DIR": "frontend/user-pages",
        "SHARED_TEMPLATE_DIR": "frontend/shared-pages",
        "ADMIN_TEMPLATES_DIR": "frontend/admin-pages/templates",
        "USER_TEMPLATES_DIR": "frontend/user-pages/templates",
        "KERBEROS_GSSAPI_ENABLED": False,
        "LDAP_ENABLED": False,
    }


@pytest.fixture
def app(app_config):
    """Flask-приложение в тестовом режиме с in-memory БД."""
    from backend import create_app
    from database.models import Base, DatabaseManager

    application = create_app(env_or_config=app_config)

    # Подменяем db_manager на in-memory БД (приложение уже импортировало database.models)
    import database.models as db_models
    test_manager = DatabaseManager("sqlite:///:memory:")
    Base.metadata.create_all(bind=test_manager.engine)
    db_models.db_manager = test_manager

    # API использует db_manager из database.models при вызове get_db_session()
    import backend.api as api_module
    api_module.db_manager = test_manager

    yield application


@pytest.fixture
def client(app):
    """Тестовый клиент Flask (без мока аутентификации — для тестов с моком в самом тесте)."""
    return app.test_client()


@pytest.fixture
def auth_headers_user():
    """Заголовки для имитации аутентифицированного пользователя (роль user)."""
    return {"Authorization": "Negotiate FAKE_TOKEN_USER"}


@pytest.fixture
def auth_headers_admin():
    """Заголовки для имитации аутентифицированного администратора."""
    return {"Authorization": "Negotiate FAKE_TOKEN_ADMIN"}


def _mock_kerberos_username(auth_header=None, token=None):
    """Извлекает логин из фейкового заголовка для тестов."""
    if auth_header and auth_header.startswith("Negotiate "):
        token = (auth_header or "")[10:].strip()
    if token:
        lower = token.lower()
        if "admin" in lower or lower == "fake_token_admin":
            return "testadmin"
        if "user" in lower or lower == "fake_token_user":
            return "testuser"
    return None


def _mock_ad_info(login):
    """Мок данных из AD для тестов."""
    login = (login or "").lower()
    return {
        "first_name": "Test",
        "second_name": "Middle",
        "sur_name": "User" if login != "testadmin" else "Admin",
        "department": "IT",
        "position": "Developer" if login != "testadmin" else "Administrator",
    }


@pytest.fixture
def mock_no_auth(monkeypatch):
    """Мок: аутентификация всегда возвращает None (гость). Для тестов 401."""
    import auth.new_auth as auth_module

    def fake_get_username(auth_header=None, token=None):
        return None

    monkeypatch.setattr(auth_module, "get_username_from_kerberos", fake_get_username)
    return None


@pytest.fixture
def mock_kerberos_and_ad(monkeypatch):
    """
    Мок для Kerberos и AD: get_username_from_kerberos и get_user_info_by_login.
    Используйте в тестах, где нужна контролируемая аутентификация.
    """
    import auth.new_auth as auth_module

    def fake_get_username(auth_header=None, token=None):
        return _mock_kerberos_username(auth_header=auth_header, token=token)

    def fake_get_ad_info(login):
        return _mock_ad_info(login)

    monkeypatch.setattr(auth_module, "get_username_from_kerberos", fake_get_username)
    monkeypatch.setattr(auth_module, "get_user_info_by_login", fake_get_ad_info)
    return {"get_username": fake_get_username, "get_ad_info": fake_get_ad_info}


@pytest.fixture
def client_as_user(app, mock_kerberos_and_ad):
    """Клиент с запросами от имени пользователя (user)."""
    return app.test_client()


@pytest.fixture
def client_as_admin(app, mock_kerberos_and_ad):
    """Клиент с запросами от имени администратора (admin). Требует наличия пользователя admin в БД."""
    return app.test_client()


@pytest.fixture
def db_session(app):
    """Сессия БД для тестов (создание пользователей, курсов и т.д.)."""
    import database.models as db_models
    session = db_models.db_manager.get_session()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def sample_user(db_session):
    """Пользователь с ролью user в БД."""
    from database.models import User
    user = User(
        username="testuser",
        full_name="Test User",
        surname="User",
        fst_name="Test",
        sec_name="Middle",
        department="IT",
        position="Developer",
        email="testuser@company.com",
        principal="testuser@EXAMPLE.COM",
        realm="EXAMPLE.COM",
        role="user",
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def sample_admin(db_session):
    """Пользователь с ролью admin в БД."""
    from database.models import User
    user = User(
        username="testadmin",
        full_name="Test Admin",
        surname="Admin",
        fst_name="Test",
        sec_name="",
        department="IT",
        position="Administrator",
        email="testadmin@company.com",
        principal="testadmin@EXAMPLE.COM",
        realm="EXAMPLE.COM",
        role="admin",
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user
