"""Multi-language detection for STT (Phase 42)."""

from __future__ import annotations

import re

from config import STT_AUTO_LANGUAGE_DETECT, STT_LANGUAGE
from voice.stt_config import STT_LANGUAGES_ALLOWED

_HEBREW_RE = re.compile(r"[\u0590-\u05FF]")


def detect_language_from_text(text: str) -> str | None:
    if not text or not STT_AUTO_LANGUAGE_DETECT:
        return None
    if _HEBREW_RE.search(text):
        return "he"
    if re.search(r"[a-zA-Z]", text):
        return "en"
    return None


def resolve_transcription_language(
    *,
    forced: str | None = None,
    detected: str | None = None,
    hint_text: str = "",
) -> str:
    """Pick language code for backends."""
    if detected and detected in STT_LANGUAGES_ALLOWED:
        return detected
    text_lang = detect_language_from_text(hint_text)
    if text_lang:
        return text_lang
    lang = (forced or STT_LANGUAGE or "en").strip().lower()
    if lang not in STT_LANGUAGES_ALLOWED:
        return "en"
    return lang
