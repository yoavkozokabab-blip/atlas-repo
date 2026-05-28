"""Alpha safety layer — blocks destructive actions unless developer mode (Phase 68)."""

from __future__ import annotations

import re

from alpha.mode import is_alpha_mode, is_developer_mode
from core.results import result_blocked
from core.types import ActionStatus, CommandRequest, CommandResult, Intent

# Intents blocked in alpha unless DEVELOPER_MODE=true
_ALPHA_BLOCKED_INTENTS: frozenset[str] = frozenset(
    {
        "enable_kill_switch",
        "disable_kill_switch",
        "run_live_daily_loop",
        "run_live_weekly_loop",
        "stop_trading_loop",
        "shutdown_jarvis",
        "enable_autostart",
        "disable_autostart",
        "apply_task_patch",
        "apply_approved_patch",
        "delete_file",
        "forget_memory",
        "forget_preference",
        "delete_alias",
        "clear_clipboard",
        "send_message",
        "send_email",
        "repair_memory_store",
        "reset_jarvis_runtime",
        "investigate_trading_mismatch",
        "compare_live_vs_backtest",
        "inspect_latest_live_report",
        "run_safe_diagnostics",
        "generate_findings_report",
        "build_investigation_graph",
        "hunt_algorithm_bugs",
        "explain_latest_error",
        "find_failing_tests",
        "review_latest_patch",
    }
)

_RISKY_TEXT = re.compile(
    r"\b(delete|remove|purchase|buy now|send email|send message|password|credential|"
    r"pay\b|checkout|wire transfer|system settings|registry edit)\b",
    re.I,
)


def check_alpha_safety(request: CommandRequest) -> CommandResult | None:
    """
    Return a blocked CommandResult when alpha safety applies.
    Returns None when the command may proceed.
    """
    if not is_alpha_mode() or is_developer_mode():
        return None

    intent_val = request.intent.value
    if intent_val in _ALPHA_BLOCKED_INTENTS:
        return _block(request, f"intent_blocked_in_alpha:{intent_val}")

    raw = request.raw_text or ""
    if _RISKY_TEXT.search(raw):
        return _block(request, "risky_phrase_in_alpha")

    params = request.params or {}
    target = str(params.get("target") or params.get("text") or params.get("label") or "")
    if target and _RISKY_TEXT.search(target):
        return _block(request, "risky_target_in_alpha")

    return None


def _block(request: CommandRequest, reason: str) -> CommandResult:
    from alpha.session_log import log_alpha_safety_block

    log_alpha_safety_block(
        command=request.raw_text,
        intent=request.intent.value,
        reason=reason,
    )
    return result_blocked(
        request.intent,
        "Alpha safety: this action is blocked for friend & family testing. "
        "Ask the developer if you need it enabled.",
        error=reason,
    )


def intent_requires_alpha_approval(intent_value: str) -> bool:
    """Extra confirmation for borderline intents in alpha."""
    if not is_alpha_mode() or is_developer_mode():
        return False
    borderline = {
        "open_website",
        "open_app",
        "open_browser",
        "search_web_for",
        "type_this",
        "summarize_my_inbox",
        "show_urgent_emails",
    }
    return intent_value in borderline
