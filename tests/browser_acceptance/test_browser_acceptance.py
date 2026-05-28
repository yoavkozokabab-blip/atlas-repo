"""Browser acceptance suite (Phase 65 Track C)."""

from __future__ import annotations

from reliability.browser_health import run_browser_acceptance, show_browser_health


def test_show_browser_health():
    assert "Browser health" in show_browser_health()


def test_browser_acceptance_suite():
    score = run_browser_acceptance()
    assert len(score.cases) >= 4
