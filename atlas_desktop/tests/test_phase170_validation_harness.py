"""Phase 170 — harness smoke tests (no live API required)."""
from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

_HARNESS = ROOT / "benchmarks" / "phase170_real_llm_validation.py"
if not _HARNESS.exists():
    pytest.skip("benchmarks harness is not shipped in the product repo", allow_module_level=True)
_spec = importlib.util.spec_from_file_location("phase170_harness", _HARNESS)
assert _spec and _spec.loader
phase170 = importlib.util.module_from_spec(_spec)
sys.modules["phase170_harness"] = phase170
_spec.loader.exec_module(phase170)


def test_pass_criteria_accepts_zero_delta():
    agg = {
        "quality_delta": 0.0,
        "grounding_delta": 0.0,
        "hallucination_increase_pct": 0.0,
        "export_token_reduction_pct": 79.0,
    }
    passes = phase170._passes_criteria(agg)
    assert all(passes.values())


def test_pass_criteria_rejects_large_quality_delta():
    agg = {
        "quality_delta": -0.5,
        "grounding_delta": 0.0,
        "hallucination_increase_pct": 0.0,
        "export_token_reduction_pct": 80.0,
    }
    passes = phase170._passes_criteria(agg)
    assert passes["quality_delta_lte_0_2"] is False


def test_symmetric_refusal_scoring():
    refused = {"ok": False}
    full = phase170._score_response(
        "no paths",
        atlas_result=refused,
        workflow="impact",
        export_text="long full export with fake/path.py",
        index_paths=set(),
    )
    minimal = phase170._score_response(
        "no paths",
        atlas_result=refused,
        workflow="impact",
        export_text="short",
        index_paths=set(),
    )
    assert full == minimal


def test_task_count_per_repo():
    assert len(phase170.BASE_TASKS) == 15
    assert len(phase170._tasks_for_repo("fastapi")) == 15
