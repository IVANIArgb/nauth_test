#!/usr/bin/env python3
"""
Тестовый скрипт для проверки системы ролевой маршрутизации.
"""

import os
import sys
import requests
from unittest.mock import patch

# Добавляем корень проекта в path
_project_root = os.path.dirname(os.path.abspath(__file__))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from backend import create_app
from auth.new_auth import NewAuth


def test_role_detection():
    """Тестируем определение ролей пользователей."""
    print("🔍 Тестирование определения ролей...")
    
    auth = NewAuth()
    
    # Тестируем админов
    admin_users = ['admin', 'administrator', 'root', 'manager', 'админ']
    for username in admin_users:
        role = auth._determine_user_role(username)
        print(f"  {username} -> {role}")
        assert role == 'admin', f"Ожидался 'admin' для {username}, получен {role}"
    
    # Тестируем обычных пользователей
    regular_users = ['ivan.petrov', 'maria.sidorova', 'user123', 'test']
    for username in regular_users:
        role = auth._determine_user_role(username)
        print(f"  {username} -> {role}")
        assert role == 'user', f"Ожидался 'user' для {username}, получен {role}"
    
    print("✅ Определение ролей работает корректно!")


def test_app_creation():
    """Тестируем создание приложения."""
    print("\n🔍 Тестирование создания приложения...")
    
    app = create_app("development")
    
    # Проверяем конфигурацию
    assert app.config['ADMIN_TEMPLATE_DIR'] == 'frontend/admin-pages'
    assert app.config['USER_TEMPLATE_DIR'] == 'frontend/user-pages'
    assert 'PROJECT_ROOT' in app.config
    
    print("✅ Приложение создается корректно!")
    return app


def test_template_paths():
    """Тестируем пути к шаблонам."""
    print("\n🔍 Тестирование путей к шаблонам...")
    
    app = create_app("development")
    project_root = app.config['PROJECT_ROOT']
    
    # Проверяем существование папок
    admin_path = os.path.join(project_root, 'frontend', 'admin-pages')
    user_path = os.path.join(project_root, 'frontend', 'user-pages')
    
    print(f"  Корневая папка проекта: {project_root}")
    print(f"  Папка админских шаблонов: {admin_path}")
    print(f"  Папка пользовательских шаблонов: {user_path}")
    
    assert os.path.exists(admin_path), f"Папка админских шаблонов не найдена: {admin_path}"
    assert os.path.exists(user_path), f"Папка пользовательских шаблонов не найдена: {user_path}"
    
    # Проверяем наличие основных страниц
    main_pages = ['main-pg', 'all-courses-pg', 'questions-pg']
    for page in main_pages:
        admin_page_path = os.path.join(admin_path, page)
        user_page_path = os.path.join(user_path, page)
        
        assert os.path.exists(admin_page_path), f"Админская страница не найдена: {admin_page_path}"
        assert os.path.exists(user_page_path), f"Пользовательская страница не найдена: {user_page_path}"
        
        # Проверяем наличие index.html
        admin_index = os.path.join(admin_page_path, 'index.html')
        user_index = os.path.join(user_page_path, 'index.html')
        
        assert os.path.exists(admin_index), f"Админский index.html не найден: {admin_index}"
        assert os.path.exists(user_index), f"Пользовательский index.html не найден: {user_index}"
    
    print("✅ Все пути к шаблонам корректны!")


def test_mock_requests():
    """Тестируем запросы с мок-пользователями."""
    print("\n🔍 Тестирование запросов с разными ролями...")
    
    app = create_app("development")
    
    with app.test_client() as client:
        # Тестируем с мок-админом
        with patch('flask.g') as mock_g:
            mock_g.user_info = {'role': 'admin', 'username': 'admin'}
            
            # Делаем запрос к главной странице
            response = client.get('/main')
            print(f"  Запрос админа к /main: {response.status_code}")
            
            if response.status_code == 200:
                # Проверяем, что используется админский шаблон
                content = response.get_data(as_text=True)
                if 'Образовательный' in content and 'портал ГТНГ' in content:
                    print("  ✅ Админский шаблон используется корректно")
                else:
                    print("  ⚠️  Возможно, используется неправильный шаблон")
        
        # Тестируем с мок-пользователем
        with patch('flask.g') as mock_g:
            mock_g.user_info = {'role': 'user', 'username': 'ivan.petrov'}
            
            # Делаем запрос к главной странице
            response = client.get('/main')
            print(f"  Запрос пользователя к /main: {response.status_code}")
            
            if response.status_code == 200:
                # Проверяем, что используется пользовательский шаблон
                content = response.get_data(as_text=True)
                if 'learnSite' in content:
                    print("  ✅ Пользовательский шаблон используется корректно")
                else:
                    print("  ⚠️  Возможно, используется неправильный шаблон")


def main():
    """Основная функция тестирования."""
    print("🚀 Запуск тестирования системы ролевой маршрутизации\n")
    
    try:
        test_role_detection()
        test_app_creation()
        test_template_paths()
        test_mock_requests()
        
        print("\n🎉 Все тесты прошли успешно!")
        print("\n📋 Инструкции по использованию:")
        print("1. Запустите сервер: python run.py")
        print("2. Откройте браузер и перейдите на http://127.0.0.1:5000")
        print("3. Для тестирования админского интерфейса используйте имя пользователя 'admin'")
        print("4. Для тестирования пользовательского интерфейса используйте любое другое имя")
        print("5. Проверьте /debug/auth для отладки аутентификации")
        
    except Exception as e:
        print(f"\n❌ Ошибка при тестировании: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
