#!/usr/bin/env python3
"""Скрипт для восстановления проекта до стабильной версии f426438"""
import subprocess
import sys
import os

def run_git_command(cmd, check=True):
    """Выполнить git команду и вернуть результат"""
    try:
        result = subprocess.run(['git'] + cmd, capture_output=True, text=True, check=check)
        return result.stdout.strip(), result.stderr.strip(), result.returncode
    except FileNotFoundError:
        print("Ошибка: git не найден в системе!")
        sys.exit(1)

def main():
    print("=" * 60)
    print("Восстановление проекта до стабильной версии f426438")
    print("=" * 60)
    
    # Проверка статуса репозитория
    print("\n1. Проверка статуса репозитория...")
    stdout, stderr, code = run_git_command(['status', '--porcelain'], check=False)
    
    if stdout:
        print(f"⚠ ВНИМАНИЕ: Обнаружены незакоммиченные изменения:")
        print(stdout)
        print("\nЭти изменения будут потеряны при переключении!")
        response = input("\nПродолжить? (yes/no): ").strip().lower()
        if response not in ['yes', 'y', 'да', 'д']:
            print("Отменено пользователем.")
            sys.exit(0)
    else:
        print("✓ Рабочая директория чиста")
    
    # Проверка существования коммита
    print("\n2. Поиск коммита f426438...")
    commit_hash = "f42643860008c592f6ec687bd477c08be4b3f9b9"
    
    stdout, stderr, code = run_git_command(['rev-parse', '--verify', commit_hash], check=False)
    if code != 0:
        # Попробуем короткий хеш
        stdout, stderr, code = run_git_command(['rev-parse', '--verify', 'f426438'], check=False)
        if code != 0:
            print(f"❌ Коммит {commit_hash} не найден!")
            print("\nПоиск похожих коммитов...")
            stdout, stderr, code = run_git_command(['log', '--oneline', '--all'], check=False)
            if stdout:
                for line in stdout.split('\n'):
                    if 'f426' in line.lower():
                        print(f"  {line}")
            sys.exit(1)
        else:
            commit_hash = stdout
    
    print(f"✓ Коммит найден: {commit_hash}")
    
    # Получение информации о коммите
    print("\n3. Информация о коммите:")
    stdout, stderr, code = run_git_command(['log', '-1', '--format=%h - %s - %an, %ar', commit_hash], check=False)
    if stdout:
        print(f"  {stdout}")
    
    # Переключение на коммит
    print(f"\n4. Переключение на коммит {commit_hash[:8]}...")
    stdout, stderr, code = run_git_command(['checkout', commit_hash])
    
    if code == 0:
        print(f"✓ Успешно переключено на стабильную версию f426438!")
        print(f"\nТекущий коммит:")
        stdout, _, _ = run_git_command(['log', '-1', '--oneline'], check=False)
        if stdout:
            print(f"  {stdout}")
        print("\n⚠ ВНИМАНИЕ: Вы находитесь в состоянии 'detached HEAD'.")
        print("Если хотите сохранить эту версию, создайте новую ветку:")
        print(f"  git checkout -b stable-f426438")
    else:
        print(f"❌ Ошибка при переключении:")
        print(stderr)
        sys.exit(1)

if __name__ == '__main__':
    main()


