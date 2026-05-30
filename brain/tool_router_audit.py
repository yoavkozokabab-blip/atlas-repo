"""Phase 79 — LLM tool router shadow audit (data/llm_router_audit.jsonl)."""

from __future__ import annotations

import hashlib
import json
import re
import time
from pathlib import Path
from typing import Any

from core.logger import setup_logger
from core.rotating_jsonl import RotatingJSONLWriter

logger = setup_logger("jarvis.brain.tool_router_audit")

_writer: RotatingJSONLWriter | None = None
_SECRET_KEY_RE = re.compile(
    r"(token|api_key|apikey|password|secret|auth|bearer|cookie|credential|"
    r"private_key|access_key|refresh_token|session)",
    re.IGNORECASE,
)
_SAFE_FALLBACK_REASONS = frozenset({
    "circuit_breaker_open",
    "hallucinated_tool",
    "llm_timeout",
    "malformed_llm_output",
    "no_candidates",
    "not_in_candidates",
    "safety_class_blocked",
    "shadow_disabled",
    "unknown_kind",
    "user_forbidden_phrase",
})
_TYPED_FALLBACK_PREFIXES = frozenset({
    "invalid_args",
    "llm_error",
    "registry_unavailable",
})
_EXCEPTION_TYPE_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*(?:Error|Exception)$")


def _audit_path() -> Path:
    from config import DATA_DIR

    return Path(DATA_DIR) / "llm_router_audit.jsonl"


def _get_writer() -> RotatingJSONLWriter:
    global _writer
    if _writer is None:
        _writer = RotatingJSONLWriter(_audit_path(), max_bytes=5_000_000, backup_count=5)
    return _writer


def _sha256_fingerprint(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()[:12]


def _user_fingerprint(text: str) -> str:
    raw = (text or "").encode("utf-8", errors="replace")
    return f"len={len(raw)} sha256={_sha256_fingerprint(raw)}"


def _is_secret_key(key: str) -> bool:
    return bool(_SECRET_KEY_RE.search(str(key)))


def _redact_value(key: str, value: Any) -> Any:
    if _is_secret_key(key):
        return "[REDACTED]"
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value
    if isinstance(value, str):
        raw = value.encode("utf-8", errors="replace")
        return {
            "type": "str",
            "length": len(raw),
            "sha256": _sha256_fingerprint(raw),
        }
    if isinstance(value, list):
        return [_redact_value(f"[{i}]", item) for i, item in enumerate(value)]
    if isinstance(value, dict):
        return {str(k): _redact_value(str(k), v) for k, v in value.items()}
    return {"type": type(value).__name__}


def _redact_args(args: dict[str, Any] | None) -> dict[str, Any]:
    return {str(k): _redact_value(str(k), v) for k, v in (args or {}).items()}


def _sanitize_fallback_reason(reason: str) -> str:
    raw = str(reason or "")
    if not raw:
        return ""
    if raw in _SAFE_FALLBACK_REASONS:
        return raw
    prefix, separator, detail = raw.partition(":")
    if (
        separator
        and prefix in _TYPED_FALLBACK_PREFIXES
        and _EXCEPTION_TYPE_RE.fullmatch(detail)
    ):
        return f"{prefix}:{detail}"
    return f"redacted:sha256={_sha256_fingerprint(raw.encode('utf-8', errors='replace'))}"


def _write(record: dict[str, Any]) -> None:
    record.setdefault("ts", time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
    try:
        _get_writer().write_line(json.dumps(record, ensure_ascii=True))
    except Exception as exc:
        logger.warning("llm_router audit write failed: %s", type(exc).__name__)


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
    parse_result: str = "",
    circuit_breaker_open: bool = False,
) -> None:
    _write({
        "event": "shadow_route",
        "mode": "shadow",
        "executed": False,
        "user_fingerprint": _user_fingerprint(user_text),
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
        "fallback_reason": _sanitize_fallback_reason(fallback_reason),
        "parse_result": (parse_result or "")[:40],
        "circuit_breaker_open": circuit_breaker_open,
    })


def reset_for_tests() -> None:
    global _writer
    _writer = None
