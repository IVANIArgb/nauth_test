"""UTF-8 для AD/PowerShell и починка типичных кракозябр (UTF-8 прочитан как cp1251/cp866)."""
from __future__ import annotations

import re
from typing import Any

_CYRILLIC_RE = re.compile(r"[\u0400-\u04FF]")
_MOJIBAKE_MARKERS = re.compile(r"[ÐÑÃÂ][\u0080-\u00FF]|[\u00C0-\u00FF]{2,}")


def cyrillic_score(text: str) -> int:
    return len(_CYRILLIC_RE.findall(text or ""))


def decode_subprocess_stdout(raw: bytes) -> str:
    """Декодирование stdout PowerShell: UTF-8 / UTF-16 BOM / cp866 / cp1251."""
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


def repair_mojibake(text: str) -> str:
    """
    Восстановить кириллицу, если UTF-8 из AD/PowerShell ошибочно прочитали как cp1251/cp866/latin-1.
  Пример: «Ð˜Ð²Ð°Ð½Ð¾Ð²» -> «Иванов».
    """
    if not text or not isinstance(text, str):
        return ""
    s = text.strip()
    if not s:
        return ""
    if cyrillic_score(s) > 0 and not _MOJIBAKE_MARKERS.search(s):
        return s

    best = s
    best_score = cyrillic_score(s)
    for enc in ("latin-1", "cp1251", "cp866", "iso-8859-1"):
        try:
            candidate = s.encode(enc).decode("utf-8")
        except (UnicodeEncodeError, UnicodeDecodeError):
            continue
        sc = cyrillic_score(candidate)
        if sc > best_score:
            best, best_score = candidate, sc
    return best


def normalize_ad_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (list, tuple)):
        parts = [normalize_ad_text(v) for v in value if v is not None]
        return " ".join(p for p in parts if p).strip()
    s = str(value).strip()
    if not s:
        return ""
    return repair_mojibake(s)


POWERSHELL_UTF8_PREFIX = (
    "[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false); "
    "$OutputEncoding = [Console]::OutputEncoding; "
)
