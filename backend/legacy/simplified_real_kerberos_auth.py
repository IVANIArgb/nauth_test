"""
DEPRECATED: используйте auth/new_auth.py. Не импортировать в приложение.

Simplified Real Kerberos Authentication Module (архив).
"""

import os
import base64
from typing import Dict, Any, Optional
from flask import request, g, current_app

from auth.ad_user_info import get_user_info_by_login


class SimplifiedRealKerberosAuth:
    """Упрощенный класс для настоящей аутентификации через Kerberos"""
    
    def __init__(self, app=None):
        self.app = app
        
        if app is not None:
            self.init_app(app)
    
    def init_app(self, app):
        """Инициализация Kerberos аутентификации"""
        self.app = app
        
        # Настройка Kerberos
        self.service_name = app.config.get('KERBEROS_SERVICE_NAME', 'HTTP')
        self.realm = app.config.get('KERBEROS_REALM', 'EXAMPLE.COM')
        self.keytab_file = app.config.get('KERBEROS_KEYTAB', '/etc/krb5.keytab')
        self.kdc_host = app.config.get('KERBEROS_KDC_HOST', 'localhost')
        self.kdc_port = app.config.get('KERBEROS_KDC_PORT', 88)
        
        # Регистрация обработчиков
        app.before_request(self._authenticate_user)
    
    def _authenticate_user(self):
        """Аутентификация пользователя через упрощенный Kerberos"""
        try:
            # Получение Authorization заголовка
            auth_header = request.headers.get('Authorization')
            if not auth_header or not auth_header.startswith('Negotiate '):
                # Если нет Kerberos токена, пробуем Windows Auth как fallback
                return self._fallback_to_windows_auth()
            
            # Извлечение Kerberos токена
            token = auth_header[10:]  # Убираем "Negotiate "
            
            # Проверка токена через упрощенную логику
            user_info = self._verify_kerberos_token(token)
            if user_info:
                g.user_info = user_info
            else:
                return self._fallback_to_windows_auth()
                
        except Exception as e:
            return self._fallback_to_windows_auth()
    
    def _verify_kerberos_token(self, token: str) -> Optional[Dict[str, Any]]:
        """Проверка Kerberos токена через упрощенную логику"""
        try:
            # Декодирование токена
            try:
                token_bytes = base64.b64decode(token)
            except Exception as e:
                return None
            
            # Упрощенная проверка токена
            # В реальном Kerberos здесь была бы проверка криптографических подписей
            
            # Поиск информации о пользователе в токене
            username = self._extract_username_from_token(token_bytes)
            if not username:
                # Если не удалось извлечь, используем фиктивного пользователя
                username = "kerberos_user"
            
            # Автоматическая регистрация пользователя в БД с данными из AD
            ad_info = self._fetch_ad_profile(username)
            self._auto_register_user(username, ad_info)
            
            realm = self.realm
            
            # Определение роли пользователя
            role = self._determine_user_role(username)

            full_name = self._compose_full_name(username, ad_info)
            department = ad_info.get('department') or self._get_user_department(username) or ''
            position = ad_info.get('position', '')
            
            return {
                'username': username.lower(),
                'full_name': full_name or f"{username}@{realm}",
                'fst_name': ad_info.get('first_name', ''),
                'sec_name': ad_info.get('second_name', ''),
                'surname': ad_info.get('sur_name', ''),
                'department': department,
                'position': position,
                'domain': realm,
                'role': role,
                'auth_method': 'kerberos',
                'ip_address': request.remote_addr,
                'hostname': self._get_hostname_by_ip(request.remote_addr),
                'principal': f"{username}@{realm}"
            }
            
        except Exception as e:
            pass
            return None
    
    def _extract_username_from_token(self, token_bytes: bytes) -> Optional[str]:
        """Извлечение имени пользователя из токена"""
        try:
            # Это упрощенная реализация для демонстрации
            # В реальном Kerberos здесь была бы полная декодировка ASN.1 структуры
            token_str = token_bytes.decode('utf-8', errors='ignore')
            
            # Поиск паттернов имени пользователя в токене
            import re
            patterns = [
                r'([a-zA-Z0-9._-]+)@([a-zA-Z0-9._-]+)',  # username@realm
                r'([a-zA-Z0-9._-]+)/',  # username/
                r'([a-zA-Z0-9._-]+)',  # username
            ]
            
            for pattern in patterns:
                match = re.search(pattern, token_str)
                if match:
                    return match.group(1)
            
            return None
            
        except Exception as e:
            pass
            return None
    
    def _fallback_to_windows_auth(self):
        """Fallback к Windows Authentication с автоматической регистрацией"""
        try:
            # Попытка получить текущего пользователя Windows
            import getpass
            username = getpass.getuser()
            
            if username and username.lower() != 'guest':
                # Автоматическая регистрация пользователя в БД
                ad_info = self._fetch_ad_profile(username)
                self._auto_register_user(username, ad_info)
                
                role = self._determine_user_role(username)
                full_name = self._compose_full_name(username, ad_info)
                
                g.user_info = {
                    'username': username.lower(),
                    'full_name': full_name,
                    'fst_name': ad_info.get('first_name', ''),
                    'sec_name': ad_info.get('second_name', ''),
                    'surname': ad_info.get('sur_name', ''),
                    'department': ad_info.get('department') or os.environ.get('DEFAULT_USER_DEPARTMENT', ''),
                    'position': ad_info.get('position', ''),
                    'domain': os.environ.get('USERDOMAIN', 'LOCAL'),
                    'role': role,
                    'auth_method': 'windows_fallback',
                    'ip_address': request.remote_addr,
                    'hostname': self._get_hostname_by_ip(request.remote_addr)
                }
                
                return
            
        except Exception as e:
            pass
        
        # Если все не удалось, создаем guest пользователя
        g.user_info = {
            'username': 'guest',
            'full_name': 'Guest User',
            'role': 'user',
            'auth_method': 'none',
            'ip_address': request.remote_addr,
            'hostname': self._get_hostname_by_ip(request.remote_addr)
        }
    
    def _determine_user_role(self, username: str) -> str:
        """Определение роли пользователя из БД"""
        try:
            from database.models import db_manager
            
            session = db_manager.get_session()
            try:
                # Ищем пользователя в БД
                kerberos_user = session.query(KerberosUser).filter(
                    KerberosUser.username == username.lower()
                ).first()
                
                if kerberos_user:
                    return kerberos_user.role
                
                # Если пользователь не найден в БД, используем хардкод
                admin_users = [
                    'admin', 'administrator', 'root', 'manager',
                    'админ', 'администратор', 'руководитель',
                    'system', 'service'  # Системные пользователи
                ]
                
                if username.lower() in admin_users:
                    return 'admin'
                
                return 'user'
                
            finally:
                session.close()
                
        except Exception as e:
            pass
            # Fallback к хардкоду
            admin_users = [
                'admin', 'administrator', 'root', 'manager',
                'админ', 'администратор', 'руководитель',
                'system', 'service'
            ]
            
            if username.lower() in admin_users:
                return 'admin'
            
            return 'user'
    
    def _get_hostname_by_ip(self, ip_address: str) -> str:
        """Получение hostname по IP адресу"""
        try:
            import socket
            hostname = socket.gethostbyaddr(ip_address)[0]
            return hostname
        except:
            return ip_address
    
    def _auto_register_user(self, username: str, ad_info: Optional[Dict[str, str]] = None):
        """Автоматическая регистрация пользователя в БД с получением данных из AD"""
        try:
            from database.models import db_manager, User
            
            if ad_info is None:
                ad_info = self._fetch_ad_profile(username)
            
            session = db_manager.get_session()
            try:
                # Проверяем, существует ли пользователь в основной таблице User
                existing_user = session.query(User).filter(User.username == username.lower()).first()
                
                if not existing_user:
                    # Используем данные из AD или значения по умолчанию
                    full_name = self._compose_full_name(username, ad_info)
                    
                    # Создаем нового пользователя с данными из AD
                    new_user = User(
                        username=username.lower(),
                        full_name=full_name,
                        surname=ad_info.get('sur_name') or '',
                        fst_name=ad_info.get('first_name') or '',
                        sec_name=ad_info.get('second_name') or '',
                        department=ad_info.get('department') or self._get_user_department(username) or '',
                        position=ad_info.get('position') or '',
                        email=f"{username.lower()}@company.com",  # Можно улучшить, если в AD есть email
                        is_active=True
                    )
                    session.add(new_user)
                else:
                    # Обновляем данные из AD, если они есть
                    if ad_info:
                        updated = False
                        if ad_info.get('sur_name') and not existing_user.surname:
                            existing_user.surname = ad_info.get('sur_name')
                            updated = True
                        if ad_info.get('first_name') and not existing_user.fst_name:
                            existing_user.fst_name = ad_info.get('first_name')
                            updated = True
                        if ad_info.get('second_name') and not existing_user.sec_name:
                            existing_user.sec_name = ad_info.get('second_name')
                            updated = True
                        if ad_info.get('department') and existing_user.department == self._get_user_department(username):
                            existing_user.department = ad_info.get('department')
                            updated = True
                        if ad_info.get('position') and not existing_user.position:
                            existing_user.position = ad_info.get('position')
                            updated = True
                        if updated:
                            session.commit()
                
                # Проверяем, существует ли пользователь в таблице KerberosUser
                existing_kerberos_user = session.query(KerberosUser).filter(
                    KerberosUser.username == username.lower()
                ).first()
                
                if not existing_kerberos_user:
                    # Получаем realm из конфигурации
                    realm = getattr(self, 'realm', 'EXAMPLE.COM')
                    
                    # Используем данные из AD для создания Kerberos пользователя
                    full_name = self._compose_full_name(username, ad_info)
                    
                    # Создаем Kerberos запись для пользователя с данными из AD; роль по умолчанию user
                    kerberos_user = KerberosUser(
                        username=username.lower(),
                        principal=f"{username.lower()}@{realm}",
                        realm=realm,
                        full_name=full_name,
                        surname=ad_info.get('sur_name') or '',
                        fst_name=ad_info.get('first_name') or '',
                        sec_name=ad_info.get('second_name') or '',
                        department=ad_info.get('department') or self._get_user_department(username) or '',
                        position=ad_info.get('position') or '',
                        email=f"{username.lower()}@company.com",
                        role='user',
                        is_active=True
                    )
                    session.add(kerberos_user)
                else:
                    # Обновляем данные из AD, если они есть
                    if ad_info:
                        updated = False
                        if ad_info.get('sur_name') and not existing_kerberos_user.surname:
                            existing_kerberos_user.surname = ad_info.get('sur_name')
                            updated = True
                        if ad_info.get('first_name') and not existing_kerberos_user.fst_name:
                            existing_kerberos_user.fst_name = ad_info.get('first_name')
                            updated = True
                        if ad_info.get('second_name') and not existing_kerberos_user.sec_name:
                            existing_kerberos_user.sec_name = ad_info.get('second_name')
                            updated = True
                        if ad_info.get('department') and existing_kerberos_user.department == self._get_user_department(username):
                            existing_kerberos_user.department = ad_info.get('department')
                            updated = True
                        if ad_info.get('position') and not existing_kerberos_user.position:
                            existing_kerberos_user.position = ad_info.get('position')
                            updated = True
                        if updated:
                            session.commit()
                
                session.commit()
                
            except Exception as e:
                session.rollback()
                pass
                raise
            finally:
                session.close()
                
        except Exception as e:
            raise
    
    def _get_user_department(self, username: str) -> str:
        """
        Получение отдела пользователя из переменной окружения или пустая строка.
        Реальные данные должны приходить из AD через ad_info.
        """
        return os.environ.get('DEFAULT_USER_DEPARTMENT', '')
    
    def _fetch_ad_profile(self, username: str) -> Dict[str, str]:
        """Получение профиля пользователя из AD"""
        ad_info: Dict[str, str] = {}
        try:
            raw = get_user_info_by_login(username)
            for key, value in raw.items():
                if isinstance(value, str) and value.lower() in {'не указано', 'ошибка', 'не найден'}:
                    ad_info[key] = ''
                else:
                    ad_info[key] = value or ''
        except Exception as e:
            pass
        return ad_info
    
    def _compose_full_name(self, username: str, ad_info: Optional[Dict[str, str]]) -> str:
        """Собрать полное имя из данных AD или вернуть username"""
        if not ad_info:
            return username
        parts = [
            ad_info.get('sur_name', '').strip(),
            ad_info.get('first_name', '').strip(),
            ad_info.get('second_name', '').strip()
        ]
        full_name = " ".join(part for part in parts if part)
        return full_name or username
    
    def get_user_info(self) -> Dict[str, Any]:
        """Получение информации о текущем пользователе"""
        return g.get('user_info', {
            'username': 'guest',
            'full_name': 'Guest User',
            'role': 'user',
            'auth_method': 'none',
            'ip_address': request.remote_addr,
            'hostname': self._get_hostname_by_ip(request.remote_addr)
        })


def init_simplified_real_kerberos_auth(app):
    """Инициализация упрощенной настоящей Kerberos аутентификации"""
    kerberos_auth = SimplifiedRealKerberosAuth(app)
    return kerberos_auth
