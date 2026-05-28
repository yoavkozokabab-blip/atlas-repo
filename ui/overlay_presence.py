"""Phase 38a — overlay presence helpers (display-only, no execution)."""

from __future__ import annotations

from config import OVERLAY_MAX_TEXT_CHARS
from vision.redaction import redact_sensitive_text

OVERLAY_MAX_SUGGESTION_CHIPS = 4
OVERLAY_SUGGESTION_CHIP_MAX_CHARS = 48

SUBTEXT_RECORDING = "Recording audio..."
SUBTEXT_TRANSCRIBING = "Transcribing speech..."
SUBTEXT_EXECUTING = "Executing command..."
SUBTEXT_CONFIRMATION = "Waiting for confirmation..."
def _ready_subtext() -> str:
    try:
        from voice.wake_phrases import parse_wake_display_phrases

        phrases = parse_wake_display_phrases()
        if len(phrases) >= 2:
            return f"Standing by — say {phrases[0]} or {phrases[1]}"
        if phrases:
            return f"Standing by — say {phrases[0]}"
    except Exception:
        pass
    return "Standing by — say Jarvis or Hey Jarvis"


SUBTEXT_READY = _ready_subtext()
CONFIRM_GUIDANCE = "Say yes or no."

DEFAULT_IDLE_SUGGESTIONS: tuple[str, ...] = (
    "show jarvis status",
    "open dashboard",
    "describe screen",
    "run diagnostics",
    "show voice debug",
)


def build_mode_idle_suggestions() -> tuple[str, ...]:
    """Blend mode hints into idle chips without dropping default standby phrases."""
    try:
        from conversation.suggestion_engine import build_workspace_suggestions
        from core.session import SessionState

        mode = (SessionState.load().activity_mode or "").strip().lower()
        if mode in ("coding", "trading", "studying", "focus"):
            merged: list[str] = []
            seen: set[str] = set()
            for phrase in list(build_workspace_suggestions(mode)[:2]) + list(DEFAULT_IDLE_SUGGESTIONS):
                key = phrase.strip().lower()
                if not key or key in seen:
                    continue
                seen.add(key)
                merged.append(phrase.strip())
                if len(merged) >= 4:
                    break
            if merged:
                return tuple(merged)
    except Exception:
        pass
    return DEFAULT_IDLE_SUGGESTIONS

ERROR_SUGGESTIONS: tuple[str, ...] = (
    "show voice debug",
    "show audio status",
    "diagnose voice runtime",
    "reset jarvis runtime",
)

# Redacted intent → HUD subtitle (never raw OCR / secrets).
_INTENT_LABELS: dict[str, str] = {
    "open_trading_dashboard": "Opening dashboard",
    "open_trading_dashboard_url": "Opening dashboard",
    "show_dashboard_health": "Reviewing dashboard health",
    "run_diagnostics": "Running diagnostics",
    "diagnose_dashboard": "Diagnosing dashboard",
    "diagnose_trading_loop": "Reviewing trading diagnostics",
    "show_last_errors": "Reviewing recent errors",
    "summarize_latest_log": "Summarizing log",
    "describe_screen": "Analyzing screen",
    "read_screen_text": "Reading screen text",
    "analyze_active_window": "Analyzing active window",
    "find_on_screen": "Searching on screen",
    "detect_screen_errors": "Scanning for screen errors",
    "take_screenshot": "Capturing screen",
    "analyze_current_screen": "Analyzing screen",
    "open_cursor": "Opening Cursor",
    "open_chrome": "Opening Chrome",
    "open_terminal": "Opening terminal",
    "open_project_folder": "Opening project folder",
    "open_latest_log": "Opening latest log",
    "open_app": "Opening application",
    "open_website": "Opening website",
    "run_workflow": "Running workflow",
    "show_jarvis_status": "Checking JARVIS status",
    "show_voice_debug": "Voice diagnostics",
    "show_audio_status": "Audio playback status",
    "test_voice_output": "Testing voice output",
    "show_capabilities": "Listing capabilities",
    "show_command_audit": "Reviewing command audit",
    "start_task": "Starting supervised task",
    "show_task_status": "Checking task status",
    "show_task_report": "Loading task report",
}


def intent_display_label(intent: str) -> str:
    """Safe HUD subtitle from classified intent name."""
    key = (intent or "").strip().lower()
    if not key:
        return "Processing command"
    if key in _INTENT_LABELS:
        return _INTENT_LABELS[key]
    if key.startswith("open_"):
        return "Opening resource"
    if key.startswith("show_"):
        return "Gathering information"
    if key.startswith("diagnose_"):
        return "Running diagnostics"
    if key.startswith("analyze_"):
        return "Analyzing"
    readable = key.replace("_", " ").strip()
    return readable[:60].title() if readable else "Processing command"


def sanitize_suggestion_chips(phrases: list[str] | tuple[str, ...] | None) -> tuple[str, ...]:
    """Display-only chips: redact, truncate, max 4."""
    if not phrases:
        return ()
    out: list[str] = []
    seen: set[str] = set()
    for raw in phrases:
        text = redact_sensitive_text(str(raw or "").strip())
        if not text:
            continue
        chip = text[:OVERLAY_SUGGESTION_CHIP_MAX_CHARS]
        if len(text) > OVERLAY_SUGGESTION_CHIP_MAX_CHARS:
            chip = chip.rstrip() + "…"
        key = chip.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(chip)
        if len(out) >= OVERLAY_MAX_SUGGESTION_CHIPS:
            break
    return tuple(out)


def truncate_result_for_overlay(summary: str) -> str:
    """Result panel text without continuation clutter when split to chips."""
    if not summary:
        return ""
    safe = redact_sensitive_text(summary)
    if len(safe) > OVERLAY_MAX_TEXT_CHARS:
        return safe[: OVERLAY_MAX_TEXT_CHARS - 3].rstrip() + "..."
    return safe


def format_workflow_hint(
    *,
    status: str,
    workflow_name: str = "",
    step_index: int | None = None,
    step_total: int | None = None,
    step_intent: str = "",
    paused: bool = False,
) -> str:
    """One-line workflow presence (display-only)."""
    name = (workflow_name or "workflow").strip()[:40]
    if paused:
        step = (step_index or 0) + 1
        total = step_total or "?"
        intent = (step_intent or "step").replace("_", " ")[:32]
        return f"Workflow {name}: paused at step {step}/{total} ({intent}) — confirmation required"
    if status == "running" and step_index is not None and step_total:
        step = step_index + 1
        intent = (step_intent or "").replace("_", " ")[:28]
        line = f"Workflow {name}: step {step}/{step_total}"
        if intent:
            line += f" — {intent}"
        return line[:120]
    if status in ("completed", "completed_with_failures"):
        return f"Workflow {name}: finished"
    return f"Workflow {name}: {status}"[:120]
