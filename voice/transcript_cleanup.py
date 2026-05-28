"""Normalize common STT mis-hearings before classification (no execution)."""

from __future__ import annotations

import re
import unicodedata

# (pattern, replacement) — applied on lowercased spaced text, then re-cased lightly
_STT_FIXES: list[tuple[str, str]] = [
    (r"\bdash\s+board\b", "dashboard"),
    (r"\bdash\s+boards\b", "dashboards"),
    (r"\bdiagnostic\b", "diagnostics"),
    (r"\bchat\s+gpt\b", "chatgpt"),
    (r"\btrading\s+view\b", "tradingview"),
    (r"\byou\s+tube\b", "youtube"),
    (r"\bdis\s+cord\b", "discord"),
    (r"\brun\s+diagnostic\b", "run diagnostics"),
    (r"\bshow\s+dash\s+board\b", "show dashboard"),
    (r"\bopen\s+dash\s+board\b", "open dashboard"),
    (r"\bshow\s+dash\s+board\s+health\b", "show dashboard health"),
    (r"\bopen\s+trading\s+view\b", "open tradingview"),
    (r"\bshow\s+job\s+is\s+status\b", "show jarvis status"),
    (r"\bshow\s+jar\s+vis\s+status\b", "show jarvis status"),
    (r"\bshow\s+voice\s+deb\w+\b", "show voice debug"),
    (r"\bshow\s+audio\s+status\b", "show audio status"),
    (r"\btest\s+voice\s+out\w+\b", "test voice output"),
    (r"\bquiet\s+mode\b", "toggle quiet mode"),
    (r"\bover\s+lay\b", "overlay"),
    (r"\bjar\s+vis\b", "jarvis"),
    (r"\bthe\s+screener\b", "the screen"),
    (r"\bmy\s+screener\b", "my screen"),
    (r"\bdisc\s+ord\b", "discord"),
    (r"\bdashbord\b", "dashboard"),
    (r"^(?!show\s)jarvis\s+status\b", "show jarvis status"),
    (r"\bvoice\s+debug\b", "show voice debug"),
    (r"\baudio\s+status\b", "show audio status"),
    (r"\bfoundation\s+health\b", "foundation health check"),
    (r"\bvalidate\s+patch\s+safe\b", "validate patch safety"),
    (r"\breplay\s+patch\s+validation\b", "replay after patch"),
    (r"\breplay\s+validation\b", "replay after patch"),
]


def _normalize_ws(text: str) -> str:
    text = unicodedata.normalize("NFKC", text).strip()
    return re.sub(r"\s+", " ", text)


def cleanup_transcript(text: str) -> str:
    """Fix frequent English STT spacing/word splits."""
    if not text or not str(text).strip():
        return ""
    from voice.normalization import normalize_wake_transcript

    cleaned = normalize_wake_transcript(str(text))
    if not cleaned:
        return ""
    lower = cleaned.lower()
    for pattern, repl in _STT_FIXES:
        lower = re.sub(pattern, repl, lower, flags=re.IGNORECASE)
    return lower.strip() if lower != cleaned.lower() else cleaned
