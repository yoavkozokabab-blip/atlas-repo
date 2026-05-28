"""Phase 37e — fast ack after classification (display/TTS only, no execution)."""

from __future__ import annotations

from core.logger import setup_logger
from config import (
    CONFIRMATION_REQUIRED_INTENTS,
    CONVERSATION_FAST_ACK_ENABLED,
)
from core.types import CommandRequest, Intent
from vision.screen_redaction import redact_screen_text

_CONFIRM_ACK = "I need confirmation before doing that."

_SCREEN_INTENTS = frozenset(
    {
        Intent.DESCRIBE_SCREEN.value,
        Intent.READ_SCREEN_TEXT.value,
        Intent.ANALYZE_ACTIVE_WINDOW.value,
        Intent.FIND_ON_SCREEN.value,
        Intent.DETECT_SCREEN_ERRORS.value,
        Intent.TAKE_SCREENSHOT.value,
        Intent.ANALYZE_CURRENT_SCREEN.value,
    }
)

logger = setup_logger("jarvis.conversation.latency")

_OPEN_PREFIX_INTENTS = frozenset(
    {
        Intent.OPEN_CURSOR.value,
        Intent.OPEN_CHROME.value,
        Intent.OPEN_TERMINAL.value,
        Intent.OPEN_PROJECT_FOLDER.value,
        Intent.OPEN_LATEST_LOG.value,
        Intent.OPEN_TRADING_DASHBOARD.value,
        Intent.OPEN_TRADING_DASHBOARD_URL.value,
        Intent.OPEN_APP.value,
        Intent.OPEN_WEBSITE.value,
    }
)


def build_fast_ack(request: CommandRequest) -> str:
    """
    Deterministic ack from classified intent only (no OCR, no action output).
    Must run after classify, before registry execute.
    """
    if not CONVERSATION_FAST_ACK_ENABLED:
        return ""

    intent_val = request.intent.value
    if (
        intent_val in CONFIRMATION_REQUIRED_INTENTS
        and not request.confirmed
    ):
        return _CONFIRM_ACK

    if intent_val in _SCREEN_INTENTS:
        return "Looking at your screen..."

    if intent_val in _OPEN_PREFIX_INTENTS or intent_val.startswith("open_"):
        return "Opening..."

    return "Got it — checking..."


def redact_fast_ack(text: str) -> str:
    if not text:
        return ""
    return redact_screen_text(text, max_len=120)


def deliver_fast_ack(
    ack: str,
    *,
    input_mode: str = "text",
    speak: bool = False,
    intent: str = "",
) -> None:
    """Overlay + optional voice TTS for ack (never executes commands)."""
    safe = redact_fast_ack(ack)
    if not safe:
        return

    try:
        from ui.overlay_app import notify_overlay_fast_ack

        notify_overlay_fast_ack(safe, intent=intent)
    except Exception:
        pass

    if not speak:
        return
    if input_mode not in ("voice", "wakeword"):
        return

    try:
        from core.runtime_state import get_runtime_state

        if not get_runtime_state().speak_enabled:
            return
        from voice.tts import TTSService

        TTSService(enabled=True).speak(safe)
    except Exception as exc:
        logger.warning("Fast-ack TTS failed: %s", exc)
