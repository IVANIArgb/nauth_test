"""
Текущий пользователь Windows (SAM, в т.ч. кириллица). Без AD/keytab.
"""
from __future__ import annotations

import os
import subprocess
import sys
from typing import Optional


def _decode_powershell_stdout(raw: bytes) -> str:
    if not raw:
        return ""
    raw = raw.replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    if raw.startswith(b"\xff\xfe"):
        return raw[2:].decode("utf-16-le", errors="replace").strip()
    if raw.startswith(b"\xfe\xff"):
        return raw[2:].decode("utf-16-be", errors="replace").strip()
    for enc in ("utf-8-sig", "utf-8", "cp866", "cp1251"):
        try:
            s = raw.decode(enc).strip()
            if s:
                return s
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace").strip()


def current_logon_name() -> str:
    """DOMAIN\\user или только user."""
    if sys.platform != "win32":
        return (os.environ.get("USER") or os.environ.get("USERNAME") or "").strip()

    cmd = (
        "[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false); "
        "[System.Security.Principal.WindowsIdentity]::GetCurrent().Name"
    )
    try:
        r = subprocess.run(
            ["powershell", "-NoProfile", "-Command", cmd],
            capture_output=True,
            timeout=15,
        )
        if r.returncode == 0 and r.stdout:
            s = _decode_powershell_stdout(r.stdout)
            if s:
                return s
    except (OSError, subprocess.SubprocessError):
        pass

    dom = (os.environ.get("USERDOMAIN") or "").strip()
    user = (os.environ.get("USERNAME") or "").strip()
    if dom and user:
        return f"{dom}\\{user}"
    return user


def sam_account_name(full: Optional[str] = None) -> Optional[str]:
    """Короткий логин (ManakovIV, Пользователь, …)."""
    name = (full if full is not None else current_logon_name()).strip()
    if not name:
        return None
    if "\\" in name:
        name = name.rsplit("\\", 1)[-1].strip()
    return name or None
