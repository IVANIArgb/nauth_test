"""
Утилиты для валидации входных данных.
"""
from typing import Optional
import re


def validate_search_string(search: Optional[str], max_length: int = 100) -> Optional[str]:
    """
    Валидировать строку поиска.
    
    Args:
        search: Строка поиска
        max_length: Максимальная длина
        
    Returns:
        Валидированная строка или None
    """
    if not search:
        return None
    
    search = search.strip()
    
    # Проверка длины
    if len(search) > max_length:
        return None
    
    # Удаление потенциально опасных символов
    search = re.sub(r'[<>"\']', '', search)
    
    return search if search else None


def validate_department(department: Optional[str], max_length: int = 100) -> Optional[str]:
    """
    Валидировать название отдела.
    
    Args:
        department: Название отдела
        max_length: Максимальная длина
        
    Returns:
        Валидированная строка или None
    """
    if not department:
        return None
    
    department = department.strip()
    
    if len(department) > max_length:
        return None
    
    return department if department else None


def validate_title(title: Optional[str], max_length: int = 200) -> Optional[str]:
    """
    Валидировать заголовок.
    
    Args:
        title: Заголовок
        max_length: Максимальная длина
        
    Returns:
        Валидированная строка или None
    """
    if not title:
        return None
    
    title = title.strip()
    
    if len(title) > max_length or len(title) == 0:
        return None
    
    return title
