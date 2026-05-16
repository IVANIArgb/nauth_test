# -*- coding: utf-8 -*-
import subprocess
import sys
import os

os.chdir(os.path.dirname(os.path.abspath(__file__)))

commit = "f42643860008c592f6ec687bd477c08be4b3f9b9"
print("Восстановление до f426438...")

try:
    r = subprocess.run(['git', 'checkout', commit], 
                      capture_output=True, text=True, timeout=30)
    if r.returncode != 0:
        r = subprocess.run(['git', 'checkout', 'f426438'],
                          capture_output=True, text=True, timeout=30)
    
    output = r.stdout + r.stderr
    print(output)
    
    if r.returncode == 0:
        log_r = subprocess.run(['git', 'log', '-1', '--oneline'],
                              capture_output=True, text=True, timeout=10)
        print(f"\n✓ Успешно! Текущий коммит: {log_r.stdout.strip()}")
    else:
        print(f"\n✗ Ошибка (код {r.returncode})")
        sys.exit(1)
except Exception as e:
    print(f"Ошибка: {e}")
    sys.exit(1)


