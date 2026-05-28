"""Voice acceptance suite (Phase 65 Track A)."""

from __future__ import annotations

import pytest

from reliability.voice_health import run_voice_acceptance, show_voice_health


def test_show_voice_health():
    body = show_voice_health()
    assert "Voice health" in body


def test_voice_acceptance_suite():
    score = run_voice_acceptance()
    assert score.pass_rate >= 80.0
    assert score.current_pct > 0
