#!/usr/bin/env python3
"""
Утилита для проверки текущего имени пользователя.
Запустите этот скрипт для получения информации о текущем пользователе.
"""

import os
import sys
import getpass
import socket
import platform
from flask import Flask

# Добавляем путь к проекту
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from backend import create_app

def check_username():
    """Проверка имени пользователя."""
    print("👤 Проверка имени пользователя...")
    print("=" * 50)
    
    # Системная информация
    print("📋 Системная информация:")
    print(f"   Текущий пользователь: {getpass.getuser()}")
    print(f"   Хост: {socket.gethostname()}")
    print(f"   Платформа: {platform.system()} {platform.release()}")
    print(f"   Рабочая директория: {os.getcwd()}")
    
    # Информация о домене
    try:
        domain = os.environ.get('USERDOMAIN', 'не определен')
        print(f"   Домен: {domain}")
    except:
        print("   Домен: не определен")
    
    print("\n🔐 Проверка через Flask приложение:")
    try:
        # Создаем приложение
        app = create_app("development")
        
        with app.test_client() as client:
            # Проверяем API пользователя
            response = client.get('/api/current-user')
            if response.status_code == 200:
                user_data = response.get_json()
                print("   ✅ API доступен")
                print(f"   Пользователь: {user_data.get('username', 'не определен')}")
                print(f"   Полное имя: {user_data.get('full_name', 'не определен')}")
                print(f"   Роль: {user_data.get('role', 'не определена')}")
                print(f"   Отдел: {user_data.get('department', 'не определен')}")
                print(f"   Аутентифицирован: {user_data.get('authenticated', False)}")
            else:
                print(f"   ❌ API недоступен: {response.status_code}")
                
    except Exception as e:
        print(f"   ❌ Ошибка: {e}")
    
    print("\n💡 Для полной проверки:")
    print("1. Запустите сервер: python run.py")
    print("2. Откройте: http://localhost:5000")
    print("3. Проверьте API: http://localhost:5000/api/current-user")

if __name__ == "__main__":
    check_username()
