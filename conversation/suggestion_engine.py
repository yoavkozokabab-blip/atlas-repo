"""Phase 37b — deterministic next-step suggestions (supervised, no auto-execute)."""

from __future__ import annotations

from config import (
    CONVERSATION_ENABLED,
    CONVERSATION_MAX_SUGGESTIONS,
    WORKSPACE_SUGGESTIONS_ENABLED,
)
from core.types import ActionStatus, CommandRequest, CommandResult

# Phrases users can speak — must map to allowlisted implemented intents via classifier.
_SUGGESTIONS: dict[str, list[str]] = {
    "show_dashboard_health": [
        "show last errors",
        "run diagnostics",
        "open trading dashboard",
    ],
    "open_trading_dashboard": [
        "show dashboard health",
        "show last errors",
    ],
    "show_last_errors": [
        "summarize latest log",
        "search trading logs",
        "suggest next steps",
    ],
    "summarize_latest_log": [
        "show last errors",
        "open latest log",
    ],
    "run_diagnostics": [
        "diagnose dashboard",
        "diagnose trading loop",
        "show jarvis status",
    ],
    "diagnose_dashboard": [
        "show dashboard health",
        "show last errors",
    ],
    "diagnose_trading_loop": [
        "show last errors",
        "show rejection reasons",
    ],
    "describe_screen": [
        "read screen",
        "analyze active window",
    ],
    "read_screen_text": [
        "describe screen",
        "find on screen settings",
    ],
    "analyze_active_window": [
        "describe screen",
        "read screen",
    ],
    "show_jarvis_status": [
        "show command audit",
        "show capabilities",
    ],
    "show_capabilities": [
        "list skills",
        "show jarvis status",
    ],
    "list_memory": [
        "show memory",
        "search project knowledge",
    ],
    "show_memory": [
        "remember this",
        "index project",
    ],
    "start_task": [
        "show task status",
        "show task plan",
    ],
    "show_task_status": [
        "show task report",
        "show task findings",
    ],
    "run_workflow": [
        "list workflows",
        "explain workflow",
    ],
    "unknown": [
        "show capabilities",
        "help",
    ],
    "clarify": [
        "show capabilities",
        "show jarvis status",
    ],
    "what_am_i_doing": [
        "run diagnostics",
        "summarize session",
        "show recent commands",
    ],
    "assistant_explain": [
        "suggest next steps",
        "make a plan",
        "run diagnostics",
    ],
    "assistant_plan": [
        "what am i doing",
        "start task",
        "show task status",
    ],
    "what_were_we_doing": [
        "summarize session",
        "what am i doing",
        "show task status",
    ],
}

_DEFAULT = [
    "show jarvis status",
    "show capabilities",
    "run diagnostics",
]

_MODE_SUGGESTIONS: dict[str, list[str]] = {
    "coding": [
        "run diagnostics",
        "show task queue",
        "review latest patch",
        "what am i doing",
    ],
    "trading": [
        "show dashboard health",
        "show last errors",
        "open trading dashboard",
        "diagnose trading loop",
    ],
    "studying": [
        "start study mode",
        "summarize my notes",
        "what should i study next",
        "quiz me",
    ],
    "focus": [
        "what am i doing",
        "toggle quiet mode",
        "summarize session",
    ],
    "idle": [
        "what am i doing",
        "show jarvis status",
        "run diagnostics",
    ],
}


def build_workspace_suggestions(mode: str) -> list[str]:
    """Mode-keyed speakable phrases (implemented intents only)."""
    if not WORKSPACE_SUGGESTIONS_ENABLED:
        return []
    key = (mode or "idle").strip().lower()
    return list(_MODE_SUGGESTIONS.get(key, _MODE_SUGGESTIONS["idle"]))


def _safe_phrases(phrases: list[str]) -> list[str]:
    """Drop confirm-required-looking commands unless already confirm flow."""
    out: list[str] = []
    for phrase in phrases:
        p = phrase.strip().lower()
        if not p:
            continue
        out.append(phrase.strip())
    return out


def build_suggestions(
    request: CommandRequest,
    result: CommandResult,
) -> list[str]:
    """Deterministic suggestions from last intent + status."""
    if not CONVERSATION_ENABLED:
        return list(result.next_suggestions or [])[:CONVERSATION_MAX_SUGGESTIONS]

    intent_key = result.intent.value
    if result.status == ActionStatus.CONFIRMATION_REQUIRED:
        return list(result.next_suggestions or [])[:CONVERSATION_MAX_SUGGESTIONS] or [
            "Reply yes / confirm / כן to proceed.",
            "Reply no / cancel / לא to abort.",
        ]

    if result.intent.value == "unknown" and "cancelled" in (result.summary or "").lower():
        return []

    if result.status in (ActionStatus.BLOCKED, ActionStatus.NOT_IMPLEMENTED):
        return ["show capabilities", "show jarvis status"]

    base = list(_SUGGESTIONS.get(intent_key, _DEFAULT))
    try:
        from operating.workspace_context import get_cached_mode

        mode_extra = build_workspace_suggestions(get_cached_mode())
    except Exception:
        mode_extra = []
    merged: list[str] = []
    seen: set[str] = set()

    for item in list(result.next_suggestions or []) + mode_extra + base:
        key = item.strip().lower()
        if not key or key in seen:
            continue
        if key == request.raw_text.strip().lower():
            continue
        seen.add(key)
        merged.append(item.strip())

    safe: list[str] = []
    for phrase in merged:
        low = phrase.lower()
        if any(
            bad in low
            for bad in (
                "shutdown",
                "run live",
                "apply task patch",
                "confirm ui click",
                "enable autostart",
                "focus window",
                "clipboard",
            )
        ):
            continue
        safe.append(phrase)
        if len(safe) >= CONVERSATION_MAX_SUGGESTIONS:
            break

    return safe[:CONVERSATION_MAX_SUGGESTIONS]


def build_continuation_prompt(
    request: CommandRequest,
    result: CommandResult,
    suggestions: list[str],
) -> str:
    """One optional assistant-style line (question only — user must command next)."""
    from config import CONVERSATION_CONTINUATION_ENABLED

    if not CONVERSATION_CONTINUATION_ENABLED:
        return ""
    if result.status in (
        ActionStatus.CONFIRMATION_REQUIRED,
        ActionStatus.BLOCKED,
        ActionStatus.FAILED,
        ActionStatus.NOT_IMPLEMENTED,
    ):
        return ""
    if "action cancelled" in (result.summary or "").lower():
        return ""
    if not suggestions:
        return ""
    first = suggestions[0]
    return f"Would you also like me to {first}?"
