"""
Модуль для получения информации о пользователе из Active Directory.
"""
import json
import logging
import os
import re
import subprocess
from typing import Dict, Optional

from auth.ad_ps_output import decode_powershell_stdout

logger = logging.getLogger(__name__)

# Только безопасные символы для sAMAccountName / PowerShell -Filter (защита от injection).
_AD_LOGIN_RE = re.compile(r"^[A-Za-z0-9._-]{1,128}$")


def sanitize_ad_login(login: str) -> Optional[str]:
    """Вернуть логин, безопасный для Get-ADUser, или None."""
    s = (login or "").strip()
    if not s or not _AD_LOGIN_RE.fullmatch(s):
        return None
    return s


class ADUserInfo:
    """
    Класс для поиска информации о пользователе в Active Directory по логину
    """

    def __init__(self, login: str):
        safe = sanitize_ad_login(login)
        if not safe:
            raise ValueError(f"Недопустимый логин для AD: {login!r}")
        self.login = safe
        self.user_data = {}
        self.result = {
            'first_name': 'Не указано',
            'second_name': 'Не указано',
            'sur_name': 'Не указано',
            'department': 'Не указано',
            'position': 'Не указано'
        }

    def get_user_info(self) -> dict:
        """
        Основной метод для получения информации о пользователе

        Returns:
            dict: Словарь с информацией о пользователе
        """
        if not self._fetch_user_data():
            self._set_error_state()
            return self.result

        self._extract_basic_info()
        self._extract_middle_name()
        self._extract_department()
        self._extract_position()

        return self.result

    def _fetch_user_data(self) -> bool:
        """
        Получает данные пользователя из Active Directory

        Returns:
            bool: Успешно ли получены данные
        """
        root = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
        ps1 = os.path.join(root, "scripts", "get-ad-user-json.ps1")
        if os.path.isfile(ps1):
            try:
                proc = subprocess.run(
                    [
                        "powershell.exe",
                        "-NoLogo",
                        "-NoProfile",
                        "-ExecutionPolicy",
                        "Bypass",
                        "-File",
                        ps1,
                        self.login,
                    ],
                    capture_output=True,
                    timeout=60,
                    cwd=root,
                )
                if proc.returncode == 0 and proc.stdout.strip():
                    text = decode_powershell_stdout(proc.stdout)
                    data = json.loads(text.strip())
                    self.user_data = {
                        "GivenName": data.get("first_name"),
                        "Surname": data.get("sur_name"),
                        "MiddleName": data.get("second_name"),
                        "Department": data.get("department"),
                        "Title": data.get("position"),
                    }
                    return True
            except Exception:
                pass

        login_escaped = self.login.replace("'", "''")
        command = (
            f"$u = '{login_escaped}'; "
            "Get-ADUser -Filter \"sAMAccountName -eq '$u'\" "
            "-Properties GivenName,Surname,MiddleName,Name,DisplayName,Department,Title,Company,Office,Description "
            "| Select-Object GivenName,Surname,MiddleName,Name,DisplayName,Department,Title,Company,Office,Description "
            "| ConvertTo-Json -Depth 1 -Compress"
        )

        try:
            result = subprocess.run(
                ["powershell.exe", "-NoLogo", "-NoProfile", "-Command", command],
                capture_output=True,
                timeout=20,
            )

            if result.returncode == 0 and result.stdout.strip():
                text = decode_powershell_stdout(result.stdout)
                self.user_data = json.loads(text.strip())
                return True
            return False

        except Exception:
            return False

    def _extract_basic_info(self):
        """Извлекает основную информацию о пользователе"""
        # Получаем основные данные из стандартных атрибутов (безопасная обработка None)
        self.result['first_name'] = self.user_data.get('GivenName') or ''
        self.result['sur_name'] = self.user_data.get('Surname') or ''
        self.result['second_name'] = self.user_data.get('MiddleName') or ''

        # Если имя или фамилия не найдены, пробуем извлечь из полного имени
        full_name = self.user_data.get('Name') or ''
        if full_name and (not self.result['first_name'] or not self.result['sur_name']):
            parsed_name = self._parse_full_name(full_name)
            if not self.result['first_name']:
                self.result['first_name'] = parsed_name['first_name']
            if not self.result['sur_name']:
                self.result['sur_name'] = parsed_name['sur_name']

    def _extract_middle_name(self):
        """Извлекает отчество из различных атрибутов"""
        if self.result['second_name']:
            return

        # Пробуем найти отчество в других атрибутах
        self.result['second_name'] = self._find_middle_name_in_attributes()

        # Если все еще не найдено, пробуем из полного имени
        if not self.result['second_name']:
            full_name = self.user_data.get('Name') or ''
            if full_name:
                name_parts = full_name.split()
                if len(name_parts) >= 3 and self._is_middle_name(name_parts[2]):
                    self.result['second_name'] = name_parts[2]

    def _extract_department(self):
        """Извлекает информацию об отделе"""
        department = self.user_data.get('Department') or ''
        if department:
            self.result['department'] = department
        else:
            self.result['department'] = self._find_department_in_attributes()

    def _extract_position(self):
        """Извлекает информацию о должности"""
        position = self.user_data.get('Title') or ''
        if position:
            self.result['position'] = position
        else:
            self.result['position'] = self._find_position_in_attributes()

    def _find_middle_name_in_attributes(self) -> str:
        """
        Ищет отчество во всех возможных атрибутах AD

        Returns:
            str: Найденное отчество или пустая строка
        """
        attributes_to_check = ['DisplayName', 'Description']

        for attr in attributes_to_check:
            value = self.user_data.get(attr) or ''
            if value:
                middle_name = self._extract_middle_name_from_text(value)
                if middle_name:
                    return middle_name

        return ''

    def _extract_middle_name_from_text(self, text: str) -> str:
        """
        Извлекает отчество из текста используя регулярные выражения

        Args:
            text: Текст для поиска отчества

        Returns:
            str: Найденное отчество или пустая строка
        """
        if not text:
            return ''

        patterns = [
            r'\b([А-Я][а-я]*ович)\b',
            r'\b([А-Я][а-я]*евич)\b',
            r'\b([А-Я][а-я]*овна)\b',
            r'\b([А-Я][а-я]*евна)\b',
            r'\b([А-Я][а-я]*ич)\b',
            r'\b([А-Я][а-я]*ична)\b'
        ]

        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1)

        return ''

    def _is_middle_name(self, word: str) -> bool:
        """
        Проверяет, является ли слово отчеством

        Args:
            word: Слово для проверки

        Returns:
            bool: True если слово является отчеством
        """
        if not word:
            return False

        middle_name_endings = [
            'ович', 'евич', 'овна', 'евна', 'ич', 'ична'
        ]

        return any(word.lower().endswith(ending) for ending in middle_name_endings)

    def _parse_full_name(self, full_name: str) -> dict:
        """
        Парсит полное имя на составляющие

        Args:
            full_name: Полное имя пользователя

        Returns:
            dict: Разобранные компоненты имени
        """
        if not full_name:
            return {'first_name': '', 'second_name': '', 'sur_name': ''}

        parts = full_name.split()

        if len(parts) == 1:
            return {'first_name': '', 'second_name': '', 'sur_name': parts[0]}
        elif len(parts) == 2:
            return {'first_name': parts[1], 'second_name': '', 'sur_name': parts[0]}
        elif len(parts) == 3:
            if self._is_middle_name(parts[2]):
                return {'first_name': parts[1], 'second_name': parts[2], 'sur_name': parts[0]}
            else:
                return {'first_name': parts[1], 'second_name': '', 'sur_name': parts[0]}
        else:
            for i in range(2, len(parts)):
                if self._is_middle_name(parts[i]):
                    return {
                        'first_name': parts[1],
                        'second_name': parts[i],
                        'sur_name': parts[0]
                    }
            return {'first_name': parts[1], 'second_name': '', 'sur_name': parts[0]}

    def _find_department_in_attributes(self) -> str:
        """
        Ищет информацию об отделе в различных атрибутах AD

        Returns:
            str: Найденный отдел или пустая строка
        """
        # Компания иногда содержит отдел
        company = self.user_data.get('Company', '')
        if company and any(word in company.lower() for word in ['отдел', 'департамент', 'управление', 'служба']):
            return company

        # Офис может содержать информацию об отделе
        office = self.user_data.get('Office', '')
        if office and any(word in office.lower() for word in ['отдел', 'кабинет', 'офис']):
            return office

        # Описание может содержать отдел
        description = self.user_data.get('Description', '')
        if description:
            dept_patterns = [
                r'отдел[а-я]*\s+([^.,!?]+)',
                r'департамент[а-я]*\s+([^.,!?]+)',
                r'управление[а-я]*\s+([^.,!?]+)',
                r'служб[а-я]*\s+([^.,!?]+)'
            ]

            for pattern in dept_patterns:
                match = re.search(pattern, description, re.IGNORECASE)
                if match and match.group(1):
                    return match.group(1).strip()

        return ''

    def _find_position_in_attributes(self) -> str:
        """
        Ищет информацию о должности в различных атрибутах AD

        Returns:
            str: Найденная должность или пустая строка
        """
        # Описание может содержать должность
        description = self.user_data.get('Description', '')
        if description:
            position_patterns = [
                r'должность[а-я]*\s*:\s*([^.,!?]+)',
                r'позиция[а-я]*\s*:\s*([^.,!?]+)',
                r'([А-Я][а-я]+\s+[А-Я][а-я]+)\s+отдел',
                r'([А-Я][а-я]+\s+[А-Я][а-я]+)\s+департамент'
            ]

            for pattern in position_patterns:
                match = re.search(pattern, description, re.IGNORECASE)
                if match and match.group(1):
                    return match.group(1).strip()

        # DisplayName иногда содержит должность
        display_name = self.user_data.get('DisplayName') or ''
        if display_name and any(
                word in display_name.lower() for word in ['инженер', 'менеджер', 'специалист', 'руководитель']):
            return self._extract_position_from_display_name(display_name)

        return ''

    def _extract_position_from_display_name(self, display_name: str) -> str:
        """
        Извлекает должность из DisplayName

        Args:
            display_name: DisplayName пользователя

        Returns:
            str: Извлеченная должность или пустая строка
        """
        positions = [
            'инженер', 'менеджер', 'специалист', 'руководитель', 'директор',
            'начальник', 'заместитель', 'главный', 'ведущий', 'старший',
            'младший', 'аналитик', 'разработчик', 'администратор', 'координатор'
        ]

        words = display_name.split()
        for i, word in enumerate(words):
            if word.lower() in positions and i > 0:
                if i >= 1 and words[i - 1].lower() in ['ведущий', 'старший', 'младший', 'главный']:
                    return f"{words[i - 1]} {word}"
                return word

        return ''

    def _set_error_state(self):
        """Устанавливает состояние ошибки для всех полей"""
        self.result = {
            'first_name': 'Ошибка',
            'second_name': 'Ошибка',
            'sur_name': 'Ошибка',
            'department': 'Ошибка',
            'position': 'Ошибка'
        }


def get_user_info_by_login(login: str) -> dict:
    """
    Функция-обертка для удобного использования класса

    Args:
        login: Логин пользователя

    Returns:
        dict: Информация о пользователе
    """
    if not sanitize_ad_login(login):
        return {
            "first_name": "Не указано",
            "second_name": "Не указано",
            "sur_name": "Не указано",
            "department": "Не указано",
            "position": "Не указано",
        }
    user_info = ADUserInfo(login)
    return user_info.get_user_info()
