from __future__ import annotations

from typing import Any, Dict
from datetime import datetime
from flask import request, g

import spnego
from ldap3 import Server, Connection, ALL, NTLM
from auth.ad_user_info import get_user_info_by_login


class RealKerberosAuth:
    def __init__(self, app=None):
        self.app = app
        if app is not None:
            self.init_app(app)

    def init_app(self, app):
        self.app = app
        app.before_request(self._authenticate)

    def _authenticate(self):
        try:
            auth_header = request.headers.get('Authorization')
            if not auth_header or not auth_header.startswith('Negotiate '):
                # Нет Kerberos заголовка — пробуем Windows-пользователя как fallback
                try:
                    import getpass
                    username = getpass.getuser()
                    if username:
                        # Получаем данные из AD
                        ad_info = {}
                        try:
                            ad_info = get_user_info_by_login(username)
                        except Exception as e:
                            ad_info = {}
                        
                        # Авторегистрация в БД как обычного пользователя
                        try:
                            from database.models import db_manager, User
                            session = db_manager.get_session()
                            user = session.query(User).filter(User.username == username.lower()).first()
                            if not user:
                                # Создаем нового пользователя с данными из AD
                                surname = ad_info.get('sur_name', '') if ad_info and ad_info.get('sur_name') not in ['Не указано', 'Ошибка'] else ''
                                fst_name = ad_info.get('first_name', '') if ad_info and ad_info.get('first_name') not in ['Не указано', 'Ошибка'] else ''
                                sec_name = ad_info.get('second_name', '') if ad_info and ad_info.get('second_name') not in ['Не указано', 'Ошибка'] else ''
                                department = ad_info.get('department', '') if ad_info and ad_info.get('department') not in ['Не указано', 'Ошибка'] else ''
                                position = ad_info.get('position', '') if ad_info and ad_info.get('position') not in ['Не указано', 'Ошибка'] else ''
                                
                                name_parts = [surname, fst_name, sec_name]
                                constructed_full_name = ' '.join(filter(None, name_parts)) if any(name_parts) else username
                                
                                user = User(
                                    username=username.lower(),
                                    surname=surname,
                                    fst_name=fst_name,
                                    sec_name=sec_name,
                                    full_name=constructed_full_name,
                                    department=department,
                                    position=position,
                                    email=f"{username.lower()}@company.com",
                                    is_active=True
                                )
                                session.add(user)
                                session.commit()
                            session.close()
                        except Exception as e:
                            pass
                        
                        # Формируем user_info
                        surname = ad_info.get('sur_name', '') if ad_info and ad_info.get('sur_name') not in ['Не указано', 'Ошибка'] else ''
                        fst_name = ad_info.get('first_name', '') if ad_info and ad_info.get('first_name') not in ['Не указано', 'Ошибка'] else ''
                        sec_name = ad_info.get('second_name', '') if ad_info and ad_info.get('second_name') not in ['Не указано', 'Ошибка'] else ''
                        department = ad_info.get('department', '') if ad_info and ad_info.get('department') not in ['Не указано', 'Ошибка'] else ''
                        position = ad_info.get('position', '') if ad_info and ad_info.get('position') not in ['Не указано', 'Ошибка'] else ''
                        
                        name_parts = [surname, fst_name, sec_name]
                        constructed_full_name = ' '.join(filter(None, name_parts)) if any(name_parts) else username
                        
                        g.user_info = {
                            'username': username.lower(),
                            'full_name': constructed_full_name,
                            'surname': surname,
                            'fst_name': fst_name,
                            'sec_name': sec_name,
                            'department': department,
                            'position': position,
                            'role': 'user',
                            'auth_method': 'windows_fallback',
                            'ip_address': request.remote_addr
                        }
                        return
                except Exception:
                    pass
                # Если и Windows недоступен — считаем обычным user, но без имени
                g.user_info = {'username': 'user', 'role': 'user', 'auth_method': 'none', 'ip_address': request.remote_addr}
                return

            in_token = auth_header.split(' ', 1)[1]
            server = spnego.server(service=self.app.config.get('KERBEROS_SERVICE_NAME', 'HTTP'))
            out_token = server.step(in_token)
            if out_token:
                # Client may require WWW-Authenticate: Negotiate <token>, but for simplicity skip header write here
                pass
            if not server.complete:
                return

            principal = server.principal
            username = principal.split('@')[0] if principal else None
            realm = principal.split('@')[1] if principal and '@' in principal else self.app.config.get('KERBEROS_REALM', 'EXAMPLE.COM')

            # Получаем данные из AD через PowerShell скрипт
            ad_info = {}
            if username:
                try:
                    ad_info = get_user_info_by_login(username)
                except Exception as e:
                    ad_info = {}

            # Enrich with LDAP if enabled
            full_name = username
            if self.app.config.get('LDAP_ENABLED', True):
                try:
                    full_name = self._ldap_display_name(username)
                except Exception as e:
                    pass

            # Role resolution and user registration/update
            role = 'user'
            try:
                from database.models import db_manager, User
                session = db_manager.get_session()
                try:
                    # Обновляем или создаем KerberosUser
                    ku = session.query(KerberosUser).filter(KerberosUser.username == username.lower()).first()
                    if ku:
                        # Обновляем существующего пользователя
                        if ad_info:
                            ku.surname = ad_info.get('sur_name', '') if ad_info.get('sur_name') != 'Не указано' and ad_info.get('sur_name') != 'Ошибка' else ku.surname
                            ku.fst_name = ad_info.get('first_name', '') if ad_info.get('first_name') != 'Не указано' and ad_info.get('first_name') != 'Ошибка' else ku.fst_name
                            ku.sec_name = ad_info.get('second_name', '') if ad_info.get('second_name') != 'Не указано' and ad_info.get('second_name') != 'Ошибка' else ku.sec_name
                            ku.department = ad_info.get('department', '') if ad_info.get('department') != 'Не указано' and ad_info.get('department') != 'Ошибка' else ku.department
                            ku.position = ad_info.get('position', '') if ad_info.get('position') != 'Не указано' and ad_info.get('position') != 'Ошибка' else ku.position
                            ku.full_name = ku._get_full_name_from_parts() if (ku.surname or ku.fst_name) else full_name
                        ku.last_login = datetime.now()
                        role = ku.role
                    else:
                        # Создаем нового KerberosUser
                        surname = ad_info.get('sur_name', '') if ad_info and ad_info.get('sur_name') not in ['Не указано', 'Ошибка'] else ''
                        fst_name = ad_info.get('first_name', '') if ad_info and ad_info.get('first_name') not in ['Не указано', 'Ошибка'] else ''
                        sec_name = ad_info.get('second_name', '') if ad_info and ad_info.get('second_name') not in ['Не указано', 'Ошибка'] else ''
                        department = ad_info.get('department', '') if ad_info and ad_info.get('department') not in ['Не указано', 'Ошибка'] else ''
                        position = ad_info.get('position', '') if ad_info and ad_info.get('position') not in ['Не указано', 'Ошибка'] else ''
                        
                        # Формируем полное имя
                        name_parts = [surname, fst_name, sec_name]
                        constructed_full_name = ' '.join(filter(None, name_parts)) if any(name_parts) else full_name
                        
                        ku = KerberosUser(
                            username=username.lower(),
                            principal=principal,
                            realm=realm,
                            surname=surname,
                            fst_name=fst_name,
                            sec_name=sec_name,
                            full_name=constructed_full_name,
                            department=department,
                            position=position,
                            email=f"{username.lower()}@company.com",
                            role=role,
                            is_active=True,
                            last_login=datetime.now()
                        )
                        session.add(ku)
                    
                    # Обновляем или создаем User
                    user = session.query(User).filter(User.username == username.lower()).first()
                    if user:
                        # Обновляем существующего пользователя
                        if ad_info:
                            user.surname = ad_info.get('sur_name', '') if ad_info.get('sur_name') not in ['Не указано', 'Ошибка'] else user.surname
                            user.fst_name = ad_info.get('first_name', '') if ad_info.get('first_name') not in ['Не указано', 'Ошибка'] else user.fst_name
                            user.sec_name = ad_info.get('second_name', '') if ad_info.get('second_name') not in ['Не указано', 'Ошибка'] else user.sec_name
                            user.department = ad_info.get('department', user.department) if ad_info.get('department') not in ['Не указано', 'Ошибка'] else user.department
                            user.position = ad_info.get('position', '') if ad_info.get('position') not in ['Не указано', 'Ошибка'] else user.position
                            user.full_name = user._get_full_name_from_parts() if (user.surname or user.fst_name) else user.full_name
                    else:
                        # Создаем нового User
                        surname = ad_info.get('sur_name', '') if ad_info and ad_info.get('sur_name') not in ['Не указано', 'Ошибка'] else ''
                        fst_name = ad_info.get('first_name', '') if ad_info and ad_info.get('first_name') not in ['Не указано', 'Ошибка'] else ''
                        sec_name = ad_info.get('second_name', '') if ad_info and ad_info.get('second_name') not in ['Не указано', 'Ошибка'] else ''
                        department = ad_info.get('department', '') if ad_info and ad_info.get('department') not in ['Не указано', 'Ошибка'] else ''
                        position = ad_info.get('position', '') if ad_info and ad_info.get('position') not in ['Не указано', 'Ошибка'] else ''
                        
                        name_parts = [surname, fst_name, sec_name]
                        constructed_full_name = ' '.join(filter(None, name_parts)) if any(name_parts) else username
                        
                        user = User(
                            username=username.lower(),
                            surname=surname,
                            fst_name=fst_name,
                            sec_name=sec_name,
                            full_name=constructed_full_name,
                            department=department,
                            position=position,
                            email=f"{username.lower()}@company.com",
                            is_active=True
                        )
                        session.add(user)
                    
                    session.commit()
                except Exception as e:
                    session.rollback()
                    pass
                finally:
                    session.close()
            except Exception as e:
                pass

            # Формируем g.user_info с данными из AD
            surname = ad_info.get('sur_name', '') if ad_info and ad_info.get('sur_name') not in ['Не указано', 'Ошибка'] else ''
            fst_name = ad_info.get('first_name', '') if ad_info and ad_info.get('first_name') not in ['Не указано', 'Ошибка'] else ''
            sec_name = ad_info.get('second_name', '') if ad_info and ad_info.get('second_name') not in ['Не указано', 'Ошибка'] else ''
            department = ad_info.get('department', 'Общий отдел') if ad_info and ad_info.get('department') not in ['Не указано', 'Ошибка'] else 'Общий отдел'
            position = ad_info.get('position', '') if ad_info and ad_info.get('position') not in ['Не указано', 'Ошибка'] else ''
            
            name_parts = [surname, fst_name, sec_name]
            constructed_full_name = ' '.join(filter(None, name_parts)) if any(name_parts) else full_name

            g.user_info = {
                'username': username.lower() if username else None,
                'full_name': constructed_full_name,
                'surname': surname,
                'fst_name': fst_name,
                'sec_name': sec_name,
                'department': department,
                'position': position,
                'domain': realm,
                'role': role,
                'auth_method': 'kerberos',
                'ip_address': request.remote_addr,
                'principal': principal
            }
        except Exception as e:
            pass
            g.user_info = {'username': 'user', 'role': 'user', 'auth_method': 'none', 'ip_address': request.remote_addr}

    def _ldap_display_name(self, username: str) -> str:
        server_uri = self.app.config.get('LDAP_SERVER')
        base_dn = self.app.config.get('LDAP_BASE_DN')
        bind_user = self.app.config.get('LDAP_USER')
        bind_pass = self.app.config.get('LDAP_PASSWORD')

        server = Server(server_uri, get_info=ALL)
        if bind_user and bind_pass:
            conn = Connection(server, user=bind_user, password=bind_pass, authentication=NTLM, auto_bind=True)
        else:
            conn = Connection(server, auto_bind=True)
        conn.search(base_dn, f'(sAMAccountName={username})', attributes=['displayName', 'cn'])
        try:
            entry = conn.entries[0]
            return str(entry.displayName or entry.cn or username)
        except Exception:
            return username


def init_real_kerberos_auth(app):
    RealKerberosAuth(app)
    return app


