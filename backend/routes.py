import os
import mimetypes
from typing import Dict, List, Tuple
from flask import Flask, send_from_directory, abort, redirect, Response, render_template, jsonify, g

from backend.utils.categories_data_sync import (
    get_base_categories_data_path,
    ensure_categories_data_directory,
)
def _page_map(base_path: str, allowed_dirs: List[str]) -> Dict[str, Tuple[str, str]]:
    """Map route name to (directory, index file)."""
    mapping: Dict[str, Tuple[str, str]] = {}
    for dir_name in allowed_dirs:
        if not os.path.isdir(os.path.join(base_path, dir_name)):
            continue
        route_name = dir_name.replace("-pg", "").replace("_", "-")
        # Добавляем оба варианта: с -pg и без
        mapping[route_name] = (dir_name, "index.html")
        mapping[dir_name] = (dir_name, "index.html")  # Также поддерживаем полное имя
    return mapping


def _split_head_body(html: str) -> Dict[str, str]:
    """Extract <head> stylesheet hrefs and body inner HTML, then strip old header/footer.
    This preserves original visuals while avoiding duplicate header/footer.
    """
    lower = html.lower()
    head_start = lower.find("<head")
    head_end = lower.find("</head>")
    body_start = lower.find("<body")
    body_end = lower.rfind("</body>")

    head_html = html[head_start:head_end] if (head_start != -1 and head_end != -1) else ""
    body_html = html[body_start:body_end] if (body_start != -1 and body_end != -1) else html

    import re

    # collect stylesheet hrefs
    hrefs = re.findall(r'<link[^>]+rel=["\']stylesheet["\'][^>]*href=["\']([^"\']+)["\']', head_html, flags=re.I)
    page_styles = [h for h in hrefs if not h.startswith("http")]

    # strip <body ...> wrapper
    body_inner = re.sub(r"^<body[^>]*>\s*", "", body_html, flags=re.I)

    # remove first <header ...>...</header>
    body_inner = re.sub(r"<header[^>]*class=\"[^\"]*header[^\"]*\"[\s\S]*?</header>\s*", "", body_inner, count=1, flags=re.I)

    # remove last footer block and optional following made-by div
    # remove any <div class="made-by">...</div>
    body_inner = re.sub(r"<div[^>]*class=\"[^\"]*made-by[^\"]*\"[\s\S]*?</div>\s*", "", body_inner, flags=re.I)
    # remove the last footer occurrence
    footers = list(re.finditer(r"<footer[\s\S]*?</footer>", body_inner, flags=re.I))
    if footers:
        last = footers[-1]
        body_inner = body_inner[: last.start()] + body_inner[last.end() :]

    return {"page_styles": page_styles, "body_inner": body_inner}


def register_routes(app: Flask) -> None:
    base_path = app.config["PROJECT_ROOT"]
    allowed_dirs = app.config["ALLOWED_PAGE_DIRS"]
    admin_template_dir = app.config["ADMIN_TEMPLATE_DIR"]
    user_template_dir = app.config["USER_TEMPLATE_DIR"]
    shared_template_dir = app.config["SHARED_TEMPLATE_DIR"]
    admin_base_template = f"{app.config['ADMIN_TEMPLATES_DIR']}/base_static_page.html"
    user_base_template = f"{app.config['USER_TEMPLATES_DIR']}/base_static_page.html"
    
    # Создаем карты страниц для обеих ролей
    admin_pages = _page_map(os.path.join(base_path, admin_template_dir), allowed_dirs)
    user_pages = _page_map(os.path.join(base_path, user_template_dir), allowed_dirs)
    # Создаем карту страниц для frontend/shared-pages (для lessons-content-pg)
    shared_pages_path = os.path.join(base_path, shared_template_dir)
    shared_pages = _page_map(shared_pages_path, allowed_dirs) if os.path.exists(shared_pages_path) else {}
    
    def _get_pages_for_user_role():
        """Get pages map based on current user role и выбранный режим просмотра.
        
        Для lessons-content-pg всегда используется frontend/shared-pages независимо от роли.
        В TEST_MODE все пользователи считаются админами.
        Админы/суперадмины могут переключаться в режим просмотра «как пользователь»
        через cookie ls_view_mode=user.
        """
        from flask import g, request
        if app.config.get("TEST_MODE"):
            return admin_pages, os.path.join(base_path, admin_template_dir)
        user_info = g.get('user_info', {}) or {}
        user_role = user_info.get('role', 'user') or 'user'
        view_mode = (request.cookies.get('ls_view_mode') or '').strip().lower()
        is_admin_like = user_role in ('admin', 'super_admin')
        # Если админ включил режим пользователя — отдаём пользовательские страницы
        if is_admin_like and view_mode == 'user':
            return user_pages, os.path.join(base_path, user_template_dir)
        if is_admin_like:
            return admin_pages, os.path.join(base_path, admin_template_dir)
        return user_pages, os.path.join(base_path, user_template_dir)
    
    def _get_template_path_for_page(page_key: str, legacy_dir: str = None):
        """
        Получить путь к шаблону для страницы.
        Для lessons-content-pg всегда возвращает frontend/shared-pages независимо от роли.
        В TEST_MODE все считаются админами.
        """
        from flask import g, request
        if app.config.get("TEST_MODE"):
            target_dir = page_key or legacy_dir
            if target_dir == 'lessons-content-pg' or target_dir == 'lessons-content':
                return os.path.join(base_path, shared_template_dir)
            return os.path.join(base_path, admin_template_dir)
        user_info = g.get('user_info', {}) or {}
        user_role = user_info.get('role', 'user') or 'user'
        view_mode = (request.cookies.get('ls_view_mode') or '').strip().lower()
        target_dir = page_key or legacy_dir
        if target_dir == 'lessons-content-pg' or target_dir == 'lessons-content':
            return os.path.join(base_path, shared_template_dir)
        is_admin_like = user_role in ('admin', 'super_admin')
        if is_admin_like and view_mode != 'user':
            return os.path.join(base_path, admin_template_dir)
        return os.path.join(base_path, user_template_dir)

    # Healthcheck for load balancers and uptime checks
    @app.get("/healthz")
    def healthcheck():
        return {"status": "ok"}, 200

    @app.get("/debug/auth")
    def debug_auth():
        """Return auth debug data in debug/testing mode."""
        if not app.config.get('DEBUG') and not app.config.get('TESTING'):
            from flask import abort
            abort(404)
        # H2: при SSO через прокси не отдаём заголовки без явного ALLOW_DEBUG_AUTH.
        if app.config.get("TRUST_REMOTE_USER") and not (
            (os.environ.get("ALLOW_DEBUG_AUTH") or "").strip().lower() in ("true", "1", "yes")
        ):
            from flask import abort
            abort(404)
        from flask import g, request
        from database.models import db_manager, User
        
        user_info = g.get('user_info', {})
        username = user_info.get('username')
        
        db_data = None
        if username:
            try:
                session = db_manager.get_session()
                try:
                    user = session.query(User).filter(User.username == username.lower()).first()
                    if user:
                        db_data = user.to_dict()
                finally:
                    session.close()
            except Exception as e:
                db_data = {'error': str(e)}
        
        return jsonify({
            "user_info": user_info,
            "db_data": db_data,
            "request_headers": {
                "authorization": request.headers.get('Authorization', 'Not present'),
                "user_agent": request.headers.get('User-Agent', ''),
            },
            "config": {
                "kerberos_auth_enabled": app.config.get('KERBEROS_AUTH_ENABLED', True),
                "kerberos_service_name": app.config.get('KERBEROS_SERVICE_NAME', 'HTTP'),
                "kerberos_realm": app.config.get('KERBEROS_REALM', 'EXAMPLE.COM')
            }
        })

    @app.get("/templates/<path:template_path>")
    def serve_template(template_path: str):
        from flask import g, request
        user_info = g.get('user_info', {}) or {}
        user_role = user_info.get('role', 'user') or 'user'
        view_mode = (request.cookies.get('ls_view_mode') or '').strip().lower()
        if app.config.get("TEST_MODE"):
            user_role = str(user_role).strip().lower()
            user_role = 'super_admin' if user_role == 'super_admin' else 'admin'
        is_admin_like = user_role in ('admin', 'super_admin')
        use_admin_templates = is_admin_like and view_mode != 'user'
        templates_dir = os.path.join(base_path, app.config["ADMIN_TEMPLATES_DIR"]) if use_admin_templates else os.path.join(base_path, app.config["USER_TEMPLATES_DIR"])
        return send_from_directory(templates_dir, template_path)

    # Serve backend templates (CSS, images from backend/templates)
    @app.get("/backend/templates/<path:template_path>")
    def serve_backend_template(template_path: str):
        backend_templates_dir = os.path.join(base_path, "backend", "templates")
        return send_from_directory(backend_templates_dir, template_path)

    # User info test JSON endpoint
    @app.get("/user/info-test")
    def user_info_test():
        from flask import g, request
        from database.models import db_manager, User
        
        info = g.get('user_info', {}) or {}
        if not info.get('username'):
            return jsonify({'error': 'Пользователь не аутентифицирован'}), 401
        
        username = info.get('username')
        payload = {
            'authenticated': True,
            'username': username,
            'role': (
                ('super_admin' if str(info.get('role', 'user')).strip().lower() == 'super_admin' else 'admin')
                if app.config.get('TEST_MODE')
                else info.get('role', 'user')
            ),
            'auth_method': info.get('auth_method'),
            'ip_address': info.get('ip_address'),
            'hostname': info.get('hostname'),
        }
        
        if 'full_name' in info:
            payload['full_name'] = info.get('full_name')
        if 'surname' in info:
            payload['surname'] = info.get('surname')
        if 'fst_name' in info:
            payload['fst_name'] = info.get('fst_name')
        if 'sec_name' in info:
            payload['sec_name'] = info.get('sec_name')
        if 'department' in info:
            payload['department'] = info.get('department')
        if 'position' in info:
            payload['position'] = info.get('position')
        if 'principal' in info:
            payload['principal'] = info.get('principal')
        if 'domain' in info:
            payload['domain'] = info.get('domain')
        
        try:
            session = db_manager.get_session()
            try:
                user = session.query(User).filter(User.username == username.lower()).first()
                if user:
                    def safe_str(value):
                        """Безопасное преобразование в строку"""
                        if value is None:
                            return ''
                        if isinstance(value, (int, float)):
                            if value <= 0:
                                return ''
                            return str(value)
                        value_str = str(value).strip()
                        if value_str in ['0', '00', '000', '0000', '00000', '000000']:
                            return ''
                        return value_str
                    
                    # Профиль из AD (g.user_info) важнее устаревшей записи в SQLite (GUEST и т.п.)
                    payload['surname'] = payload.get('surname') or safe_str(user.surname)
                    payload['fst_name'] = payload.get('fst_name') or safe_str(user.fst_name)
                    payload['sec_name'] = payload.get('sec_name') or safe_str(user.sec_name)
                    payload['department'] = payload.get('department') or safe_str(user.department)
                    payload['position'] = payload.get('position') or safe_str(user.position)

                    full_name_from_parts = user._get_full_name_from_parts()
                    payload['full_name'] = (
                        payload.get('full_name')
                        or (full_name_from_parts or safe_str(user.full_name) or '').strip()
                    )
                    
                    payload['role'] = user.role
                    payload['email'] = safe_str(user.email) or ''
                    payload['principal'] = safe_str(user.principal) or payload.get('principal', '')
                    payload['realm'] = safe_str(user.realm) or payload.get('domain', '')
                    payload['last_login'] = user.last_login.isoformat() if user.last_login else None
            finally:
                session.close()
        except Exception as e:
            pass
        
        return jsonify(payload)

    @app.get("/<legacy_dir>/user/info-test")
    def user_info_test_legacy_nested(legacy_dir: str):
        """Совместимость для относительных URL вида /all-categories-pg/user/info-test."""
        if legacy_dir not in allowed_dirs:
            abort(404)
        return user_info_test()

    # Serve uploaded files (Q&A attachments) — только для аутентифицированных пользователей
    @app.get("/uploads/<path:filename>")
    def serve_upload(filename: str):
        user_info = getattr(g, "user_info", None) or {}
        username = (user_info.get("username") or "").strip().lower()
        if not username or username in ("guest", "user"):
            return jsonify({"error": "Требуется авторизация"}), 401
        if (user_info.get("auth_method") or "").strip().lower() in ("none", ""):
            return jsonify({"error": "Требуется авторизация"}), 401
        uploads_path = os.path.join(base_path, "backend", "uploads")
        safe_name = os.path.basename(filename)
        if ".." in filename or "/" in filename.replace("\\", "/"):
            abort(403)
        if not os.path.exists(os.path.join(uploads_path, safe_name)):
            abort(404)
        return send_from_directory(uploads_path, safe_name)

    # Serve files from categories-data (must be registered before generic routes)
    @app.get("/categories-data/<path:filepath>")
    def serve_categories_data(filepath: str):
        """Обслуживать файлы из папки categories-data.
        
        Ожидаемый формат пути: {path_identifier}/{file_type}/{filename}
        где path_identifier = category-{slug}/course-{slug}/lesson-{slug}
        Физическое расположение папки задаётся через CONTENT_ROOT_DIR
        или по умолчанию находится в корне проекта.
        """
        categories_data_path = get_base_categories_data_path()
        ensure_categories_data_directory()
        
        # Нормализуем пути для безопасной работы с ними
        categories_data_path_abs = os.path.abspath(os.path.realpath(categories_data_path))
        
        # Flask передает пути с прямыми слешами, разбиваем на части и собираем через os.path.join
        path_parts = [p for p in filepath.split('/') if p]  # Убираем пустые части
        
        # Минимум должно быть: path_identifier (3 части: category/course/lesson) + file_type + filename = 5 частей
        # Но также может быть только category + file_type + filename = 3 части (для файлов категории)
        # Или category/course + file_type + filename = 4 части (для файлов курса)
        if len(path_parts) < 3:  # Минимум: category/file_type/filename
            abort(404)
        
        safe_path = os.path.join(*path_parts)
        
        # Формируем полный путь к файлу
        full_path = os.path.abspath(os.path.realpath(os.path.join(categories_data_path, safe_path)))
        
        # Проверка безопасности пути (защита от path traversal)
        try:
            if os.path.commonpath([full_path, categories_data_path_abs]) != categories_data_path_abs:
                abort(403)
        except ValueError:
            abort(403)
        
        # Критическая защита: файлы тестов содержат correct_answer/accepted_answers.
        # Нельзя отдавать их публично через /categories-data.
        if "tests" in path_parts:
            import json as _json
            from flask import g as _g

            user_info = getattr(_g, "user_info", None) or {}
            username = (user_info.get("username") or "").strip().lower()
            auth_method = (user_info.get("auth_method") or "").strip().lower()
            authenticated = bool(username) and username not in ("guest", "user") and auth_method not in ("none", "")

            if not authenticated:
                abort(401)

            lesson_id = None
            # Для тестов ожидаем lesson path: category-*/course-*/lesson-*/tests/...
            if len(path_parts) >= 3 and path_parts[2].startswith("lesson-"):
                lesson_rel = os.path.join(*path_parts[:3])
                lesson_dir_full = os.path.abspath(os.path.realpath(os.path.join(categories_data_path, lesson_rel)))
                try:
                    in_content_root = os.path.commonpath([lesson_dir_full, categories_data_path_abs]) == categories_data_path_abs
                except ValueError:
                    in_content_root = False
                if in_content_root:
                    cfg_path = os.path.join(lesson_dir_full, "config.json")
                    if os.path.exists(cfg_path):
                        try:
                            cfg = _json.load(open(cfg_path, "r", encoding="utf-8"))
                            raw_id = cfg.get("id")
                            lesson_id = int(raw_id) if isinstance(raw_id, (int, float, str)) and str(raw_id).isdigit() else None
                        except Exception:
                            lesson_id = None

            if lesson_id is None:
                abort(403)

            # Проверяем последовательный доступ к уроку (иначе можно подсмотреть ответы).
            from database.models import db_manager, User
            from backend.api import fs_is_lesson_accessible_for_user

            session = db_manager.get_session()
            try:
                user = session.query(User).filter(User.username == username.lower()).first()
                user_id = user.id if user else -1
                ok, _, _ = fs_is_lesson_accessible_for_user(session, user_id, lesson_id)
                if not ok:
                    abort(403)
            finally:
                session.close()

        if os.path.exists(full_path) and os.path.isfile(full_path):
            dir_path = os.path.dirname(full_path)
            file_basename = os.path.basename(full_path)
            # Используем send_file для больших файлов с правильными заголовками
            # send_file автоматически использует потоковую передачу для больших файлов
            # и поддерживает Range requests для возобновления загрузки
            from flask import send_file, request
            
            # Получаем размер файла для заголовка Content-Length
            file_size = os.path.getsize(full_path)
            
            # Определяем MIME тип на основе расширения файла для правильной обработки видео
            mime_type, _ = mimetypes.guess_type(full_path)
            if not mime_type:
                if file_basename.lower().endswith(('.mp4', '.mpeg', '.avi', '.webm', '.wmv')):
                    mime_type = 'video/mp4'
                elif file_basename.lower().endswith(('.jpg', '.jpeg', '.png', '.gif', '.webp')):
                    mime_type = 'image/jpeg'
                else:
                    mime_type = 'application/octet-stream'
            
            # send_file автоматически обрабатывает Range requests (для возобновления загрузки)
            # и использует потоковую передачу для больших файлов (важно для файлов > 5GB)
            response = send_file(
                full_path,
                mimetype=mime_type,  # Указываем MIME тип для правильной обработки браузером
                as_attachment=False,  # Позволяем браузеру решать, как обрабатывать файл
                download_name=file_basename,
                conditional=True  # Включает поддержку Range requests (ETag, If-Range)
            )
            
            # Устанавливаем заголовки для больших файлов (критично для файлов > 5GB)
            response.headers['Accept-Ranges'] = 'bytes'
            response.headers['Content-Length'] = str(file_size)
            
            # Для видео файлов добавляем дополнительные заголовки для лучшей поддержки стриминга
            if mime_type.startswith('video/'):
                response.headers['Cache-Control'] = 'public, max-age=31536000'  # Кэширование на год
                response.headers['X-Content-Type-Options'] = 'nosniff'
            
            return response
        
        abort(404)

    @app.get("/")
    def root_redirect():
        return redirect("/main-pg/", code=302)

    # Explicit aliases for lessons list page so users can access it via /lessons
    @app.get("/lessons")
    def lessons_page():
        """
        Страница списка уроков.
        Алиас для all-lessons-pg, чтобы URL /lessons всегда открывал список уроков
        с тем же контентом, что и /all-lessons или /all-lessons-pg/.
        """
        pages_map, template_base_path = _get_pages_for_user_role()
        page = pages_map.get("all-lessons")
        if page:
            directory, filename = page
            return _render_static_page(directory, filename, template_base_path)
        return redirect("/all-lessons-pg/", code=302)

    @app.get("/lessons/")
    def lessons_page_trailing_slash():
        """Вариант с закрывающим слэшем для совместимости."""
        return lessons_page()

    # Explicit route for bin (trash) page so it never conflicts with generic routes
    @app.get("/bin")
    def bin_page():
        """
        Страница корзины. Для admin и user используется соответствующий шаблон
        (frontend/admin-pages / frontend/user-pages),
        а сама страница лежит в директории bin-pg.
        """
        _, template_base_path = _get_pages_for_user_role()
        return _render_static_page("bin-pg", "index.html", template_base_path)

    @app.get("/terminal")
    def terminal_page():
        """Страница терминала (команды смены роли — см. TERMINAL_ROLE_COMMANDS_ENABLED)."""
        _, template_base_path = _get_pages_for_user_role()
        return _render_static_page("terminal-pg", "index.html", template_base_path)

    def _render_static_page(dir_name: str, filename: str, template_base_path: str = None):
        if template_base_path is None:
            template_base_path = base_path
        abs_dir = os.path.join(template_base_path, dir_name)
        index_path = os.path.join(abs_dir, filename)
        try:
            with open(index_path, "r", encoding="utf-8") as f:
                html = f.read()
        except FileNotFoundError:
            abort(404)
        parts = _split_head_body(html)
        
        from flask import g
        user_info = g.get('user_info', {}) or {}
        real_role = user_info.get('role', 'user') or 'user'
        if app.config.get("TEST_MODE"):
            real_role = str(real_role).strip().lower()
            real_role = 'super_admin' if real_role == 'super_admin' else 'admin'
        from flask import request as _request
        view_mode = (_request.cookies.get('ls_view_mode') or '').strip().lower()
        if real_role in ('admin', 'super_admin') and view_mode == 'user':
            effective_role = 'user'
        else:
            effective_role = real_role
        if dir_name == 'lessons-content-pg':
            template_name = admin_base_template if effective_role in ('admin', 'super_admin') else user_base_template
        elif effective_role in ('admin', 'super_admin'):
            template_name = admin_base_template
        else:
            template_name = user_base_template
        username_ctx = user_info.get('username')
        full_name_ctx = user_info.get('full_name')
        role_ctx = effective_role
        display_name_ctx = None
        db_user_role_override = None
        if username_ctx:
            try:
                from database.models import db_manager, User
                session = db_manager.get_session()
                try:
                    user = session.query(User).filter(User.username == username_ctx.lower()).first()
                    if user:
                        db_user_role_override = user.role
                        if not (full_name_ctx and str(full_name_ctx).strip()):
                            full_name_ctx = (user._get_full_name_from_parts() if hasattr(user, '_get_full_name_from_parts') else None) or (getattr(user, 'full_name', None) or '').strip()
                        sn = (getattr(user, 'surname', None) or '').strip()
                        fn = (getattr(user, 'fst_name', None) or '').strip()
                        display_name_ctx = (' '.join([sn, fn]) if (sn or fn) else '').strip()
                        if not display_name_ctx:
                            display_name_ctx = username_ctx or 'Пользователь'
                finally:
                    session.close()
            except Exception:
                pass

        if db_user_role_override:
            real_role = (db_user_role_override or real_role) or 'user'
            if app.config.get("TEST_MODE"):
                real_role = str(real_role).strip().lower()
                real_role = 'super_admin' if real_role == 'super_admin' else 'admin'

            if real_role in ('admin', 'super_admin') and view_mode == 'user':
                effective_role = 'user'
            else:
                effective_role = real_role

            if dir_name == 'lessons-content-pg':
                template_name = (
                    admin_base_template
                    if effective_role in ('admin', 'super_admin')
                    else user_base_template
                )
            elif effective_role in ('admin', 'super_admin'):
                template_name = admin_base_template
            else:
                template_name = user_base_template

            role_ctx = effective_role
        if not display_name_ctx:
            display_name_ctx = username_ctx or 'Пользователь'

        return render_template(
            template_name,
            title=None,
            page_styles=parts["page_styles"],
            page_body=parts["body_inner"],
            username=username_ctx,
            full_name=full_name_ctx,
            display_name=display_name_ctx,
            role=role_ctx,
            real_role=real_role,
            view_mode=view_mode or ('admin' if real_role in ('admin', 'super_admin') else 'user'),
        )
    
    @app.get("/ui/switch-view")
    def switch_view_mode():
        """Переключить режим интерфейса для админа/суперадмина (admin <-> user)."""
        from flask import g, request, make_response
        user_info = g.get('user_info', {}) or {}
        user_role = user_info.get('role', 'user') or 'user'
        if user_role not in ('admin', 'super_admin'):
            return redirect(request.referrer or "/main-pg/", code=302)
        
        requested_mode = (request.args.get("mode") or "").strip().lower()
        current_mode = (request.cookies.get("ls_view_mode") or "").strip().lower() or "admin"
        if requested_mode in ("admin", "user"):
            new_mode = requested_mode
        else:
            new_mode = "user" if current_mode != "user" else "admin"
        
        resp = make_response(redirect(request.referrer or "/main-pg/", code=302))
        resp.set_cookie(
            "ls_view_mode",
            new_mode,
            max_age=60 * 60 * 24 * 365,
            secure=False,
            httponly=False,
            samesite="Lax",
        )
        return resp

    # Serve pages via friendly URLs (e.g., /main, /questions)
    # Исключаем конфликтующие маршруты
    @app.get("/<page_key>")
    def serve_page(page_key: str):
        # Исключаем API и системные маршруты
        if page_key in ['api', 'healthz', 'debug']:
            abort(404)
        
        # Для lessons-content-pg используем frontend/user-pages независимо от роли
        if page_key == 'lessons-content' or page_key == 'lessons-content-pg':
            template_base_path = _get_template_path_for_page('lessons-content-pg')
            pages_map = user_pages  # Всегда используем user_pages для lessons-content-pg
        else:
            pages_map, template_base_path = _get_pages_for_user_role()
        
        page = pages_map.get(page_key)
        
        # Если не найдено в маппинге, проверяем как legacy_dir (для bin, all-categories-pg и т.д.)
        if not page:
            # Проверяем, может быть это legacy_dir
            abs_dir = os.path.join(template_base_path, page_key)
            if page_key in allowed_dirs or os.path.isdir(abs_dir):
                return _render_static_page(page_key, "index.html", template_base_path)
            abort(404)
        
        directory, filename = page
        return _render_static_page(directory, filename, template_base_path)

    # Serve legacy URLs (e.g., /main-pg/, /questions-pg/)
    @app.get("/<legacy_dir>/")
    def serve_legacy_index(legacy_dir: str):
        # Allow either configured allowed dir or physically existing dir under site root
        # Для lessons-content-pg используем frontend/shared-pages независимо от роли
        template_base_path = _get_template_path_for_page(None, legacy_dir)
        abs_dir = os.path.join(template_base_path, legacy_dir)
        if legacy_dir not in allowed_dirs and not os.path.isdir(abs_dir):
            abort(404)
        return _render_static_page(legacy_dir, "index.html", template_base_path)

    # Serve assets from legacy directories (e.g., /main-pg/img/file.png) - ролевая система
    @app.get("/<legacy_dir>/<path:legacy_path>")
    def serve_legacy_asset(legacy_dir: str, legacy_path: str):
        if legacy_dir not in allowed_dirs:
            abort(404)
        
        # Для lessons-content-pg используем frontend/shared-pages независимо от роли
        template_base_path = _get_template_path_for_page(None, legacy_dir)
        
        abs_dir = os.path.join(template_base_path, legacy_dir)
        safe_path = os.path.abspath(os.path.realpath(os.path.normpath(os.path.join(abs_dir, legacy_path))))
        abs_dir_real = os.path.abspath(os.path.realpath(abs_dir))
        try:
            if os.path.commonpath([safe_path, abs_dir_real]) != abs_dir_real:
                abort(403)
        except ValueError:
            abort(403)
        if not os.path.exists(safe_path):
            abort(404)
        rel_dir = os.path.dirname(os.path.relpath(safe_path, abs_dir))
        return send_from_directory(os.path.join(abs_dir, rel_dir), os.path.basename(safe_path))

    # Serve assets from friendly URLs (e.g., /main/img/file.png) - ролевая система
    @app.get("/<page_key>/<path:asset_path>")
    def serve_asset(page_key: str, asset_path: str):
        # Для lessons-content-pg используем frontend/shared-pages независимо от роли
        if page_key == 'lessons-content' or page_key == 'lessons-content-pg':
            template_base_path = _get_template_path_for_page('lessons-content-pg')
            pages_map = shared_pages  # Всегда используем shared_pages для lessons-content-pg
        else:
            pages_map, template_base_path = _get_pages_for_user_role()
        
        page = pages_map.get(page_key)
        if not page:
            abort(404)
        directory, _ = page
        abs_dir = os.path.join(template_base_path, directory)
        safe_path = os.path.abspath(os.path.realpath(os.path.normpath(os.path.join(abs_dir, asset_path))))
        abs_dir_real = os.path.abspath(os.path.realpath(abs_dir))
        try:
            if os.path.commonpath([safe_path, abs_dir_real]) != abs_dir_real:
                abort(403)
        except ValueError:
            abort(403)
        if not os.path.exists(safe_path):
            abort(404)
        rel_dir = os.path.dirname(os.path.relpath(safe_path, abs_dir))
        return send_from_directory(os.path.join(abs_dir, rel_dir), os.path.basename(safe_path))

    # Testing-only endpoint
    @app.get("/__trigger_error")
    def trigger_error():
        if not app.config.get("TESTING"):
            abort(404)
        raise RuntimeError("Test error for 500 handler")


