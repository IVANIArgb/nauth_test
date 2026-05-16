# -*- coding: utf-8 -*-
"""Прямое выполнение git checkout для восстановления версии"""
import subprocess
import sys
import os

# Переходим в директорию проекта
project_dir = r'C:\Users\ManakovIV\Desktop\current_prjct'
os.chdir(project_dir)

commit_hash = "f42643860008c592f6ec687bd477c08be4b3f9b9"

print("=" * 60)
print("Восстановление до стабильной версии f426438")
print("=" * 60)
print()

try:
    # Пробуем найти git
    git_paths = [
        'git',
        r'C:\Program Files\Git\bin\git.exe',
        r'C:\Program Files (x86)\Git\bin\git.exe',
    ]
    
    git_cmd = None
    for path in git_paths:
        try:
            result = subprocess.run([path, '--version'], 
                                  capture_output=True, timeout=5)
            if result.returncode == 0:
                git_cmd = path
                break
        except:
            continue
    
    if not git_cmd:
        print("❌ Git не найден в системе!")
        sys.exit(1)
    
    print(f"✓ Git найден: {git_cmd}")
    print(f"Переключение на коммит {commit_hash[:8]}...")
    print()
    
    # Выполняем checkout
    result = subprocess.run([git_cmd, 'checkout', commit_hash],
                          capture_output=True, text=True, timeout=30)
    
    if result.returncode != 0:
        print("Попытка с полным хешем не удалась, пробуем короткий...")
        result = subprocess.run([git_cmd, 'checkout', 'f426438'],
                              capture_output=True, text=True, timeout=30)
    
    print(result.stdout)
    if result.stderr:
        print(result.stderr, file=sys.stderr)
    
    if result.returncode == 0:
        print()
        print("=" * 60)
        print("✓ УСПЕШНО! Проект восстановлен до стабильной версии")
        print("=" * 60)
        print()
        
        # Показываем текущий коммит
        log_result = subprocess.run([git_cmd, 'log', '-1', '--oneline'],
                                   capture_output=True, text=True, timeout=10)
        if log_result.returncode == 0:
            print(f"Текущий коммит: {log_result.stdout.strip()}")
        
        print()
        print("⚠ ВНИМАНИЕ: Вы находитесь в состоянии 'detached HEAD'.")
        print("Для создания ветки выполните:")
        print("  git checkout -b stable-f426438")
    else:
        print("❌ Ошибка при переключении")
        sys.exit(1)
        
except subprocess.TimeoutExpired:
    print("❌ Команда выполняется слишком долго")
    sys.exit(1)
except Exception as e:
    print(f"❌ Ошибка: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)


