"""
Утилиты для пагинации запросов.
"""
from typing import Tuple, Optional
from flask import request
from sqlalchemy.orm import Query


def get_pagination_params() -> Tuple[int, int]:
    """
    Получить параметры пагинации из запроса.
    
    Returns:
        Tuple[int, int]: (page, per_page)
    """
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    
    # Валидация параметров
    page = max(1, page)  # Минимум 1
    per_page = min(max(1, per_page), 100)  # От 1 до 100
    
    return page, per_page


def paginate_query(query: Query, page: int, per_page: int) -> dict:
    """
    Применить пагинацию к запросу.
    
    Args:
        query: SQLAlchemy запрос
        page: Номер страницы (начиная с 1)
        per_page: Количество элементов на странице
        
    Returns:
        dict: Словарь с данными и метаинформацией о пагинации
    """
    total = query.count()
    items = query.offset((page - 1) * per_page).limit(per_page).all()
    
    total_pages = (total + per_page - 1) // per_page if total > 0 else 0
    
    return {
        'items': items,
        'pagination': {
            'page': page,
            'per_page': per_page,
            'total': total,
            'total_pages': total_pages,
            'has_next': page < total_pages,
            'has_prev': page > 1
        }
    }
