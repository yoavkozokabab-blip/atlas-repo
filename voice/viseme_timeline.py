"""Approximate viseme energy timeline from text (Phase 41 — no true phoneme engine)."""

from __future__ import annotations

import re
import math


_VOWELS = set("aeiouy")


def estimate_duration_ms(text: str, *, rate_raw: str = "+0%") -> int:
    words = len(re.findall(r"\w+", text or ""))
    base = max(800, words * 380)
    m = re.fullmatch(r"([+-])(\d+)%", (rate_raw or "+0%").strip())
    if m:
        sign, pct = m.group(1), int(m.group(2))
        factor = 1.0 - (pct / 200.0) if sign == "+" else 1.0 + (pct / 200.0)
        base = int(base * max(0.6, min(1.4, factor)))
    return min(base, 30000)


def build_viseme_frames(text: str, *, frame_ms: int = 50, rate_raw: str = "+0%") -> list[float]:
    """
    Syllable-ish energy curve for HUD lip-sync style animation.
    Returns values 0.0–1.0 per frame_ms step.
    """
    safe = (text or "").strip().lower()
    if not safe:
        return [0.2]

    total_ms = estimate_duration_ms(safe, rate_raw=rate_raw)
    n_frames = max(1, total_ms // frame_ms)
    tokens = re.findall(r"[a-z0-9']+", safe)
    if not tokens:
        tokens = list(safe)

    energies: list[float] = []
    ti = 0
    for frame_i in range(n_frames):
        tok = tokens[ti % len(tokens)]
        ti += 1
        vowel_boost = 0.35 if any(c in _VOWELS for c in tok) else 0.1
        base = 0.25 + vowel_boost + 0.15 * (len(tok) % 4)
        wobble = 0.12 * math.sin(frame_i * 0.7)
        energies.append(max(0.1, min(1.0, base + wobble)))
    return energies
