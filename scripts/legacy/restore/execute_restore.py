import subprocess
import sys
import os

os.chdir(r'C:\Users\ManakovIV\Desktop\current_prjct')

commit = "f42643860008c592f6ec687bd477c08be4b3f9b9"
print(f"Checkout to {commit[:8]}...")

try:
    r = subprocess.run(['git', 'checkout', commit], capture_output=True, text=True, timeout=30)
    if r.returncode != 0:
        r = subprocess.run(['git', 'checkout', 'f426438'], capture_output=True, text=True, timeout=30)
    print(r.stdout or r.stderr)
    if r.returncode == 0:
        subprocess.run(['git', 'log', '-1', '--oneline'], timeout=10)
except Exception as e:
    print(f"Error: {e}")


