"""Decode PowerShell stdout (UTF-8 / UTF-16 / Windows code pages)."""
from __future__ import annotations


def decode_powershell_stdout(raw: bytes) -> str:
    if not raw:
        return ""
    for enc in ("utf-8-sig", "utf-8", "utf-16-le", "utf-16", "cp1251", "cp866"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")
