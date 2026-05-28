"""TTS rate/voice helpers (edge-tts % vs pyttsx3 integer rate)."""

from __future__ import annotations

import re

_DEFAULT_PYTTS_RATE = 185


def resolve_edge_tts_rate(raw: str) -> str:
    """Edge-tts rate string, e.g. +15%."""
    r = (raw or "+0%").strip()
    if re.fullmatch(r"[+-]\d+%", r):
        return r
    if re.fullmatch(r"[+-]\d+", r):
        return f"{r}%"
    try:
        int(r)
        return "+0%"
    except ValueError:
        return "+0%"


def resolve_pyttsx_rate(raw: str) -> int:
    """pyttsx3 words-per-minute style integer."""
    r = (raw or str(_DEFAULT_PYTTS_RATE)).strip()
    m = re.fullmatch(r"([+-])(\d+)%", r)
    if m:
        sign, pct = m.group(1), int(m.group(2))
        delta = _DEFAULT_PYTTS_RATE * pct / 100
        return int(_DEFAULT_PYTTS_RATE + delta) if sign == "+" else int(_DEFAULT_PYTTS_RATE - delta)
    try:
        return int(r)
    except ValueError:
        return _DEFAULT_PYTTS_RATE


def normalize_tts_engine(name: str) -> str:
    key = (name or "edge_tts").strip().lower().replace("-", "_")
    if key in {"edge", "edge_tts"}:
        return "edge_tts"
    if key in {"pyttsx3", "pyttsx", "sapi"}:
        return "pyttsx3"
    if key in {"piper"}:
        return "piper"
    if key in {"xtts", "xtts_v2", "xtts2"}:
        return "xtts_v2"
    if key in {"styletts2", "style_tts2"}:
        return "styletts2"
    return key
