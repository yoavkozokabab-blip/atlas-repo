"""Context-aware transcript repair using session + workspace hints."""

from __future__ import annotations

from config import STT_TRANSCRIPT_REPAIR_ENABLED
from voice.transcript_cleanup import cleanup_transcript

_MODE_HINTS: dict[str, list[tuple[str, str]]] = {
    "trading": [
        ("open dash", "open dashboard"),
        ("trading view", "tradingview"),
        ("show positions", "show open positions"),
    ],
    "coding": [
        ("open cursor", "open cursor"),
        ("run test", "show failing tests"),
        ("review patch", "review latest patch"),
    ],
    "study": [
        ("quiz me", "quiz me"),
        ("study mode", "start study mode"),
    ],
}


def _recent_intent_hints() -> list[str]:
    try:
        from memory.session_memory import get_recent_intents

        return get_recent_intents(limit=5)
    except Exception:
        return []


def repair_transcript(text: str) -> tuple[str, bool]:
    """Apply cleanup + context hints; returns (text, repaired)."""
    if not text.strip():
        return "", False
    base = cleanup_transcript(text)
    if not STT_TRANSCRIPT_REPAIR_ENABLED:
        return base, base != text.strip()
    repaired = base
    changed = repaired != text.strip()
    try:
        from operating.workspace_context import get_cached_mode

        mode = get_cached_mode() or ""
        for wrong, right in _MODE_HINTS.get(mode, []):
            if wrong in repaired.lower():
                repaired = repaired.lower().replace(wrong, right)
                changed = True
    except Exception:
        pass
    recent = _recent_intent_hints()
    for intent in recent:
        token = intent.replace("_", " ")
        if token and token in repaired.lower():
            continue
    return repaired.strip(), changed
