"""Normalize user/STT text before classification (no execution)."""

from __future__ import annotations

import re
import unicodedata

from voice.transcript_cleanup import cleanup_transcript


def strip_command_punctuation(text: str) -> str:
    """Remove trailing sentence punctuation from voice transcripts."""
    value = unicodedata.normalize("NFKC", text or "").strip()
    value = re.sub(r"[.!?,;:]+$", "", value).strip()
    return value


def prepare_command_text(text: str) -> str:
    """Cleanup + punctuation strip for router classification."""
    cleaned = cleanup_transcript(text)
    return strip_command_punctuation(cleaned)
