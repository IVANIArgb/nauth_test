"""
Новый модуль аутентификации на основе auth_script.py.
Заменяет simplified_real_kerberos_auth.py
"""
import base64
import os
import re
import sys
import shutil
from typing import Dict, Any, Optional
from datetime import datetime
from flask import request, g, current_app

from auth.auth_script import get_username_from_kerberos
from auth.ad_user_info import get_user_info_by_login
from auth.trusted_proxy import is_trusted_proxy_ip, request_client_ip


class NewAuth:
    """Новый класс аутентификации с использованием auth_script.py"""
    
    def __init__(self, app=None):
        self.app = app
        
        if app is not None:
            self.init_app(app)
    
    def init_app(self, app):
        """Инициализация аутентификации"""
        self.app = app
        self.realm = app.config.get('KERBEROS_REALM', 'EXAMPLE.COM')
        
        # Регистрация обработчиков
        app.before_request(self._authenticate_user)

    def _is_test_mode(self) -> bool:
        """Тестовый режим: все пользователи считаются admin.

        Включается переменной окружения TEST_MODE=true либо app.config['TEST_MODE']=True.
        Нужен для контейнеров/демо без Kerberos/AD.
        """
        try:
            cfg_val = current_app.config.get("TEST_MODE", None)
        except Exception:
            cfg_val = None
        env_val = os.environ.get("TEST_MODE", "")
        val = cfg_val if cfg_val is not None else env_val
        return str(val).strip().lower() in ("true", "1", "yes", "y", "on")

    def _is_root_test_mode(self) -> bool:
        """
        Root-test режим: подмена пользователя на "root" для тестов/контейнера.
        В production запрещено fail-fast в backend/__init__.py.
        """
        val = os.environ.get("ROOT_TEST_AUTH_ENABLED", "")
        return str(val).strip().lower() in ("true", "1", "yes", "y", "on")

    @staticmethod
    def _sanitize_remote_user_header(val: str) -> Optional[str]:
        """Нормализация логина из заголовка прокси (email, DOMAIN\\user)."""
        val = (val or "").strip().strip('"')
        if not val:
            return None
        if "@" in val:
            val = val.split("@", 1)[0].strip()
        if "\\" in val:
            val = val.split("\\")[-1].strip()
        # Логин из прокси: латиница, кириллица, цифры, «.», «-», «_» (Unicode-слово)
        if not re.match(r"^[\w.-]{1,128}$", val, re.UNICODE):
            return None
        low = val.lower()
        if low in ("guest", "user", "anonymous"):
            return None
        return low

    @staticmethod
    def _username_from_b64_header(hdr: str) -> Optional[str]:
        """Кириллица в логине: прокси передаёт X-Remote-User-B64 (UTF-8 → base64)."""
        raw = (hdr or "").strip()
        if not raw:
            return None
        try:
            pad = "=" * ((4 - len(raw) % 4) % 4)
            decoded = base64.b64decode(raw + pad, validate=False).decode("utf-8").strip()
        except Exception:
            return None
        return NewAuth._sanitize_remote_user_header(decoded)

    def _username_from_trusted_proxy(self) -> Optional[str]:
        """Логин из доверенных заголовков (только если TRUST_REMOTE_USER включён в конфиге)."""
        try:
            if not current_app.config.get("TRUST_REMOTE_USER"):
                return None
        except Exception:
            return None
        client_ip = request_client_ip(
            request.remote_addr,
            request.headers.get("X-Forwarded-For"),
        )
        if not is_trusted_proxy_ip(client_ip):
            return None
        b64_hdr = request.headers.get("X-Remote-User-B64")
        if b64_hdr:
            parsed = self._username_from_b64_header(b64_hdr)
            if parsed:
                return parsed
        for raw_name in current_app.config.get("REMOTE_USER_HEADERS") or []:
            name = (raw_name or "").strip()
            if not name:
                continue
            hdr = request.headers.get(name)
            if not hdr:
                continue
            parsed = self._sanitize_remote_user_header(hdr)
            if parsed:
                return parsed
        return None

    def _username_from_docker_fallback(self) -> Optional[str]:
        """
        Контейнер: без Kerberos/прокси логин неизвестен (ОС — root/www-data отбрасывается).
        Подстановка DOCKER_DEFAULT_USER, если включено DOCKER_AUTH_FALLBACK и не production.
        """
        try:
            if not current_app.config.get("DOCKER_AUTH_FALLBACK"):
                return None
        except Exception:
            return None
        if not (os.environ.get("DOCKER") or "").strip():
            return None
        env_flask = (os.environ.get("FLASK_ENV") or "").strip().lower()
        if env_flask == "production":
            return None
        raw = (current_app.config.get("DOCKER_DEFAULT_USER") or "testadmin") or ""
        u = raw.strip()
        if not u or not re.match(r"^[\w.-]{1,128}$", u, re.UNICODE):
            return None
        return u.lower()

    def _ad_lookup_available(self) -> bool:
        """LDAP в контейнере или PowerShell Get-ADUser на Windows-хосте."""
        try:
            if current_app.config.get("LDAP_ENABLED"):
                if current_app.config.get("LDAP_SERVER") and current_app.config.get("LDAP_BASE_DN"):
                    return True
        except Exception:
            pass
        if sys.platform == "win32" and shutil.which("powershell"):
            return True
        return False

    def _authenticate_user(self):
        """Аутентификация пользователя через новый механизм"""
        try:
            test_mode = self._is_test_mode()
            root_test_mode = self._is_root_test_mode()
            auth_header = request.headers.get('Authorization')
            from_docker_fallback = False

            # 1) Reverse-proxy SSO (nginx auth_request, oauth2-proxy, Cloudflare Access, …)
            username = self._username_from_trusted_proxy()
            from_trusted_proxy = bool(username)

            # 2) Kerberos Negotiate / локальный пользователь ОС (не root в контейнере — см. auth_script)
            if not username:
                username = get_username_from_kerberos(auth_header=auth_header)

            if not username:
                u_fb = self._username_from_docker_fallback()
                if u_fb:
                    username = u_fb
                    from_docker_fallback = True
            
            # Root-test: для любого пользователя (без trusted proxy) считаем, что он root
            # и отдаём полный доступ через роль в БД/хардкоде.
            if root_test_mode and not from_trusted_proxy:
                username = (os.environ.get("ROOT_TEST_USERNAME") or "root").strip()

            if test_mode and not from_trusted_proxy:
                # Подмена только если логин не пришёл из доверенного прокси
                default_user = os.environ.get("TEST_MODE_DEFAULT_USER", "testadmin")
                username_norm = (username or "").strip().lower()
                if not username_norm or username_norm in {"root", "admin", "administrator", "guest", "user"}:
                    username = default_user

            if not username:
                # Если не удалось получить логин, создаем guest пользователя
                g.user_info = {
                    'username': 'guest',
                    'full_name': 'Guest User',
                    'role': 'user' if not test_mode else 'admin',
                    'auth_method': 'none' if not test_mode else 'test_mode',
                    'ip_address': request.remote_addr
                }
                return
            
            # AD: только если есть LDAP или Windows; иначе — пустой профиль (логин уже из SSO/Windows)
            skip_ad = (
                (test_mode or from_docker_fallback or (root_test_mode and not from_trusted_proxy))
                and not from_trusted_proxy
            ) or not self._ad_lookup_available()
            if skip_ad:
                ad_info = {}
            else:
                try:
                    ad_info_raw = get_user_info_by_login(username)
                    ad_info = self._validate_and_clean_ad_info(ad_info_raw)
                except Exception:
                    ad_info = {}
            
            # Автоматическая регистрация/обновление пользователя в БД
            self._auto_register_user(username, ad_info)
            
            # Определяем роль
            role = self._determine_user_role(username)
            
            # Получаем очищенные данные из БД для g.user_info (приоритет БД)
            from database.models import db_manager, User
            session = db_manager.get_session()
            try:
                db_user = session.query(User).filter(User.username == username.lower()).first()
                if db_user:
                    # Используем данные из БД (они уже очищены)
                    surname = self._clean_ad_value(db_user.surname) if db_user.surname else ''
                    fst_name = self._clean_ad_value(db_user.fst_name) if db_user.fst_name else ''
                    sec_name = self._clean_ad_value(db_user.sec_name) if db_user.sec_name else ''
                    department = self._clean_ad_value(db_user.department) if db_user.department else ''
                    position = self._clean_ad_value(db_user.position) if db_user.position else ''
                    full_name = db_user._get_full_name_from_parts() or self._clean_ad_value(db_user.full_name) or username
                else:
                    # Fallback на данные из AD
                    surname = ad_info.get('sur_name', '')
                    fst_name = ad_info.get('first_name', '')
                    sec_name = ad_info.get('second_name', '')
                    department = ad_info.get('department', '') or os.environ.get('DEFAULT_USER_DEPARTMENT', '')
                    position = ad_info.get('position', '') or os.environ.get('DEFAULT_USER_POSITION', '')
                    full_name_parts = [surname, fst_name, sec_name]
                    full_name = ' '.join(part for part in full_name_parts if part).strip() or username
            finally:
                session.close()
            
            # Формируем user_info с очищенными данными
            g.user_info = {
                'username': username.lower(),
                'full_name': full_name,
                'surname': surname,
                'fst_name': fst_name,
                'sec_name': sec_name,
                'department': department,
                'position': position,
                'email': f"{username.lower()}@company.com",
                'role': role,
                'auth_method': (
                    'trusted_proxy'
                    if from_trusted_proxy
                    else (
                        'docker_fallback'
                        if from_docker_fallback
                        else (
                            'root_test'
                            if (root_test_mode and not from_trusted_proxy)
                            else (
                                'test_mode'
                                if test_mode
                                else (
                                    'kerberos'
                                    if auth_header and auth_header.startswith('Negotiate ')
                                    else 'windows_fallback'
                                )
                            )
                        )
                    )
                ),
                'ip_address': request.remote_addr,
                'domain': os.environ.get('USERDOMAIN', 'LOCAL'),
                'principal': f"{username.lower()}@{self.realm}"
            }
            
            
        except Exception as e:
            test_mode = False
            try:
                test_mode = self._is_test_mode()
            except Exception:
                test_mode = False
            g.user_info = {
                'username': 'guest',
                'full_name': 'Guest User',
                'role': 'user' if not test_mode else 'admin',
                'auth_method': 'none' if not test_mode else 'test_mode',
                'ip_address': request.remote_addr
            }
    
    @staticmethod
    def _is_placeholder_profile_field(value: Any) -> bool:
        """Пустые/демо-значения, которые можно заменить данными из AD."""
        v = (value or "").strip().lower()
        if not v:
            return True
        return v in (
            "guest",
            "gость",
            "не указано",
            "ошибка",
            "error",
            "none",
            "null",
            "testadmin",
        )

    def _clean_ad_value(self, value: Any) -> str:
        """Очистка и валидация значения из AD"""
        if not value:
            return ''
        
        # Преобразуем в строку
        if isinstance(value, (int, float)):
            # Если это число 0 или отрицательное - возвращаем пустую строку
            if value <= 0:
                return ''
            value = str(value)
        
        if not isinstance(value, str):
            value = str(value)
        
        # Убираем пробелы
        value = value.strip()
        
        # Проверяем на мусорные значения
        invalid_values = [
            '000000', '00000', '0000', '000', '00', '0',
            'не указано', 'не найден', 'ошибка', 'error', 'none', 'null',
            'не указано', 'не найден', 'ошибка'
        ]
        
        if value.lower() in invalid_values:
            return ''
        
        # Проверяем на мусорные символы (только цифры или только спецсимволы)
        if value and (value.isdigit() and len(value) <= 3) or (not any(c.isalnum() for c in value)):
            return ''
        
        # Убираем невидимые символы и мусор
        value = ''.join(c for c in value if c.isprintable() or c.isspace())
        value = value.strip()
        
        return value
    
    def _validate_and_clean_ad_info(self, ad_info: Dict[str, Any]) -> Dict[str, str]:
        """Валидация и очистка данных из AD"""
        cleaned = {}
        for key, value in ad_info.items():
            cleaned[key] = self._clean_ad_value(value)
        return cleaned
    
    def _determine_user_role(self, username: str) -> str:
        """Определение роли пользователя из БД"""
        try:
            from database.models import db_manager, User

            root_test_mode = self._is_root_test_mode()
            if root_test_mode:
                forced_role = (os.environ.get("ROOT_TEST_FORCE_ROLE") or "").strip().lower()
                if forced_role in ("user", "admin", "super_admin"):
                    return forced_role
            
            session = db_manager.get_session()
            try:
                user = session.query(User).filter(
                    User.username == username.lower()
                ).first()
                
                # В TEST_MODE по умолчанию считаем всех админами, но если пользователь
                # уже помечен как super_admin в БД — не затираем его роль.
                if self._is_test_mode():
                    if user and (user.role or "").strip().lower() == "super_admin":
                        return "super_admin"
                    # В тестовом режиме назначаем суперадмином отдельного пользователя,
                    # чтобы UI/доступы работали корректно в контейнере/демо.
                    default_user = (os.environ.get("TEST_MODE_DEFAULT_USER") or "testadmin").strip().lower()
                    return "super_admin" if username.lower() == default_user else "admin"

                if user:
                    return user.role
                
                # Если пользователь не найден в БД, используем хардкод
                admin_users = [
                    'admin', 'administrator', 'root', 'manager',
                    'админ', 'администратор', 'руководитель',
                    'system', 'service'
                ]
                
                if username.lower() in admin_users:
                    return 'admin'
                
                return 'user'
                
            finally:
                session.close()
                
        except Exception as e:
            return 'user'
    
    def _auto_register_user(self, username: str, ad_info: Dict[str, str]):
        """Автоматическая регистрация пользователя в БД с данными из AD"""
        try:
            from database.models import db_manager, User
            
            session = db_manager.get_session()
            try:
                # Проверяем, существует ли пользователь
                existing_user = session.query(User).filter(
                    User.username == username.lower()
                ).first()
                
                # Очищаем и валидируем данные из AD
                surname = self._clean_ad_value(ad_info.get('sur_name', ''))
                fst_name = self._clean_ad_value(ad_info.get('first_name', ''))
                sec_name = self._clean_ad_value(ad_info.get('second_name', ''))
                department = self._clean_ad_value(ad_info.get('department', '')) or os.environ.get('DEFAULT_USER_DEPARTMENT', '')
                position = self._clean_ad_value(ad_info.get('position', '')) or os.environ.get('DEFAULT_USER_POSITION', '')
                
                # В TEST_MODE мы не ходим в AD, поэтому ФИО может быть пустым.
                # Чтобы UI "видел всё о пользователе", дергаем ФИО из логина (например: ivan.petrov).
                if self._is_test_mode() and not (surname or fst_name or sec_name):
                    # Для тестового дефолтного пользователя задаём нормальное отображаемое имя,
                    # а не “разобранные куски” логина testadmin -> tadmin te.
                    default_user = (os.environ.get("TEST_MODE_DEFAULT_USER") or "testadmin").strip().lower()
                    if (username or "").strip().lower() == default_user:
                        # Можно переопределить через env, но даём понятный дефолт.
                        # Формат: "Фамилия Имя Отчество" (отчество опционально)
                        full = (os.environ.get("TEST_MODE_DEFAULT_FULL_NAME") or "Тестовый Админ").strip()
                        parts = [p for p in full.split() if p]
                        if len(parts) >= 3:
                            surname, fst_name, sec_name = parts[0], parts[1], parts[2]
                        elif len(parts) == 2:
                            surname, fst_name, sec_name = parts[0], parts[1], ""
                        elif len(parts) == 1:
                            surname, fst_name, sec_name = parts[0], "", ""
                    else:
                        import re
                        tokens = [t for t in re.split(r'[._\\-\\s]+', (username or '').strip().lower()) if t]
                        if len(tokens) >= 3:
                            fst_name = tokens[0]
                            sec_name = tokens[1]
                            surname = tokens[2]
                        elif len(tokens) == 2:
                            fst_name = tokens[0]
                            surname = tokens[1]
                            sec_name = ''
                        elif len(tokens) == 1:
                            fst_name = tokens[0]
                            surname = ''
                            sec_name = ''
                
                # Формируем полное имя из валидных частей
                full_name_parts = [surname, fst_name, sec_name]
                full_name = ' '.join(part for part in full_name_parts if part).strip() or username
                
                # Определяем роль
                role = self._determine_user_role(username)
                
                if existing_user:
                    # Обновляем существующего пользователя - обновляем если новое значение валидное
                    updated = False
                    
                    # Обновляем surname если новое значение валидное и отличается
                    if surname and surname != existing_user.surname:
                        existing_user.surname = surname
                        updated = True
                    
                    # Обновляем fst_name если новое значение валидное и отличается
                    if fst_name and fst_name != existing_user.fst_name:
                        existing_user.fst_name = fst_name
                        updated = True
                    
                    # Обновляем sec_name если новое значение валидное и отличается
                    if sec_name and sec_name != existing_user.sec_name:
                        existing_user.sec_name = sec_name
                        updated = True
                    
                    # Обновляем department/position: и при смене, и если в БД остался GUEST/пусто
                    if department and (
                        department != existing_user.department
                        or self._is_placeholder_profile_field(existing_user.department)
                    ):
                        existing_user.department = department
                        updated = True

                    if position and (
                        position != existing_user.position
                        or self._is_placeholder_profile_field(existing_user.position)
                    ):
                        existing_user.position = position
                        updated = True

                    new_full_name = ' '.join(part for part in [surname, fst_name, sec_name] if part).strip() or username
                    if new_full_name and (
                        new_full_name != (existing_user.full_name or '')
                        or existing_user.full_name == username
                        or self._is_placeholder_profile_field(existing_user.full_name)
                    ):
                        existing_user.full_name = new_full_name
                        updated = True
                    
                    # Обновляем principal и realm если не установлены
                    if not existing_user.principal:
                        existing_user.principal = f"{username.lower()}@{self.realm}"
                        existing_user.realm = self.realm
                        updated = True
                    
                    existing_user.last_login = datetime.now()
                    existing_user.role = role
                    
                    if updated:
                        session.commit()
                else:
                    # Создаем нового пользователя с очищенными данными
                    new_user = User(
                        username=username.lower(),
                        full_name=full_name,
                        surname=surname,
                        fst_name=fst_name,
                        sec_name=sec_name,
                        department=department,
                        position=position,
                        email=f"{username.lower()}@company.com",
                        principal=f"{username.lower()}@{self.realm}",
                        realm=self.realm,
                        role=role,
                        is_active=True,
                        last_login=datetime.now()
                    )
                    session.add(new_user)
                    session.commit()
                
            except Exception as e:
                session.rollback()
                raise
            finally:
                session.close()
                
        except Exception as e:
            raise


def init_new_auth(app):
    """Инициализация нового механизма аутентификации"""
    auth = NewAuth(app)
    return auth

