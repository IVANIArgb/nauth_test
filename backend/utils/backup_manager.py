from __future__ import annotations

import os
import json
import time
import shutil
import zipfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


def _utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _safe_slug(s: str) -> str:
    out = []
    for ch in (s or ""):
        if ch.isalnum() or ch in ("-", "_", "."):
            out.append(ch)
        elif ch in (" ", ":", "/","\\"):
            out.append("_")
    v = "".join(out).strip("._-")
    return v or "backup"


@dataclass
class BackupPaths:
    backup_dir: Path
    backup_file: Path
    meta_file: Path


def get_backup_dir() -> Path:
    # По умолчанию — /app/backups (в контейнере) или <repo>/backups (в dev).
    raw = (os.environ.get("BACKUP_DIR") or "").strip()
    if raw:
        return Path(os.path.abspath(os.path.expanduser(raw)))
    # repo root: <repo>/backend/utils/backup_manager.py -> <repo>
    repo_root = Path(__file__).resolve().parents[2]
    return repo_root / "backups"


def ensure_backup_dir() -> Path:
    d = get_backup_dir()
    d.mkdir(parents=True, exist_ok=True)
    return d


def _db_file_path() -> Optional[Path]:
    # Пытаемся найти sqlite-файл из DATABASE_URL, если он sqlite:///...
    url = (os.environ.get("DATABASE_URL") or "").strip()
    if url.startswith("sqlite:///"):
        p = url[len("sqlite:///") :]
        return Path(p)
    return None


def _iter_files(root: Path):
    # Снимаем снапшот каталога: только файлы, без симлинков.
    if not root.exists():
        return
    for p in root.rglob("*"):
        try:
            if p.is_file() and not p.is_symlink():
                yield p
        except Exception:
            continue


def _zip_add_dir(zf: zipfile.ZipFile, root: Path, arc_prefix: str):
    root = root.resolve()
    for f in _iter_files(root):
        try:
            rel = f.relative_to(root).as_posix()
        except Exception:
            rel = f.name
        arc = f"{arc_prefix}/{rel}"
        zf.write(f, arcname=arc)


def _zip_add_file(zf: zipfile.ZipFile, file_path: Path, arcname: str):
    if file_path.exists() and file_path.is_file():
        zf.write(file_path, arcname=arcname)


def _prune_old_backups(backup_dir: Path, retention_days: int) -> None:
    if retention_days <= 0:
        return
    now = time.time()
    cutoff = now - (retention_days * 86400)
    for p in backup_dir.glob("ls_backup_*.zip"):
        try:
            if p.stat().st_mtime < cutoff:
                p.unlink(missing_ok=True)
                meta = p.with_suffix(".meta.json")
                meta.unlink(missing_ok=True)
        except Exception:
            continue


def create_backup(
    *,
    content_root: Path,
    reason: str,
    include_db: bool = True,
    retention_days: int = 14,
) -> BackupPaths:
    """Создать zip-бэкап контента (+ опционально sqlite БД)."""
    backup_dir = ensure_backup_dir()
    stamp = _utc_stamp()
    name = f"ls_backup_{stamp}_{_safe_slug(reason)}"
    backup_file = backup_dir / f"{name}.zip"
    meta_file = backup_dir / f"{name}.meta.json"

    db_file = _db_file_path() if include_db else None

    meta = {
        "created_at_utc": stamp,
        "reason": reason,
        "content_root": str(content_root),
        "include_db": bool(include_db),
        "db_file": str(db_file) if db_file else None,
    }

    # Создаём архив
    with zipfile.ZipFile(backup_file, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        zf.writestr("META.json", json.dumps(meta, ensure_ascii=False, indent=2))
        # Контент
        _zip_add_dir(zf, content_root, "content")
        # БД
        if db_file:
            # В контейнере БД может быть внутри /app/...; копируем как есть.
            _zip_add_file(zf, db_file, "db/users_courses.db")

    # Запишем метаданные отдельным файлом для быстрого списка
    try:
        meta_file.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass

    # Ретеншен
    try:
        _prune_old_backups(backup_dir, int(retention_days))
    except Exception:
        pass

    return BackupPaths(backup_dir=backup_dir, backup_file=backup_file, meta_file=meta_file)


def list_backups() -> list[dict]:
    d = ensure_backup_dir()
    out: list[dict] = []
    for meta in sorted(d.glob("ls_backup_*.meta.json"), reverse=True):
        try:
            raw = meta.read_text(encoding="utf-8")
            data = json.loads(raw) if raw else {}
            zip_path = meta.with_suffix(".zip")
            size = zip_path.stat().st_size if zip_path.exists() else None
            out.append({
                "name": zip_path.name if zip_path.exists() else meta.name.replace(".meta.json", ".zip"),
                "zip_path": str(zip_path),
                "meta_path": str(meta),
                "size_bytes": size,
                "meta": data if isinstance(data, dict) else {},
            })
        except Exception:
            continue
    return out


def get_backup_file(name: str) -> Optional[Path]:
    if not name:
        return None
    d = ensure_backup_dir()
    p = (d / name).resolve()
    try:
        # Защита от ../
        if d.resolve() not in p.parents:
            return None
    except Exception:
        return None
    if p.exists() and p.is_file() and p.suffix.lower() == ".zip":
        return p
    return None


def delete_backup(name: str) -> bool:
    p = get_backup_file(name)
    if not p:
        return False
    try:
        p.unlink(missing_ok=True)
        p.with_suffix(".meta.json").unlink(missing_ok=True)
        return True
    except Exception:
        return False

