"""Wake phrase display + post-STT strip helpers (config-driven, no execution)."""

from __future__ import annotations

# openWakeWord pre-trained id -> primary spoken phrase the model was trained on
OWW_MODEL_TRAINED_PHRASE: dict[str, str] = {
    "hey_jarvis": "Hey Jarvis",
    "hey_mycroft": "Hey Mycroft",
    "hey_rhasspy": "Hey Rhasspy",
    "alexa": "Alexa",
}

_EXTRA_STRIP_PHRASES: tuple[str, ...] = (
    "hi jarvis",
    "ok jarvis",
)


def parse_wake_display_phrases(raw: str | None = None) -> tuple[str, ...]:
    """Parse WAKE_WORD_DISPLAY_PHRASES (comma-separated) into display strings."""
    if raw is None:
        from config import WAKE_WORD_DISPLAY_PHRASES

        raw = WAKE_WORD_DISPLAY_PHRASES
    parts = [p.strip() for p in (raw or "").split(",") if p.strip()]
    if not parts:
        return ("Jarvis", "Hey Jarvis")
    return tuple(parts)


def wake_strip_phrases() -> tuple[str, ...]:
    """Lower-case phrases removed from post-wake STT (longest match first)."""
    lowered = [p.lower() for p in parse_wake_display_phrases()]
    for extra in _EXTRA_STRIP_PHRASES:
        if extra not in lowered:
            lowered.append(extra)
    return tuple(sorted(set(lowered), key=len, reverse=True))


def wake_listen_prompt() -> str:
    """Startup/console hint for supported wake phrases."""
    phrases = parse_wake_display_phrases()
    if len(phrases) == 1:
        return f"Say '{phrases[0]}' to activate listening."
    if len(phrases) == 2:
        return f"Say '{phrases[0]}' or '{phrases[1]}' to activate listening."
    quoted = ", ".join(f"'{p}'" for p in phrases[:-1])
    return f"Say {quoted} or '{phrases[-1]}' to activate listening."


def trained_phrase_for_model(oww_model_name: str) -> str:
    """Primary phrase the openWakeWord model was trained to detect."""
    key = (oww_model_name or "").strip().lower()
    return OWW_MODEL_TRAINED_PHRASE.get(key, oww_model_name.replace("_", " ").title())
