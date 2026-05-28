"""Coding assistant acceptance suite (Phase 65 Track E)."""

from __future__ import annotations

from reliability.coding_health import run_coding_acceptance, score_patch_recommendation, validate_patch_path


def test_patch_confidence():
    conf, hit = score_patch_recommendation("brain/router", ["brain/router.py"])
    assert conf >= 0.7
    assert "router" in hit


def test_patch_validation():
    ok, _ = validate_patch_path("brain/router.py")
    assert ok is True


def test_coding_acceptance_suite():
    score = run_coding_acceptance()
    assert len(score.cases) >= 4
