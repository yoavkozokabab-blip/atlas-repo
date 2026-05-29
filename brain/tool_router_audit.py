"""Phase 79 — LLM tool router shadow audit (data/llm_router_audit.jsonl)."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from core.logger import setup_logger
from core.rotating_jsonl import RotatingJSONLWriter

logger = setup_logger("jarvis.brain.tool_router_audit")

_writer: RotatingJSONLWriter | None = None


def _audit_path() -> Path:
    from config import DATA_DIR

    return Path(DATA_DIR) / "llm_router_audit.jsonl"


def _get_writer() -> RotatingJSONLWriter:
    global _writer
    if _writer is None:
        _writer = RotatingJSONLWriter(_audit_path(), max_bytes=5_000_000, backup_count=5)
    return _writer


def _redact_args(args: dict[str, Any] | None) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in (args or {}).items():
        if isinstance(value, (str, int, float, bool)):
            out[key] = value[:120] if isinstance(value, str) else value
        else:
            out[key] = f"<{type(value).__name__}>"
    return out


def _write(record: dict[str, Any]) -> None:
    record.setdefault("ts", time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
    try:
        _get_writer().write_line(json.dumps(record, ensure_ascii=True))
    except Exception as exc:
        logger.warning("llm_router audit write failed: %s", exc)


def record_shadow_decision(
    *,
    user_text: str,
    classifier_intent: str,
    classifier_confidence: float,
    classifier_source: str,
    outcome: str,
    candidate_tools: list[str],
    selected_tool: str = "",
    selected_args: dict[str, Any] | None = None,
    mapped_intent: str = "",
    shadow_would_execute: bool = False,
    latency_ms: float = 0.0,
    fallback_reason: str = "",
    llm_raw_excerpt: str = "",
    circuit_breaker_open: bool = False,
) -> None:
    _write({
        "event": "shadow_route",
        "mode": "shadow",
        "executed": False,
        "user_text": (user_text or "")[:240],
        "classifier_intent": classifier_intent,
        "classifier_confidence": round(classifier_confidence, 4),
        "classifier_source": classifier_source,
        "outcome": outcome,
        "candidate_tools": candidate_tools[:16],
        "selected_tool": selected_tool,
        "selected_args": _redact_args(selected_args),
        "mapped_intent": mapped_intent,
        "shadow_would_execute": shadow_would_execute,
        "latency_ms": round(latency_ms, 2),
        "fallback_reason": (fallback_reason or "")[:200],
        "llm_raw_excerpt": (llm_raw_excerpt or "")[:300],
        "circuit_breaker_open": circuit_breaker_open,
    })


def reset_for_tests() -> None:
    global _writer
    _writer = None
