#!/usr/bin/env python3
"""
Скрипт для проверки работоспособности проекта после рефакторинга.
Проверяет импорты, подключение к БД, аутентификацию и основные страницы.
"""

import sys
import os

# Добавляем корневую директорию в путь
project_root = os.path.abspath(os.path.dirname(__file__))
sys.path.insert(0, project_root)

def test_imports():
    """Проверка всех импортов"""
    print("=" * 60)
    print("ТЕСТ 1: Проверка импортов")
    print("=" * 60)
    
    errors = []
    
    # Тест импортов backend
    try:
        from backend import create_app
        print("✅ backend.create_app - OK")
    except Exception as e:
        errors.append(f"backend.create_app: {e}")
        print(f"❌ backend.create_app - FAILED: {e}")
    
    try:
        from backend.config import get_config
        print("✅ backend.config - OK")
    except Exception as e:
        errors.append(f"backend.config: {e}")
        print(f"❌ backend.config - FAILED: {e}")
    
    # Тест импортов database
    try:
        from database.models import db_manager, User, Course
        print("✅ database.models - OK")
    except Exception as e:
        errors.append(f"database.models: {e}")
        print(f"❌ database.models - FAILED: {e}")
    
    # Тест импортов auth
    try:
        from auth.auth_script import get_username_from_kerberos
        print("✅ auth.auth_script - OK")
    except Exception as e:
        errors.append(f"auth.auth_script: {e}")
        print(f"❌ auth.auth_script - FAILED: {e}")
    
    try:
        from auth.ad_user_info import get_user_info_by_login
        print("✅ auth.ad_user_info - OK")
    except Exception as e:
        errors.append(f"auth.ad_user_info: {e}")
        print(f"❌ auth.ad_user_info - FAILED: {e}")
    
    if errors:
        print(f"\n⚠️  Найдено ошибок импорта: {len(errors)}")
        return False
    else:
        print("\n✅ Все импорты успешны!")
        return True


def test_database():
    """Проверка подключения к БД"""
    print("\n" + "=" * 60)
    print("ТЕСТ 2: Проверка базы данных")
    print("=" * 60)
    
    try:
        from database.models import db_manager
        
        # Проверяем подключение
        session = db_manager.get_session()
        try:
            # Простой запрос
            from sqlalchemy import text
            result = session.execute(text("SELECT 1"))
            print("✅ Подключение к БД - OK")
            
            # Проверяем наличие таблиц
            from sqlalchemy import inspect
            inspector = inspect(db_manager.engine)
            tables = inspector.get_table_names()
            print(f"✅ Найдено таблиц: {len(tables)}")
            for table in tables:
                print(f"   - {table}")
            
            return True
        finally:
            session.close()
            
    except Exception as e:
        print(f"❌ Ошибка подключения к БД: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_flask_app():
    """Проверка создания Flask приложения"""
    print("\n" + "=" * 60)
    print("ТЕСТ 3: Проверка Flask приложения")
    print("=" * 60)
    
    try:
        from backend import create_app
        
        app = create_app("testing")
        print("✅ Flask приложение создано - OK")
        
        # Проверяем конфигурацию
        print(f"   - DEBUG: {app.config.get('DEBUG')}")
        print(f"   - TESTING: {app.config.get('TESTING')}")
        print(f"   - PROJECT_ROOT: {app.config.get('PROJECT_ROOT')}")
        
        # Проверяем наличие основных компонентов
        with app.app_context():
            # Проверяем наличие blueprints
            blueprints = list(app.blueprints.keys())
            print(f"✅ Зарегистрировано blueprints: {len(blueprints)}")
            for bp in blueprints:
                print(f"   - {bp}")
        
        return True
        
    except Exception as e:
        print(f"❌ Ошибка создания Flask приложения: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_auth():
    """Проверка модулей аутентификации"""
    print("\n" + "=" * 60)
    print("ТЕСТ 4: Проверка аутентификации")
    print("=" * 60)
    
    try:
        from auth.auth_script import get_username_from_kerberos
        from auth.ad_user_info import get_user_info_by_login
        
        # Тест получения username (может вернуть None, это нормально)
        username = get_username_from_kerberos()
        print(f"✅ get_username_from_kerberos - OK (username: {username})")
        
        # Тест AD (может не работать без AD, это нормально)
        try:
            if username:
                ad_info = get_user_info_by_login(username)
                print(f"✅ get_user_info_by_login - OK (для {username})")
            else:
                print("⚠️  get_user_info_by_login - пропущен (нет username)")
        except Exception as e:
            print(f"⚠️  get_user_info_by_login - предупреждение: {e}")
        
        return True
        
    except Exception as e:
        print(f"❌ Ошибка в модулях аутентификации: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_routes():
    """Проверка регистрации маршрутов"""
    print("\n" + "=" * 60)
    print("ТЕСТ 5: Проверка маршрутов")
    print("=" * 60)
    
    try:
        from backend import create_app
        
        app = create_app("testing")
        
        with app.app_context():
            # Получаем список всех маршрутов
            routes = []
            for rule in app.url_map.iter_rules():
                routes.append({
                    'endpoint': rule.endpoint,
                    'methods': list(rule.methods),
                    'path': str(rule)
                })
            
            print(f"✅ Найдено маршрутов: {len(routes)}")
            
            # Показываем основные маршруты
            important_routes = ['/', '/healthz', '/api/users', '/api/courses']
            for route_info in routes:
                if any(important in route_info['path'] for important in important_routes):
                    print(f"   - {route_info['path']} [{', '.join(route_info['methods'])}]")
            
            return True
            
    except Exception as e:
        print(f"❌ Ошибка проверки маршрутов: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Главная функция тестирования"""
    print("\n" + "=" * 60)
    print("ТЕСТИРОВАНИЕ ПРОЕКТА ПОСЛЕ РЕФАКТОРИНГА")
    print("=" * 60)
    
    results = []
    
    # Запускаем все тесты
    results.append(("Импорты", test_imports()))
    results.append(("База данных", test_database()))
    results.append(("Flask приложение", test_flask_app()))
    results.append(("Аутентификация", test_auth()))
    results.append(("Маршруты", test_routes()))
    
    # Итоговый отчет
    print("\n" + "=" * 60)
    print("ИТОГОВЫЙ ОТЧЕТ")
    print("=" * 60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = "✅ PASSED" if result else "❌ FAILED"
        print(f"{name}: {status}")
    
    print(f"\nВсего тестов: {total}")
    print(f"Пройдено: {passed}")
    print(f"Провалено: {total - passed}")
    
    if passed == total:
        print("\n🎉 ВСЕ ТЕСТЫ ПРОЙДЕНЫ УСПЕШНО!")
        return 0
    else:
        print(f"\n⚠️  НЕКОТОРЫЕ ТЕСТЫ ПРОВАЛЕНЫ ({total - passed})")
        return 1


if __name__ == "__main__":
    sys.exit(main())

