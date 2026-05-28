"""Phase 33 — persistent approval inbox (safe metadata only)."""

from __future__ import annotations

import json
import re
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from config import CONFIRMATION_TIMEOUT_SECONDS, DATA_DIR
from core.types import CommandRequest

APPROVAL_INBOX_PATH = DATA_DIR / "approval_inbox.json"

_SECRET_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"(?i)(api[_-]?key|secret|password|token|credential)\s*[=:]\s*\S+"),
    re.compile(r"(?i)Bearer\s+[A-Za-z0-9._-]+"),
    re.compile(r"sk-[A-Za-z0-9]{20,}"),
]

_BLOCKED_KEYS: frozenset[str] = frozenset(
    {
        "unified_diff",
        "patch",
        "diff",
        "file_content",
        "contents",
        "body",
        "env",
        "password",
        "token",
        "secret",
        "api_key",
    }
)

_BLOCKED_MARKERS: tuple[str, ...] = (
    "+++ b/",
    "--- a/",
    "BEGIN PATCH",
    "OPENAI_API",
    "TELEGRAM_BOT",
)

_HIGH_RISK_INTENTS: frozenset[str] = frozenset(
    {
        "shutdown_jarvis",
        "run_live_daily_loop",
        "run_live_weekly_loop",
        "stop_trading_loop",
        "enable_kill_switch",
        "disable_kill_switch",
        "apply_task_patch",
    }
)

_MEDIUM_RISK_INTENTS: frozenset[str] = frozenset(
    {
        "enable_autostart",
        "disable_autostart",
        "focus_window",
        "copy_text_to_clipboard",
        "clear_clipboard",
        "minimize_window",
        "maximize_window",
        "confirm_ui_click",
    }
)


@dataclass
class ApprovalItem:
    item_id: str
    confirmation_id: str
    timestamp: str
    intent: str
    action_name: str
    summary: str
    risk_level: str
    required_confirmation: bool = True
    status: str = "pending"  # pending | approved | rejected | expired | completed
    safe_payload: dict[str, Any] = field(default_factory=dict)


def redact_text(text: str | None, *, max_len: int = 400) -> str:
    if not text:
        return ""
    out = str(text)
    for pat in _SECRET_PATTERNS:
        out = pat.sub("***REDACTED***", out)
    lower = out.lower()
    for marker in _BLOCKED_MARKERS:
        if marker.lower() in lower:
            return "[omitted — sensitive or file/patch content]"
    if len(out) > max_len:
        out = out[:max_len] + "…"
    return out


def risk_level_for_intent(intent: str) -> str:
    name = (intent or "").strip().lower()
    if name in _HIGH_RISK_INTENTS:
        return "high"
    if name in _MEDIUM_RISK_INTENTS:
        return "medium"
    return "low"


def _sanitize_params(params: dict[str, Any] | None) -> dict[str, str]:
    if not params:
        return {}
    safe: dict[str, str] = {}
    for key, value in (params or {}).items():
        k = str(key).lower()
        if k in _BLOCKED_KEYS or any(b in k for b in ("secret", "password", "token", "patch", "diff")):
            safe[str(key)] = "[omitted]"
            continue
        if isinstance(value, (dict, list)):
            safe[str(key)] = "[omitted]"
            continue
        safe[str(key)] = redact_text(str(value), max_len=120)
    return safe


def build_safe_payload(request: CommandRequest) -> dict[str, Any]:
    return {
        "raw_text": redact_text(request.raw_text, max_len=200),
        "params": _sanitize_params(request.params),
    }


def _load_items() -> list[ApprovalItem]:
    path = Path(APPROVAL_INBOX_PATH)
    if not path.is_file():
        return []
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        items = raw.get("items", []) if isinstance(raw, dict) else []
        return [ApprovalItem(**row) for row in items if isinstance(row, dict)]
    except (json.JSONDecodeError, TypeError, ValueError):
        return []


def _save_items(items: list[ApprovalItem]) -> bool:
    try:
        path = Path(APPROVAL_INBOX_PATH)
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"items": [asdict(i) for i in items]}
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return True
    except OSError:
        return False


def _expire_stale_items(items: list[ApprovalItem]) -> list[ApprovalItem]:
    now = datetime.now(timezone.utc)
    updated: list[ApprovalItem] = []
    for item in items:
        if item.status != "pending":
            updated.append(item)
            continue
        try:
            created = datetime.fromisoformat(item.timestamp.replace("Z", "+00:00"))
            if created.tzinfo is None:
                created = created.replace(tzinfo=timezone.utc)
            age = (now - created).total_seconds()
            if age > CONFIRMATION_TIMEOUT_SECONDS:
                item.status = "expired"
        except (ValueError, TypeError):
            item.status = "expired"
        updated.append(item)
    return updated


def record_pending_approval(
    confirmation_id: str,
    request: CommandRequest,
    *,
    summary: str = "",
) -> str | None:
    """Add or update pending inbox row. Never raises."""
    try:
        items = _expire_stale_items(_load_items())
        intent_val = request.intent.value
        safe_summary = redact_text(
            summary or f"{intent_val} requires confirmation before execution."
        )
        item_id = str(uuid.uuid4())[:8]
        item = ApprovalItem(
            item_id=item_id,
            confirmation_id=confirmation_id,
            timestamp=datetime.now(timezone.utc).isoformat(),
            intent=intent_val,
            action_name=intent_val,
            summary=safe_summary,
            risk_level=risk_level_for_intent(intent_val),
            required_confirmation=True,
            status="pending",
            safe_payload=build_safe_payload(request),
        )
        # Replace existing pending row for same confirmation_id
        items = [i for i in items if i.confirmation_id != confirmation_id]
        items.append(item)
        if not _save_items(items):
            return None
        return item_id
    except Exception:
        return None


def list_approval_items(*, status: str | None = None) -> list[ApprovalItem]:
    items = _expire_stale_items(_load_items())
    _save_items(items)
    if status:
        return [i for i in items if i.status == status]
    return items


def get_pending_item(item_id: str | None = None) -> ApprovalItem | None:
    pending = list_approval_items(status="pending")
    if not pending:
        return None
    if item_id:
        for item in pending:
            if item.item_id == item_id or item.confirmation_id == item_id:
                return item
        return None
    return pending[-1]


def update_item_status(
    item_id: str,
    status: str,
) -> bool:
    try:
        items = _load_items()
        found = False
        for item in items:
            if item.item_id == item_id or item.confirmation_id == item_id:
                item.status = status
                found = True
                break
        if found:
            return _save_items(items)
        return False
    except Exception:
        return False


def update_by_confirmation_id(confirmation_id: str, status: str) -> bool:
    try:
        items = _load_items()
        found = False
        for item in items:
            if item.confirmation_id == confirmation_id:
                item.status = status
                found = True
        if found:
            return _save_items(items)
        return False
    except Exception:
        return False


def clear_inbox() -> tuple[int, int]:
    """Remove rejected, expired, and completed items. Keep pending (and approved awaiting sync)."""
    try:
        items = _load_items()
        kept = [i for i in items if i.status in ("pending", "approved")]
        removed = len(items) - len(kept)
        _save_items(kept)
        return removed, len(kept)
    except Exception:
        return 0, 0


def format_approvals_report(items: list[ApprovalItem] | None = None) -> str:
    rows = items if items is not None else list_approval_items()
    pending = [i for i in rows if i.status == "pending"]
    lines = [
        "Approval inbox",
        f"Source: {APPROVAL_INBOX_PATH}",
        f"Pending: {len(pending)} | Total listed: {len(rows)}",
        "",
    ]
    if not rows:
        lines.append("No approval items.")
        return "\n".join(lines)
    for i, item in enumerate(rows, start=1):
        lines.append(
            f"{i}. [{item.status}] id={item.item_id} confirm={item.confirmation_id} "
            f"risk={item.risk_level} intent={item.intent}"
        )
        lines.append(f"   summary: {item.summary}")
        lines.append(f"   required_confirmation: {item.required_confirmation}")
    lines.append("")
    lines.append("Approve: 'approve pending action' or 'approve pending action <id>'")
    lines.append("Reject: 'reject pending action' or 'reject pending action <id>'")
    lines.append("Clear: 'clear approvals' (removes rejected/expired/completed only)")
    return "\n".join(lines)


def reset_inbox_store() -> None:
    path = Path(APPROVAL_INBOX_PATH)
    if path.is_file():
        try:
            path.unlink()
        except OSError:
            try:
                path.write_text("[]", encoding="utf-8")
            except OSError:
                pass
