#!/usr/bin/env python3
"""
Тестовый скрипт для проверки базы данных пользователей и курсов.
"""

import os
import sys
from flask import Flask

# Добавляем путь к проекту
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from backend import create_app
from backend.models import db_manager

def test_database():
    """Тестирование базы данных."""
    print("🗄️ Тестирование базы данных...")
    
    # Создаем приложение
    app = create_app("development")
    
    with app.app_context():
        # Создаем таблицы
        db_manager.create_tables()
        print("✅ Таблицы созданы")
        
        # Инициализируем тестовые данные
        db_manager.init_sample_data()
        print("✅ Тестовые данные созданы")
        
        # Тестируем API endpoints
        with app.test_client() as client:
            print("\n📋 Тестирование API endpoints:")
            
            # Тест статистики
            response = client.get('/api/statistics')
            if response.status_code == 200:
                data = response.get_json()
                print(f"✅ Statistics: {data['overview']}")
            else:
                print(f"❌ Statistics: {response.status_code}")
            
            # Тест пользователей
            response = client.get('/api/users')
            if response.status_code == 200:
                data = response.get_json()
                print(f"✅ Users: {data['total']} пользователей")
            else:
                print(f"❌ Users: {response.status_code}")
            
            # Тест курсов
            response = client.get('/api/courses')
            if response.status_code == 200:
                data = response.get_json()
                print(f"✅ Courses: {data['total']} курсов")
            else:
                print(f"❌ Courses: {response.status_code}")
            
            # Тест отделов
            response = client.get('/api/departments')
            if response.status_code == 200:
                data = response.get_json()
                print(f"✅ Departments: {data['total']} отделов")
            else:
                print(f"❌ Departments: {response.status_code}")
            
            # Тест детального прогресса пользователя
            response = client.get('/api/users/1/progress')
            if response.status_code == 200:
                data = response.get_json()
                print(f"✅ User Progress: {data['summary']}")
            else:
                print(f"❌ User Progress: {response.status_code}")
        
        print("\n🎯 Тестирование базы данных завершено!")
        print("\n📝 Для полного тестирования:")
        print("1. Запустите сервер: python run.py")
        print("2. Откройте страницу пользователей: http://localhost:5000/users-info-pg/")
        print("3. Проверьте API: http://localhost:5000/api/users")

if __name__ == "__main__":
    test_database()
