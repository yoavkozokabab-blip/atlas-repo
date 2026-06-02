"""Autonomous Agent Stack v1 — audit + per-run report artifacts.

Writes:
  - data/autonomous_agent_audit.jsonl                (append-only, rotating)
  - reports/autonomous_runs/<task_id>.json           (full structured record)
  - reports/autonomous_runs/<task_id>.md             (human report)

Contains goal, plan, approved hash, timings, every step + URL, verification,
recovery attempts, final status, report, confidence, and safety blocks.
No secrets/cookies/personal data are written (URLs + abstract status only).
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from core.logger import setup_logger
from core.rotating_jsonl import RotatingJSONLWriter

logger = setup_logger("jarvis.autonomy.audit")

_writer: RotatingJSONLWriter | None = None


def _jsonl_path() -> Path:
    from config import DATA_DIR

    return Path(DATA_DIR) / "autonomous_agent_audit.jsonl"


def _runs_dir() -> Path:
    from config import PROJECT_ROOT

    return Path(PROJECT_ROOT) / "reports" / "autonomous_runs"


def _get_writer() -> RotatingJSONLWriter:
    global _writer
    if _writer is None:
        _writer = RotatingJSONLWriter(_jsonl_path(), max_bytes=5_000_000, backup_count=5)
    return _writer


def record_blocked(goal: str, reason: str, *, intent: str, detected: list[str] | None = None) -> None:
    try:
        _get_writer().write_line(json.dumps({
            "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "event": "blocked",
            "intent": intent,
            "goal": (goal or "")[:300],
            "reason": (reason or "")[:300],
            "forbidden_detected": list(detected or []),
        }, ensure_ascii=True))
    except Exception as exc:
        logger.warning("autonomy audit (blocked) failed: %s", exc)


def record_run(task, plan, *, safety_blocks: list[str] | None = None) -> dict[str, Any]:
    """Write jsonl + per-run md/json artifacts. Returns paths written."""
    record = task.to_dict()
    record["event"] = "run"
    record["plan_hash"] = plan.plan_hash if plan is not None else ""
    record["plan"] = plan.canonical() if plan is not None else {}
    record["safety_blocks"] = list(safety_blocks or [])
    record["urls_opened"] = [r.url for r in task.step_results if r.url]
    record["ts"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    paths: dict[str, Any] = {}
    try:
        _get_writer().write_line(json.dumps(record, ensure_ascii=True))
    except Exception as exc:
        logger.warning("autonomy audit (run jsonl) failed: %s", exc)

    try:
        d = _runs_dir()
        d.mkdir(parents=True, exist_ok=True)
        jpath = d / f"{task.task_id}.json"
        jpath.write_text(json.dumps(record, ensure_ascii=True, indent=2), encoding="utf-8")
        paths["json"] = str(jpath)

        mpath = d / f"{task.task_id}.md"
        header = [
            f"<!-- task_id={task.task_id} status={task.status.value} "
            f"confidence={task.confidence:.2f} plan_hash={record['plan_hash']} -->",
            "",
        ]
        mpath.write_text("\n".join(header) + (task.final_report or "(no report)"), encoding="utf-8")
        paths["md"] = str(mpath)
    except Exception as exc:
        logger.warning("autonomy audit (run artifacts) failed: %s", exc)
    return paths


def reset_for_tests() -> None:
    global _writer
    _writer = None
