"""Wake-word greeting (TTS only — no command execution)."""

from __future__ import annotations

from typing import TYPE_CHECKING

import threading
import time

from config import (
    JARVIS_USER_NAME,
    WAKE_GREETING_ASYNC,
    WAKE_GREETING_ENABLED,
    WAKE_GREETING_MAX_DELAY_SECONDS,
    WAKE_GREETING_TEXT,
)
from core.logger import setup_logger

if TYPE_CHECKING:
    from core.app import JarvisApp

logger = setup_logger("jarvis.voice.wake_greeting")

def format_wake_greeting() -> str:
    """Build greeting text from config template."""
    name = (JARVIS_USER_NAME or "Yoav").strip()
    template = WAKE_GREETING_TEXT or "Hey {name}"
    try:
        return template.format(name=name)
    except (KeyError, ValueError):
        return f"Hey {name}"


def play_wake_greeting(app: "JarvisApp") -> bool:
    """
    Speak personalized wake greeting when enabled and TTS is on.
    Returns True if greeting was spoken.
    """
    if not WAKE_GREETING_ENABLED:
        return False
    if not app.speak_enabled:
        return False
    text = format_wake_greeting()
    if not text.strip():
        return False
    try:
        from voice.tts import TTSError

        app.tts.speak(text)
        logger.info("Wake greeting spoken")
        return True
    except Exception as exc:
        from voice.tts import TTSError

        if isinstance(exc, TTSError):
            logger.warning("Wake greeting TTS failed: %s", exc)
        else:
            logger.warning("Wake greeting failed: %s", exc)
        return False


def play_wake_greeting_async(app: "JarvisApp") -> bool:
    """
    Start greeting without blocking recording.
    When async is disabled, blocks up to WAKE_GREETING_MAX_DELAY_SECONDS then continues.
    """
    if not WAKE_GREETING_ENABLED or not app.speak_enabled:
        return False
    if WAKE_GREETING_ASYNC:
        threading.Thread(
            target=play_wake_greeting,
            args=(app,),
            name="jarvis-wake-greeting",
            daemon=True,
        ).start()
        return True
    deadline = time.monotonic() + WAKE_GREETING_MAX_DELAY_SECONDS
    thread = threading.Thread(
        target=play_wake_greeting,
        args=(app,),
        name="jarvis-wake-greeting",
        daemon=True,
    )
    thread.start()
    thread.join(timeout=max(0.0, deadline - time.monotonic()))
    return True


def strip_wake_phrase_from_transcript(text: str) -> str:
    """Remove wake-word echo from STT so it is not routed as a command."""
    from voice.wake_phrases import wake_strip_phrases

    cleaned = (text or "").strip()
    if not cleaned:
        return ""
    lower = cleaned.lower()
    changed = True
    while changed:
        changed = False
        for phrase in wake_strip_phrases():
            if lower == phrase:
                return ""
            if lower.startswith(phrase):
                rest = cleaned[len(phrase) :].lstrip(" ,.-!?:;")
                if rest != cleaned:
                    cleaned = rest
                    lower = cleaned.lower()
                    changed = True
                    break
            suffix = " " + phrase
            if lower.endswith(suffix):
                cleaned = cleaned[: -len(suffix)].strip(" ,.-!?:;")
                lower = cleaned.lower()
                changed = True
                break
    return cleaned.strip()
