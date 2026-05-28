"""STT configuration helpers (language, model)."""

from __future__ import annotations

import os

STT_MODELS_ALLOWED: frozenset[str] = frozenset(
    {
        "tiny",
        "base",
        "small",
        "medium",
        "large-v3",
        "large-v2",
        "large",
        "distil-large-v3",
        "distil-medium.en",
    }
)

STT_LANGUAGES_ALLOWED: frozenset[str] = frozenset({"en", "he"})

HEBREW_MODEL_HINT = "Try STT_MODEL=medium or large-v3 for better Hebrew."
ENGLISH_MODEL_HINT = "Try STT_MODEL=small or medium for better English accuracy."


def resolve_stt_language(explicit: str | None = None) -> str:
    """
    STT language for Whisper.

    Default: English (`en`). Hebrew (`he`) only when explicitly set in STT_LANGUAGE.
    No locale auto-detection.
    """
    raw = (explicit if explicit is not None else os.getenv("STT_LANGUAGE", "")).strip().lower()
    if not raw or raw == "auto":
        return "en"
    if raw in STT_LANGUAGES_ALLOWED:
        return raw
    return "en"


def normalize_stt_model(name: str | None) -> str:
    """Validate model size name; fall back to base if unknown."""
    key = (name or "base").strip().lower()
    if key in STT_MODELS_ALLOWED:
        return key
    return "base"
