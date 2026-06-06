"""Phase 169 — Minimal Atlas export regression (FULL vs MINIMAL)."""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from jarvis_desktop import api, atlas_export

REF_REPO = Path(__file__).resolve().parents[2] / "benchmarks" / "repos" / "atlas_reference"

BUILD_PROMPT = "add rate limiting to API routes"
INVESTIGATE_PROMPT = "why does authentication fail on login"
IMPACT_TARGET = "api/rate_limit.py"

FORBIDDEN_MINIMAL = (
    "rollback",
    "how to work safely",
    "how to use",
    "concept understanding",
    "repository evidence",
)


@pytest.fixture(scope="module")
def scanned_repo():
    api._STATE.clear()  # type: ignore[attr-defined]
    scan = api.scan_repository(str(REF_REPO))
    assert scan.get("ok"), scan.get("error")
    return scan


def _assert_export_blocks(result: dict, workflow: str) -> None:
    assert result.get("ok"), result.get("error")
    for key in ("export", "export_full", "export_minimal"):
        block = result.get(key)
        assert block, f"missing {key}"
        assert block.get("mode")
        assert block.get("tokens", 0) > 0
        assert block.get("text")
        assert block.get("reduction_vs_full_pct") is not None
    exp = result["export"]
    assert exp["mode"] == atlas_export.MINIMAL_EXPORT
    assert exp["workflow"] == workflow
    assert exp["minimal_export_tokens"] < exp["full_export_tokens"]
    assert exp["reduction_vs_full_pct"] >= 40.0


def _fidelity(workflow: str, result: dict) -> dict:
    full = result["export_full"]["text"]
    minimal = result["export_minimal"]["text"]
    return atlas_export.quality_fidelity_score(workflow, full, minimal, result)


def test_session_export_once_per_scan(scanned_repo):
    packet = api.session_export_packet()
    assert packet.get("ok")
    # Phase 172: mode is MEMORY (upgraded from SESSION); both are valid
    assert packet.get("mode") in ("SESSION", "MEMORY")
    text = packet.get("text", "")
    # Phase 172 uses ATLAS_REPOSITORY_MEMORY v1 header; SESSION v1 is fallback
    assert "ATLAS_SESSION v1" in text or "ATLAS_REPOSITORY_MEMORY v1" in text
    assert packet.get("tokens", 0) <= 350
    assert "graph_health" in text
    # top_subsystems appears in both SESSION v1 and MEMORY v1
    assert "subsystem" in text


def test_build_export_regression(scanned_repo):
    result = api.plan_change(BUILD_PROMPT)
    _assert_export_blocks(result, "build")
    fid = _fidelity("build", result)
    assert fid["quality_loss_pct"] <= 5.0
    assert fid["checks"]["confidence_preserved"]
    low = result["export_minimal"]["text"].lower()
    for phrase in FORBIDDEN_MINIMAL:
        assert phrase not in low


def test_investigate_export_regression(scanned_repo):
    result = api.investigate_symptom(INVESTIGATE_PROMPT)
    _assert_export_blocks(result, "investigate")
    fid = _fidelity("investigate", result)
    assert fid["quality_loss_pct"] <= 5.0
    assert fid["checks"]["confidence_preserved"]
    low = result["export_minimal"]["text"].lower()
    for phrase in FORBIDDEN_MINIMAL:
        assert phrase not in low


def test_impact_export_regression(scanned_repo):
    result = api.change_impact_simulation(IMPACT_TARGET)
    _assert_export_blocks(result, "impact")
    fid = _fidelity("impact", result)
    assert fid["quality_loss_pct"] <= 5.0
    assert fid["checks"]["confidence_preserved"]
    low = result["export_minimal"]["text"].lower()
    for phrase in FORBIDDEN_MINIMAL:
        assert phrase not in low


def test_trust_fields_preserved_in_minimal(scanned_repo):
    build = api.plan_change(BUILD_PROMPT)
    inv = api.investigate_symptom(INVESTIGATE_PROMPT)
    imp = api.change_impact_simulation(IMPACT_TARGET)
    for res, plan_key in ((build, "plan"), (inv, "plan")):
        conf = (res.get(plan_key) or {}).get("confidence") or res.get("confidence")
        assert conf
        assert conf.lower() in res["export_minimal"]["text"].lower()
    assert imp.get("confidence")
    assert imp["confidence"].lower() in imp["export_minimal"]["text"].lower()


def test_impact_refusal_still_blocks_trust_bypass(scanned_repo):
    """No ok=true mock blast radius on shallow generic targets (Phase 164D guard)."""
    miss = api.change_impact_simulation("validation/missing.py")
    if miss.get("ok"):
        pytest.skip("target resolved in reference repo")
    assert miss.get("ok") is False
    assert miss.get("mock") is not True


def test_js_prefers_server_minimal_export():
    js_path = Path(__file__).resolve().parents[1] / "static" / "atlas_zero_friction.js"
    text = js_path.read_text(encoding="utf-8")
    assert "zfServerExportText" in text
    assert "MINIMAL_EXPORT" in text
    assert "zfSessionPrefix" in text
