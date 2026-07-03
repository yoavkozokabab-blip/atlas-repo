"""Phase 163 — symbol evidence collection."""

from __future__ import annotations

from pathlib import Path

import pytest

from atlas_desktop.evidence_engine import build_evidence_store
from atlas_desktop.evidence_engine.symbol_evidence import (
    build_evidence_panel,
    file_symbol_evidence,
    why_selected_for_file,
)

BENCHMARK_ROOT = Path(__file__).resolve().parents[2] / "benchmarks" / "repos" / "atlas_reference"


def _atlas_index():
    return {
        "files": [
            {"path": str(p.relative_to(BENCHMARK_ROOT)).replace("\\", "/")}
            for p in BENCHMARK_ROOT.rglob("*.py")
        ]
    }


@pytest.fixture
def atlas_store():
    if not BENCHMARK_ROOT.is_dir():
        pytest.skip("atlas_reference benchmark repo missing")
    return build_evidence_store(str(BENCHMARK_ROOT), None, _atlas_index())


def test_file_symbol_evidence_finds_definitions(atlas_store):
    syms, boost = file_symbol_evidence(atlas_store, "indicators/sma.py", ["sma", "indicator"])
    assert boost > 0
    assert any(s.kind in ("class", "function", "method") for s in syms)
    assert syms[0].defined_here


def test_why_selected_explains_symbol(atlas_store):
    syms, _ = file_symbol_evidence(atlas_store, "registry/signal_registry.py", ["signal", "registry"])
    why = why_selected_for_file("registry/signal_registry.py", syms)
    assert "Symbol" in why or "path" in why.lower()


def test_evidence_panel_has_summary_fields(atlas_store):
    panel = build_evidence_panel(
        atlas_store,
        ["indicators/sma.py", "registry/signal_registry.py"],
        ["indicator", "registry"],
        anchor_path="registry/signal_registry.py",
    )
    d = panel.to_dict()
    assert "matched_symbols" in d
    assert "repository_evidence" in d
    assert "selected_because" in d
    assert d["matched_symbols"] or d["selected_because"]
