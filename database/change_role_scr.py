#!/usr/bin/env python3
"""
Объединенный скрипт для изменения роли пользователя.
"""

import sys
import os
import argparse
from typing import Optional

# Добавляем путь к директории проекта, чтобы можно было импортировать модули
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.models import User, db_manager


def list_users():
    """Выводит список всех пользователей в базе данных."""
    db = db_manager.get_session()
    
    try:
        users = db.query(User).all()
        
        if not users:
            print("База данных не содержит пользователей.")
            return []
        
        print(f"Найдено {len(users)} пользователей:")
        print("-" * 80)
        print(f"{'ID':<5} {'Username':<20} {'Full Name':<30} {'Role':<10}")
        print("-" * 80)
        
        user_list = []
        for user in users:
            full_name = user.full_name or user._get_full_name_from_parts() or ""
            if len(full_name) > 28:
                full_name = full_name[:27] + "..."
            print(f"{user.id:<5} {user.username:<20} {full_name:<30} {user.role:<10}")
            user_list.append({
                'id': user.id,
                'username': user.username,
                'full_name': full_name,
                'role': user.role
            })
        
        print("-" * 80)
        return user_list
        
    finally:
        db.close()


def change_user_role(username: str, new_role: str) -> bool:
    """
    Изменяет роль пользователя по его имени/логину.
    
    Args:
        username: Имя пользователя/логин
        new_role: Новая роль ('admin' или 'user')
        
    Returns:
        bool: True если роль успешно изменена, False в противном случае
    """
    # Проверяем, что новая роль допустима
    valid_roles = ['user', 'admin', 'super_admin']
    new_role = new_role.lower()
    if new_role not in valid_roles:
        print(f"[ERROR] Invalid role '{new_role}'. Valid values: {', '.join(valid_roles)}")
        return False
    
    # Создаем сессию базы данных
    db = db_manager.get_session()
    
    try:
        # Находим пользователя по имени
        user = db.query(User).filter(User.username == username).first()
        
        if not user:
            print(f"[ERROR] User with username '{username}' not found")
            return False
        
        # Сохраняем старую роль для отчета
        old_role = user.role
        
        # Обновляем роль пользователя
        user.role = new_role
        db.commit()
        
        print(f"[SUCCESS] Successfully changed role for user '{username}': {old_role} -> {new_role}")
        return True
        
    except Exception as e:
        print(f"[ERROR] Error changing user role: {str(e)}")
        db.rollback()
        return False
    finally:
        db.close()


def get_current_user_role(username: str) -> Optional[str]:
    """
    Gets the current role of a user.
    
    Args:
        username: Username/login
        
    Returns:
        str or None: Current user role or None if user not found
    """
    db = db_manager.get_session()
    
    try:
        user = db.query(User).filter(User.username == username).first()
        if user:
            return user.role
        return None
    finally:
        db.close()


def interactive_change_role():
    """
    Интерактивное изменение роли пользователя.
    """
    print("=== Изменение роли пользователя ===")
    
    # Показываем список всех пользователей
    db = db_manager.get_session()
    try:
        users = db.query(User).all()
        if users:
            print(f"\nFound {len(users)} users:")
            print("-" * 80)
            print(f"{'ID':<5} {'Username':<20} {'Full Name':<30} {'Role':<10}")
            print("-" * 80)
            for user in users:
                full_name = user.full_name or user._get_full_name_from_parts() or ""
                if len(full_name) > 28:
                    full_name = full_name[:27] + "..."
                print(f"{user.id:<5} {user.username:<20} {full_name:<30} {user.role:<10}")
            print("-" * 80)
        else:
            print("Database contains no users.")
            return
    finally:
        db.close()
    
    # Запрашиваем имя пользователя
    username = input("\nEnter username: ").strip()
    if not username:
        print("[ERROR] Username cannot be empty")
        return False
    
    # Запрашиваем новую роль
    valid_roles = ['user', 'admin', 'super_admin']
    print(f"Available roles: {', '.join(valid_roles)}")
    new_role = input("Enter new role: ").strip().lower()
    
    if new_role not in valid_roles:
        print(f"[ERROR] Invalid role '{new_role}'. Valid values: {', '.join(valid_roles)}")
        return False
    
    # Проверяем текущую роль пользователя
    current_role = get_current_user_role(username)
    if current_role:
        print(f"Current role of user '{username}': {current_role}")
    else:
        print(f"User '{username}' not found in database")
        return False
    
    # Подтверждение действия
    confirm = input(f"\nAre you sure you want to change role for user '{username}' from '{current_role}' to '{new_role}'? (y/N): ")
    if confirm.lower() not in ['y', 'yes', 'да', 'д']:
        print("Operation cancelled.")
        return False
    
    # Изменяем роль пользователя
    return change_user_role(username, new_role)


def interactive_menu():
    """Интерактивное меню для изменения роли пользователя."""
    while True:
        print("\n=== Меню изменения роли пользователя ===")
        print("1. Показать всех пользователей")
        print("2. Изменить роль пользователя")
        print("3. Выйти")
        
        choice = input("Выберите действие (1-3): ").strip()
        
        if choice == '1':
            print()
            list_users()
        elif choice == '2':
            print()
            # Показываем список пользователей
            users = list_users()
            if not users:
                continue
            
            # Запрашиваем имя пользователя
            username = input("\nВведите имя пользователя (username): ").strip()
            if not username:
                print("[ERROR] Имя пользователя не может быть пустым")
                continue
            
            # Проверяем, существует ли пользователь
            user_exists = any(u['username'] == username for u in users)
            if not user_exists:
                print(f"[ERROR] Пользователь '{username}' не найден в списке")
                continue
            
            # Запрашиваем новую роль
            valid_roles = ['user', 'admin', 'super_admin']
            print(f"Доступные роли: {', '.join(valid_roles)}")
            new_role = input("Введите новую роль: ").strip().lower()
            
            if new_role not in valid_roles:
                print(f"[ERROR] Недопустимая роль '{new_role}'. Допустимые значения: {', '.join(valid_roles)}")
                continue
            
            # Подтверждение действия
            current_role = next((u['role'] for u in users if u['username'] == username), 'unknown')
            confirm = input(f"Вы уверены, что хотите изменить роль пользователя '{username}' с '{current_role}' на '{new_role}'? (y/N): ")
            if confirm.lower() not in ['y', 'yes', 'да', 'д']:
                print("Операция отменена.")
                continue
            
            # Изменяем роль пользователя
            success = change_user_role(username, new_role)
            if success:
                print("Роль успешно изменена!")
        elif choice == '3':
            print("Выход из программы.")
            break
        else:
            print("Неверный выбор. Пожалуйста, введите число от 1 до 3.")


def main():
    parser = argparse.ArgumentParser(
        description="Объединенный скрипт для изменения роли пользователя",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Usage examples:
  python change_role_scr.py --list-users                  # Show all users
  python change_role_scr.py --username john.doe --role admin  # Change role
  python change_role_scr.py --interactive                 # Interactive mode
  python change_role_scr.py --menu                        # Menu mode
        """
    )
    
    parser.add_argument('--list-users', action='store_true', help='Show all users in the database')
    parser.add_argument('--username', help='Username/login to change role for')
    parser.add_argument('--role', help='New role (user, admin or super_admin)')
    parser.add_argument('--interactive', action='store_true', help='Run in interactive mode')
    parser.add_argument('--menu', action='store_true', help='Run in menu mode')
    
    args = parser.parse_args()
    
    # Если указан флаг --menu, запускаем интерактивное меню
    if args.menu:
        interactive_menu()
        return
    
    # Если указан флаг --interactive, запускаем интерактивный режим
    if args.interactive:
        success = interactive_change_role()
        if not success:
            sys.exit(1)
        return
    
    # Если указан флаг --list-users, просто выводим список пользователей
    if args.list_users:
        list_users()
        return
    
    # Проверяем, что переданы оба обязательных аргумента для изменения роли
    if args.username and args.role:
        # Проверяем текущую роль пользователя
        current_role = get_current_user_role(args.username)
        if current_role:
            print(f"Current role of user '{args.username}': {current_role}")
        else:
            print(f"User '{args.username}' not found in database")
            return
        
        # Изменяем роль пользователя
        success = change_user_role(args.username, args.role)
        
        if not success:
            sys.exit(1)
    else:
        # Если не указаны аргументы, показываем список пользователей и инструкции
        print("Для изменения роли пользователя используйте:")
        print("  --username ИМЯ_ПОЛЬЗОВАТЕЛЯ --role РОЛЬ")
        print("  Доступные роли: user, admin, super_admin")
        print("\nДругие опции:")
        print("  --list-users : Показать список всех пользователей")
        print("  --interactive : Интерактивный режим")
        print("  --menu : Режим меню")
        print("\nСписок пользователей:")
        list_users()


if __name__ == "__main__":
    main()