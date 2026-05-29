"""Phase 72 — tool-use audit log (data/tool_use_audit.jsonl).

Every executed tool run AND every blocked/forbidden attempt is recorded with
per-step verification/status. Append-only with size-bounded rotation (reuses
core.rotating_jsonl). No secrets/credentials are written (the flow is read-only).
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from core.logger import setup_logger
from core.rotating_jsonl import RotatingJSONLWriter
from tooluse.contracts import TaskRun

logger = setup_logger("jarvis.tooluse.audit")

_writer: RotatingJSONLWriter | None = None


def _get_writer() -> RotatingJSONLWriter:
    global _writer
    if _writer is None:
        from config import DATA_DIR

        _writer = RotatingJSONLWriter(
            Path(DATA_DIR) / "tool_use_audit.jsonl",
            max_bytes=5_000_000,
            backup_count=5,
        )
    return _writer


def _write(record: dict[str, Any]) -> None:
    record.setdefault("ts", time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
    try:
        _get_writer().write_line(json.dumps(record, ensure_ascii=True))
    except Exception as exc:  # auditing must never break the command
        logger.warning("tool_use audit write failed: %s", exc)


def record_blocked(goal: str, reason: str, *, intent: str = "run_tool_task") -> None:
    _write({
        "event": "blocked",
        "intent": intent,
        "goal": (goal or "")[:300],
        "reason": (reason or "")[:300],
    })


def record_tool_run(
    *,
    goal: str,
    intent: str,
    confirmation_id: str,
    approved: bool,
    run: TaskRun,
    plan_hash: str = "",
    duration_ms: int = 0,
) -> None:
    steps = []
    for r in run.steps:
        steps.append({
            "kind": r.step.kind.value,
            "risk": r.step.risk.value,
            "status": r.status.value,
            "verification_ok": (r.verification.ok if r.verification else None),
            "verification_reason": (r.verification.reason if r.verification else ""),
            "recovery_attempts": r.recovery_attempts,
            "url": (r.observation.url if r.observation else ""),
            "screenshot_path": (r.observation.screenshot_path if r.observation else ""),
        })
    _write({
        "event": "run",
        "intent": intent,
        "goal": (goal or "")[:300],
        "confirmation_id": confirmation_id,
        "approved": bool(approved),
        "plan_hash": plan_hash,
        "final_status": run.status.value,
        "summary_excerpt": (run.summary or "")[:300],
        "duration_ms": duration_ms,
        "steps": steps,
    })


def reset_for_tests() -> None:
    global _writer
    _writer = None
