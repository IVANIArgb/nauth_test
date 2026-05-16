import json
import os
from pathlib import Path
from typing import Any, Optional


def _read_json(path: Path) -> Optional[dict]:
    try:
        with open(path, "r", encoding="utf-8") as f:
            v = json.load(f)
        return v if isinstance(v, dict) else None
    except Exception:
        return None


def _write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def blocks_file(lesson_dir: Path) -> Path:
    return lesson_dir / "blocks.json"


def read_blocks(lesson_dir: Path) -> list[dict]:
    cfg = _read_json(blocks_file(lesson_dir))
    if not cfg:
        return []
    blocks = cfg.get("blocks")
    if not isinstance(blocks, list):
        return []
    out = []
    for b in blocks:
        if isinstance(b, dict) and isinstance(b.get("id"), int) and isinstance(b.get("block_type"), str):
            out.append(b)
    out.sort(key=lambda x: int(x.get("order") or 0))
    return out


def write_blocks(lesson_dir: Path, blocks: list[dict]) -> None:
    norm: list[dict] = []
    for b in blocks or []:
        if not isinstance(b, dict):
            continue
        if not isinstance(b.get("id"), int) or not isinstance(b.get("block_type"), str):
            continue
        norm.append(b)
    norm.sort(key=lambda x: int(x.get("order") or 0))
    _write_json(blocks_file(lesson_dir), {"blocks": norm})


def next_block_id(blocks: list[dict]) -> int:
    mx = 0
    for b in blocks or []:
        try:
            mx = max(mx, int(b.get("id") or 0))
        except Exception:
            continue
    return mx + 1

