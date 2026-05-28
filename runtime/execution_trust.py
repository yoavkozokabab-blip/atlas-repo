"""Execution trust layer with dry-run, audit and rollback hooks."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from config import DATA_DIR

_AUDIT_PATH = DATA_DIR / "execution_audit.jsonl"
_ROLLBACK_PATH = DATA_DIR / "execution_rollbacks.json"


@dataclass(frozen=True)
class TrustDecision:
    allowed: bool
    confidence: float
    reason: str


def evaluate_execution(
    *,
    op_name: str,
    dry_run: bool,
    reversible: bool,
    approval_scope: str,
) -> TrustDecision:
    confidence = 0.9
    reason = "approved"
    if not approval_scope:
        confidence -= 0.25
        reason = "missing_approval_scope"
    if not reversible:
        confidence -= 0.2
    if dry_run:
        confidence = min(1.0, confidence + 0.05)
    return TrustDecision(allowed=confidence >= 0.45, confidence=max(0.0, confidence), reason=reason)


def execute_with_trust(
    *,
    op_name: str,
    run: Callable[[], str],
    rollback: Callable[[], str] | None = None,
    dry_run: bool = False,
    approval_scope: str = "",
) -> str:
    decision = evaluate_execution(
        op_name=op_name,
        dry_run=dry_run,
        reversible=rollback is not None,
        approval_scope=approval_scope,
    )
    if not decision.allowed:
        _audit(op_name, "blocked", f"{decision.reason} conf={decision.confidence:.2f}", dry_run=dry_run)
        return f"Execution blocked: {decision.reason} (confidence={decision.confidence:.2f})"
    if dry_run:
        _audit(op_name, "dry_run", f"allowed conf={decision.confidence:.2f}", dry_run=True)
        return f"Dry-run OK for {op_name} (confidence={decision.confidence:.2f})"
    try:
        out = run()
        _audit(op_name, "executed", out[:240], dry_run=False)
        if rollback is not None:
            _register_rollback(op_name, rollback)
        return out
    except Exception as exc:
        _audit(op_name, "failed", str(exc)[:240], dry_run=False)
        return f"{op_name} failed: {exc}"


def rollback_last(op_name: str) -> str:
    payload = _load_rollbacks()
    stack = payload.get(op_name, [])
    if not stack:
        return f"No rollback available for {op_name}."
    marker = stack.pop()
    payload[op_name] = stack
    _save_rollbacks(payload)
    _audit(op_name, "rollback", marker, dry_run=False)
    return f"Rollback marker consumed for {op_name}: {marker}"


def _audit(op_name: str, status: str, detail: str, *, dry_run: bool) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    row = {
        "ts": int(time.time() * 1000),
        "op": op_name,
        "status": status,
        "dry_run": dry_run,
        "detail": detail,
    }
    with _AUDIT_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=True) + "\n")


def _register_rollback(op_name: str, rollback: Callable[[], str]) -> None:
    payload = _load_rollbacks()
    marker = f"rollback_registered:{int(time.time()*1000)}"
    payload.setdefault(op_name, []).append(marker)
    _save_rollbacks(payload)
    del rollback


def _load_rollbacks() -> dict:
    if not _ROLLBACK_PATH.is_file():
        return {}
    try:
        return json.loads(_ROLLBACK_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_rollbacks(payload: dict) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    _ROLLBACK_PATH.write_text(json.dumps(payload, indent=2, ensure_ascii=True), encoding="utf-8")

