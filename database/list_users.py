#!/usr/bin/env python3
"""
Вспомогательный скрипт для просмотра всех пользователей в базе данных.
"""

import sys
import os

# Добавляем путь к директории проекта
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.models import User, db_manager


def list_all_users():
    """Выводит список всех пользователей в базе данных."""
    db = db_manager.get_session()
    
    try:
        users = db.query(User).all()
        
        if not users:
            print("База данных не содержит пользователей.")
            return
        
        print(f"Найдено {len(users)} пользователей:")
        print("-" * 80)
        print(f"{'ID':<5} {'Username':<20} {'Full Name':<30} {'Role':<10}")
        print("-" * 80)
        
        for user in users:
            full_name = user.full_name or user._get_full_name_from_parts() or ""
            if len(full_name) > 28:
                full_name = full_name[:27] + "…"
            print(f"{user.id:<5} {user.username:<20} {full_name:<30} {user.role:<10}")
        
        print("-" * 80)
        
    finally:
        db.close()


if __name__ == "__main__":
    list_all_users()