"""NDJSON debug logs for agent session 2fa264 (debug-2fa264.log in project root)."""
from __future__ import annotations

import json
import os
import time
from typing import Any, Optional

_SESSION = "2fa264"
_LOG_NAME = "debug-2fa264.log"


def _log_path() -> str:
    root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    return os.path.join(root, _LOG_NAME)


def agent_debug_log(
    hypothesis_id: str,
    location: str,
    message: str,
    data: Optional[dict[str, Any]] = None,
    run_id: str = "run1",
) -> None:
    # #region agent log
    if (os.environ.get("FLASK_ENV") or "").strip().lower() == "production":
        return
    if (os.environ.get("AGENT_DEBUG_LOG") or "").strip().lower() not in (
        "true",
        "1",
        "yes",
    ):
        return
    try:
        payload = {
            "sessionId": _SESSION,
            "hypothesisId": hypothesis_id,
            "location": location,
            "message": message,
            "data": data or {},
            "timestamp": int(time.time() * 1000),
            "runId": run_id,
        }
        with open(_log_path(), "a", encoding="utf-8") as f:
            f.write(json.dumps(payload, ensure_ascii=False) + "\n")
    except Exception:
        pass
    # #endregion
