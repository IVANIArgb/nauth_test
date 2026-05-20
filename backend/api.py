"""
API endpoints для работы с пользователями, курсами и прогрессом.
"""

import os
import json as _json
from typing import List, Dict, Any, Optional
from pathlib import Path
from flask import Blueprint, request, jsonify, g, current_app, send_file
from sqlalchemy.orm import Session, joinedload, selectinload
from sqlalchemy import and_, or_, func

from database.models import (
    User, Category, Course, Lesson,
    UserCourseProgress, UserLessonProgress,
    LESSON_STATUS_NOT_VISITED, LESSON_STATUS_IN_PROGRESS, LESSON_STATUS_COMPLETED,
    LessonContentBlock, LessonTestResult,
    DeletedObject, CourseDepartmentAccess,
    Question, Answer, QuestionAttachment, AnswerAttachment,
    BIN_RETENTION_DAYS,
)

from backend.utils.pagination import get_pagination_params, paginate_query
from backend.utils.validation import validate_search_string, validate_department, validate_title
from backend.utils.file_upload import (
    validate_file_size, validate_file_extension, validate_mime_type,
    save_file_streaming, get_uploads_directory
)
from backend.utils.content_fs import (
    load_categories as fs_load_categories,
    find_category as fs_find_category,
    find_course as fs_find_course,
    find_lesson as fs_find_lesson,
    load_courses as fs_load_courses,
    load_lessons as fs_load_lessons,
    to_public_dict as fs_to_public_dict,
)
from backend.utils.lesson_blocks_fs import (
    read_blocks as fs_read_blocks,
    write_blocks as fs_write_blocks,
    next_block_id as fs_next_block_id,
)
from backend.utils.test_fs import (
    ensure_test_dirs,
    read_test_config,
    write_test_config,
    read_questions_from_dir,
    write_questions_to_dir,
    FsTestConfig,
)
from backend.utils.categories_data_sync import (
    get_base_categories_data_path,
    is_external_content_root,
    LEGACY_CATEGORIES_DATA_PATH,
)
from backend.utils.backup_manager import (
    create_backup as bm_create_backup,
    list_backups as bm_list_backups,
    get_backup_file as bm_get_backup_file,
    delete_backup as bm_delete_backup,
)

# Создаем Blueprint для API
api_bp = Blueprint('api', __name__, url_prefix='/api')

# Глобальный менеджер базы данных
# Используем тот же экземпляр, что и в models.py
from database.models import db_manager


def _is_authenticated_user(user_info: Dict[str, Any] | None) -> bool:
    """Единая проверка аутентификации для API.

    NewAuth/RealKerberosAuth заполняют `g.user_info`. При неаутентифицированном доступе
    проект сейчас подставляет guest/user с auth_method='none' — для UI это может быть ок,
    но для API это означает полный слив данных.
    """
    if not user_info:
        return False
    username = (user_info.get("username") or "").strip().lower()
    if not username or username in {"guest", "user"}:
        return False
    if (user_info.get("auth_method") or "").strip().lower() in {"none", ""}:
        return False
    return True


@api_bp.before_request
def _require_auth_for_api():
    """Запрещаем неаутентифицированный доступ ко всему /api по умолчанию."""
    # Разрешаем только healthcheck-подобные публичные эндпоинты (если появятся).
    # Сейчас публичных API эндпоинтов нет — это сознательно.
    #
    # Но страница "Терминал" в dev-режиме может быть полезна даже без Kerberos/SSO:
    # когда включён флаг TERMINAL_ROLE_COMMANDS_ENABLED, позволяем терминальным
    # эндпоинтам отработать, чтобы UI не "залипал" на 401.
    terminal_enabled = bool(current_app.config.get("TERMINAL_ROLE_COMMANDS_ENABLED"))
    terminal_test_mode = bool(current_app.config.get("TEST_MODE"))
    if request.path.startswith("/api/me/terminal-"):
        if terminal_enabled or terminal_test_mode:
            return None
    user_info = getattr(g, "user_info", None)
    if not _is_authenticated_user(user_info):
        return jsonify({"error": "Unauthorized"}), 401


def _effective_role(user_info: Dict[str, Any] | None) -> str:
    """Роль пользователя с учётом TEST_MODE (в тестовом режиме все — админы)."""
    if current_app.config.get("TEST_MODE"):
        role = ((user_info or {}).get("role") or "user").strip().lower()
        # В TEST_MODE не превращаем super_admin в admin, иначе проверка `_require_super_admin`
        # становится недостижимой.
        return "super_admin" if role == "super_admin" else "admin"
    return ((user_info or {}).get("role") or "user").strip().lower()


def _is_super_admin(user_info: Dict[str, Any] | None) -> bool:
    """Проверить, является ли пользователь супер-админом."""
    return _effective_role(user_info) == "super_admin"


def _require_admin(user_info: Dict[str, Any] | None) -> Optional[tuple]:
    """Проверка admin-прав (admin или super_admin). Возвращает Flask response tuple при запрете."""
    if not _is_authenticated_user(user_info):
        return jsonify({"error": "Unauthorized"}), 401
    if _effective_role(user_info) in ("admin", "super_admin"):
        return None
    return jsonify({"error": "Forbidden"}), 403


def _require_super_admin(user_info: Dict[str, Any] | None) -> Optional[tuple]:
    """Проверка прав супер-админа. Только super_admin."""
    if not _is_authenticated_user(user_info):
        return jsonify({"error": "Unauthorized"}), 401
    if _is_super_admin(user_info):
        return None
    return jsonify({"error": "Forbidden"}), 403


def get_db_session() -> Session:
    """Получить сессию базы данных."""
    return db_manager.get_session()


def _safe_json_loads(raw: Any) -> dict:
    import json as _json
    if not raw or not isinstance(raw, str):
        return {}
    try:
        v = _json.loads(raw)
        return v if isinstance(v, dict) else {}
    except Exception:
        return {}


def _parse_int(value: Any) -> Optional[int]:
    try:
        if value is None:
            return None
        n = int(value)
        return n
    except Exception:
        return None


def _lesson_test_gate_for_user(session: Session, user_id: int, lesson_id: int) -> dict:
    """Проверка, можно ли считать тесты урока пройденными для завершения урока.

    Возвращает структуру:
      { "has_tests": bool, "all_passed": bool, "tests": [ ... ] }
    """
    lesson = fs_find_lesson(lesson_id)
    if not lesson:
        return {"has_tests": False, "all_passed": True, "tests": []}

    blocks = fs_read_blocks(lesson.path)
    test_blocks = [b for b in blocks if isinstance(b, dict) and (b.get("block_type") == "test")]
    if not test_blocks:
        return {"has_tests": False, "all_passed": True, "tests": []}

    tests_info: list[dict] = []
    all_passed = True

    for b in test_blocks:
        block_id = int(b.get("id") or 0)
        tests_dir = ensure_test_dirs(str(lesson.path))
        test_dir = os.path.join(tests_dir, f"block-{block_id}")
        questions_dir = os.path.join(test_dir, "questions")

        cfg = read_test_config(test_dir)
        questions = read_questions_from_dir(questions_dir)
        has_questions = bool(questions)

        # Пустой тест, отключённый тест или временный тест
        # НЕ блокируют завершение урока. Временные тесты считаются факультативными.
        if (not has_questions) or (not cfg.enabled) or (str(cfg.test_type or "").strip() == "temporary"):
            tests_info.append({
                "block_id": block_id,
                "passed": True,
                "skipped": True,
                "attempts_used": 0,
                "max_attempts": None,
                "attempts_left": None,
            })
            continue

        max_attempts = cfg.max_attempts if cfg.limit_attempts else None
        attempts_used = session.query(LessonTestResult).filter(
            LessonTestResult.user_id == user_id,
            LessonTestResult.lesson_id == lesson_id,
            LessonTestResult.block_id == block_id,
        ).count()
        passed = session.query(LessonTestResult).filter(
            LessonTestResult.user_id == user_id,
            LessonTestResult.lesson_id == lesson_id,
            LessonTestResult.block_id == block_id,
            LessonTestResult.passed == True,
        ).count() > 0

        attempts_left = None
        exhausted = False
        if max_attempts is not None:
            attempts_left = max(0, max_attempts - attempts_used)
            exhausted = (attempts_used >= max_attempts) and (not passed)

        if not passed:
            all_passed = False

        tests_info.append({
            "block_id": block_id,
            "passed": bool(passed),
            "attempts_used": attempts_used,
            "max_attempts": max_attempts,
            "attempts_left": attempts_left,
            "attempts_exhausted": bool(exhausted),
        })

    return {"has_tests": True, "all_passed": all_passed, "tests": tests_info}


@api_bp.route('/admin/content-root', methods=['GET', 'PUT'])
def admin_content_root():
    """
    Получить или изменить корневую папку файлового контента (CONTENT_ROOT_DIR).

    Доступно только для super_admin.
    - GET: возвращает текущие пути (фактический, legacy, значение переменной окружения).
    - PUT: принимает JSON {"path": "<новый_путь>"},
      создаёт каталог при необходимости и обновляет/добавляет CONTENT_ROOT_DIR в .env в корне проекта.
      Фактическое использование нового пути начнётся после перезапуска backend‑процесса.
    """
    user_info = getattr(g, "user_info", None)
    deny = _require_super_admin(user_info)
    if deny:
        return deny

    # Корень проекта: на уровень выше папки backend
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
    env_path = os.path.join(project_root, ".env")

    if request.method == 'GET':
        return jsonify({
            "current_root": get_base_categories_data_path(),
            "external": is_external_content_root(),
            "env_value": os.environ.get("CONTENT_ROOT_DIR") or None,
            "legacy_root": LEGACY_CATEGORIES_DATA_PATH,
            "env_path": env_path,
        })

    data = request.get_json(silent=True) or {}
    raw_path = (data.get("path") or "").strip()
    if not raw_path:
        return jsonify({"error": "Путь к папке контента обязателен"}), 400

    # В контейнере Windows-путь сам по себе не существует.
    # Универсальное правило: для пути вида "X:/foo/bar" маппим в "/host/X/foo/bar".
    # Конкретные диски (C:, D:, ...) должны быть примонтированы в docker-compose.windows.yml.
    new_root: str
    import re
    if os.name != "nt" and re.match(r"^[a-zA-Z]:[\\/]", raw_path):
        # Пример: C:\Users\...\content  ->  /host/C/Users/.../content
        drive_letter = raw_path[0].upper()
        rest = raw_path[2:]  # после "C:"
        rest_norm = rest.replace("\\", "/").lstrip("/ ")
        base = "/host/" + drive_letter
        if rest_norm:
            new_root = os.path.join(base, *[p for p in rest_norm.split("/") if p])
        else:
            new_root = base
    else:
        new_root = ""

    # Разрешаем как абсолютные, так и относительные пути (относительно корня проекта)
    if not new_root:
        if os.path.isabs(raw_path):
            new_root = os.path.abspath(os.path.expanduser(raw_path))
        else:
            new_root = os.path.abspath(os.path.join(project_root, os.path.expanduser(raw_path)))

    try:
        os.makedirs(new_root, exist_ok=True)
    except Exception as e:
        return jsonify({"error": f"Не удалось создать/открыть папку: {e}"}), 400

    # Авто-бэкап перед переключением корня контента (по желанию).
    # Важно для эксплуатации: админ переключил папку — всегда можно откатиться.
    try:
        if str(os.environ.get("BACKUP_ON_CONTENT_ROOT_CHANGE", "true")).strip().lower() in ("true", "1", "yes", "y", "on"):
            prev_root = Path(get_base_categories_data_path())
            retention_days = int(os.environ.get("BACKUP_RETENTION_DAYS", "14"))
            bm_create_backup(
                content_root=prev_root,
                reason=f"before_content_root_change",
                include_db=(str(os.environ.get("BACKUP_INCLUDE_DB", "true")).strip().lower() in ("true", "1", "yes", "y", "on")),
                retention_days=retention_days,
            )
    except Exception:
        pass

    # Аккуратно обновляем/добавляем CONTENT_ROOT_DIR в .env
    lines: list[str] = []
    if os.path.exists(env_path):
        try:
            with open(env_path, "r", encoding="utf-8") as f:
                lines = f.readlines()
        except Exception as e:
            return jsonify({"error": f"Не удалось прочитать .env: {e}"}), 500

    key = "CONTENT_ROOT_DIR"
    new_line = f"{key}={new_root}\n"
    updated_lines: list[str] = []
    found = False
    for line in lines:
        stripped = line.strip()
        if stripped.startswith(f"{key}="):
            updated_lines.append(new_line)
            found = True
        else:
            updated_lines.append(line)

    if not found:
        if updated_lines and not updated_lines[-1].endswith("\n"):
            updated_lines[-1] = updated_lines[-1] + "\n"
        updated_lines.append(new_line)

    try:
        with open(env_path, "w", encoding="utf-8") as f:
            f.writelines(updated_lines)
    except Exception as e:
        return jsonify({"error": f"Не удалось записать .env: {e}"}), 500

    try:
        os.environ["CONTENT_ROOT_DIR"] = new_root
        override_file = os.path.join(project_root, ".content_root_dir_override")
        try:
            with open(override_file, "w", encoding="utf-8") as f:
                f.write(new_root)
        except Exception:
            pass
        from backend.utils.categories_data_sync import ensure_categories_data_directory
        ensure_categories_data_directory()
    except Exception:
        pass

    return jsonify({
        "ok": True,
        "new_root": new_root,
        "env_path": env_path,
        "message": (
            "CONTENT_ROOT_DIR обновлён в .env. "
            "Новое значение применится сразу в этом процессе, но на всякий случай "
            "контейнер можно перезапустить при проблемах."
        ),
    })


@api_bp.route('/admin/backups', methods=['GET', 'POST'])
def admin_backups():
    """Бэкапы (контент + опционально БД). Только super_admin."""
    user_info = getattr(g, "user_info", None)
    deny = _require_super_admin(user_info)
    if deny:
        return deny

    if request.method == "GET":
        return jsonify({
            "backup_dir": os.environ.get("BACKUP_DIR") or None,
            "items": bm_list_backups(),
        })

    data = request.get_json(silent=True) or {}
    reason = (data.get("reason") or "manual").strip()
    include_db = bool(data.get("include_db")) if ("include_db" in data) else (str(os.environ.get("BACKUP_INCLUDE_DB", "true")).strip().lower() in ("true", "1", "yes", "y", "on"))
    retention_days = int(data.get("retention_days") or os.environ.get("BACKUP_RETENTION_DAYS", "14"))

    paths = bm_create_backup(
        content_root=Path(get_base_categories_data_path()),
        reason=reason,
        include_db=include_db,
        retention_days=retention_days,
    )
    return jsonify({
        "ok": True,
        "backup_name": paths.backup_file.name,
        "meta_name": paths.meta_file.name,
    })


@api_bp.route('/admin/backups/<path:name>', methods=['GET', 'DELETE'])
def admin_backup_item(name: str):
    """Скачать или удалить конкретный бэкап. Только super_admin."""
    user_info = getattr(g, "user_info", None)
    deny = _require_super_admin(user_info)
    if deny:
        return deny

    if request.method == "DELETE":
        ok = bm_delete_backup(name)
        if not ok:
            return jsonify({"error": "Backup not found"}), 404
        return jsonify({"ok": True})

    p = bm_get_backup_file(name)
    if not p:
        return jsonify({"error": "Backup not found"}), 404
    return send_file(str(p), as_attachment=True, download_name=p.name)


@api_bp.route('/users', methods=['GET'])
def get_users():
    """Получить список всех пользователей с пагинацией."""
    # Это PII. Не отдаём список пользователей всем подряд.
    deny = _require_admin(getattr(g, "user_info", None))
    if deny:
        return deny
    session = get_db_session()
    try:
        # Параметры пагинации
        page, per_page = get_pagination_params()
        
        # Параметры фильтрации с валидацией
        department = validate_department(request.args.get('department'))
        search = validate_search_string(request.args.get('search'))
        
        query = session.query(User)
        
        # Фильтр по отделу
        if department:
            query = query.filter(User.department.ilike(f'%{department}%'))
        
        # Поиск по имени или логину
        if search:
            query = query.filter(
                or_(
                    User.full_name.ilike(f'%{search}%'),
                    User.username.ilike(f'%{search}%')
                )
            )
        
        # Применяем пагинацию
        result = paginate_query(query, page, per_page)
        
        return jsonify({
            'users': [user.to_dict() for user in result['items']],
            'pagination': result['pagination']
        })
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        session.close()


@api_bp.route('/users/<int:user_id>/role', methods=['PUT'])
def update_user_role(user_id: int):
    """
    Обновить роль пользователя. Доступно только super_admin.
    
    Ожидаемый JSON:
      { "role": "user" | "admin" | "super_admin" }
    """
    current_user_info = getattr(g, "user_info", None)
    deny = _require_super_admin(current_user_info)
    if deny:
        return deny

    data = request.get_json(silent=True) or {}
    new_role = (data.get("role") or "").strip().lower()
    if new_role not in ("user", "admin", "super_admin"):
        return jsonify({"error": "Недопустимая роль", "allowed": ["user", "admin", "super_admin"]}), 400

    session = get_db_session()
    try:
        user = session.query(User).filter(User.id == user_id).first()
        if not user:
            return jsonify({"error": "Пользователь не найден"}), 404

        # Запрещаем супер-админу случайно снять права super_admin сам с себя
        current_username = (current_user_info or {}).get("username", "").lower()
        if user.username.lower() == current_username and new_role != "super_admin":
            return jsonify({"error": "Нельзя снять роль super_admin с самого себя"}), 400

        user.role = new_role
        session.commit()

        return jsonify({"id": user.id, "username": user.username, "role": user.role})
    except Exception as e:
        session.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        session.close()


def _terminal_mask_database_url(url: str) -> str:
    if not url or not isinstance(url, str):
        return ""
    low = url.strip().lower()
    if low.startswith("sqlite"):
        return url
    try:
        from urllib.parse import urlparse, urlunparse

        p = urlparse(url)
        if not p.password and not p.username:
            return url
        host = p.hostname or ""
        if p.port:
            host = f"{host}:{p.port}"
        if p.username:
            host = f"{p.username}:***@{host}"
        return urlunparse((p.scheme, host, p.path or "", p.params, p.query, p.fragment))
    except Exception:
        return "(скрыто)"


def _terminal_commands_catalog() -> List[Dict[str, str]]:
    return [
        {"command": "change-role-admin", "description": "Роль admin в БД для текущего пользователя"},
        {"command": "change-role-super-admin", "description": "Роль super_admin в БД"},
        {"command": "seed-test-data", "description": "Тестовые категории, курсы и уроки (как python run.py seed)"},
        {"command": "show-settings", "description": "Показать FLASK_ENV, TEST_MODE, пути контента и др. (без секретов)"},
        {"command": "list-commands", "description": "Показать список команд в окне сообщения (дублирует таблицу на странице)"},
    ]


def _terminal_known_command_names() -> List[str]:
    return [row["command"] for row in _terminal_commands_catalog()]


def _terminal_safe_settings() -> Dict[str, Any]:
    from backend.utils.categories_data_sync import get_base_categories_data_path

    return {
        "FLASK_ENV": os.environ.get("FLASK_ENV"),
        "TEST_MODE": current_app.config.get("TEST_MODE"),
        "DEBUG": current_app.config.get("DEBUG"),
        "TESTING": current_app.config.get("TESTING"),
        "TERMINAL_ROLE_COMMANDS_ENABLED": current_app.config.get(
            "TERMINAL_ROLE_COMMANDS_ENABLED"
        ),
        "CONTENT_ROOT_DIR": os.environ.get("CONTENT_ROOT_DIR"),
        "content_path_resolved": get_base_categories_data_path(),
        "DOCKER": os.environ.get("DOCKER"),
        "DATABASE_URL": _terminal_mask_database_url(os.environ.get("DATABASE_URL") or ""),
        "TRUST_REMOTE_USER": current_app.config.get("TRUST_REMOTE_USER"),
        "KERBEROS_AUTH_ENABLED": current_app.config.get("KERBEROS_AUTH_ENABLED"),
        "DB_SEED_ON_START": os.environ.get("DB_SEED_ON_START"),
        "DB_RECREATE_ON_START": os.environ.get("DB_RECREATE_ON_START"),
        "RUN_WITH_GUNICORN": os.environ.get("RUN_WITH_GUNICORN"),
        "GUNICORN_WORKERS": os.environ.get("GUNICORN_WORKERS"),
        "SECRET_KEY_set": bool(os.environ.get("SECRET_KEY")),
    }


@api_bp.route("/me/terminal-role-command", methods=["POST"])
def terminal_role_command():
    """
    Команды страницы «Терминал»: роли, seed, просмотр настроек.

    В этой реализации смена ролей доступна в:
    - TEST_MODE, либо
    - при явном TERMINAL_ROLE_COMMANDS_ENABLED=true (dev/контейнерный сценарий).
    """
    test_mode = bool(current_app.config.get("TEST_MODE"))
    enabled_flag = bool(current_app.config.get("TERMINAL_ROLE_COMMANDS_ENABLED"))
    if not (test_mode or enabled_flag):
        return (
            jsonify(
                {
                    "error": "Команды терминала отключены",
                    "code": "terminal_disabled",
                }
            ),
            403,
        )

    current_user_info = getattr(g, "user_info", None) or {}
    username = (current_user_info.get("username") or "").strip().lower()
    if not username:
        return jsonify({"error": "Пользователь не аутентифицирован"}), 401

    data = request.get_json(silent=True) or {}
    line = (data.get("command") or data.get("line") or "").strip().lower()
    line = " ".join(line.split())

    if line == "list-commands":
        return jsonify({"ok": True, "commands": _terminal_commands_catalog()})

    if line == "show-settings":
        return jsonify({"ok": True, "settings": _terminal_safe_settings()})

    if line == "seed-test-data":
        try:
            import seed_test_data

            seed_test_data.main()
        except Exception as e:
            return jsonify({"error": str(e), "ok": False}), 500
        return jsonify(
            {
                "ok": True,
                "message": "Тестовые данные обновлены (выполнен seed_test_data).",
            }
        )

    role_by_command = {
        "change-role-admin": "admin",
        "change-role-super-admin": "super_admin",
    }
    if line not in role_by_command:
        return (
            jsonify(
                {
                    "error": "Неизвестная команда",
                    "known_commands": _terminal_known_command_names(),
                }
            ),
            400,
        )

    new_role = role_by_command[line]
    session = get_db_session()
    try:
        user = session.query(User).filter(User.username == username).first()
        if not user:
            from datetime import datetime

            realm = current_app.config.get("KERBEROS_REALM") or "EXAMPLE.COM"
            department = (current_user_info.get("department") or os.environ.get("DEFAULT_USER_DEPARTMENT") or "GUEST").strip()
            position = (current_user_info.get("position") or os.environ.get("DEFAULT_USER_POSITION") or "").strip()

            user = User(
                username=username,
                full_name=current_user_info.get("full_name") or username,
                surname=current_user_info.get("surname") or "",
                fst_name=current_user_info.get("fst_name") or "",
                sec_name=current_user_info.get("sec_name") or "",
                department=department,
                position=position or None,
                email=current_user_info.get("email") or f"{username}@company.com",
                principal=current_user_info.get("principal") or f"{username}@{realm}",
                realm=realm,
                role="user",
                is_active=True,
                last_login=datetime.now(),
            )
            session.add(user)
            session.commit()

        user.role = new_role
        session.commit()
        resp = jsonify({"ok": True, "role": new_role, "username": user.username})
        # Если пользователь стал админом, но UI завис в режиме "как пользователь",
        # принудительно возвращаем режим админа.
        if new_role in ("admin", "super_admin"):
            resp.set_cookie(
                "ls_view_mode",
                "admin",
                max_age=60 * 60 * 24 * 365,
                secure=False,
                httponly=False,
                samesite="Lax",
            )
        return resp
    except Exception as e:
        session.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        session.close()


@api_bp.route("/me/terminal-commands-enabled", methods=["GET"])
def terminal_commands_enabled():
    """Для UI страницы терминала: включены ли команды смены роли."""
    return jsonify(
        {
            "enabled": bool(
                current_app.config.get("TEST_MODE")
                or current_app.config.get("TERMINAL_ROLE_COMMANDS_ENABLED")
            )
        }
    )


@api_bp.route('/users/<int:user_id>', methods=['GET'])
def get_user(user_id: int):
    """Получить информацию о конкретном пользователе."""
    deny = _require_admin(getattr(g, "user_info", None))
    if deny:
        return deny
    session = get_db_session()
    try:
        user = session.query(User).options(
            joinedload(User.course_progress).joinedload(UserCourseProgress.course)
        ).filter(User.id == user_id).first()
        if not user:
            return jsonify({'error': 'Пользователь не найден'}), 404
        
        # Получаем детальную информацию о прогрессе
        user_data = user.to_dict()
        
        # Добавляем информацию о курсах (теперь без N+1 запросов)
        course_progress = []
        for progress in user.course_progress:
            course_data = progress.course.to_dict()
            progress_data = progress.to_dict()
            course_data.update(progress_data)
            course_progress.append(course_data)
        
        user_data['course_progress'] = course_progress
        
        return jsonify(user_data)
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        session.close()


@api_bp.route('/users/<int:user_id>/progress', methods=['GET'])
def get_user_progress(user_id: int):
    """Получить детальный прогресс пользователя по всем курсам."""
    deny = _require_admin(getattr(g, "user_info", None))
    if deny:
        return deny
    session = get_db_session()
    try:
        # Используем eager loading для избежания N+1 запросов
        user = session.query(User).options(
            joinedload(User.course_progress)
              .joinedload(UserCourseProgress.course)
              .joinedload(Course.category)
        ).filter(User.id == user_id).first()
        if not user:
            return jsonify({'error': 'Пользователь не найден'}), 404
        
        progress_data = []
        for progress in user.course_progress:
            course = progress.course
            progress_info = {
                'course_id': course.id,
                'course_title': course.title,
                'course_description': course.description,
                'total_lessons': course.total_lessons,
                'lessons_completed': progress.lessons_completed,
                'progress_percentage': progress.get_progress_percentage(),
                'is_completed': progress.is_completed,
                'started_at': progress.started_at.isoformat() if progress.started_at else None,
                'completed_at': progress.completed_at.isoformat() if progress.completed_at else None
            }
            # Явно отдаем категорию; если курс битый и категория не найдена — так и скажем.
            progress_info['category_id'] = getattr(course, 'category_id', None)
            progress_info['category_title'] = course.category.title if getattr(course, 'category', None) else None
            if progress_info['category_id'] and not progress_info['category_title']:
                progress_info['category_title'] = 'Категория удалена/не найдена'
            progress_data.append(progress_info)
        
        return jsonify({
            'user_id': user_id,
            'username': user.username,
            'full_name': user.full_name,
            'department': user.department,
            'progress': progress_data,
            'summary': {
                'total_courses': len(progress_data),
                'completed_courses': len([p for p in progress_data if p['is_completed']]),
                'total_lessons_completed': sum(p['lessons_completed'] for p in progress_data),
                'average_progress': round(
                    sum(p['progress_percentage'] for p in progress_data) / len(progress_data) 
                    if progress_data else 0, 2
                )
            }
        })
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        session.close()


def is_course_accessible_for_user(session, user_id, course, user_role='user'):
    """
    Проверить доступность курса для пользователя (последовательная категория).
    Последовательность соблюдается для всех ролей (включая admin).
    Returns: (is_accessible: bool, locked_reason: str | None, required_course_id: int | None)
    """
    category = course.category
    if not category or not getattr(category, 'sequential_progression', False):
        return True, None, None
    # Первый курс в категории доступен
    prev_course = session.query(Course).filter(
        Course.category_id == category.id,
        Course.order < course.order,
        Course.is_active == True
    ).order_by(Course.order.desc()).first()
    if not prev_course:
        return True, None, None
    progress = session.query(UserCourseProgress).filter(
        UserCourseProgress.user_id == user_id,
        UserCourseProgress.course_id == prev_course.id
    ).first()
    if progress and progress.is_completed:
        return True, None, None
    return False, f'Необходимо завершить курс «{prev_course.title}»', prev_course.id


def _recalc_course_total_lessons(session, course_id: int) -> int:
    """
    Пересчитать и сохранить course.total_lessons как количество активных уроков.
    Возвращает пересчитанное значение.
    """
    total = session.query(func.count(Lesson.id)).filter(
        Lesson.course_id == course_id,
        Lesson.is_active == True,
    ).scalar() or 0
    course = session.query(Course).filter(Course.id == course_id).first()
    if course:
        course.total_lessons = int(total)
    return int(total)


@api_bp.route('/admin/recalc-course-totals', methods=['POST'])
def admin_recalc_course_totals():
    """Админ‑утилита: пересчитать total_lessons у всех курсов по урокам."""
    session = get_db_session()
    try:
        deny = _require_admin(g.get('user_info', None))
        if deny:
            return deny

        # Считаем активные уроки по курсам одним запросом
        counts = dict(
            session.query(Lesson.course_id, func.count(Lesson.id))
            .filter(Lesson.is_active == True)
            .group_by(Lesson.course_id)
            .all()
        )

        updated = 0
        courses = session.query(Course).all()
        for c in courses:
            new_total = int(counts.get(c.id, 0))
            if int(c.total_lessons or 0) != new_total:
                c.total_lessons = new_total
                updated += 1

        session.commit()
        return jsonify({"updated_courses": updated})
    except Exception as e:
        session.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        session.close()


def fs_is_course_accessible_for_user(session: Session, user_id: int, course_id: int) -> tuple[bool, Optional[str], Optional[int]]:
    """FS-версия: доступ к курсу по порядку в категории (progress в БД, метаданные в FS)."""
    course = fs_find_course(course_id)
    if not course:
        return False, "Курс не найден", None
    cat = fs_find_category(course.category_id)
    if not cat:
        return False, "Категория не найдена", None
    sequential = bool(cat.cfg.get("sequential_progression"))
    if not sequential:
        return True, None, None

    courses = fs_load_courses(cat)
    # найдём предыдущий курс по order
    cur_order = course.cfg.get("order")
    try:
        cur_order_val = int(cur_order) if cur_order is not None else None
    except Exception:
        cur_order_val = None
    if cur_order_val is None:
        # если order не задан — считаем доступным
        return True, None, None
    prev = None
    for c in courses:
        try:
            o = int(c.cfg.get("order")) if c.cfg.get("order") is not None else None
        except Exception:
            o = None
        if o is not None and o < cur_order_val:
            if prev is None or int(prev.cfg.get("order") or 0) < o:
                prev = c
    if not prev:
        return True, None, None

    progress = session.query(UserCourseProgress).filter(
        UserCourseProgress.user_id == user_id,
        UserCourseProgress.course_id == prev.id,
    ).first()
    if progress and progress.is_completed:
        return True, None, None
    return False, f"Необходимо завершить курс «{prev.title}»", prev.id


@api_bp.route('/courses', methods=['GET'])
def get_courses():
    """Получить список всех курсов с пагинацией. Поддерживает фильтр category_id."""
    session = get_db_session()
    try:
        page, per_page = get_pagination_params()
        category_id = request.args.get('category_id', type=int)

        from flask import g
        user_info = g.get('user_info', {}) or {}
        username_raw = user_info.get('username') or ''
        username = username_raw.strip().lower()
        user_id = None
        if username:
            user = session.query(User).filter(User.username == username).first()
            if user:
                user_id = user.id

        courses = []
        if category_id:
            cat = fs_find_category(category_id)
            if not cat:
                return jsonify({'courses': [], 'pagination': {'page': page, 'per_page': per_page, 'total': 0, 'total_pages': 0, 'has_next': False, 'has_prev': False}})
            courses = fs_load_courses(cat)
        else:
            for cat in fs_load_categories():
                courses.extend(fs_load_courses(cat))

        total = len(courses)
        start = (page - 1) * per_page
        end = start + per_page
        items = courses[start:end]

        out = []
        for c in items:
            d = fs_to_public_dict(c.cfg, {"id": c.id, "title": c.title, "category_id": c.category_id})
            if user_id:
                ok, locked_reason, _ = fs_is_course_accessible_for_user(session, user_id, c.id)
                d["is_accessible"] = ok
                if not ok and locked_reason:
                    d["locked_reason"] = locked_reason
            else:
                d["is_accessible"] = True
            out.append(d)

        total_pages = (total + per_page - 1) // per_page if per_page else 1
        return jsonify({
            "courses": out,
            "pagination": {
                "page": page,
                "per_page": per_page,
                "total": total,
                "total_pages": total_pages,
                "has_next": page < total_pages,
                "has_prev": page > 1,
            },
        })
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        session.close()


@api_bp.route('/courses/<int:course_id>', methods=['GET'])
def get_course(course_id: int):
    """Получить информацию о конкретном курсе. Проверяет последовательный доступ в категории."""
    session = get_db_session()
    try:
        from flask import g
        user_info = g.get('user_info', {})
        username = user_info.get('username')
        user_id = None
        if username:
            user = session.query(User).filter(User.username == username).first()
            if user:
                user_id = user.id

        course = fs_find_course(course_id)
        if not course:
            return jsonify({'error': 'Курс не найден'}), 404

        if user_id:
            ok, locked_reason, required_course_id = fs_is_course_accessible_for_user(session, user_id, course_id)
            if not ok:
                return jsonify({'error': locked_reason or 'Курс недоступен', 'required_course_id': required_course_id}), 403

        lessons = fs_load_lessons(course)
        course_data = fs_to_public_dict(course.cfg, {"id": course.id, "title": course.title, "category_id": course.category_id})
        course_data["lessons"] = [fs_to_public_dict(l.cfg, {"id": l.id, "title": l.title, "course_id": l.course_id}) for l in lessons]
        return jsonify(course_data)
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        session.close()


@api_bp.route('/courses', methods=['POST'])
def create_course():
    """Создать курс (admin only)."""
    session = get_db_session()
    try:
        # Проверка прав администратора (admin или super_admin)
        deny = _require_admin(g.get('user_info', None))
        if deny:
            return deny
        
        import os
        from backend.utils.categories_data_sync import (  # type: ignore
            is_external_content_root,
            get_course_path,
            sync_course,
        )

        data = request.get_json()
        if not data:
            return jsonify({'error': 'Данные не предоставлены'}), 400
        
        title = data.get('title', '').strip()
        if not title:
            return jsonify({'error': 'Название курса обязательно'}), 400
        
        category_id = data.get('category_id')
        if not category_id:
            return jsonify({'error': 'ID категории обязателен'}), 400
        
        # Проверка существования категории
        category = session.query(Category).filter(Category.id == category_id).first()
        if not category:
            return jsonify({'error': 'Категория не найдена'}), 404

        # Если внешний CONTENT_ROOT_DIR и курс с таким названием уже есть в БД,
        # но для него ещё нет папки в текущем хранилище, просто пересоздаём FS
        existing_course = session.query(Course).filter(
            Course.category_id == category_id,
            Course.title == title,
        ).first()
        if existing_course and is_external_content_root():
            course_path = get_course_path(category.title, existing_course.title)
            if not os.path.isdir(course_path):
                settings = {
                    "description": existing_course.description,
                    "order": existing_course.order,
                    "sequential_progression": existing_course.sequential_progression,
                    "total_lessons": existing_course.total_lessons,
                    "is_active": existing_course.is_active,
                }
                path_identifier = sync_course(category.title, existing_course.id, existing_course.title, settings=settings)
                existing_course.path_identifier = path_identifier
                session.commit()
                return jsonify(existing_course.to_dict()), 200
        
        # Порядок по умолчанию: max+1 в категории
        order_val = data.get('order')
        if order_val is None:
            max_order = session.query(func.max(Course.order)).filter(Course.category_id == category_id).scalar()
            order_val = (max_order or 0) + 1
        
        course = Course(
            category_id=category_id,
            title=title,
            description=data.get('description', '').strip(),
            order=order_val,
            sequential_progression=data.get('sequential_progression', False),
            total_lessons=data.get('total_lessons', 0),
            is_active=data.get('is_active', True)
        )
        
        session.add(course)
        session.flush()  # Получить ID курса
        
        # Синхронизация файловой структуры
        path_identifier = sync_course(
            category.title,
            course.id,
            course.title,
            settings={
                "description": course.description,
                "order": course.order,
                "sequential_progression": course.sequential_progression,
                "total_lessons": course.total_lessons,
                "is_active": course.is_active,
            },
        )
        course.path_identifier = path_identifier
        
        # news
        try:
            user = _get_current_db_user(session)
            if user:
                from database.models import NewsEvent  # type: ignore
                session.add(NewsEvent(
                    event_type="course_created",
                    title=f"Создан курс: {course.title}",
                    body=course.description or None,
                    meta=_json.dumps({"course_id": course.id, "category_id": course.category_id}, ensure_ascii=False),
                    created_by=user.id,
                ))
        except Exception:
            pass

        session.commit()

        return jsonify(course.to_dict()), 201
    except Exception as e:
        session.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        session.close()


@api_bp.route('/courses/<int:course_id>', methods=['PUT'])
def update_course(course_id: int):
    """Обновить курс (admin only)."""
    session = get_db_session()
    try:
        # Проверка прав администратора (admin или super_admin)
        deny = _require_admin(g.get('user_info', None))
        if deny:
            return deny
        
        course = session.query(Course).filter(Course.id == course_id).first()
        if not course:
            return jsonify({'error': 'Курс не найден'}), 404
        
        data = request.get_json()
        if not data:
            return jsonify({'error': 'Данные не предоставлены'}), 400
        
        # Сохраняем старые значения для синхронизации
        old_title = course.title
        old_category = course.category
        
        # Обновление полей
        if 'title' in data:
            title = data['title'].strip()
            if not title:
                return jsonify({'error': 'Название курса не может быть пустым'}), 400
            course.title = title
        
        if 'description' in data:
            course.description = data['description'].strip()
        
        if 'category_id' in data:
            category_id = data['category_id']
            # Проверка существования категории
            category = session.query(Category).filter(Category.id == category_id).first()
            if not category:
                return jsonify({'error': 'Категория не найдена'}), 404
            course.category_id = category_id
            course.category = category
        
        if 'order' in data:
            course.order = data.get('order', 0)
        
        if 'sequential_progression' in data:
            course.sequential_progression = data.get('sequential_progression', False)
        
        if 'total_lessons' in data:
            course.total_lessons = data.get('total_lessons', 0)
        
        if 'is_active' in data:
            course.is_active = data.get('is_active', True)
        
        # Синхронизация файловой структуры (при изменении названия/категории/настроек)
        category_title = course.category.title if course.category else old_category.title if old_category else ''
        from backend.utils.categories_data_sync import sync_course
        path_identifier = sync_course(
            category_title,
            course.id,
            course.title,
            old_title if 'title' in data and old_title != course.title else None,
            settings={
                "description": course.description,
                "order": course.order,
                "sequential_progression": course.sequential_progression,
                "total_lessons": course.total_lessons,
                "is_active": course.is_active,
            },
        )
        course.path_identifier = path_identifier
        
        # news
        try:
            user = _get_current_db_user(session)
            if user:
                from database.models import NewsEvent  # type: ignore
                session.add(NewsEvent(
                    event_type="course_updated",
                    title=f"Обновлён курс: {course.title}",
                    body=None,
                    meta=_json.dumps({"course_id": course.id, "category_id": course.category_id}, ensure_ascii=False),
                    created_by=user.id,
                ))
        except Exception:
            pass

        session.commit()

        return jsonify(course.to_dict())
    except Exception as e:
        session.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        session.close()


@api_bp.route('/courses/<int:course_id>', methods=['DELETE'])
def delete_course(course_id: int):
    """Удалить курс (admin only) - перемещение в корзину."""
    session = get_db_session()
    try:
        # Проверка прав администратора (admin или super_admin)
        user_info = g.get('user_info', {})
        deny = _require_admin(user_info)
        if deny:
            return deny
        
        # Используем eager loading для избежания N+1 запросов
        course = session.query(Course).options(
            joinedload(Course.category),
            joinedload(Course.lessons)
        ).filter(Course.id == course_id).first()
        
        if not course:
            return jsonify({'error': 'Курс не найден'}), 404
        
        # Получаем user_id
        username = user_info.get('username')
        user = session.query(User).filter(User.username == username).first() if username else None
        
        # Сохраняем данные в корзину
        import json
        object_data = json.dumps(course.to_dict())
        
        deleted_obj = DeletedObject(
            object_type='course',
            object_id=course.id,
            object_data=object_data,
            parent_type='category',
            parent_id=course.category_id,
            deleted_by=user.id if user else None
        )
        session.add(deleted_obj)
        
        # Удаляем файловую структуру курса
        from backend.utils.categories_data_sync import delete_course_folder
        category_title = course.category.title if course.category else ''
        delete_course_folder(category_title, course.title)
        
        # Удалить из статистики прогресс по курсу и по всем урокам курса (результаты тестов не трогаем)
        lesson_ids = [l.id for l in course.lessons]
        if lesson_ids:
            session.query(UserLessonProgress).filter(
                UserLessonProgress.lesson_id.in_(lesson_ids)
            ).delete(synchronize_session=False)
        session.query(UserCourseProgress).filter(UserCourseProgress.course_id == course_id).delete(synchronize_session=False)
        
        # Удаляем курс (is_active = False)
        course.is_active = False
        
        # Также удаляем все связанные уроки
        for lesson in course.lessons:
            lesson.is_active = False
            # Сохраняем урок в корзину
            lesson_data = json.dumps(lesson.to_dict())
            deleted_lesson = DeletedObject(
                object_type='lesson',
                object_id=lesson.id,
                object_data=lesson_data,
                parent_type='course',
                parent_id=course.id,
                deleted_by=user.id if user else None
            )
            session.add(deleted_lesson)
        
        session.commit()
        
        return jsonify({'message': 'Курс перемещен в корзину'})
    except Exception as e:
        session.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        session.close()


@api_bp.route('/courses/<int:course_id>/users', methods=['GET'])
def get_course_users(course_id: int):
    """Получить список пользователей, проходящих курс. Только для админов."""
    deny = _require_admin(g.get('user_info'))
    if deny:
        return deny
    session = get_db_session()
    try:
        course = session.query(Course).options(
            joinedload(Course.user_progress).joinedload(UserCourseProgress.user)
        ).filter(Course.id == course_id).first()
        if not course:
            return jsonify({'error': 'Курс не найден'}), 404
        
        progress_data = []
        for progress in course.user_progress:
            user = progress.user
            progress_info = {
                'user_id': user.id,
                'username': user.username,
                'full_name': user.full_name,
                'department': user.department,
                'lessons_completed': progress.lessons_completed,
                'progress_percentage': progress.get_progress_percentage(),
                'is_completed': progress.is_completed,
                'started_at': progress.started_at.isoformat() if progress.started_at else None,
                'completed_at': progress.completed_at.isoformat() if progress.completed_at else None
            }
            progress_data.append(progress_info)
        
        # Сортируем по проценту выполнения (по убыванию)
        progress_data.sort(key=lambda x: x['progress_percentage'], reverse=True)
        
        return jsonify({
            'course_id': course_id,
            'course_title': course.title,
            'total_lessons': course.total_lessons,
            'users': progress_data,
            'summary': {
                'total_users': len(progress_data),
                'completed_users': len([p for p in progress_data if p['is_completed']]),
                'average_progress': round(
                    sum(p['progress_percentage'] for p in progress_data) / len(progress_data) 
                    if progress_data else 0, 2
                )
            }
        })
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        session.close()


@api_bp.route('/departments', methods=['GET'])
def get_departments():
    """Получить список всех отделов. Только для админов."""
    deny = _require_admin(g.get('user_info'))
    if deny:
        return deny
    session = get_db_session()
    try:
        departments = session.query(User.department).distinct().all()
        department_list = [dept[0] for dept in departments if dept[0]]
        
        return jsonify({
            'departments': department_list,
            'total': len(department_list)
        })
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        session.close()


@api_bp.route('/statistics', methods=['GET'])
def get_statistics():
    """Получить общую статистику по системе."""
    session = get_db_session()
    try:
        # Общая статистика
        total_users = session.query(User).count()
        active_users = session.query(User).filter(User.is_active == True).count()
        total_courses = session.query(Course).filter(Course.is_active == True).count()
        
        # Статистика по отделам — одним агрегирующим запросом вместо N отдельных COUNT
        departments_stats = []
        dept_rows = session.query(
            User.department,
            func.count(User.id)
        ).filter(
            User.department.isnot(None),
            User.department != ""
        ).group_by(User.department).all()
        for dept_name, dept_users_count in dept_rows:
            departments_stats.append({
                'department': dept_name,
                'users_count': dept_users_count
            })
        
        # Статистика по курсам
        courses_stats = []
        # Предзагружаем прогресс по курсам, чтобы избежать N+1 при обращении к user_progress
        courses = session.query(Course).options(
            joinedload(Course.user_progress)
        ).filter(Course.is_active == True).all()
        for course in courses:
            enrolled_users = len(course.user_progress)
            completed_users = len([p for p in course.user_progress if p.is_completed])
            courses_stats.append({
                'course_id': course.id,
                'course_title': course.title,
                'total_lessons': course.total_lessons,
                'enrolled_users': enrolled_users,
                'completed_users': completed_users,
                'completion_rate': round((completed_users / enrolled_users * 100) if enrolled_users > 0 else 0, 2)
            })
        
        return jsonify({
            'overview': {
                'total_users': total_users,
                'active_users': active_users,
                'total_courses': total_courses
            },
            'departments': departments_stats,
            'courses': courses_stats
        })
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        session.close()


# ----------------------- Q&A Endpoints -----------------------

@api_bp.route('/questions', methods=['GET'])
def list_questions():
    """Список вопросов с пагинацией. Поддерживает фильтры: author_id, mine(true), search, resolved(true/false)."""
    session = get_db_session()
    try:
        # Параметры пагинации
        page, per_page = get_pagination_params()
        
        from flask import g
        current_user = g.get('user_info', {}) or {}
        username_raw = current_user.get('username') or ''
        username = username_raw.strip().lower()

        author_id = request.args.get('author_id', type=int)
        mine = request.args.get('mine') == 'true'
        search = validate_search_string(request.args.get('search', type=str))
        resolved = request.args.get('resolved')
        department = validate_department(request.args.get('department', type=str))

        query = session.query(Question).order_by(Question.created_at.desc())

        if author_id:
            query = query.filter(Question.author_id == author_id)
        elif mine and username:
            # username в БД хранится в нижнем регистре
            user = session.query(User).filter(User.username == username).first()
            if user:
                query = query.filter(Question.author_id == user.id)

        if search:
            like = f"%{search}%"
            query = query.filter(or_(Question.title.ilike(like), Question.body.ilike(like)))

        if resolved in ('true', 'false'):
            query = query.filter(Question.is_resolved == (resolved == 'true'))

        if department:
            # Фильтрация по отделу автора вопроса
            like_dept = f"%{department}%"
            query = query.join(User).filter(User.department.ilike(like_dept))

        # ВАЖНО по производительности:
        # joinedload коллекций (answers/attachments) на списке вопросов создаёт "взрыв" строк
        # (Question x Answers x Attachments) и сильно тормозит сортировку/пагинацию.
        # Для коллекций используем selectinload (несколько быстрых запросов вместо одного огромного join).
        query = query.options(
            joinedload(Question.author),
            selectinload(Question.attachments),
            selectinload(Question.answers).joinedload(Answer.author),
            selectinload(Question.answers).selectinload(Answer.attachments),
        )
        
        # Применяем пагинацию
        result = paginate_query(query, page, per_page)
        
        return jsonify({
            # Для страницы вопросов полезно сразу иметь прикреплённые файлы и ответы
            'questions': [q.to_dict(include_relations=True) for q in result['items']],
            'pagination': result['pagination']
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        session.close()


@api_bp.route('/questions/unanswered-count', methods=['GET'])
def unanswered_questions_count():
    """Количество вопросов без ответа (admin only)."""
    session = get_db_session()
    try:
        deny = _require_admin(g.get('user_info', None))
        if deny:
            return deny
        cnt = session.query(func.count(Question.id)).filter(Question.is_resolved == False).scalar()  # noqa: E712
        return jsonify({"count": int(cnt or 0)})
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        session.close()


@api_bp.route('/questions/<int:qid>', methods=['GET'])
def get_question(qid: int):
    session = get_db_session()
    try:
        # Для одной карточки можно грузить связи, но коллекции всё равно лучше selectinload,
        # чтобы не получать дубликаты строк и не раздувать один запрос.
        q = session.query(Question).options(
            joinedload(Question.author),
            selectinload(Question.attachments),
            selectinload(Question.answers).joinedload(Answer.author),
            selectinload(Question.answers).selectinload(Answer.attachments),
        ).filter(Question.id == qid).first()
        if not q:
            return jsonify({'error': 'Вопрос не найден'}), 404
        return jsonify(q.to_dict(include_relations=True))
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        session.close()


@api_bp.route('/questions', methods=['POST'])
def create_question():
    """Создать вопрос. Требуется аутентифицированный пользователь."""
    session = get_db_session()
    try:
        from flask import g
        current_user = g.get('user_info', {}) or {}
        username_raw = current_user.get('username') or ''
        username = username_raw.strip().lower()
        if not username:
            return jsonify({'error': 'Пользователь не аутентифицирован'}), 401

        # username в БД хранится в нижнем регистре; при отсутствии записи
        # автоматически создаём пользователя на основе g.user_info.
        user = session.query(User).filter(User.username == username).first()
        if not user:
            user = User(
                username=username,
                full_name=(current_user.get('full_name') or '').strip() or None,
                surname=(current_user.get('surname') or '').strip() or None,
                fst_name=(current_user.get('fst_name') or '').strip() or None,
                sec_name=(current_user.get('sec_name') or '').strip() or None,
                department=(current_user.get('department') or '').strip() or '',
                position=(current_user.get('position') or '').strip() or None,
                email=(current_user.get('email') or '').strip() or None,
                principal=(current_user.get('principal') or '').strip() or None,
                realm=(current_user.get('realm') or '').strip() or None,
                role=(current_user.get('role') or 'user').strip() or 'user',
                is_active=True,
            )
            session.add(user)
            session.flush()

        data = request.get_json() or {}
        title = (data.get('title') or '').strip()
        body = (data.get('body') or '').strip()
        tags = (data.get('tags') or [])
        if not title:
            return jsonify({'error': 'Требуется заголовок вопроса'}), 400

        question = Question(
            author_id=user.id,
            title=title,
            body=body,
            tags=','.join(tags) if isinstance(tags, list) else str(tags)
        )
        session.add(question)
        session.commit()
        return jsonify({'message': 'Вопрос создан', 'question': question.to_dict(include_relations=False)}), 201
    except Exception as e:
        session.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        session.close()


@api_bp.route('/questions/<int:qid>/answers', methods=['GET'])
def list_answers(qid: int):
    session = get_db_session()
    try:
        # Напрямую загружаем ответы с автором и вложениями одним запросом
        answers = session.query(Answer).options(
            joinedload(Answer.author),
            joinedload(Answer.attachments),
        ).filter(Answer.question_id == qid).order_by(Answer.created_at.asc()).all()
        return jsonify({'answers': [a.to_dict() for a in answers]})
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        session.close()


@api_bp.route('/questions/<int:qid>/answers', methods=['POST'])
def create_answer(qid: int):
    """Создать ответ администратора."""
    session = get_db_session()
    try:
        from flask import g
        current_user = g.get('user_info', {})
        username = (current_user.get('username') or '').strip().lower()
        # Разрешаем создание ответов как админам, так и супер-админам
        deny = _require_admin(current_user)
        if deny:
            return deny
        if not username:
            return jsonify({'error': 'Пользователь не аутентифицирован'}), 401

        user = session.query(User).filter(User.username == username).first()
        if not user:
            return jsonify({'error': 'Пользователь не найден в БД'}), 404

        q = session.query(Question).filter(Question.id == qid).first()
        if not q:
            return jsonify({'error': 'Вопрос не найден'}), 404

        data = request.get_json() or {}
        body = (data.get('body') or '').strip()
        if not body:
            return jsonify({'error': 'Пустой ответ недопустим'}), 400

        ans = Answer(question_id=q.id, author_id=user.id, body=body)
        session.add(ans)
        q.is_resolved = True
        session.commit()
        return jsonify({'message': 'Ответ добавлен', 'answer': ans.to_dict()}), 201
    except Exception as e:
        session.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        session.close()


@api_bp.route('/questions/<int:qid>/attachments', methods=['POST'])
def upload_question_attachment(qid: int):
    """Загрузка файлов к вопросу. Разрешено только автору вопроса или админу."""
    session = get_db_session()
    try:
        from flask import g
        current_user = g.get('user_info', {}) or {}
        username = (current_user.get('username') or '').strip().lower()
        if not username:
            return jsonify({'error': 'Требуется авторизация'}), 401
        user = session.query(User).filter(User.username == username).first()
        if not user:
            return jsonify({'error': 'Пользователь не найден'}), 404

        q = session.query(Question).filter(Question.id == qid).first()
        if not q:
            return jsonify({'error': 'Вопрос не найден'}), 404
        is_admin = _effective_role(current_user) in ('admin', 'super_admin')
        if q.author_id != user.id and not is_admin:
            return jsonify({'error': 'Недостаточно прав для добавления вложений к этому вопросу'}), 403

        file = request.files.get('file')
        if not file:
            return jsonify({'error': 'Файл не передан'}), 400
        
        # Имя для скачивания: из формы или исходное имя файла
        from werkzeug.utils import secure_filename
        display_name = request.form.get('display_name', '').strip()
        original_filename = secure_filename(display_name) if display_name else (file.filename and secure_filename(file.filename) or 'file')
        if not original_filename or original_filename == 'file':
            ext = os.path.splitext(file.filename or '')[1]
            original_filename = 'file' + (ext or '')
        
        # Валидация размера файла
        is_valid, error_msg = validate_file_size(file)
        if not is_valid:
            return jsonify({'error': error_msg}), 400
        
        # Валидация расширения файла
        is_valid, error_msg = validate_file_extension(file.filename)
        if not is_valid:
            return jsonify({'error': error_msg}), 400
        
        # Валидация MIME типа (изображения, документы, архивы + application/octet-stream для .zip и др.)
        allowed_mime = (current_app.config.get('ALLOWED_MIME_TYPES') or {})
        all_allowed = (allowed_mime.get('images') or []) + (allowed_mime.get('files') or [])
        all_allowed = list(set(all_allowed + ['application/octet-stream']))  # браузер часто шлёт это для архивов
        is_valid, mime_err = validate_mime_type(file, allowed_types=all_allowed or None)
        if not is_valid:
            return jsonify({'error': mime_err or 'Недопустимый тип файла'}), 400

        # Сохраняем файл
        uploads_dir = get_uploads_directory()
        file_path, error_msg, file_size = save_file_streaming(file, uploads_dir)
        
        if error_msg:
            return jsonify({'error': error_msg}), 400
        
        # Получаем имя сохраненного файла
        stored_filename = os.path.basename(file_path)
        
        att = QuestionAttachment(
            question_id=q.id,
            stored_filename=stored_filename,
            original_filename=original_filename,
            mime_type=file.mimetype,
            size_bytes=file_size,
        )
        session.add(att)
        session.commit()
        return jsonify({'attachment': att.to_dict()}), 201
    except Exception as e:
        session.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        session.close()


@api_bp.route('/questions/attachments/<int:aid>/download', methods=['GET'])
def download_question_attachment(aid: int):
    """Скачать файл вопроса с правильным именем (original_filename)."""
    session = get_db_session()
    try:
        att = session.query(QuestionAttachment).filter(QuestionAttachment.id == aid).first()
        if not att:
            return jsonify({'error': 'Вложение не найдено'}), 404
        uploads_dir = get_uploads_directory()
        path = os.path.join(uploads_dir, att.stored_filename)
        if not os.path.isfile(path):
            return jsonify({'error': 'Файл не найден'}), 404
        return send_file(
            path,
            as_attachment=True,
            download_name=att.original_filename or att.stored_filename,
        )
    except Exception as e:
        return jsonify({'error': 'Ошибка скачивания'}), 500
    finally:
        session.close()


@api_bp.route('/answers/<int:aid>/attachments', methods=['POST'])
def upload_answer_attachment(aid: int):
    """Загрузка файлов к ответу."""
    import os
    session = get_db_session()
    try:
        a = session.query(Answer).filter(Answer.id == aid).first()
        if not a:
            return jsonify({'error': 'Ответ не найден'}), 404
        
        file = request.files.get('file')
        if not file:
            return jsonify({'error': 'Файл не передан'}), 400
        
        # Валидация размера файла
        is_valid, error_msg = validate_file_size(file)
        if not is_valid:
            return jsonify({'error': error_msg}), 400
        
        # Валидация расширения файла
        is_valid, error_msg = validate_file_extension(file.filename)
        if not is_valid:
            return jsonify({'error': error_msg}), 400
        
        # Валидация MIME типа (+ application/octet-stream для архивов)
        allowed_mime = (current_app.config.get('ALLOWED_MIME_TYPES') or {})
        all_allowed = (allowed_mime.get('images') or []) + (allowed_mime.get('files') or [])
        all_allowed = list(set(all_allowed + ['application/octet-stream']))
        is_valid, mime_err = validate_mime_type(file, allowed_types=all_allowed or None)
        if not is_valid:
            return jsonify({'error': mime_err or 'Недопустимый тип файла'}), 400

        # Сохраняем файл
        uploads_dir = get_uploads_directory()
        file_path, error_msg, file_size = save_file_streaming(file, uploads_dir)
        
        if error_msg:
            return jsonify({'error': error_msg}), 400
        
        # Получаем имя сохраненного файла
        stored_filename = os.path.basename(file_path)
        mime_type = file.mimetype or 'application/octet-stream'
        
        att = AnswerAttachment(
            answer_id=a.id,
            stored_filename=stored_filename,
            original_filename=file.filename,
            mime_type=mime_type,
            size_bytes=file_size,
        )
        session.add(att)
        session.commit()
        return jsonify({'attachment': att.to_dict()}), 201
    except Exception as e:
        session.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        session.close()
@api_bp.route('/users/register', methods=['POST'])
def register_user():
    """Ручная регистрация пользователя (для тестирования)"""
    # Никогда не должен жить в production как публичный эндпоинт.
    if not (current_app.config.get("DEBUG") or current_app.config.get("TESTING")):
        return jsonify({"error": "Not Found"}), 404
    deny = _require_admin(getattr(g, "user_info", None))
    if deny:
        return deny
    session = get_db_session()
    try:
        data = request.get_json()
        username = data.get('username')
        
        if not username:
            return jsonify({'error': 'Username is required'}), 400
        
        # Проверяем, существует ли пользователь
        existing_user = session.query(User).filter(User.username == username.lower()).first()
        if existing_user:
            return jsonify({
                'message': 'User already exists',
                'user': existing_user.to_dict()
            }), 200
        
        # Создаем нового пользователя
        new_user = User(
            username=username.lower(),
            full_name=data.get('full_name', username),
            department=data.get('department', ''),
            email=data.get('email', f"{username.lower()}@company.com"),
            is_active=True
        )
        session.add(new_user)
        session.commit()
        
        return jsonify({
            'message': 'User registered successfully',
            'user': new_user.to_dict()
        }), 201
    
    except Exception as e:
        session.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        session.close()


@api_bp.route('/users/check-registration', methods=['GET'])
def check_user_registration():
    """Проверить, зарегистрирован ли текущий пользователь"""
    session = get_db_session()
    try:
        from flask import g
        current_user_info = g.get('user_info', {})
        username = current_user_info.get('username')
        
        if not username:
            return jsonify({'error': 'User not authenticated'}), 401
        
        # Проверяем в основной таблице User
        user = session.query(User).filter(User.username == username).first()
        user_exists = user is not None
        
        return jsonify({
            'username': username,
            'user_registered': user_exists,
            'user_data': user.to_dict() if user else None
        })
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        session.close()


@api_bp.route('/current-user', methods=['GET'])
def get_current_user_info():
    """Получить информацию о текущем пользователе (из Windows Auth)."""
    session = get_db_session()
    try:
        # Получаем информацию о текущем пользователе из g (установлено в auth.py)
        current_user_info = g.get('user_info', {}) or {}
        username = current_user_info.get('username')
        # Роль всегда берём из контекста аутентификации (включая super_admin),
        # чтобы фронтенд мог корректно отрисовать права даже для незарегистрированных в БД пользователей.
        current_role = _effective_role(current_user_info)
        
        # Эффективная роль для UI: если админ в режиме «как пользователь» — показываем интерфейс юзера
        effective_role = current_role
        view_mode = (request.cookies.get('ls_view_mode') or '').strip().lower()
        if current_role in ('admin', 'super_admin') and view_mode == 'user':
            effective_role = 'user'
        
        if not username:
            return jsonify({'error': 'Пользователь не аутентифицирован'}), 401

        # username в БД хранится в нижнем регистре, а источник аутентификации может вернуть
        # его в произвольном регистре. Нормализуем для корректного поиска.
        username_norm = str(username).strip().lower()
        if not username_norm:
            return jsonify({'error': 'Пользователь не аутентифицирован'}), 401
        
        # Используем eager loading для избежания N+1 запросов
        user = session.query(User).options(
            joinedload(User.course_progress)
              .joinedload(UserCourseProgress.course)
              .joinedload(Course.category)
        ).filter(User.username == username_norm).first()
        
        if not user:
            # Пользователь прошёл аутентификацию, но записи в БД ещё нет.
            # Всё равно возвращаем его роль (user/admin/super_admin), чтобы UI мог
            # показывать соответствующие элементы управления.
            return jsonify({
                'authenticated': True,
                'username': username_norm,
                'role': current_role,
                'effective_role': effective_role,
                'in_database': False,
                'message': 'Пользователь не найден в базе данных'
            })
        
        # Получаем детальную информацию о пользователе
        user_data = user.to_dict()
        # Гарантируем наличие корректной роли в ответе.
        # Если по каким‑то причинам в БД роль пустая, используем роль из контекста.
        user_data['role'] = user_data.get('role') or current_role
        user_data['effective_role'] = effective_role
        
        # Добавляем информацию о курсах (теперь без N+1 запросов)
        course_progress = []
        for progress in user.course_progress:
            course_data = progress.course.to_dict()
            progress_data = progress.to_dict()
            course_data.update(progress_data)
            if course_data.get('category_id') and not course_data.get('category_title'):
                course_data['category_title'] = 'Категория удалена/не найдена'
            course_progress.append(course_data)
        
        user_data['course_progress'] = course_progress
        user_data['authenticated'] = True
        user_data['in_database'] = True
        
        return jsonify(user_data)
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        session.close()


# ----------------------- Categories Endpoints -----------------------

@api_bp.route('/categories', methods=['GET'])
def get_categories():
    """Получить список всех категорий с пагинацией."""
    session = get_db_session()
    try:
        # #region agent log
        try:
            from backend.utils.agent_debug_log import agent_debug_log
            from backend.utils.categories_data_sync import get_base_categories_data_path

            agent_debug_log(
                "H2",
                "api.get_categories",
                "request start",
                {"base_path": get_base_categories_data_path()},
            )
        except Exception:
            pass
        # #endregion
        page, per_page = get_pagination_params()
        cats = fs_load_categories()
        total = len(cats)
        start = (page - 1) * per_page
        end = start + per_page
        items = cats[start:end]
        total_pages = (total + per_page - 1) // per_page if per_page else 1
        return jsonify({
            "categories": [fs_to_public_dict(c.cfg, {"id": c.id, "title": c.title}) for c in items],
            "pagination": {
                "page": page,
                "per_page": per_page,
                "total": total,
                "total_pages": total_pages,
                "has_next": page < total_pages,
                "has_prev": page > 1,
            },
        })
    except Exception as e:
        # #region agent log
        try:
            from backend.utils.agent_debug_log import agent_debug_log

            agent_debug_log(
                "H2",
                "api.get_categories",
                "request failed",
                {"error": str(e), "error_type": type(e).__name__},
            )
        except Exception:
            pass
        # #endregion
        return jsonify({'error': str(e)}), 500
    finally:
        session.close()


@api_bp.route('/categories/<int:category_id>', methods=['GET'])
def get_category(category_id: int):
    """Получить категорию."""
    session = get_db_session()
    try:
        cat = fs_find_category(category_id)
        if not cat:
            return jsonify({'error': 'Категория не найдена'}), 404
        return jsonify(fs_to_public_dict(cat.cfg, {"id": cat.id, "title": cat.title}))
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        session.close()


@api_bp.route('/categories', methods=['POST'])
def create_category():
    """Создать категорию (admin only)."""
    session = get_db_session()
    try:
        # Проверка прав администратора (admin или super_admin)
        deny = _require_admin(g.get('user_info', None))
        if deny:
            return deny
        
        import os
        from backend.utils.categories_data_sync import (  # type: ignore
            is_external_content_root,
            get_category_path,
            sync_category,
        )

        data = request.get_json()
        if not data:
            return jsonify({'error': 'Данные не предоставлены'}), 400
        
        title = data.get('title', '').strip()
        if not title:
            return jsonify({'error': 'Название категории обязательно'}), 400
        # Проверка на дубликаты + восстановление FS при смене CONTENT_ROOT_DIR
        existing = session.query(Category).filter(Category.title == title).first()
        if existing:
            if is_external_content_root():
                cat_path = get_category_path(existing.title)
                # Если в новом CONTENT_ROOT_DIR ещё нет такой папки — создаём её и возвращаем существующую категорию
                if not os.path.isdir(cat_path):
                    settings = {
                        "description": existing.description,
                        "order": existing.order,
                        "sequential_progression": existing.sequential_progression,
                        "is_active": existing.is_active,
                    }
                    path_identifier = sync_category(existing.id, existing.title, settings=settings)
                    existing.path_identifier = path_identifier
                    session.commit()
                    return jsonify(existing.to_dict()), 200
            # В противном случае это действительно дубликат
            return jsonify({'error': 'Категория с таким названием уже существует'}), 400
        
        # Порядок по умолчанию: max+1
        order_val = data.get('order')
        if order_val is None:
            max_order = session.query(func.max(Category.order)).scalar()
            order_val = (max_order or 0) + 1
        
        category = Category(
            title=title,
            description=data.get('description', '').strip(),
            order=order_val,
            sequential_progression=data.get('sequential_progression', False),
            is_active=data.get('is_active', True)
        )
        
        session.add(category)
        session.flush()  # Получить ID категории
        
        # Синхронизация файловой структуры
        path_identifier = sync_category(
            category.id,
            category.title,
            settings={
                "description": category.description,
                "order": category.order,
                "sequential_progression": category.sequential_progression,
                "is_active": category.is_active,
            },
        )
        category.path_identifier = path_identifier
        
        # news
        try:
            user = _get_current_db_user(session)
            if user:
                from database.models import NewsEvent  # type: ignore
                session.add(NewsEvent(
                    event_type="category_created",
                    title=f"Создана категория: {category.title}",
                    body=category.description or None,
                    meta=_json.dumps({"category_id": category.id}, ensure_ascii=False),
                    created_by=user.id,
                ))
        except Exception:
            pass

        session.commit()

        return jsonify(category.to_dict()), 201
    except Exception as e:
        session.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        session.close()


@api_bp.route('/categories/<int:category_id>', methods=['PUT'])
def update_category(category_id: int):
    """Обновить категорию (admin only)."""
    session = get_db_session()
    try:
        # Проверка прав администратора (admin или super_admin)
        deny = _require_admin(g.get('user_info', None))
        if deny:
            return deny
        
        category = session.query(Category).filter(Category.id == category_id).first()
        if not category:
            return jsonify({'error': 'Категория не найдена'}), 404
        
        data = request.get_json()
        if not data:
            return jsonify({'error': 'Данные не предоставлены'}), 400
        
        # Сохраняем старое название для переименования папки
        old_title = category.title
        
        # Обновление полей
        if 'title' in data:
            title = data['title'].strip()
            if not title:
                return jsonify({'error': 'Название категории не может быть пустым'}), 400
            # Проверка на дубликаты (кроме текущей категории)
            existing = session.query(Category).filter(
                Category.title == title,
                Category.id != category_id
            ).first()
            if existing:
                return jsonify({'error': 'Категория с таким названием уже существует'}), 400
            category.title = title
        
        if 'description' in data:
            category.description = data['description'].strip()
        
        if 'order' in data:
            category.order = data.get('order', 0)

        if 'sequential_progression' in data:
            category.sequential_progression = data.get('sequential_progression', False)
        
        if 'is_active' in data:
            category.is_active = data.get('is_active', True)
        
        # Синхронизация файловой структуры (при изменении названия или настроек)
        from backend.utils.categories_data_sync import sync_category
        path_identifier = sync_category(
            category.id,
            category.title,
            old_title if 'title' in data and old_title != category.title else None,
            settings={
                "description": category.description,
                "order": category.order,
                "sequential_progression": category.sequential_progression,
                "is_active": category.is_active,
            },
        )
        category.path_identifier = path_identifier
        
        # news
        try:
            user = _get_current_db_user(session)
            if user:
                from database.models import NewsEvent  # type: ignore
                session.add(NewsEvent(
                    event_type="category_updated",
                    title=f"Обновлена категория: {category.title}",
                    body=None,
                    meta=_json.dumps({"category_id": category.id}, ensure_ascii=False),
                    created_by=user.id,
                ))
        except Exception:
            pass

        session.commit()

        return jsonify(category.to_dict())
    except Exception as e:
        session.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        session.close()


@api_bp.route('/categories/<int:category_id>', methods=['DELETE'])
def delete_category(category_id: int):
    """Удалить категорию (admin only) - перемещение в корзину."""
    session = get_db_session()
    try:
        # Проверка прав администратора (admin или super_admin)
        user_info = g.get('user_info', {})
        deny = _require_admin(user_info)
        if deny:
            return deny
        
        category = session.query(Category).filter(Category.id == category_id).first()
        if not category:
            return jsonify({'error': 'Категория не найдена'}), 404
        
        # Получаем user_id
        username = user_info.get('username')
        user = session.query(User).filter(User.username == username).first() if username else None
        
        # Сохраняем данные в корзину
        import json
        object_data = json.dumps(category.to_dict())
        
        deleted_obj = DeletedObject(
            object_type='category',
            object_id=category.id,
            object_data=object_data,
            deleted_by=user.id if user else None
        )
        session.add(deleted_obj)
        
        # Удаляем файловую структуру категории
        from backend.utils.categories_data_sync import delete_category_folder
        delete_category_folder(category.title)
        
        # Удалить из статистики прогресс по всем курсам и урокам категории (результаты тестов не трогаем)
        all_lesson_ids = []
        for c in category.courses:
            session.query(UserCourseProgress).filter(UserCourseProgress.course_id == c.id).delete(synchronize_session=False)
            all_lesson_ids.extend([l.id for l in c.lessons])
        if all_lesson_ids:
            session.query(UserLessonProgress).filter(
                UserLessonProgress.lesson_id.in_(all_lesson_ids)
            ).delete(synchronize_session=False)
        
        # Удаляем категорию (is_active = False)
        category.is_active = False
        
        # Также удаляем все связанные курсы и уроки
        for course in category.courses:
            course.is_active = False
            # Сохраняем курс в корзину
            course_data = json.dumps(course.to_dict())
            deleted_course = DeletedObject(
                object_type='course',
                object_id=course.id,
                object_data=course_data,
                parent_type='category',
                parent_id=category.id,
                deleted_by=user.id if user else None
            )
            session.add(deleted_course)
            
            # Удаляем уроки курса
            for lesson in course.lessons:
                lesson.is_active = False
                # Сохраняем урок в корзину
                lesson_data = json.dumps(lesson.to_dict())
                deleted_lesson = DeletedObject(
                    object_type='lesson',
                    object_id=lesson.id,
                    object_data=lesson_data,
                    parent_type='course',
                    parent_id=course.id,
                    deleted_by=user.id if user else None
                )
                session.add(deleted_lesson)
        
        session.commit()
        
        return jsonify({'message': 'Категория перемещена в корзину'})
    except Exception as e:
        session.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        session.close()


@api_bp.route('/categories/<int:category_id>/courses', methods=['GET'])
def get_category_courses(category_id: int):
    """Получить курсы категории."""
    session = get_db_session()
    try:
        cat = fs_find_category(category_id)
        if not cat:
            return jsonify({'error': 'Категория не найдена'}), 404
        courses = fs_load_courses(cat)
        return jsonify({
            "category": fs_to_public_dict(cat.cfg, {"id": cat.id, "title": cat.title}),
            "courses": [fs_to_public_dict(c.cfg, {"id": c.id, "title": c.title, "category_id": c.category_id}) for c in courses],
            "total": len(courses),
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        session.close()


# ----------------------- Lessons Endpoints -----------------------

def is_lesson_accessible_for_user(session, user_id, lesson_id, user_role='user'):
    """
    Проверить доступность урока для пользователя.
    Последовательность соблюдается для всех ролей (включая admin).
    
    Returns:
        tuple: (is_accessible: bool, locked_reason: str | None, required_lesson_id: int | None)
    """
    lesson = session.query(Lesson).filter(Lesson.id == lesson_id).first()
    if not lesson:
        return False, 'Урок не найден', None
    
    course = lesson.course
    if not course.sequential_progression:
        return True, None, None
    
    if lesson.lesson_number == 1:
        return True, None, None
    
    # Найти предыдущий урок
    previous_lesson = session.query(Lesson).filter(
        Lesson.course_id == course.id,
        Lesson.lesson_number == lesson.lesson_number - 1,
        Lesson.is_active == True
    ).first()
    
    if not previous_lesson:
        return True, None, None
    
    # Проверить, завершен ли предыдущий урок
    progress = session.query(UserLessonProgress).filter(
        UserLessonProgress.user_id == user_id,
        UserLessonProgress.lesson_id == previous_lesson.id
    ).first()
    
    is_prev_completed = progress and (
        (getattr(progress, 'lesson_status', None) == LESSON_STATUS_COMPLETED) or progress.is_completed
    )
    if not is_prev_completed:
        return False, f'Необходимо завершить урок "{previous_lesson.title}"', previous_lesson.id
    
    return True, None, None


def fs_is_lesson_accessible_for_user(session: Session, user_id: int, lesson_id: int) -> tuple[bool, Optional[str], Optional[int]]:
    """FS-версия последовательности уроков (progress в БД, порядок из FS)."""
    lesson = fs_find_lesson(lesson_id)
    if not lesson:
        return False, "Урок не найден", None
    course = fs_find_course(lesson.course_id)
    if not course:
        return False, "Курс не найден", None
    sequential = bool(course.cfg.get("sequential_progression"))
    if not sequential:
        return True, None, None

    lessons = fs_load_lessons(course)
    # Найдём позицию текущего урока
    idx = next((i for i, l in enumerate(lessons) if l.id == lesson_id), -1)
    if idx <= 0:
        return True, None, None
    prev = lessons[idx - 1]

    progress = session.query(UserLessonProgress).filter(
        UserLessonProgress.user_id == user_id,
        UserLessonProgress.lesson_id == prev.id,
    ).first()
    is_prev_completed = progress and ((getattr(progress, 'lesson_status', None) == LESSON_STATUS_COMPLETED) or progress.is_completed)
    if not is_prev_completed:
        return False, f'Необходимо завершить урок "{prev.title}"', prev.id
    return True, None, None


@api_bp.route('/lessons', methods=['GET'])
def get_lessons():
    """Получить список уроков с пагинацией. Поддерживает фильтры: course_id."""
    session = get_db_session()
    try:
        # Параметры пагинации
        page, per_page = get_pagination_params()
        
        from flask import g
        user_info = g.get('user_info', {})
        username = user_info.get('username')
        
        # Получить user_id
        user_id = None
        # Если пользователь аутентифицирован, но в БД нет записи — всё равно
        # учитываем последовательный доступ как "прогресс не завершён".
        # Для этого используем sentinel user_id=-1.
        if username:
            user = session.query(User).filter(User.username == username).first()
            user_id = user.id if user else -1
        
        course_id = request.args.get('course_id', type=int)
        lessons = []
        if course_id:
            course = fs_find_course(course_id)
            if not course:
                return jsonify({'lessons': [], 'pagination': {'page': page, 'per_page': per_page, 'total': 0, 'total_pages': 0, 'has_next': False, 'has_prev': False}})
            if user_id is not None:
                ok, locked_reason, required_course_id = fs_is_course_accessible_for_user(session, user_id, course_id)
                if not ok:
                    return jsonify({'error': locked_reason or 'Курс недоступен', 'required_course_id': required_course_id}), 403
            lessons = fs_load_lessons(course)
        else:
            for cat in fs_load_categories():
                for course in fs_load_courses(cat):
                    lessons.extend(fs_load_lessons(course))

        total = len(lessons)
        start = (page - 1) * per_page
        end = start + per_page
        items = lessons[start:end]

        progress_by_lesson_id = {}
        if user_id is not None:
            lesson_ids = [l.id for l in items]
            if lesson_ids:
                progresses = session.query(UserLessonProgress).filter(
                    UserLessonProgress.user_id == user_id,
                    UserLessonProgress.lesson_id.in_(lesson_ids)
                ).all()
                progress_by_lesson_id = {p.lesson_id: p for p in progresses}

        lessons_data = []
        for l in items:
            lesson_dict = fs_to_public_dict(l.cfg, {"id": l.id, "title": l.title, "course_id": l.course_id})
            if user_id is not None:
                ok, locked_reason, required_lesson_id = fs_is_lesson_accessible_for_user(session, user_id, l.id)
                lesson_dict["is_accessible"] = ok
                if not ok and locked_reason:
                    lesson_dict["locked_reason"] = locked_reason
                    lesson_dict["required_lesson_id"] = required_lesson_id
                progress = progress_by_lesson_id.get(l.id)
                if progress:
                    lesson_dict['is_completed'] = (getattr(progress, 'lesson_status', None) == LESSON_STATUS_COMPLETED) or progress.is_completed
                    lesson_dict['lesson_status'] = getattr(progress, 'lesson_status', LESSON_STATUS_COMPLETED if progress.is_completed else LESSON_STATUS_IN_PROGRESS)
                else:
                    lesson_dict['is_completed'] = False
                    lesson_dict['lesson_status'] = LESSON_STATUS_NOT_VISITED
            else:
                lesson_dict["is_accessible"] = True
                lesson_dict['is_completed'] = False
                lesson_dict['lesson_status'] = LESSON_STATUS_NOT_VISITED
            lessons_data.append(lesson_dict)

        total_pages = (total + per_page - 1) // per_page if per_page else 1
        return jsonify({
            "lessons": lessons_data,
            "pagination": {
                "page": page,
                "per_page": per_page,
                "total": total,
                "total_pages": total_pages,
                "has_next": page < total_pages,
                "has_prev": page > 1,
            },
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        session.close()


@api_bp.route('/lessons/<int:lesson_id>', methods=['GET'])
def get_lesson(lesson_id: int):
    """Получить урок с проверкой доступа."""
    session = get_db_session()
    try:
        from flask import g
        user_info = g.get('user_info', {})
        username = user_info.get('username')
        # Получить user_id
        user_id = None
        if username:
            user = session.query(User).filter(User.username == username).first()
            user_id = user.id if user else -1

        lesson = fs_find_lesson(lesson_id)
        if not lesson:
            return jsonify({'error': 'Урок не найден'}), 404

        lesson_data = fs_to_public_dict(lesson.cfg, {"id": lesson.id, "title": lesson.title, "course_id": lesson.course_id})
        
        # Проверка доступа
        if user_id is not None:
            is_accessible, locked_reason, required_lesson_id = fs_is_lesson_accessible_for_user(session, user_id, lesson_id)
            lesson_data['is_accessible'] = is_accessible
            if not is_accessible:
                lesson_data['locked_reason'] = locked_reason
                lesson_data['required_lesson_id'] = required_lesson_id
        else:
            lesson_data['is_accessible'] = True
        
        # Проверка и создание прогресса при первом заходе
        if user_id is not None and user_id != -1:
            progress = session.query(UserLessonProgress).filter(
                UserLessonProgress.user_id == user_id,
                UserLessonProgress.lesson_id == lesson_id
            ).first()
            if not progress:
                progress = UserLessonProgress(
                    user_id=user_id,
                    lesson_id=lesson_id,
                    lesson_status=LESSON_STATUS_IN_PROGRESS,
                    is_completed=False
                )
                session.add(progress)
                session.commit()
            lesson_data['is_completed'] = progress.lesson_status == LESSON_STATUS_COMPLETED or progress.is_completed
            lesson_data['lesson_status'] = progress.lesson_status if progress.lesson_status is not None else (LESSON_STATUS_COMPLETED if progress.is_completed else LESSON_STATUS_IN_PROGRESS)
        else:
            lesson_data['is_completed'] = False
            lesson_data['lesson_status'] = LESSON_STATUS_NOT_VISITED
        
        return jsonify(lesson_data)
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        session.close()


@api_bp.route('/lessons', methods=['POST'])
def create_lesson():
    """Создать урок (admin only)."""
    session = get_db_session()
    try:
        # Проверка прав администратора (admin или super_admin)
        deny = _require_admin(g.get('user_info', None))
        if deny:
            return deny
        
        import os
        from backend.utils.categories_data_sync import (  # type: ignore
            is_external_content_root,
            get_lesson_path,
            sync_lesson,
        )

        data = request.get_json()
        if not data:
            return jsonify({'error': 'Данные не предоставлены'}), 400
        
        title = data.get('title', '').strip()
        if not title:
            return jsonify({'error': 'Название урока обязательно'}), 400
        
        course_id = data.get('course_id')
        if not course_id:
            return jsonify({'error': 'ID курса обязателен'}), 400
        
        # Проверка существования курса
        course = session.query(Course).filter(Course.id == course_id).first()
        if not course:
            return jsonify({'error': 'Курс не найден'}), 404
        
        category = course.category
        if not category:
            return jsonify({'error': 'Категория курса не найдена'}), 404

        # При внешнем CONTENT_ROOT_DIR: если урок с таким названием уже существует в БД,
        # но его папка отсутствует в текущем хранилище, просто восстанавливаем FS.
        existing_lesson = session.query(Lesson).filter(
            Lesson.course_id == course_id,
            Lesson.title == title,
        ).first()
        if existing_lesson and is_external_content_root():
            lesson_path = get_lesson_path(category.title, course.title, existing_lesson.title)
            if not os.path.isdir(lesson_path):
                path_identifier = sync_lesson(
                    category.title,
                    course.title,
                    existing_lesson.id,
                    existing_lesson.title,
                    None,
                    settings={
                        "lesson_number": existing_lesson.lesson_number,
                        "is_active": existing_lesson.is_active,
                    },
                )
                existing_lesson.path_identifier = path_identifier
                session.commit()
                return jsonify(existing_lesson.to_dict()), 200
        
        # Порядок (lesson_number) по умолчанию: max+1 в курсе
        lesson_number_val = data.get('lesson_number')
        if lesson_number_val is None:
            max_num = session.query(func.max(Lesson.lesson_number)).filter(Lesson.course_id == course_id).scalar()
            lesson_number_val = (max_num or 0) + 1
        
        lesson = Lesson(
            course_id=course_id,
            title=title,
            description=data.get('description', '').strip(),
            lesson_number=lesson_number_val,
            content=data.get('content'),
            is_active=data.get('is_active', True)
        )
        
        session.add(lesson)
        session.flush()  # Получить ID урока
        
        # Синхронизация файловой структуры categories-data
        path_identifier = sync_lesson(
            category.title,
            course.title,
            lesson.id,
            lesson.title,
            None,
            settings={
                "lesson_number": lesson.lesson_number,
                "is_active": lesson.is_active,
            },
        )
        lesson.path_identifier = path_identifier

        # Корень бага "3/0": total_lessons не обновлялся при изменениях уроков.
        # Пересчитываем сразу после добавления урока.
        _recalc_course_total_lessons(session, course_id)
        
        # news
        try:
            user = _get_current_db_user(session)
            if user:
                from database.models import NewsEvent  # type: ignore
                session.add(NewsEvent(
                    event_type="lesson_created",
                    title=f"Создан урок: {lesson.title}",
                    body=lesson.description or None,
                    meta=_json.dumps({"lesson_id": lesson.id, "course_id": lesson.course_id}, ensure_ascii=False),
                    created_by=user.id,
                ))
        except Exception:
            pass

        session.commit()

        return jsonify(lesson.to_dict()), 201
    except Exception as e:
        session.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        session.close()


@api_bp.route('/lessons/<int:lesson_id>', methods=['PUT'])
def update_lesson(lesson_id: int):
    """Обновить урок (admin only)."""
    session = get_db_session()
    try:
        # Проверка прав администратора (admin или super_admin)
        deny = _require_admin(g.get('user_info', None))
        if deny:
            return deny
        
        lesson = session.query(Lesson).filter(Lesson.id == lesson_id).first()
        if not lesson:
            return jsonify({'error': 'Урок не найден'}), 404
        
        data = request.get_json()
        if not data:
            return jsonify({'error': 'Данные не предоставлены'}), 400
        
        # Сохраняем старые значения для синхронизации
        old_title = lesson.title
        course = lesson.course
        category = course.category if course else None
        
        # Обновление полей
        if 'title' in data:
            title = data['title'].strip()
            if not title:
                return jsonify({'error': 'Название урока не может быть пустым'}), 400
            lesson.title = title
        
        if 'description' in data:
            lesson.description = data['description'].strip()
        
        if 'lesson_number' in data:
            lesson.lesson_number = data.get('lesson_number', 1)
        
        if 'content' in data:
            lesson.content = data['content']
        
        is_active_changed = False
        if 'is_active' in data:
            new_active = bool(data.get('is_active', True))
            is_active_changed = (bool(lesson.is_active) != new_active)
            lesson.is_active = new_active
        
        # Синхронизация файловой структуры (при изменении названия/настроек)
        if category and course:
            from backend.utils.categories_data_sync import sync_lesson
            path_identifier = sync_lesson(
                category.title,
                course.title,
                lesson.id,
                lesson.title,
                old_title if 'title' in data and old_title != lesson.title else None,
                settings={
                    "lesson_number": lesson.lesson_number,
                    "is_active": lesson.is_active,
                },
            )
            lesson.path_identifier = path_identifier

        # Если активность урока менялась — пересчитаем total_lessons курса
        if is_active_changed and lesson.course_id:
            _recalc_course_total_lessons(session, int(lesson.course_id))
        
        # news
        try:
            user = _get_current_db_user(session)
            if user:
                from database.models import NewsEvent  # type: ignore
                session.add(NewsEvent(
                    event_type="lesson_updated",
                    title=f"Обновлён урок: {lesson.title}",
                    body=None,
                    meta=_json.dumps({"lesson_id": lesson.id, "course_id": lesson.course_id}, ensure_ascii=False),
                    created_by=user.id,
                ))
        except Exception:
            pass

        session.commit()

        return jsonify(lesson.to_dict())
    except Exception as e:
        session.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        session.close()


@api_bp.route('/lessons/<int:lesson_id>', methods=['DELETE'])
def delete_lesson(lesson_id: int):
    """Удалить урок (admin only) - полное удаление без корзины."""
    session = get_db_session()
    try:
        # Проверка прав администратора (admin или super_admin)
        deny = _require_admin(g.get('user_info', None))
        if deny:
            return deny
        
        lesson = session.query(Lesson).filter(Lesson.id == lesson_id).first()
        if not lesson:
            return jsonify({'error': 'Урок не найден'}), 404
        
        # Удалить папку урока из categories-data
        course = lesson.course
        category = course.category if course else None
        if category and course:
            from backend.utils.categories_data_sync import delete_lesson_folder
            delete_lesson_folder(category.title, course.title, lesson.title)
        
        # Удалить прогресс по уроку из статистики (результаты тестов не трогаем)
        affected_user_ids = [
            r[0] for r in session.query(UserLessonProgress.user_id).filter(
                UserLessonProgress.lesson_id == lesson_id
            ).distinct().all()
        ]
        session.query(UserLessonProgress).filter(UserLessonProgress.lesson_id == lesson_id).delete(synchronize_session=False)
        course_id = lesson.course_id
        # Пересчитаем total_lessons ДО правки прогресса, чтобы completed считался корректно
        total_lessons = _recalc_course_total_lessons(session, int(course_id)) if course_id else (course.total_lessons or 0)
        for uid in affected_user_ids:
            prog = session.query(UserCourseProgress).filter(
                UserCourseProgress.user_id == uid,
                UserCourseProgress.course_id == course_id,
            ).first()
            if prog:
                prog.lessons_completed = max(0, prog.lessons_completed - 1)
                prog.is_completed = total_lessons > 0 and prog.lessons_completed >= total_lessons
                if prog.is_completed and not prog.completed_at:
                    pass  # completed_at оставляем как есть
                elif not prog.is_completed:
                    prog.completed_at = None
        
        # Полное удаление (is_active = False, но не в корзину)
        lesson.is_active = False
        if course_id:
            _recalc_course_total_lessons(session, int(course_id))
        session.commit()
        
        return jsonify({'message': 'Урок удален'})
    except Exception as e:
        session.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        session.close()


@api_bp.route('/lessons/<int:lesson_id>/course-tree', methods=['GET'])
def get_lesson_course_tree(lesson_id: int):
    """Получить дерево навигации: категория → курс → урок."""
    session = get_db_session()
    try:
        lesson = fs_find_lesson(lesson_id)
        if not lesson:
            return jsonify({'error': 'Урок не найден'}), 404
        course = fs_find_course(lesson.course_id)
        if not course:
            return jsonify({'error': 'Курс не найден'}), 404
        category = fs_find_category(course.category_id)
        if not category:
            return jsonify({'error': 'Категория не найдена'}), 404

        return jsonify({
            'category': {
                'id': category.id,
                'title': category.title
            },
            'course': {
                'id': course.id,
                'title': course.title
            },
            'lesson': {
                'id': lesson.id,
                'title': lesson.title,
                'lesson_number': lesson.cfg.get('lesson_number')
            }
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        session.close()


@api_bp.route('/lessons/<int:lesson_id>/previous', methods=['GET'])
def get_previous_lesson(lesson_id: int):
    """Получить предыдущий урок."""
    session = get_db_session()
    try:
        lesson = fs_find_lesson(lesson_id)
        if not lesson:
            return jsonify({'error': 'Урок не найден'}), 404
        course = fs_find_course(lesson.course_id)
        if not course:
            return jsonify({'lesson': None})
        lessons = fs_load_lessons(course)
        idx = next((i for i, l in enumerate(lessons) if l.id == lesson_id), -1)
        if idx <= 0:
            return jsonify({'lesson': None})
        prev = lessons[idx - 1]
        return jsonify({'lesson': fs_to_public_dict(prev.cfg, {"id": prev.id, "title": prev.title, "course_id": prev.course_id})})
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        session.close()


@api_bp.route('/lessons/<int:lesson_id>/next', methods=['GET'])
def get_next_lesson(lesson_id: int):
    """Получить следующий урок."""
    session = get_db_session()
    try:
        from flask import g
        user_info = g.get('user_info', {})
        username = user_info.get('username')
        user_id = None
        if username:
            user = session.query(User).filter(User.username == username).first()
            if user:
                user_id = user.id
        
        lesson = fs_find_lesson(lesson_id)
        if not lesson:
            return jsonify({'error': 'Урок не найден'}), 404
        course = fs_find_course(lesson.course_id)
        if not course:
            return jsonify({'lesson': None})
        lessons = fs_load_lessons(course)
        idx = next((i for i, l in enumerate(lessons) if l.id == lesson_id), -1)
        if idx < 0 or idx >= len(lessons) - 1:
            return jsonify({'lesson': None})
        nxt = lessons[idx + 1]
        next_lesson_dict = fs_to_public_dict(nxt.cfg, {"id": nxt.id, "title": nxt.title, "course_id": nxt.course_id})
        if user_id:
            ok, locked_reason, required_lesson_id = fs_is_lesson_accessible_for_user(session, user_id, nxt.id)
            next_lesson_dict['is_accessible'] = ok
            if not ok and locked_reason:
                next_lesson_dict['locked_reason'] = locked_reason
                next_lesson_dict['required_lesson_id'] = required_lesson_id
        else:
            next_lesson_dict['is_accessible'] = True
        return jsonify({'lesson': next_lesson_dict})
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        session.close()


@api_bp.route('/lessons/<int:lesson_id>/complete', methods=['POST'])
def complete_lesson(lesson_id: int):
    """Завершить урок."""
    session = get_db_session()
    try:
        from flask import g
        user_info = g.get('user_info', {})
        username = user_info.get('username')
        
        if not username:
            return jsonify({'error': 'Пользователь не аутентифицирован'}), 401

        # username в БД хранится в нижнем регистре
        user = session.query(User).filter(User.username == username).first()
        if not user:
            return jsonify({'error': 'Пользователь не найден'}), 404
        lesson = fs_find_lesson(lesson_id)
        if not lesson:
            return jsonify({'error': 'Урок не найден'}), 404
        course = fs_find_course(lesson.course_id)
        if not course:
            return jsonify({'error': 'Курс не найден'}), 404
        
        # Проверка доступа
        is_accessible, locked_reason, required_lesson_id = fs_is_lesson_accessible_for_user(session, user.id, lesson_id)
        if not is_accessible:
            return jsonify({'error': locked_reason or 'Урок недоступен'}), 403

        # Если в уроке есть тест(ы), не даём завершить, пока тесты не пройдены
        test_gate = _lesson_test_gate_for_user(session, user.id, lesson_id)
        if test_gate.get("has_tests") and not test_gate.get("all_passed"):
            any_exhausted = any(t.get("attempts_exhausted") for t in (test_gate.get("tests") or []) if isinstance(t, dict))
            return jsonify({
                "error": "Нельзя завершить урок: тест не пройден",
                "code": "test_not_passed_exhausted" if any_exhausted else "test_not_passed",
                "tests": test_gate.get("tests") or [],
            }), 403
        
        # Найти или создать прогресс (запомнить, был ли урок уже завершён — до изменения)
        progress = session.query(UserLessonProgress).filter(
            UserLessonProgress.user_id == user.id,
            UserLessonProgress.lesson_id == lesson_id
        ).first()
        was_already_completed = (
            (progress.lesson_status == LESSON_STATUS_COMPLETED if progress and progress.lesson_status is not None else False)
            or (progress.is_completed if progress else False)
        )

        if not progress:
            progress = UserLessonProgress(
                user_id=user.id,
                lesson_id=lesson_id,
                is_completed=True,
                lesson_status=LESSON_STATUS_COMPLETED
            )
            session.add(progress)
        else:
            progress.is_completed = True
            progress.lesson_status = LESSON_STATUS_COMPLETED

        from datetime import datetime
        progress.completed_at = datetime.now()

        # Обновить прогресс по курсу (инкремент только если урок завершён впервые)
        course_progress = session.query(UserCourseProgress).filter(
            UserCourseProgress.user_id == user.id,
            UserCourseProgress.course_id == lesson.course_id
        ).first()

        if not course_progress:
            course_progress = UserCourseProgress(
                user_id=user.id,
                course_id=lesson.course_id,
                lessons_completed=1
            )
            session.add(course_progress)
        elif not was_already_completed:
            course_progress.lessons_completed += 1
        
        # Проверить, завершен ли курс
        try:
            total_lessons = int(course.cfg.get("total_lessons") or 0)
        except Exception:
            total_lessons = 0
        if total_lessons <= 0:
            total_lessons = len(fs_load_lessons(course))
        if course_progress.lessons_completed >= total_lessons and total_lessons > 0:
            course_progress.is_completed = True
            course_progress.completed_at = datetime.now()
        
        session.commit()
        
        return jsonify({
            'message': 'Урок завершен',
            'just_completed': not was_already_completed,
            'progress': progress.to_dict()
        })
    except Exception as e:
        session.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        session.close()


@api_bp.route('/lessons/<int:lesson_id>/progress', methods=['GET'])
def get_lesson_progress(lesson_id: int):
    """Получить прогресс по уроку."""
    session = get_db_session()
    try:
        from flask import g
        user_info = g.get('user_info', {})
        username = user_info.get('username')
        
        if not username:
            return jsonify({'error': 'Пользователь не аутентифицирован'}), 401
        
        user = session.query(User).filter(User.username == username).first()
        if not user:
            return jsonify({'error': 'Пользователь не найден'}), 404
        
        lesson = session.query(Lesson).filter(Lesson.id == lesson_id).first()
        if not lesson:
            return jsonify({'error': 'Урок не найден'}), 404
        
        progress = session.query(UserLessonProgress).filter(
            UserLessonProgress.user_id == user.id,
            UserLessonProgress.lesson_id == lesson_id
        ).first()
        
        if progress:
            return jsonify(progress.to_dict())
        else:
            return jsonify({
                'user_id': user.id,
                'lesson_id': lesson_id,
                'is_completed': False,
                'completed_at': None,
                'time_spent': 0
            })
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        session.close()


@api_bp.route('/lessons/<int:lesson_id>/ask-question', methods=['POST'])
def ask_question_about_lesson(lesson_id: int):
    """Задать вопрос по уроку."""
    session = get_db_session()
    try:
        from flask import g
        user_info = g.get('user_info', {})
        username = user_info.get('username')
        
        if not username:
            return jsonify({'error': 'Пользователь не аутентифицирован'}), 401
        
        user = session.query(User).filter(User.username == username).first()
        if not user:
            return jsonify({'error': 'Пользователь не найден'}), 404
        
        lesson = session.query(Lesson).filter(Lesson.id == lesson_id).first()
        if not lesson:
            return jsonify({'error': 'Урок не найден'}), 404
        
        course = lesson.course
        category = course.category
        
        # Формируем теги
        tags = f"Категория: {category.title}, Курс: {course.title}, Урок: {lesson.title}"
        
        # Получаем данные из запроса (если есть title и body)
        data = request.get_json() or {}
        title = data.get('title', f'Вопрос по уроку: {lesson.title}')
        body = data.get('body', '')
        
        # Создаем вопрос
        question = Question(
            author_id=user.id,
            title=title,
            body=body,
            tags=tags
        )
        session.add(question)
        session.commit()
        
        return jsonify({
            'message': 'Вопрос создан',
            'question_id': question.id,
            'question': question.to_dict(include_relations=False)
        }), 201
    except Exception as e:
        session.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        session.close()


# ----------------------- Lesson Content Blocks Endpoints -----------------------

@api_bp.route('/lessons/<int:lesson_id>/blocks', methods=['GET'])
def get_lesson_blocks(lesson_id: int):
    """Получить блоки контента урока. Проверяет последовательный доступ."""
    session = get_db_session()
    try:
        from flask import g
        user_info = g.get('user_info', {})
        username = user_info.get('username')
        user_id = None
        if username:
            user = session.query(User).filter(User.username == username).first()
            user_id = user.id if user else -1

        lesson = fs_find_lesson(lesson_id)
        if not lesson:
            return jsonify({'error': 'Урок не найден'}), 404

        if user_id is not None:
            ok, locked_reason, _ = fs_is_lesson_accessible_for_user(session, user_id, lesson_id)
            if not ok:
                return jsonify({'error': locked_reason or 'Урок недоступен'}), 403

        blocks = fs_read_blocks(lesson.path)
        result_blocks: list[dict] = []

        is_admin_like = _effective_role(user_info) in ('admin', 'super_admin')

        for b in blocks:
            block_type = (b.get("block_type") or "").strip()
            block_id = b.get("id")
            order = int(b.get("order") or 0)
            content = b.get("content") if isinstance(b.get("content"), dict) else {}
            if block_type in ("heading", "text"):
                text_file = lesson.path / "texts" / f"block-{block_id}.txt"
                if text_file.exists():
                    try:
                        text_value = text_file.read_text(encoding="utf-8")
                        if content.get("html"):
                            content["html"] = text_value
                        else:
                            content["text"] = text_value
                    except Exception:
                        pass
            elif block_type == "test":
                tests_dir = ensure_test_dirs(str(lesson.path))
                # каждый тест-блок лежит в отдельной папке
                test_dir = os.path.join(tests_dir, f"block-{block_id}")
                cfg = read_test_config(test_dir)
                questions_dir = os.path.join(test_dir, "questions")
                questions = read_questions_from_dir(questions_dir)

                settings = {
                    "pass_percent": cfg.pass_percent,
                    "limit_attempts": cfg.limit_attempts,
                    "max_attempts": cfg.max_attempts,
                    "available_from": cfg.available_from if cfg.test_type == "temporary" else None,
                    "available_until": cfg.available_until if cfg.test_type == "temporary" else None,
                    "shuffle_questions": cfg.shuffle_questions,
                    "shuffle_options": cfg.shuffle_options,
                    "time_limit_seconds": cfg.time_limit_seconds,
                }
                if not is_admin_like:
                    for q in questions:
                        if isinstance(q, dict):
                            q.pop("correct_answer", None)
                            q.pop("accepted_answers", None)
                content = {
                    "title": cfg.title,
                    "settings": settings,
                    "questions": questions,
                }

            result_blocks.append({
                "id": block_id,
                "lesson_id": lesson_id,
                "block_type": block_type,
                "order": order,
                "content": content,
            })

        return jsonify({
            'blocks': result_blocks,
            'total': len(result_blocks)
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        session.close()


@api_bp.route('/lessons/<int:lesson_id>/blocks', methods=['POST'])
def create_lesson_block(lesson_id: int):
    """Добавить блок контента к уроку (admin only)."""
    session = get_db_session()
    try:
        # Проверка прав администратора (admin или super_admin)
        deny = _require_admin(g.get('user_info', None))
        if deny:
            return deny
        lesson = fs_find_lesson(lesson_id)
        if not lesson:
            return jsonify({'error': 'Урок не найден'}), 404
        
        data = request.get_json()
        if not data:
            return jsonify({'error': 'Данные не предоставлены'}), 400
        
        block_type = data.get('block_type', '').strip()
        if block_type not in ['heading', 'text', 'video', 'file', 'image', 'test']:
            return jsonify({'error': 'Неверный тип блока'}), 400

        blocks = fs_read_blocks(lesson.path)
        new_id = fs_next_block_id(blocks)
        max_order = max([int(b.get("order") or 0) for b in blocks], default=-1)
        order = max_order + 1

        content = data.get("content") if isinstance(data.get("content"), dict) else {}

        # FS side-effects
        if block_type in ("heading", "text"):
            text_value = content.get("text") or content.get("html") or ""
            try:
                (lesson.path / "texts").mkdir(parents=True, exist_ok=True)
                (lesson.path / "texts" / f"block-{new_id}.txt").write_text(str(text_value), encoding="utf-8")
            except Exception:
                pass
        elif block_type == "test":
            tests_dir = ensure_test_dirs(str(lesson.path))
            test_dir = os.path.join(tests_dir, f"block-{new_id}")
            os.makedirs(os.path.join(test_dir, "questions"), exist_ok=True)
            cfg_raw = content.get("settings") if isinstance(content.get("settings"), dict) else {}
            cfg = FsTestConfig(
                title=str(content.get("title") or "Тест"),
                pass_percent=int(cfg_raw.get("pass_percent") or 70),
                limit_attempts=bool(cfg_raw.get("limit_attempts")),
                max_attempts=int(cfg_raw.get("max_attempts")) if cfg_raw.get("max_attempts") else None,
                test_type="temporary" if (cfg_raw.get("available_from") or cfg_raw.get("available_until")) else "permanent",
                available_from=cfg_raw.get("available_from") if isinstance(cfg_raw.get("available_from"), str) else None,
                available_until=cfg_raw.get("available_until") if isinstance(cfg_raw.get("available_until"), str) else None,
                shuffle_questions=bool(cfg_raw.get("shuffle_questions")),
                shuffle_options=bool(cfg_raw.get("shuffle_options")),
                time_limit_seconds=_parse_time_limit_seconds(cfg_raw),
            )
            write_test_config(test_dir, cfg)
            questions = content.get("questions") if isinstance(content.get("questions"), list) else []
            write_questions_to_dir(os.path.join(test_dir, "questions"), [q for q in questions if isinstance(q, dict)])
            # В blocks.json для теста держим только мета
            content = {"title": cfg.title}

        block = {"id": new_id, "lesson_id": lesson_id, "block_type": block_type, "order": order, "content": content}
        blocks.append(block)
        fs_write_blocks(lesson.path, blocks)
        return jsonify(block), 201
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        session.close()


@api_bp.route('/lessons/<int:lesson_id>/blocks/<int:block_id>', methods=['PUT'])
def update_lesson_block(lesson_id: int, block_id: int):
    """Обновить блок контента урока (admin only)."""
    session = get_db_session()
    try:
        # Проверка прав администратора (admin или super_admin)
        deny = _require_admin(g.get('user_info', None))
        if deny:
            return deny

        lesson = fs_find_lesson(lesson_id)
        if not lesson:
            return jsonify({'error': 'Урок не найден'}), 404
        blocks = fs_read_blocks(lesson.path)
        block = next((b for b in blocks if int(b.get("id") or 0) == block_id), None)
        if not block:
            return jsonify({'error': 'Блок не найден'}), 404
        
        data = request.get_json()
        if not data:
            return jsonify({'error': 'Данные не предоставлены'}), 400

        if 'block_type' in data:
            bt = str(data.get('block_type') or '').strip()
            if bt not in ['heading', 'text', 'video', 'file', 'image', 'test']:
                return jsonify({'error': 'Неверный тип блока'}), 400
            block['block_type'] = bt

        if 'content' in data and isinstance(data.get('content'), dict):
            block['content'] = data.get('content') or {}

        if 'order' in data:
            try:
                block['order'] = int(data.get('order') or 0)
            except Exception:
                block['order'] = 0

        bt_eff = str(block.get('block_type') or '').strip()
        content = block.get('content') if isinstance(block.get('content'), dict) else {}

        if bt_eff in ("heading", "text"):
            text_value = content.get("text") or content.get("html") or ""
            try:
                (lesson.path / "texts").mkdir(parents=True, exist_ok=True)
                (lesson.path / "texts" / f"block-{block_id}.txt").write_text(str(text_value), encoding="utf-8")
            except Exception:
                pass
        elif bt_eff == "test":
            tests_dir = ensure_test_dirs(str(lesson.path))
            test_dir = os.path.join(tests_dir, f"block-{block_id}")
            os.makedirs(os.path.join(test_dir, "questions"), exist_ok=True)
            settings = content.get("settings") if isinstance(content.get("settings"), dict) else {}
            cfg = FsTestConfig(
                title=str(content.get("title") or "Тест"),
                pass_percent=int(settings.get("pass_percent") or 70),
                limit_attempts=bool(settings.get("limit_attempts")),
                max_attempts=int(settings.get("max_attempts")) if settings.get("max_attempts") else None,
                test_type="temporary" if (settings.get("available_from") or settings.get("available_until")) else "permanent",
                available_from=settings.get("available_from") if isinstance(settings.get("available_from"), str) else None,
                available_until=settings.get("available_until") if isinstance(settings.get("available_until"), str) else None,
                shuffle_questions=bool(settings.get("shuffle_questions")),
                shuffle_options=bool(settings.get("shuffle_options")),
                time_limit_seconds=_parse_time_limit_seconds(settings),
            )
            write_test_config(test_dir, cfg)
            questions = content.get("questions") if isinstance(content.get("questions"), list) else []
            write_questions_to_dir(os.path.join(test_dir, "questions"), [q for q in questions if isinstance(q, dict)])
            block["content"] = {"title": cfg.title}

        fs_write_blocks(lesson.path, blocks)
        return jsonify(block)
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        session.close()


@api_bp.route('/lessons/<int:lesson_id>/blocks/<int:block_id>', methods=['DELETE'])
def delete_lesson_block(lesson_id: int, block_id: int):
    """Удалить блок контента урока (admin only)."""
    session = get_db_session()
    try:
        # Проверка прав администратора (admin или super_admin)
        deny = _require_admin(g.get('user_info', None))
        if deny:
            return deny

        lesson = fs_find_lesson(lesson_id)
        if not lesson:
            return jsonify({'error': 'Урок не найден'}), 404
        blocks = fs_read_blocks(lesson.path)
        idx = next((i for i, b in enumerate(blocks) if int(b.get("id") or 0) == block_id), -1)
        if idx < 0:
            return jsonify({'error': 'Блок не найден'}), 404
        bt = str(blocks[idx].get("block_type") or "")
        blocks.pop(idx)
        fs_write_blocks(lesson.path, blocks)

        # best-effort cleanup
        try:
            if bt in ("heading", "text"):
                p = lesson.path / "texts" / f"block-{block_id}.txt"
                if p.exists():
                    p.unlink()
            if bt == "test":
                tests_dir = ensure_test_dirs(str(lesson.path))
                td = os.path.join(tests_dir, f"block-{block_id}")
                if os.path.isdir(td):
                    import shutil
                    shutil.rmtree(td, ignore_errors=True)
        except Exception:
            pass

        return jsonify({'message': 'Блок удален'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        session.close()


def _parse_time_limit_seconds(raw: dict) -> Optional[int]:
    """Из настроек теста извлечь time_limit_seconds (поддержка seconds, enabled+minutes)."""
    if not raw or not isinstance(raw, dict):
        return None
    tl = raw.get("time_limit_seconds")
    if tl is not None:
        try:
            s = int(tl)
            return s if s > 0 else None
        except (TypeError, ValueError):
            pass
    if raw.get("time_limit_enabled") and raw.get("time_limit_minutes") is not None:
        try:
            m = int(raw["time_limit_minutes"])
            return (m * 60) if m > 0 else None
        except (TypeError, ValueError):
            pass
    return None


def _normalize_correct_answer(ca):
    """Привести correct_answer к отсортированному списку индексов."""
    if ca is None:
        return []
    if isinstance(ca, (int, float)):
        return [int(ca)] if int(ca) >= 0 else []
    if isinstance(ca, (list, tuple)):
        return sorted(int(x) for x in ca if isinstance(x, (int, float)) and int(x) >= 0)
    return []


@api_bp.route('/lessons/<int:lesson_id>/blocks/<int:block_id>/submit-test/last', methods=['GET'])
def get_last_lesson_test_result(lesson_id: int, block_id: int):
    """Последняя попытка прохождения теста для текущего пользователя (если он уже проходил тест)."""
    import json as _json
    session = get_db_session()
    try:
        from flask import g
        user_info = g.get('user_info', {})
        username = user_info.get('username')
        user_id = None
        if username:
            user = session.query(User).filter(User.username == username).first()
            if user:
                user_id = user.id
        if not user_id:
            return jsonify({'error': 'Пользователь не найден'}), 404

        lesson = fs_find_lesson(lesson_id)
        if not lesson:
            return jsonify({'error': 'Урок не найден'}), 404

        blocks = fs_read_blocks(lesson.path)
        block = next((b for b in blocks if isinstance(b, dict) and int(b.get("id") or 0) == block_id), None)
        if not block or str(block.get("block_type") or "") != "test":
            return jsonify({'error': 'Блок не найден'}), 404

        attempts_q = session.query(LessonTestResult).filter(
            LessonTestResult.user_id == user_id,
            LessonTestResult.lesson_id == lesson_id,
            LessonTestResult.block_id == block_id,
        ).order_by(LessonTestResult.attempt_number.asc())
        results = attempts_q.all()
        if not results:
            return jsonify({'has_result': False}), 404

        last_result = results[-1]
        attempts_used = len(results)

        tests_dir = ensure_test_dirs(str(lesson.path))
        test_dir = os.path.join(tests_dir, f"block-{block_id}")
        cfg = read_test_config(test_dir)

        max_attempts = cfg.max_attempts if cfg.limit_attempts else None
        limit_attempts = bool(cfg.limit_attempts and max_attempts is not None)
        attempts_left = None
        if limit_attempts:
            attempts_left = max(0, (max_attempts or 0) - attempts_used)

        pass_percent = int(cfg.pass_percent or 70)

        payload = {}
        try:
            payload = _json.loads(last_result.answers or "{}")
        except Exception:
            payload = {}

        fb = payload.get("feedback") or []

        return jsonify({
            'has_result': True,
            'score': last_result.score,
            'total': last_result.total,
            'score_percent': last_result.score_percent,
            'passed': bool(last_result.passed),
            'feedback': fb,
            'attempts_used': attempts_used,
            'attempts_left': attempts_left,
            'max_attempts': max_attempts,
            'pass_percent': pass_percent,
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        session.close()


@api_bp.route('/lessons/<int:lesson_id>/blocks/<int:block_id>/submit-test', methods=['POST'])
def submit_lesson_test(lesson_id: int, block_id: int):
    """Отправить ответы на тест в блоке урока. Проверка правильности на сервере, учёт попыток и настроек."""
    import json as _json
    session = get_db_session()
    try:
        from flask import g
        user_info = g.get('user_info', {})
        username = user_info.get('username')
        user_role = _effective_role(user_info)
        user_id = None
        if username:
            user = session.query(User).filter(User.username == username).first()
            if user:
                user_id = user.id

        lesson = fs_find_lesson(lesson_id)
        if not lesson:
            return jsonify({'error': 'Урок не найден'}), 404

        if user_id:
            is_accessible, locked_reason, _ = fs_is_lesson_accessible_for_user(session, user_id, lesson_id)
            if not is_accessible:
                return jsonify({'error': locked_reason or 'Урок недоступен'}), 403

        blocks = fs_read_blocks(lesson.path)
        block = next((b for b in blocks if isinstance(b, dict) and int(b.get("id") or 0) == block_id), None)
        if not block or str(block.get("block_type") or "") != "test":
            return jsonify({'error': 'Блок не найден'}), 404

        tests_dir = ensure_test_dirs(str(lesson.path))
        test_dir = os.path.join(tests_dir, f"block-{block_id}")
        cfg = read_test_config(test_dir)
        questions_dir = os.path.join(test_dir, "questions")
        questions = read_questions_from_dir(questions_dir)
        if not cfg.enabled:
            return jsonify({'error': 'Тест отключён'}), 403
        if not questions:
            return jsonify({'error': 'В тесте нет вопросов'}), 400

        # Проверка доступности по настройкам теста (дата/время)
        from datetime import datetime, timedelta, timezone
        now = datetime.utcnow()
        available_from_raw = cfg.available_from if cfg.test_type == "temporary" else None
        available_until_raw = cfg.available_until if cfg.test_type == "temporary" else None
        def _parse_dt(value: Optional[str]) -> Optional[datetime]:
            """Разобрать дату/время теста, считая локальным временем Екатеринбурга (UTC+5), если часовой пояс не указан.

            Возвращает naive-дату в UTC, чтобы сравнение с datetime.utcnow() было корректным.
            """
            if not value or not isinstance(value, str):
                return None
            try:
                dt = datetime.fromisoformat(value)
            except Exception:
                return None

            ekb_offset = timedelta(hours=5)

            # Если в строке нет таймзоны — считаем, что это время Екатеринбурга (UTC+5)
            if dt.tzinfo is None:
                return dt - ekb_offset

            # Если таймзона есть — переводим в UTC и убираем tzinfo
            return dt.astimezone(timezone.utc).replace(tzinfo=None)
        available_from = _parse_dt(available_from_raw)
        available_until = _parse_dt(available_until_raw)
        if available_from and now < available_from:
            return jsonify({'error': 'Тест ещё недоступен', 'code': 'not_started'}), 403
        if available_until and now > available_until:
            return jsonify({'error': 'Срок действия теста истёк', 'code': 'expired'}), 403

        # Ограничение по попыткам
        max_attempts = cfg.max_attempts if cfg.limit_attempts else None
        limit_attempts = bool(cfg.limit_attempts and max_attempts is not None)

        attempts_used = 0
        last_result: Optional[LessonTestResult] = None
        if user_id:
            attempts_q = session.query(LessonTestResult).filter(
                LessonTestResult.user_id == user_id,
                LessonTestResult.lesson_id == lesson_id,
                LessonTestResult.block_id == block_id,
            ).order_by(LessonTestResult.attempt_number.asc())
            results = attempts_q.all()
            attempts_used = len(results)
            if results:
                last_result = results[-1]
        if limit_attempts and attempts_used >= (max_attempts or 0):
            return jsonify({
                'error': 'Исчерпано количество попыток для этого теста',
                'code': 'attempts_exhausted',
                'attempts_used': attempts_used,
                'max_attempts': max_attempts,
                'last_result': last_result.to_dict() if last_result else None,
            }), 403

        data = request.get_json() or {}
        answers_raw = data.get('answers')
        if not isinstance(answers_raw, list):
            return jsonify({'error': 'Неверный формат ответов'}), 400

        feedback = []
        correct_count = 0
        for q_index, q in enumerate(questions):
            if not isinstance(q, dict):
                feedback.append({'questionIndex': q_index, 'correct': False, 'explanation': None})
                continue
            answer_type = (q.get('answer_type') or '').lower()
            if not answer_type:
                answer_type = 'multiple' if q.get('multiple') else 'single'

            options = q.get('options') or []
            user_selected = []
            user_answer_text = None

            if q_index < len(answers_raw):
                val = answers_raw[q_index]
                if answer_type == 'input':
                    if isinstance(val, str):
                        user_answer_text = val.strip()
                    elif isinstance(val, (list, tuple)) and val:
                        first = val[0]
                        if isinstance(first, str):
                            user_answer_text = first.strip()
                else:
                    if isinstance(val, (int, float)):
                        user_selected = [int(val)] if int(val) >= 0 else []
                    elif isinstance(val, (list, tuple)):
                        user_selected = sorted(int(x) for x in val if isinstance(x, (int, float)) and int(x) >= 0)

            if answer_type == 'input':
                accepted_answers = q.get('accepted_answers') or []
                normalized_accepted = [str(a).strip().lower() for a in accepted_answers if isinstance(a, str) and a.strip()]
                ua_norm = (user_answer_text or '').strip().lower()
                is_correct = bool(ua_norm and ua_norm in normalized_accepted)
                if is_correct:
                    correct_count += 1
                feedback.append({
                    'questionIndex': q_index,
                    'correct': is_correct,
                    'userAnswerText': user_answer_text,
                    'acceptedAnswersText': accepted_answers,
                    'answerType': 'input',
                })
            else:
                correct_answer = _normalize_correct_answer(q.get('correct_answer'))
                is_correct = user_selected == correct_answer
                if is_correct:
                    correct_count += 1
                correct_options_text = [options[i] for i in correct_answer if 0 <= i < len(options)]
                feedback.append({
                    'questionIndex': q_index,
                    'correct': is_correct,
                    'userSelected': user_selected,
                    'correctAnswer': correct_answer,
                    'correctOptionsText': correct_options_text,
                    'answerType': 'multiple' if q.get('multiple') else 'single',
                })
        total = len(questions)
        score_pct = round((correct_count / total) * 100, 0) if total else 0
        pass_percent = int(cfg.pass_percent or 70)
        passed = score_pct >= pass_percent

        # Сохраняем результат попытки
        attempts_used_after = attempts_used
        attempts_left = None
        if user_id:
            attempts_used_after = attempts_used + 1
            result_row = LessonTestResult(
                user_id=user_id,
                lesson_id=lesson_id,
                block_id=block_id,
                attempt_number=attempts_used_after,
                score=correct_count,
                total=total,
                score_percent=int(score_pct),
                passed=bool(passed),
                answers=_json.dumps({
                    'answers': answers_raw,
                    'feedback': feedback,
                }),
            )
            session.add(result_row)
            session.commit()
        if limit_attempts and max_attempts is not None:
            attempts_left = max(0, max_attempts - attempts_used_after)

        return jsonify({
            'score': correct_count,
            'total': total,
            'score_percent': score_pct,
            'passed': passed,
            'feedback': feedback,
            'attempts_used': attempts_used_after,
            'max_attempts': max_attempts,
            'attempts_left': attempts_left,
            'pass_percent': pass_percent,
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        session.close()


@api_bp.route('/lessons/<int:lesson_id>/tests/status', methods=['GET'])
def get_lesson_tests_status(lesson_id: int):
    """Статус тестов в уроке для текущего пользователя (пройден/попытки)."""
    session = get_db_session()
    try:
        from flask import g
        user_info = g.get('user_info', {})
        username = user_info.get('username')
        if not username:
            return jsonify({'error': 'Пользователь не аутентифицирован'}), 401

        user = session.query(User).filter(User.username == username).first()
        if not user:
            return jsonify({'error': 'Пользователь не найден'}), 404

        lesson = fs_find_lesson(lesson_id)
        if not lesson:
            return jsonify({'error': 'Урок не найден'}), 404

        # Проверка доступа
        is_accessible, locked_reason, _ = fs_is_lesson_accessible_for_user(session, user.id, lesson_id)
        if not is_accessible:
            return jsonify({'error': locked_reason or 'Урок недоступен'}), 403

        gate = _lesson_test_gate_for_user(session, user.id, lesson_id)
        return jsonify(gate)
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        session.close()


# ----------------------- Tests Catalog Endpoints -----------------------

def _lesson_test_public_id(lesson_id: int, block_id: int) -> str:
    return f"lesson-{lesson_id}-block-{block_id}"


def _parse_lesson_test_public_id(test_id: str) -> tuple[int, int] | tuple[None, None]:
    try:
        parts = (test_id or "").strip().split("-")
        # lesson-<lesson_id>-block-<block_id>
        if len(parts) != 4 or parts[0] != "lesson" or parts[2] != "block":
            return None, None
        return int(parts[1]), int(parts[3])
    except Exception:
        return None, None


@api_bp.route('/tests', methods=['GET'])
def list_tests_catalog():
    """Каталог тестов: тесты в уроках + глобальные тесты (если включены)."""
    session = get_db_session()
    try:
        from flask import g
        user_info = g.get('user_info', {}) or {}
        username = user_info.get('username')
        user = None
        if username:
            user = session.query(User).filter(User.username == username).first()
        if not user:
            return jsonify({'error': 'Пользователь не аутентифицирован'}), 401

        effective_role = _effective_role(user_info)
        is_admin_like = effective_role in ('admin', 'super_admin')

        # Админ может смотреть каталог тестов "глазами" другого пользователя
        # (нужно для страницы профиля пользователя).
        target_user = user
        if is_admin_like:
            user_id_q = request.args.get("user_id")
            if user_id_q is not None:
                try:
                    uid = int(user_id_q)
                    other = session.query(User).filter(User.id == uid).first()
                    if other:
                        target_user = other
                except Exception:
                    pass

        # 1) Тесты в уроках (FS)
        lesson_tests: list[dict] = []
        try:
            from backend.utils.content_fs import load_categories as fs_load_categories, load_courses as fs_load_courses, load_lessons as fs_load_lessons  # type: ignore
            for cat in fs_load_categories():
                for course in fs_load_courses(cat):
                    for lesson in fs_load_lessons(course):
                        if not is_admin_like:
                            ok, _, _ = fs_is_lesson_accessible_for_user(session, target_user.id, lesson.id)
                            if not ok:
                                continue
                        blocks = fs_read_blocks(lesson.path)
                        for b in blocks:
                            if (b.get("block_type") or "").strip() != "test":
                                continue
                            block_id = b.get("id")
                            if block_id is None:
                                continue
                            tests_dir = ensure_test_dirs(str(lesson.path))
                            test_dir = os.path.join(tests_dir, f"block-{block_id}")
                            cfg = read_test_config(test_dir)
                            questions_dir = os.path.join(test_dir, "questions")
                            questions = read_questions_from_dir(questions_dir)
                            # пропускаем пустые/выключенные/временные
                            if (not questions) or (not cfg.enabled) or (str(cfg.test_type or "").strip() == "temporary"):
                                continue

                            lesson_tests.append({
                                "kind": "lesson",
                                "id": _lesson_test_public_id(lesson.id, int(block_id)),
                                "title": cfg.title or "Тест",
                                "source": {
                                    "category_id": cat.id,
                                    "category_title": cat.title,
                                    "course_id": course.id,
                                    "course_title": course.title,
                                    "lesson_id": lesson.id,
                                    "lesson_title": lesson.title,
                                    "block_id": int(block_id),
                                },
                            })
        except Exception:
            # каталог уроков не критичен для работоспособности страницы
            pass

        # Последние результаты пользователя по тестам в уроках
        lesson_last_by_key: dict = {}
        if lesson_tests and target_user:
            from database.models import LessonTestResult  # type: ignore
            for r in session.query(LessonTestResult).filter(
                LessonTestResult.user_id == target_user.id,
            ).all():
                key = (r.lesson_id, r.block_id)
                if key not in lesson_last_by_key or r.attempt_number > lesson_last_by_key[key].attempt_number:
                    lesson_last_by_key[key] = r
            for lt in lesson_tests:
                src = lt.get("source") or {}
                lid = src.get("lesson_id")
                bid = src.get("block_id")
                last_r = lesson_last_by_key.get((lid, bid)) if lid is not None and bid is not None else None
                if last_r:
                    lt["last_result"] = {
                        "passed": bool(last_r.passed),
                        "score": last_r.score,
                        "total": last_r.total,
                        "score_percent": last_r.score_percent,
                        "attempt_number": last_r.attempt_number,
                        "created_at": last_r.created_at.isoformat() if last_r.created_at else None,
                    }
                else:
                    lt["last_result"] = None

        # 2) Глобальные тесты (БД) + последний результат пользователя
        global_tests: list[dict] = []
        try:
            from database.models import GlobalTest, GlobalTestResult  # type: ignore
            q = session.query(GlobalTest)
            if not is_admin_like:
                q = q.filter(GlobalTest.is_active == True)  # noqa: E712
            gt_list = q.order_by(GlobalTest.updated_at.desc(), GlobalTest.created_at.desc()).all()
            gt_ids = [g.id for g in gt_list]
            last_by_test: dict = {}
            if gt_ids and target_user:
                for r in session.query(GlobalTestResult).filter(
                    GlobalTestResult.user_id == target_user.id,
                    GlobalTestResult.global_test_id.in_(gt_ids),
                ).all():
                    tid = r.global_test_id
                    if tid not in last_by_test or r.attempt_number > last_by_test[tid].attempt_number:
                        last_by_test[tid] = r
            for gt in gt_list:
                st = gt._settings_dict() if hasattr(gt, '_settings_dict') and callable(getattr(gt, '_settings_dict')) else {}
                limit_attempts = bool(st.get('limit_attempts'))
                max_attempts = None
                if limit_attempts and st.get('max_attempts') is not None:
                    try:
                        max_attempts = int(st.get('max_attempts'))
                    except (TypeError, ValueError):
                        pass
                last_r = last_by_test.get(gt.id)
                last_result = None
                if last_r:
                    last_result = {
                        "passed": bool(last_r.passed),
                        "score": last_r.score,
                        "total": last_r.total,
                        "score_percent": last_r.score_percent,
                        "attempt_number": last_r.attempt_number,
                        "created_at": last_r.created_at.isoformat() if last_r.created_at else None,
                    }
                global_tests.append({
                    "kind": "global",
                    "id": str(gt.id),
                    "title": gt.title,
                    "source": {"global_test_id": gt.id},
                    "is_active": bool(gt.is_active),
                    "updated_at": gt.updated_at.isoformat() if gt.updated_at else None,
                    "settings": st,
                    "limit_attempts": limit_attempts,
                    "max_attempts": max_attempts,
                    "last_result": last_result,
                })
        except Exception:
            pass

        tests = lesson_tests + global_tests
        return jsonify({"tests": tests, "total": len(tests)})
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        session.close()


@api_bp.route('/tests/<string:kind>/<path:test_id>', methods=['GET'])
def get_test_details(kind: str, test_id: str):
    """Детали теста из каталога."""
    session = get_db_session()
    try:
        from flask import g
        user_info = g.get('user_info', {}) or {}
        username = user_info.get('username')
        user = None
        if username:
            user = session.query(User).filter(User.username == username).first()
        if not user:
            return jsonify({'error': 'Пользователь не аутентифицирован'}), 401

        effective_role = _effective_role(user_info)
        is_admin_like = effective_role in ('admin', 'super_admin')

        if kind == "lesson":
            lesson_id, block_id = _parse_lesson_test_public_id(test_id)
            if not lesson_id or not block_id:
                return jsonify({"error": "Некорректный идентификатор теста"}), 400
            lesson = fs_find_lesson(int(lesson_id))
            if not lesson:
                return jsonify({"error": "Урок не найден"}), 404
            if not is_admin_like:
                ok, locked_reason, _ = fs_is_lesson_accessible_for_user(session, user.id, int(lesson_id))
                if not ok:
                    return jsonify({"error": locked_reason or "Урок недоступен"}), 403

            tests_dir = ensure_test_dirs(str(lesson.path))
            test_dir = os.path.join(tests_dir, f"block-{block_id}")
            cfg = read_test_config(test_dir)
            questions_dir = os.path.join(test_dir, "questions")
            questions = read_questions_from_dir(questions_dir)
            if not is_admin_like:
                for q in questions:
                    if isinstance(q, dict):
                        q.pop("correct_answer", None)
                        q.pop("accepted_answers", None)
            return jsonify({
                "kind": "lesson",
                "id": test_id,
                "title": cfg.title,
                "settings": {
                    "pass_percent": cfg.pass_percent,
                    "limit_attempts": cfg.limit_attempts,
                    "max_attempts": cfg.max_attempts,
                    "shuffle_questions": cfg.shuffle_questions,
                    "shuffle_options": cfg.shuffle_options,
                    "time_limit_seconds": cfg.time_limit_seconds,
                },
                "questions": questions,
                "source": {"lesson_id": int(lesson_id), "block_id": int(block_id)},
            })

        if kind == "global":
            try:
                from database.models import GlobalTest, GlobalTestQuestion  # type: ignore
            except Exception:
                return jsonify({"error": "Глобальные тесты не поддерживаются в этой версии"}), 404
            gt = session.query(GlobalTest).filter(GlobalTest.id == int(test_id)).first()
            if not gt:
                return jsonify({"error": "Тест не найден"}), 404
            if (not is_admin_like) and (not gt.is_active):
                return jsonify({"error": "Тест недоступен"}), 403
            qs = session.query(GlobalTestQuestion).filter(GlobalTestQuestion.global_test_id == gt.id).order_by(GlobalTestQuestion.order.asc()).all()
            questions = [q.to_public_dict(include_correct=is_admin_like) for q in qs]
            return jsonify({
                "kind": "global",
                "id": str(gt.id),
                "title": gt.title,
                "description": gt.description,
                "is_active": bool(gt.is_active),
                "questions": questions,
            })

        return jsonify({"error": "Неизвестный тип теста"}), 400
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        session.close()


# ----------------------- Global Tests Endpoints -----------------------

def _normalize_answer_value(val):
    # Для единообразия: list[int] для choice, str для input
    if isinstance(val, list):
        out = []
        for x in val:
            try:
                out.append(int(x))
            except Exception:
                continue
        return out
    if val is None:
        return ""
    return str(val).strip()


def _evaluate_questions_payload(questions: list[dict], answers_raw: list):
    """Возвращает (correct_count, total, feedback:list[dict])."""
    feedback: list[dict] = []
    correct_count = 0
    total = len(questions)

    for q_index, q in enumerate(questions):
        if not isinstance(q, dict):
            continue
        answer_type = str(q.get("answer_type") or ("multiple" if q.get("multiple") else "single")).lower()
        user_val = answers_raw[q_index] if q_index < len(answers_raw) else ([] if answer_type != "input" else "")
        user_norm = _normalize_answer_value(user_val)

        is_correct = False
        correct_answer = q.get("correct_answer")
        accepted_answers = q.get("accepted_answers") or []

        if answer_type == "input":
            ua = str(user_norm or "").strip().lower()
            normalized_accepted = [str(a).strip().lower() for a in accepted_answers if isinstance(a, str) and str(a).strip()]
            is_correct = bool(ua) and (ua in normalized_accepted)
        else:
            # correct_answer: один индекс (int/float) или список индексов
            correct_list = []
            if isinstance(correct_answer, list):
                for x in correct_answer:
                    try:
                        correct_list.append(int(x))
                    except Exception:
                        pass
            elif isinstance(correct_answer, (int, float)):
                try:
                    correct_list = [int(correct_answer)]
                except Exception:
                    pass
            user_list = user_norm if isinstance(user_norm, list) else []
            is_correct = sorted(user_list) == sorted(correct_list)

        if is_correct:
            correct_count += 1

        # тексты вариантов для фронта (по возможности)
        options = q.get("options") if isinstance(q.get("options"), list) else []
        def opt_text(idx):
            try:
                return str(options[int(idx)])
            except Exception:
                return ""

        fb = {
            "correct": bool(is_correct),
            "answerType": answer_type,
            "userSelected": user_norm if isinstance(user_norm, list) else [],
            "userAnswerText": user_norm if isinstance(user_norm, str) else "",
            "correctAnswer": correct_answer if isinstance(correct_answer, list) else [],
            "correctOptionsText": [opt_text(i) for i in (correct_answer or [])] if isinstance(correct_answer, list) else [],
            "acceptedAnswersText": accepted_answers if isinstance(accepted_answers, list) else [],
        }
        feedback.append(fb)

    return correct_count, total, feedback


@api_bp.route('/global-tests/<int:test_id>', methods=['GET'])
def get_global_test(test_id: int):
    """Получить глобальный тест и вопросы."""
    session = get_db_session()
    try:
        from flask import g
        user_info = g.get('user_info', {}) or {}
        username = user_info.get('username')
        user = session.query(User).filter(User.username == username).first() if username else None
        if not user:
            return jsonify({'error': 'Пользователь не аутентифицирован'}), 401

        effective_role = _effective_role(user_info)
        is_admin_like = effective_role in ('admin', 'super_admin')

        from database.models import GlobalTest, GlobalTestQuestion  # type: ignore
        gt = session.query(GlobalTest).filter(GlobalTest.id == test_id).first()
        if not gt:
            return jsonify({'error': 'Тест не найден'}), 404
        if (not is_admin_like) and (not gt.is_active):
            return jsonify({'error': 'Тест недоступен'}), 403
        qs = session.query(GlobalTestQuestion).filter(GlobalTestQuestion.global_test_id == gt.id).order_by(GlobalTestQuestion.order.asc()).all()
        return jsonify({
            "test": gt.to_dict(),
            "questions": [q.to_public_dict(include_correct=is_admin_like) for q in qs],
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        session.close()


@api_bp.route('/global-tests', methods=['POST'])
def create_global_test():
    """Создать глобальный тест (admin+)."""
    session = get_db_session()
    try:
        deny = _require_admin(g.get('user_info', None))
        if deny:
            return deny
        user_info = g.get('user_info', {}) or {}
        username = user_info.get('username')
        user = session.query(User).filter(User.username == username).first() if username else None
        if not user:
            return jsonify({'error': 'Пользователь не найден'}), 404

        data = request.get_json() or {}
        title = str(data.get("title") or "").strip()
        if not title:
            return jsonify({"error": "Название теста обязательно"}), 400
        description = str(data.get("description") or "").strip()
        is_active = bool(data.get("is_active", True))
        questions = data.get("questions") if isinstance(data.get("questions"), list) else []
        settings_raw = data.get("settings")
        settings_json = _json.dumps(settings_raw, ensure_ascii=False) if isinstance(settings_raw, dict) else None

        from database.models import GlobalTest, GlobalTestQuestion, NewsEvent  # type: ignore

        gt = GlobalTest(title=title, description=description, is_active=is_active, settings=settings_json, created_by=user.id)
        session.add(gt)
        session.flush()

        order = 0
        for q in questions:
            if not isinstance(q, dict):
                continue
            session.add(GlobalTestQuestion(global_test_id=gt.id, order=order, content=_json.dumps(q, ensure_ascii=False)))
            order += 1

        # news
        try:
            session.add(NewsEvent(
                event_type="global_test_created",
                title=f"Новый тест: {title}",
                body=description or None,
                meta=_json.dumps({"global_test_id": gt.id}, ensure_ascii=False),
                created_by=user.id,
            ))
        except Exception:
            pass

        session.commit()
        return jsonify({"test": gt.to_dict()}), 201
    except Exception as e:
        session.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        session.close()


@api_bp.route('/global-tests/<int:test_id>', methods=['PUT'])
def update_global_test(test_id: int):
    """Обновить глобальный тест (admin+)."""
    session = get_db_session()
    try:
        deny = _require_admin(g.get('user_info', None))
        if deny:
            return deny
        user_info = g.get('user_info', {}) or {}
        username = user_info.get('username')
        user = session.query(User).filter(User.username == username).first() if username else None
        if not user:
            return jsonify({'error': 'Пользователь не найден'}), 404

        from database.models import GlobalTest, GlobalTestQuestion, NewsEvent  # type: ignore
        gt = session.query(GlobalTest).filter(GlobalTest.id == test_id).first()
        if not gt:
            return jsonify({'error': 'Тест не найден'}), 404

        data = request.get_json() or {}
        if "title" in data:
            gt.title = str(data.get("title") or "").strip() or gt.title
        if "description" in data:
            gt.description = str(data.get("description") or "").strip()
        if "is_active" in data:
            gt.is_active = bool(data.get("is_active"))
        if "settings" in data and isinstance(data.get("settings"), dict):
            gt.settings = _json.dumps(data.get("settings"), ensure_ascii=False)

        if "questions" in data and isinstance(data.get("questions"), list):
            # Полная замена вопросов
            session.query(GlobalTestQuestion).filter(GlobalTestQuestion.global_test_id == gt.id).delete()
            order = 0
            for q in (data.get("questions") or []):
                if not isinstance(q, dict):
                    continue
                session.add(GlobalTestQuestion(global_test_id=gt.id, order=order, content=_json.dumps(q, ensure_ascii=False)))
                order += 1

        # news
        try:
            session.add(NewsEvent(
                event_type="global_test_updated",
                title=f"Обновлён тест: {gt.title}",
                body=None,
                meta=_json.dumps({"global_test_id": gt.id}, ensure_ascii=False),
                created_by=user.id,
            ))
        except Exception:
            pass

        session.commit()
        return jsonify({"test": gt.to_dict()}), 200
    except Exception as e:
        session.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        session.close()


@api_bp.route('/global-tests/<int:test_id>', methods=['DELETE'])
def delete_global_test(test_id: int):
    """Удалить глобальный тест (super_admin)."""
    session = get_db_session()
    try:
        deny = _require_super_admin(g.get('user_info', None))
        if deny:
            return deny
        from database.models import GlobalTest, GlobalTestQuestion  # type: ignore
        gt = session.query(GlobalTest).filter(GlobalTest.id == test_id).first()
        if not gt:
            return jsonify({'error': 'Тест не найден'}), 404
        session.query(GlobalTestQuestion).filter(GlobalTestQuestion.global_test_id == gt.id).delete()
        session.delete(gt)
        session.commit()
        return jsonify({"message": "Тест удалён"}), 200
    except Exception as e:
        session.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        session.close()


@api_bp.route('/global-tests/<int:test_id>/submit/last', methods=['GET'])
def get_last_global_test_result(test_id: int):
    session = get_db_session()
    try:
        from flask import g
        user_info = g.get('user_info', {}) or {}
        username = user_info.get('username')
        user = session.query(User).filter(User.username == username).first() if username else None
        if not user:
            return jsonify({'error': 'Пользователь не аутентифицирован'}), 401

        from database.models import GlobalTestResult  # type: ignore
        last = session.query(GlobalTestResult).filter(
            GlobalTestResult.user_id == user.id,
            GlobalTestResult.global_test_id == test_id,
        ).order_by(GlobalTestResult.attempt_number.desc(), GlobalTestResult.created_at.desc()).first()
        if not last:
            return jsonify({"result": None})
        return jsonify({"result": last.to_dict()})
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        session.close()


@api_bp.route('/global-tests/<int:test_id>/submit', methods=['POST'])
def submit_global_test(test_id: int):
    session = get_db_session()
    try:
        from flask import g
        user_info = g.get('user_info', {}) or {}
        username = user_info.get('username')
        user = session.query(User).filter(User.username == username).first() if username else None
        if not user:
            return jsonify({'error': 'Пользователь не аутентифицирован'}), 401

        effective_role = _effective_role(user_info)
        is_admin_like = effective_role in ('admin', 'super_admin')

        from database.models import GlobalTest, GlobalTestQuestion, GlobalTestResult  # type: ignore
        gt = session.query(GlobalTest).filter(GlobalTest.id == test_id).first()
        if not gt:
            return jsonify({'error': 'Тест не найден'}), 404
        if (not is_admin_like) and (not gt.is_active):
            return jsonify({'error': 'Тест недоступен'}), 403

        qs = session.query(GlobalTestQuestion).filter(GlobalTestQuestion.global_test_id == gt.id).order_by(GlobalTestQuestion.order.asc()).all()
        questions = [q._parse_content() for q in qs]

        settings = gt._settings_dict() if hasattr(gt, '_settings_dict') and callable(getattr(gt, '_settings_dict')) else {}
        pass_percent = int(settings.get('pass_percent') or 70)
        limit_attempts = bool(settings.get('limit_attempts'))
        max_attempts = None
        if limit_attempts and settings.get('max_attempts') is not None:
            try:
                max_attempts = int(settings.get('max_attempts'))
            except (TypeError, ValueError):
                max_attempts = None

        last_attempt = session.query(func.max(GlobalTestResult.attempt_number)).filter(
            GlobalTestResult.user_id == user.id,
            GlobalTestResult.global_test_id == gt.id,
        ).scalar() or 0
        attempts_used = int(last_attempt)
        if limit_attempts and max_attempts is not None and attempts_used >= max_attempts:
            return jsonify({
                "error": "Попытки исчерпаны",
                "code": "attempts_exhausted",
                "attempts_used": attempts_used,
                "max_attempts": max_attempts,
            }), 400

        data = request.get_json() or {}
        answers_raw = data.get("answers")
        if not isinstance(answers_raw, list):
            return jsonify({"error": "answers должен быть списком"}), 400

        correct_count, total, feedback = _evaluate_questions_payload(questions, answers_raw)
        score_pct = int(round((correct_count / total) * 100)) if total > 0 else 0
        passed = score_pct >= pass_percent

        attempt_number = attempts_used + 1
        attempts_left = (max(0, max_attempts - attempt_number)) if max_attempts is not None else None

        session.add(GlobalTestResult(
            user_id=user.id,
            global_test_id=gt.id,
            attempt_number=attempt_number,
            score=correct_count,
            total=total,
            score_percent=score_pct,
            passed=bool(passed),
            answers=_json.dumps({"answers": answers_raw, "feedback": feedback}, ensure_ascii=False),
        ))
        session.commit()

        return jsonify({
            "score": correct_count,
            "total": total,
            "score_percent": score_pct,
            "passed": bool(passed),
            "feedback": feedback,
            "attempts_used": attempt_number,
            "max_attempts": max_attempts,
            "attempts_left": attempts_left,
            "pass_percent": pass_percent,
        })
    except Exception as e:
        session.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        session.close()


# ----------------------- News Endpoints -----------------------

def _get_current_db_user(session):
    user_info = g.get('user_info', {}) or {}
    username = (user_info.get('username') or '').strip()
    if not username:
        return None
    return session.query(User).filter(User.username == username).first()


@api_bp.route('/news', methods=['GET'])
def list_news():
    session = get_db_session()
    try:
        user = _get_current_db_user(session)
        if not user:
            return jsonify({'error': 'Пользователь не аутентифицирован'}), 401
        from database.models import NewsEvent  # type: ignore
        limit = request.args.get("limit")
        try:
            limit_i = int(limit) if limit is not None else 50
        except Exception:
            limit_i = 50
        limit_i = max(1, min(200, limit_i))
        items = session.query(NewsEvent).order_by(NewsEvent.created_at.desc(), NewsEvent.id.desc()).limit(limit_i).all()
        # дополняем автором (username/full_name)
        out = []
        for ev in items:
            d = ev.to_dict()
            try:
                au = ev.author
                d["author_username"] = au.username if au else None
                d["author_full_name"] = (au._get_full_name_from_parts() if au and hasattr(au, "_get_full_name_from_parts") else None) or (au.full_name if au else None)
            except Exception:
                d["author_username"] = None
                d["author_full_name"] = None
            out.append(d)
        return jsonify({"events": out, "total": len(out)})
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        session.close()


@api_bp.route('/news', methods=['POST'])
def create_news():
    session = get_db_session()
    try:
        deny = _require_super_admin(g.get('user_info', None))
        if deny:
            return deny
        user = _get_current_db_user(session)
        if not user:
            return jsonify({'error': 'Пользователь не аутентифицирован'}), 401
        data = request.get_json() or {}
        event_type = str(data.get("event_type") or "manual").strip() or "manual"
        title = str(data.get("title") or "").strip()
        body = str(data.get("body") or "").strip()
        meta = data.get("meta")
        if not title:
            return jsonify({"error": "title обязателен"}), 400
        from database.models import NewsEvent  # type: ignore
        ev = NewsEvent(
            event_type=event_type[:80],
            title=title[:255],
            body=body or None,
            meta=_json.dumps(meta, ensure_ascii=False) if isinstance(meta, (dict, list)) else None,
            created_by=user.id,
        )
        session.add(ev)
        session.commit()
        return jsonify({"event": ev.to_dict()}), 201
    except Exception as e:
        session.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        session.close()


# ----------------------- Lesson Files Endpoints -----------------------

@api_bp.route('/lessons/<int:lesson_id>/files', methods=['POST'])
def upload_lesson_file(lesson_id: int):
    """Загрузить файл к уроку (admin only)."""
    import os
    import secrets
    from werkzeug.utils import secure_filename
    
    session = get_db_session()
    try:
        # Проверка прав администратора (admin или super_admin)
        deny = _require_admin(g.get('user_info', None))
        if deny:
            return deny
        
        lesson = fs_find_lesson(lesson_id)
        if not lesson:
            return jsonify({'error': 'Урок не найден'}), 404
        
        if 'file' not in request.files:
            return jsonify({'error': 'Файл не передан'}), 400
        
        file = request.files['file']
        file_type = request.form.get('type', 'files')  # 'images', 'files', 'videos'
        
        if file.filename == '':
            return jsonify({'error': 'Имя файла пустое'}), 400
        
        if file_type not in ['images', 'files', 'videos']:
            return jsonify({'error': 'Неверный тип файла'}), 400
        
        # Импортируем current_app в начале функции
        from flask import current_app
        
        # Валидация расширения файла
        ext = os.path.splitext(file.filename)[1].lower()
        forbidden_extensions = current_app.config.get('FORBIDDEN_EXTENSIONS', set())
        if ext in forbidden_extensions:
            return jsonify({'error': f'Загрузка файлов с расширением {ext} запрещена'}), 400
        
        # Валидация MIME типа
        mime_type = file.mimetype or 'application/octet-stream'
        allowed_mime_cfg = current_app.config.get('ALLOWED_MIME_TYPES', {}) or {}
        allowed_mime_types = list(allowed_mime_cfg.get(file_type, []) or [])
        # Для "files" дополнительно разрешаем generic application/octet-stream,
        # чтобы не ломать загрузку архивов и бинарников, и все text/* кроме HTML.
        if file_type == 'files':
            if 'application/octet-stream' not in allowed_mime_types:
                allowed_mime_types.append('application/octet-stream')
            if mime_type.startswith('text/') and mime_type != 'text/html' and mime_type not in allowed_mime_types:
                allowed_mime_types.append(mime_type)
        if allowed_mime_types and mime_type not in allowed_mime_types:
            return jsonify({'error': f'Тип файла {mime_type} не разрешен для {file_type}. Разрешенные типы: {", ".join(allowed_mime_types)}'}), 400
        
        # Проверка размера файла
        # Используем значение из конфига (по умолчанию 10GB для поддержки больших видео)
        max_size = current_app.config.get('MAX_CONTENT_LENGTH', 10 * 1024 * 1024 * 1024)
        # Flask автоматически проверяет MAX_CONTENT_LENGTH, но добавим дополнительную проверку
        if hasattr(file, 'content_length') and file.content_length and file.content_length > max_size:
            max_size_mb = max_size // (1024 * 1024)
            max_size_gb = max_size_mb / 1024
            if max_size_gb >= 1:
                return jsonify({'error': f'Файл слишком большой. Максимальный размер: {max_size_gb:.1f} GB'}), 400
            else:
                return jsonify({'error': f'Файл слишком большой. Максимальный размер: {max_size_mb} MB'}), 400
        
        upload_dir = os.path.join(str(lesson.path), file_type)
        
        # Создать директории, если не существуют
        os.makedirs(upload_dir, exist_ok=True)
        
        if not os.path.exists(upload_dir):
            raise Exception(f'Не удалось создать директорию: {upload_dir}')
        
        # Сохранить файл
        original_filename = secure_filename(file.filename)
        # Добавить уникальный префикс для избежания конфликтов
        unique_filename = f"{secrets.token_hex(8)}_{original_filename}"
        file_path = os.path.join(upload_dir, unique_filename)
        
        # Сохраняем файл потоково для больших файлов (поддержка файлов > 5GB)
        # Используем chunked writing для экономии памяти
        chunk_size = 1024 * 1024  # 1MB chunks
        total_written = 0
        
        try:
            with open(file_path, 'wb') as f:
                while True:
                    chunk = file.stream.read(chunk_size)
                    if not chunk:
                        break
                    f.write(chunk)
                    total_written += len(chunk)
                    
                    # Проверка размера во время загрузки (защита от переполнения)
                    if total_written > max_size:
                        f.close()
                        os.remove(file_path)
                        max_size_mb = max_size // (1024 * 1024)
                        max_size_gb = max_size_mb / 1024
                        if max_size_gb >= 1:
                            return jsonify({'error': f'Файл слишком большой. Максимальный размер: {max_size_gb:.1f} GB'}), 400
                        else:
                            return jsonify({'error': f'Файл слишком большой. Максимальный размер: {max_size_mb} MB'}), 400
        except Exception as e:
            # Если произошла ошибка, удаляем частично загруженный файл
            if os.path.exists(file_path):
                try:
                    os.remove(file_path)
                except:
                    pass
            raise e
        
        # Проверяем, что файл действительно сохранился
        if not os.path.exists(file_path):
            raise Exception(f'Файл не был сохранен: {file_path}')
        
        file_size = os.path.getsize(file_path)
        
        # Дополнительная проверка размера после сохранения
        if file_size > max_size:
            os.remove(file_path)
            max_size_mb = max_size // (1024 * 1024)
            max_size_gb = max_size_mb / 1024
            if max_size_gb >= 1:
                return jsonify({'error': f'Файл слишком большой. Максимальный размер: {max_size_gb:.1f} GB'}), 400
            else:
                return jsonify({'error': f'Файл слишком большой. Максимальный размер: {max_size_mb} MB'}), 400
        
        # Формируем URL для доступа к файлу.
        # Пытаемся использовать path_identifier из config.json, а если его нет –
        # берём относительный путь от корня categories-data, чтобы URL всегда
        # совпадал с фактической файловой структурой.
        from backend.utils.categories_data_sync import get_base_categories_data_path
        base_root = os.path.abspath(get_base_categories_data_path())
        lesson_path_abs = os.path.abspath(str(lesson.path))
        path_identifier_cfg = lesson.cfg.get("path_identifier") if isinstance(lesson.cfg, dict) else None
        if path_identifier_cfg:
            path_identifier = path_identifier_cfg
        else:
            rel = os.path.relpath(lesson_path_abs, base_root)
            path_identifier = rel.replace(os.sep, "/")
        file_url = f"/categories-data/{path_identifier}/{file_type}/{unique_filename}"
        
        return jsonify({
            'message': 'Файл загружен',
            'url': file_url,
            'filename': original_filename,
            'stored_filename': unique_filename,
            'size': file_size,
            'type': file.content_type or 'application/octet-stream'
        }), 201
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        session.close()


@api_bp.route('/lessons/<int:lesson_id>/files', methods=['GET'])
def get_lesson_files(lesson_id: int):
    """Получить список файлов урока из categories-data."""
    session = get_db_session()
    try:
        lesson = fs_find_lesson(lesson_id)
        if not lesson:
            return jsonify({'error': 'Урок не найден'}), 404
        import os

        files_data = {
            'files': [],
            'images': [],
            'videos': [],
            'texts': []
        }
        
        path_id = (lesson.cfg.get("path_identifier") if isinstance(lesson.cfg, dict) else None) or ""
        for file_type in ['files', 'images', 'videos', 'texts']:
            content_dir = os.path.join(str(lesson.path), file_type)
            if os.path.exists(content_dir):
                for filename in os.listdir(content_dir):
                    file_path = os.path.join(content_dir, filename)
                    if os.path.isfile(file_path):
                        file_url = f"/categories-data/{path_id}/{file_type}/{filename}"
                        file_info = {
                            'filename': filename,
                            'url': file_url,
                            'size': os.path.getsize(file_path),
                            'type': file_type
                        }
                        files_data[file_type].append(file_info)
        
        total = len(files_data['files']) + len(files_data['images']) + len(files_data['videos']) + len(files_data['texts'])
        files_data['total'] = total
        
        return jsonify(files_data)
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        session.close()


@api_bp.route('/lessons/<int:lesson_id>/files/<path:filename>', methods=['DELETE'])
def delete_lesson_file(lesson_id: int, filename: str):
    """Удалить файл урока (admin only)."""
    import os
    from backend.utils.categories_data_sync import get_lesson_content_path
    
    session = get_db_session()
    try:
        # Проверка прав администратора (admin или super_admin)
        deny = _require_admin(g.get('user_info', None))
        if deny:
            return deny
        
        lesson = session.query(Lesson).filter(Lesson.id == lesson_id).first()
        if not lesson:
            return jsonify({'error': 'Урок не найден'}), 404
        
        course = lesson.course
        category = course.category if course else None
        
        if not category or not course:
            return jsonify({'error': 'Категория или курс не найдены'}), 404
        
        # Ищем файл во всех типах папок в categories-data
        file_found = False
        for file_type in ['files', 'images', 'videos', 'texts']:
            content_dir = get_lesson_content_path(category.title, course.title, lesson.title, file_type)
            file_path = os.path.join(content_dir, filename)
            
            if os.path.exists(file_path) and os.path.isfile(file_path):
                os.remove(file_path)
                file_found = True
                break
        
        if not file_found:
            return jsonify({'error': 'Файл не найден'}), 404
        
        return jsonify({'message': 'Файл удален'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        session.close()


# ----------------------- Bin (Корзина) Endpoints -----------------------

@api_bp.route('/bin', methods=['GET'])
def get_deleted_objects():
    """Получить список удаленных объектов (admin only)."""
    session = get_db_session()
    try:
        # Проверка прав администратора (admin или super_admin)
        deny = _require_admin(g.get('user_info', {}))
        if deny:
            return deny
        
        # Пагинация корзины, чтобы не загружать все объекты сразу
        page, per_page = get_pagination_params()
        query = session.query(DeletedObject).order_by(DeletedObject.deleted_at.desc())
        result = paginate_query(query, page, per_page)
        
        return jsonify({
            'deleted_objects': [obj.to_dict() for obj in result['items']],
            'pagination': result['pagination']
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        session.close()


@api_bp.route('/bin/<int:deleted_id>/restore', methods=['POST'])
def restore_deleted_object(deleted_id: int):
    """Восстановить удаленный объект (admin only)."""
    session = get_db_session()
    try:
        # Проверка прав администратора (admin или super_admin)
        deny = _require_admin(g.get('user_info', {}))
        if deny:
            return deny
        
        deleted_obj = session.query(DeletedObject).filter(DeletedObject.id == deleted_id).first()
        if not deleted_obj:
            return jsonify({'error': 'Удаленный объект не найден'}), 404
        
        import json
        object_data = json.loads(deleted_obj.object_data)
        
        # Восстанавливаем объект в зависимости от типа
        if deleted_obj.object_type == 'category':
            # Восстанавливаем существующую категорию (soft-delete), либо создаем новую
            category = session.query(Category).filter(Category.id == deleted_obj.object_id).first()
            if not category:
                category = Category(id=deleted_obj.object_id)
                session.add(category)
            
            category.title = object_data.get('title')
            category.description = object_data.get('description')
            category.order = object_data.get('order', 0)
            category.sequential_progression = object_data.get('sequential_progression', False)
            category.is_active = True
            
            # Синхронизируем файловую структуру категории и восстанавливаем path_identifier
            from backend.utils.categories_data_sync import sync_category
            path_identifier = sync_category(
                category.id,
                category.title,
                None,
                settings={
                    "description": category.description,
                    "order": category.order,
                    "sequential_progression": category.sequential_progression,
                    "is_active": category.is_active,
                },
            )
            category.path_identifier = path_identifier

        elif deleted_obj.object_type == 'course':
            # Убеждаемся, что категория курса существует и активна
            category_id = object_data.get('category_id')
            category = session.query(Category).filter(Category.id == category_id).first()
            if category:
                category.is_active = True
            else:
                # Если категории нет (например, была удалена вручную) — создаем её "по минимуму"
                category_title = object_data.get('category_title') or 'Категория'
                category = Category(
                    id=category_id,
                    title=category_title,
                    is_active=True,
                )
                session.add(category)
            
            course = session.query(Course).filter(Course.id == deleted_obj.object_id).first()
            if not course:
                course = Course(id=deleted_obj.object_id)
                session.add(course)

            course.category_id = category.id
            course.title = object_data.get('title')
            course.description = object_data.get('description')
            course.order = object_data.get('order', 0)
            course.sequential_progression = object_data.get('sequential_progression', False)
            course.total_lessons = object_data.get('total_lessons', 0)
            course.is_active = True

            # Синхронизируем файловую структуру курса и path_identifier
            from backend.utils.categories_data_sync import sync_course
            path_identifier = sync_course(
                category.title,
                course.id,
                course.title,
                None,
                settings={
                    "description": course.description,
                    "order": course.order,
                    "sequential_progression": course.sequential_progression,
                    "total_lessons": course.total_lessons,
                    "is_active": course.is_active,
                },
            )
            course.path_identifier = path_identifier

        elif deleted_obj.object_type == 'lesson':
            course_id = object_data.get('course_id')
            lesson = session.query(Lesson).filter(Lesson.id == deleted_obj.object_id).first()
            if not lesson:
                lesson = Lesson(id=deleted_obj.object_id)
                session.add(lesson)

            lesson.course_id = course_id
            lesson.title = object_data.get('title')
            lesson.description = object_data.get('description')
            lesson.lesson_number = object_data.get('lesson_number', 1)
            lesson.content = object_data.get('content')
            lesson.file_path = object_data.get('file_path')
            lesson.is_active = True

            # Для урока также убеждаемся, что курс и категория активны и что есть файловая структура
            course = session.query(Course).filter(Course.id == course_id).first()
            if course:
                course.is_active = True
                category = course.category
                if category:
                    category.is_active = True

                    from backend.utils.categories_data_sync import sync_lesson
                    path_identifier = sync_lesson(
                        category.title,
                        course.title,
                        lesson.id,
                        lesson.title,
                        None,
                        settings={
                            "lesson_number": lesson.lesson_number,
                            "is_active": lesson.is_active,
                        },
                    )
                    lesson.path_identifier = path_identifier
        
        # Удаляем из корзины
        session.delete(deleted_obj)
        session.commit()
        
        return jsonify({'message': 'Объект восстановлен'})
    except Exception as e:
        session.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        session.close()


@api_bp.route('/bin/cleanup', methods=['POST'])
def cleanup_old_deleted_objects():
    """Окончательно удалить объекты старше BIN_RETENTION_DAYS дней (admin only)."""
    session = get_db_session()
    try:
        # Проверка прав администратора (admin или super_admin)
        deny = _require_admin(g.get('user_info', {}))
        if deny:
            return deny
        
        from datetime import datetime, timedelta
        cutoff_date = datetime.now() - timedelta(days=BIN_RETENTION_DAYS)
        
        old_objects = session.query(DeletedObject).filter(
            DeletedObject.deleted_at < cutoff_date
        ).all()
        
        deleted_count = 0
        for obj in old_objects:
            # Полное удаление файлов и данных
            if obj.object_type == 'lesson':
                import json
                object_data = json.loads(obj.object_data)
                # Удаление файлов из categories-data происходит автоматически при удалении урока через delete_lesson_folder
            
            session.delete(obj)
            deleted_count += 1
        
        session.commit()
        
        return jsonify({
            'message': f'Удалено {deleted_count} объектов',
            'deleted_count': deleted_count
        })
    except Exception as e:
        session.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        session.close()


# ----------------------- Course Department Access Endpoints -----------------------

@api_bp.route('/courses/<int:course_id>/departments', methods=['GET'])
def get_course_departments(course_id: int):
    """Получить список отделов с доступом к курсу."""
    session = get_db_session()
    try:
        accesses = session.query(CourseDepartmentAccess).filter(
            CourseDepartmentAccess.course_id == course_id
        ).all()
        
        departments = [access.department for access in accesses]
        
        return jsonify({
            'course_id': course_id,
            'departments': departments,
            'total': len(departments)
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        session.close()


@api_bp.route('/courses/<int:course_id>/departments', methods=['POST'])
def set_course_departments(course_id: int):
    """Установить доступ к курсу по отделам (admin only)."""
    session = get_db_session()
    try:
        # Проверка прав администратора (admin или super_admin)
        deny = _require_admin(g.get('user_info', None))
        if deny:
            return deny
        
        course = session.query(Course).filter(Course.id == course_id).first()
        if not course:
            return jsonify({'error': 'Курс не найден'}), 404
        
        data = request.get_json()
        if not data:
            return jsonify({'error': 'Данные не предоставлены'}), 400
        
        departments = data.get('departments', [])
        
        # Удаляем старые записи
        session.query(CourseDepartmentAccess).filter(
            CourseDepartmentAccess.course_id == course_id
        ).delete()
        
        # Добавляем новые
        for dept in departments:
            access = CourseDepartmentAccess(
                course_id=course_id,
                department=dept
            )
            session.add(access)
        
        session.commit()
        
        return jsonify({
            'message': 'Доступ к курсу обновлен',
            'departments': departments
        })
    except Exception as e:
        session.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        session.close()


# ----------------------- User Progress Endpoints -----------------------

@api_bp.route('/categories/<int:category_id>/progress', methods=['GET'])
def get_category_progress(category_id: int):
    """Получить прогресс пользователя по категории."""
    session = get_db_session()
    try:
        from flask import g
        user_info = g.get('user_info', {})
        username = user_info.get('username')
        
        if not username:
            return jsonify({
                'status': 'not_started',
                'progress_percentage': 0,
                'courses_completed': 0,
                'total_courses': 0
            })
        
        user = session.query(User).filter(User.username == username).first()
        if not user:
            return jsonify({
                'status': 'not_started',
                'progress_percentage': 0,
                'courses_completed': 0,
                'total_courses': 0
            })
        
        category = session.query(Category).filter(Category.id == category_id).first()
        if not category:
            return jsonify({'error': 'Категория не найдена'}), 404
        
        # Получаем все активные курсы категории
        courses = session.query(Course).filter(
            Course.category_id == category_id,
            Course.is_active == True
        ).all()
        
        total_courses = len(courses)
        courses_completed = 0
        courses_in_progress = 0

        # Предзагружаем прогресс пользователя по всем курсам категории одним запросом
        progress_by_course_id = {}
        if courses:
            course_ids = [c.id for c in courses]
            progresses = session.query(UserCourseProgress).filter(
                UserCourseProgress.user_id == user.id,
                UserCourseProgress.course_id.in_(course_ids)
            ).all()
            progress_by_course_id = {p.course_id: p for p in progresses}
        
        for course in courses:
            progress = progress_by_course_id.get(course.id)
            
            if progress and progress.is_completed:
                courses_completed += 1
            elif progress:
                courses_in_progress += 1
        
        progress_percentage = round((courses_completed / total_courses * 100) if total_courses > 0 else 0, 2)
        
        if courses_completed == total_courses and total_courses > 0:
            status = 'completed'
        elif courses_in_progress > 0 or courses_completed > 0:
            status = 'in_progress'
        else:
            status = 'not_started'
        
        return jsonify({
            'status': status,
            'progress_percentage': progress_percentage,
            'courses_completed': courses_completed,
            'courses_in_progress': courses_in_progress,
            'total_courses': total_courses
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        session.close()


@api_bp.route('/courses/<int:course_id>/progress', methods=['GET'])
def get_course_progress_for_user(course_id: int):
    """Получить прогресс пользователя по курсу."""
    session = get_db_session()
    try:
        from flask import g
        user_info = g.get('user_info', {})
        username = user_info.get('username')
        
        if not username:
            return jsonify({
                'status': 'not_started',
                'progress_percentage': 0,
                'lessons_completed': 0,
                'total_lessons': 0
            })
        
        user = session.query(User).filter(User.username == username).first()
        if not user:
            return jsonify({
                'status': 'not_started',
                'progress_percentage': 0,
                'lessons_completed': 0,
                'total_lessons': 0
            })
        
        course = session.query(Course).filter(Course.id == course_id).first()
        if not course:
            return jsonify({'error': 'Курс не найден'}), 404
        
        progress = session.query(UserCourseProgress).filter(
            UserCourseProgress.user_id == user.id,
            UserCourseProgress.course_id == course_id
        ).first()
        
        lessons_completed = progress.lessons_completed if progress else 0
        total_lessons = course.total_lessons or 0
        progress_percentage = round((lessons_completed / total_lessons * 100) if total_lessons > 0 else 0, 2)
        
        if progress and progress.is_completed:
            status = 'completed'
        elif lessons_completed > 0:
            status = 'in_progress'
        else:
            status = 'not_started'
        
        return jsonify({
            'status': status,
            'progress_percentage': progress_percentage,
            'lessons_completed': lessons_completed,
            'total_lessons': total_lessons
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        session.close()


def init_api(app):
    """Инициализировать API для приложения."""
    # Применяем rate limiting к критическим эндпоинтам
    limiter = app.limiter if hasattr(app, 'limiter') else None
    
    if limiter:
        # Rate limiting для создания/изменения/удаления ресурсов
        limiter.limit("10 per minute")(create_course)
        limiter.limit("10 per minute")(update_course)
        limiter.limit("10 per minute")(delete_course)
        limiter.limit("10 per minute")(create_category)
        limiter.limit("10 per minute")(update_category)
        limiter.limit("10 per minute")(delete_category)
        limiter.limit("10 per minute")(create_lesson)
        limiter.limit("10 per minute")(update_lesson)
        limiter.limit("10 per minute")(delete_lesson)
        limiter.limit("20 per minute")(create_question)
        limiter.limit("20 per minute")(create_answer)
        limiter.limit("30 per minute")(upload_question_attachment)
        limiter.limit("30 per minute")(upload_answer_attachment)
        limiter.limit("5 per minute")(register_user)

    app.register_blueprint(api_bp)
    
    # Инициализируем базу данных
    # БЕЗОПАСНО: create_tables() создает таблицы только если их нет
    # Не удаляет существующие данные!
    db_manager.create_tables()

    # Мягкие миграции схемы (идемпотентно, с фиксацией версии)
    try:
        from database.migrations import apply_soft_migrations

        apply_soft_migrations(db_manager.engine)
    except Exception:
        # Важно не ронять приложение из-за миграций; ошибки миграций проявятся в логах.
        pass

    # Очищаем устаревшие таблицы (mac_users, kerberos_users)
    # Это безопасно - удаляет только старые таблицы, не users
    try:
        db_manager.cleanup_legacy_tables()
    except Exception as e:
        pass
    
    # Инициализация БД (пользователи создаются автоматически при аутентификации)
    # Этот метод больше не создает тестовые данные
    if app.config.get('DATABASE_INIT_SAMPLE_DATA', False):
        db_manager.init_sample_data()
    
    return api_bp
