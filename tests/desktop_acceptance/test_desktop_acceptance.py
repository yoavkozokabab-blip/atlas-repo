"""Desktop operator acceptance suite (Phase 65 Track D)."""

from __future__ import annotations

from reliability.desktop_health import run_desktop_acceptance, show_desktop_operator_health


def test_show_desktop_operator_health():
    assert "Desktop operator health" in show_desktop_operator_health()


def test_desktop_acceptance_suite():
    score = run_desktop_acceptance()
    assert len(score.cases) >= 4
