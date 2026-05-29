"""Phase 78 — Tool Registry audit log (data/tool_registry_audit.jsonl).

Records every tool invocation and every blocked/rejected attempt with status +
verification. No secrets: args are shallow-redacted to keys + short scalar values.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from core.logger import setup_logger
from core.rotating_jsonl import RotatingJSONLWriter
from tools.spec import ToolResult

logger = setup_logger("jarvis.tools.audit")

_writer: RotatingJSONLWriter | None = None


def _get_writer() -> RotatingJSONLWriter:
    global _writer
    if _writer is None:
        from config import DATA_DIR

        _writer = RotatingJSONLWriter(
            Path(DATA_DIR) / "tool_registry_audit.jsonl", max_bytes=5_000_000, backup_count=5
        )
    return _writer


def _redact_args(args: dict[str, Any] | None) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for k, v in (args or {}).items():
        if isinstance(v, (str, int, float, bool)):
            out[k] = (v[:120] if isinstance(v, str) else v)
        else:
            out[k] = f"<{type(v).__name__}>"
    return out


def _write(record: dict[str, Any]) -> None:
    record.setdefault("ts", time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
    try:
        _get_writer().write_line(json.dumps(record, ensure_ascii=True))
    except Exception as exc:  # auditing must never break a tool call
        logger.warning("tool_registry audit write failed: %s", exc)


def record_invocation(tool_name: str, args: dict[str, Any] | None, result: ToolResult,
                      *, latency_ms: int = 0) -> None:
    _write({
        "event": "invoke",
        "tool": tool_name,
        "args": _redact_args(args),
        "status": result.status.value,
        "verified": result.verified,
        "verification_reason": (result.verification_reason or "")[:160],
        "reason": (result.reason or "")[:120],
        "agent_id": result.agent_id,
        "latency_ms": latency_ms,
    })


def record_rejected(tool_name: str, reason: str) -> None:
    _write({"event": "rejected", "tool": tool_name, "reason": (reason or "")[:200]})


def reset_for_tests() -> None:
    global _writer
    _writer = None
