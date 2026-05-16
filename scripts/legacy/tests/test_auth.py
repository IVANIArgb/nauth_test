#!/usr/bin/env python3
"""
Тестовый скрипт для проверки Windows Authentication.
Запустите этот скрипт для тестирования аутентификации в режиме разработки.
"""

import os
import sys
from flask import Flask

# Добавляем путь к проекту
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from backend import create_app

def test_auth():
    """Тестирование аутентификации."""
    print("🔐 Тестирование Windows Authentication...")
    
    # Создаем приложение в режиме разработки
    app = create_app("development")
    
    # Включаем режим отладки аутентификации
    app.config['WINDOWS_AUTH_DEBUG'] = True
    
    with app.test_client() as client:
        print("\n📋 Тестирование endpoints:")
        
        # Тест healthcheck
        response = client.get('/healthz')
        print(f"✅ Healthcheck: {response.status_code}")
        
        # Тест API пользователя
        response = client.get('/api/user')
        print(f"✅ API User: {response.status_code}")
        if response.status_code == 200:
            user_data = response.get_json()
            print(f"   Пользователь: {user_data}")
        
        # Тест отладочной страницы
        response = client.get('/debug/auth')
        print(f"✅ Debug Auth: {response.status_code}")
        if response.status_code == 200:
            debug_data = response.get_json()
            print(f"   Отладочная информация получена")
            print(f"   Пользователь: {debug_data.get('user_info', {})}")
        
        # Тест главной страницы
        response = client.get('/main-pg/')
        print(f"✅ Main Page: {response.status_code}")
        
        print("\n🎯 Тестирование завершено!")
        print("\n📝 Для полного тестирования:")
        print("1. Запустите сервер: python run.py")
        print("2. Откройте браузер: http://localhost:5000")
        print("3. Проверьте отладку: http://localhost:5000/debug/auth")
        print("4. Проверьте API: http://localhost:5000/api/user")

if __name__ == "__main__":
    test_auth()
