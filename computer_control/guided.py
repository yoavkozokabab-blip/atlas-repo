"""Phase 27 — guided UI control (suggest + confirm, no free coordinates)."""

from __future__ import annotations

from dataclasses import dataclass

from config import GUIDED_UI_ENABLED

GUIDED_UI_DISABLED_MESSAGE = (
    "Guided UI control is disabled. Set GUIDED_UI_ENABLED=true in .env."
)

# Approved semantic targets only — mapped to window titles / roles, not x,y
APPROVED_UI_TARGETS: dict[str, str] = {
    "dashboard_refresh": "Trading dashboard — Refresh button",
    "dashboard_health": "Trading dashboard — Health indicator",
    "chatgpt_input": "ChatGPT — message input (do not submit without confirm)",
    "tradingview_chart": "TradingView — chart pane (read-only)",
    "jarvis_tray": "JARVIS tray icon",
}


@dataclass
class UiActionSuggestion:
    target_id: str
    label: str
    requires_confirmation: bool = True
    confirmed: bool = False


_pending: UiActionSuggestion | None = None


def suggest_ui_target(target_id: str) -> tuple[UiActionSuggestion | None, str]:
    global _pending
    if not GUIDED_UI_ENABLED:
        return None, GUIDED_UI_DISABLED_MESSAGE
    tid = (target_id or "").strip().lower().replace(" ", "_")
    if tid not in APPROVED_UI_TARGETS:
        allowed = ", ".join(sorted(APPROVED_UI_TARGETS))
        return None, f"Unknown UI target. Allowed: {allowed}"
    sug = UiActionSuggestion(target_id=tid, label=APPROVED_UI_TARGETS[tid])
    _pending = sug
    return (
        sug,
        f"Suggested UI action: {sug.label}\n"
        "Say 'confirm ui click' to proceed (simulated — no pixel automation).",
    )


def confirm_pending_ui_action() -> tuple[bool, str]:
    global _pending
    if not GUIDED_UI_ENABLED:
        return False, GUIDED_UI_DISABLED_MESSAGE
    if _pending is None:
        return False, "No pending UI suggestion. Use 'suggest ui click <target>' first."
    _pending.confirmed = True
    label = _pending.label
    _pending = None
    return True, f"Confirmed UI action (logged only, no coordinate automation): {label}"


def reset_guided_state() -> None:
    global _pending
    _pending = None
