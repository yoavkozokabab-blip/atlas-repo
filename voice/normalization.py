"""Deterministic wake-adjacent STT transcript fixes (no LLM, no execution)."""

from __future__ import annotations

from voice.spoken_normalization import normalize_spoken_command

normalize_wake_transcript = normalize_spoken_command
