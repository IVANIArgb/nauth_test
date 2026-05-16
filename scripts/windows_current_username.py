#!/usr/bin/env python3
"""CLI: логин текущего пользователя Windows (латиница/кириллица)."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from auth.windows_identity import current_logon_name, sam_account_name


def _configure_stdout_unicode() -> None:
    if sys.platform != "win32":
        return
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


def main() -> None:
    _configure_stdout_unicode()
    p = argparse.ArgumentParser(description="Логин текущего пользователя Windows")
    p.add_argument("--full", action="store_true", help="DOMAIN\\username")
    args = p.parse_args()
    full = current_logon_name()
    if not full:
        sys.exit(1)
    print(full if args.full else (sam_account_name(full) or ""))


if __name__ == "__main__":
    main()
