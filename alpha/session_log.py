"""Alpha session logging (Phase 68)."""

from __future__ import annotations

import json
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import config
from core.types import ActionStatus, CommandRequest, CommandResult

_SESSION_ID: str | None = None
_SESSION_DIR: Path | None = None


def alpha_sessions_dir() -> Path:
    path = getattr(config, "ALPHA_SESSIONS_DIR", config.DATA_DIR / "alpha_sessions")
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_session_id() -> str:
    global _SESSION_ID
    if _SESSION_ID is None:
        _SESSION_ID = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S") + "_" + uuid.uuid4().hex[:8]
    return _SESSION_ID


def _session_file() -> Path:
    global _SESSION_DIR
    if _SESSION_DIR is None:
        _SESSION_DIR = alpha_sessions_dir() / get_session_id()
        _SESSION_DIR.mkdir(parents=True, exist_ok=True)
    return _SESSION_DIR / "session.jsonl"


def _infer_provider(summary: str, data: dict[str, Any] | None) -> str:
    if data:
        if data.get("alpha_blocked"):
            return "blocked"
        if data.get("read_only"):
            return "readonly"
        prov = data.get("provider") or data.get("execution_mode")
        if prov:
            return str(prov)
    low = (summary or "").lower()
    if "mock mode" in low or "simulated" in low:
        return "mock"
    if "degraded" in low or "approval required" in low:
        return "degraded"
    if "real " in low or "real_" in low:
        return "real"
    return "unknown"


def _user_visible(summary: str, status: ActionStatus) -> bool:
    if status != ActionStatus.SUCCESS:
        return True
    low = (summary or "").lower()
    if "blocked" in low or "failed" in low or "error" in low:
        return True
    if len(summary or "") > 20:
        return True
    return False


def log_alpha_command(
    request: CommandRequest,
    result: CommandResult,
    *,
    latency_ms: int,
    log_meta: dict | None = None,
) -> None:
    if not getattr(config, "ALPHA_MODE", False):
        return
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "session_id": get_session_id(),
        "command": (request.raw_text or "")[:500],
        "intent": result.intent.value,
        "success": result.status == ActionStatus.SUCCESS,
        "status": result.status.value,
        "latency_ms": latency_ms,
        "provider": _infer_provider(result.summary or "", result.data),
        "user_visible": _user_visible(result.summary or "", result.status),
        "error": (result.error or "")[:300] or None,
        "input_mode": (log_meta or {}).get("input_mode", "text"),
        "summary_excerpt": (result.summary or "")[:200],
    }
    try:
        with _session_file().open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except OSError:
        pass


def log_alpha_safety_block(*, command: str, intent: str, reason: str) -> None:
    if not getattr(config, "ALPHA_MODE", False):
        return
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "session_id": get_session_id(),
        "command": command[:500],
        "intent": intent,
        "success": False,
        "status": "blocked",
        "latency_ms": 0,
        "provider": "blocked",
        "user_visible": True,
        "error": reason,
        "safety_block": True,
    }
    try:
        with _session_file().open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except OSError:
        pass


def iter_session_entries() -> list[dict[str, Any]]:
    root = alpha_sessions_dir()
    entries: list[dict[str, Any]] = []
    for path in sorted(root.glob("*/session.jsonl")):
        try:
            for line in path.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    entries.append(json.loads(line))
        except (OSError, json.JSONDecodeError):
            continue
    return entries
