#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import subprocess
import sys

commit_hash = "f42643860008c592f6ec687bd477c08be4b3f9b9"
short_hash = "f426438"

print("=" * 60)
print("Переключение на стабильную версию f426438")
print("=" * 60)
print(f"Коммит: {commit_hash[:8]}...\n")

# Проверяем статус
print("Проверка статуса...")
status_result = subprocess.run(['git', 'status', '--porcelain'], 
                              capture_output=True, text=True, timeout=10)
if status_result.stdout.strip():
    print("⚠ Найдены незакоммиченные изменения:")
    print(status_result.stdout)
else:
    print("✓ Рабочая директория чиста\n")

# Пробуем переключиться
print("Переключение на стабильную версию...")
try:
    # Пробуем полный хеш
    result = subprocess.run(['git', 'checkout', commit_hash], 
                          capture_output=True, text=True, timeout=30)
    
    if result.returncode != 0:
        print(f"Попытка с полным хешем не удалась, пробуем короткий...")
        result = subprocess.run(['git', 'checkout', short_hash],
                              capture_output=True, text=True, timeout=30)
    
    if result.returncode == 0:
        print("✓ Успешно переключено!")
        if result.stdout:
            print(result.stdout)
        
        # Показываем текущий коммит
        print("\nТекущий коммит:")
        log_result = subprocess.run(['git', 'log', '-1', '--oneline'],
                                   capture_output=True, text=True, timeout=10)
        if log_result.returncode == 0:
            print(f"  {log_result.stdout.strip()}")
        print("\n⚠ ВНИМАНИЕ: Вы находитесь в состоянии 'detached HEAD'.")
        print("Если хотите работать с этой версией, создайте ветку:")
        print("  git checkout -b stable-f426438")
    else:
        print("❌ Ошибка при переключении:")
        print(result.stderr if result.stderr else result.stdout)
        sys.exit(1)
        
except FileNotFoundError:
    print("❌ Git не найден в системе!")
    sys.exit(1)
except subprocess.TimeoutExpired:
    print("❌ Команда выполняется слишком долго, прервано.")
    sys.exit(1)
except Exception as e:
    print(f"❌ Неожиданная ошибка: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

