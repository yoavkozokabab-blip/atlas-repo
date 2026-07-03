"""Phase 164 — Surgical trust bug fixes (concept leakage, legacy bypasses, export)."""
from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import pytest

from atlas_desktop import api, domain_knowledge as dk, planning_engine as pe


def _ctx(paths):
    nodes = [
        {"id": f"n{i}", "type": "module", "path": p,
         "fan_in": 2, "dotted": p.replace("/", ".").rstrip(".py")}
        for i, p in enumerate(paths)
    ]
    return {
        "graph": {"nodes": nodes, "edges": []},
        "index": {"files": [{"path": p} for p in paths]},
        "risks": {"ranked_modules": []},
        "evidence_store": {},
        "repo_name": "test_repo",
        "entry_points": [],
        "scan": {},
    }


HA_PATHS = [
    "homeassistant/helpers/entity_registry.py",
    "homeassistant/helpers/area_registry.py",
    "homeassistant/helpers/device_registry.py",
    "homeassistant/helpers/signal.py",
    "homeassistant/core.py",
]

DJANGO_PATHS = ["django/contrib/auth/models.py", "django/core/registry.py"]
CELERY_PATHS = ["celery/worker/strategy.py", "celery/app/base.py"]
TRADING_PATHS = ["trading/strategy.py", "indicators/ema.py", "backtest/engine.py"]


# --- BUG A: quality boost cannot match without hits ---------------------------------

@pytest.mark.parametrize("prompt", [
    "add event bus tracing",
    "why is event bus tracing broken",
    "add rate limiting",
])
def test_no_ema_without_alias_hits(prompt):
    """Source-backed EMA must not win when the prompt has zero alias hits."""
    ctx = _ctx(HA_PATHS)
    if prompt.startswith("add ") or prompt.startswith("implement "):
        result = pe.plan_change(prompt, ctx)
    else:
        result = pe.investigate_symptom(prompt, ctx)
    assert result["ok"] is True
    dk_block = (result.get("plan") or {}).get("domain_knowledge") or {}
    assert dk_block.get("concept_id") != "ema", f"EMA leaked for: {prompt}"

    classification = dk.classify_request(prompt, mode="build" if "add " in prompt else "investigate")
    assert classification.concept_id != "ema"


def test_ema_still_matches_real_ema_prompt():
    ctx = _ctx(TRADING_PATHS)
    result = pe.plan_change("add EMA indicator", ctx)
    assert result["ok"] is True
    dk_block = (result.get("plan") or {}).get("domain_knowledge") or {}
    assert dk_block.get("concept_id") == "ema"


def test_match_text_rejects_boost_only():
    from atlas_desktop.atlas_knowledge.engine import get_engine

    eng = get_engine()
    m = eng.match_text("add event bus tracing", mode="build")
    assert m.concept_id != "ema"
    assert len(m.hits) == 0 or m.score < 2.0 or m.concept_id is None


# --- BUG B: trading repo evidence false positives -----------------------------------

@pytest.mark.parametrize("label,paths", [
    ("home_assistant", HA_PATHS),
    ("django", DJANGO_PATHS),
    ("celery", CELERY_PATHS),
])
def test_non_trading_repos_have_no_trading_evidence(label, paths):
    assert pe._repo_has_trading_evidence(_ctx(paths)) is False, label


def test_trading_repo_paths_detected():
    assert pe._repo_has_trading_evidence(_ctx(TRADING_PATHS)) is True
    assert pe._repo_has_trading_evidence(_ctx(["indicators/ema.py"])) is True


# --- BUG C: legacy / copilot trust bypasses -----------------------------------------

def test_bug_investigation_no_mock_success(tmp_path):
    root = tmp_path / "repo"
    (root / "core").mkdir(parents=True)
    (root / "core" / "util.py").write_text("x = 1\n", encoding="utf-8")
    assert api.scan_repository(str(root))["ok"]
    r = api.bug_investigation("something completely unrelated with no paths")
    assert r["ok"] is False
    assert r.get("mock") is not True
    assert r.get("status") == "insufficient_evidence"


def test_legacy_impact_unresolved_not_ok(tmp_path):
    root = tmp_path / "repo"
    (root / "core").mkdir(parents=True)
    (root / "core" / "util.py").write_text("def helper(): pass\n", encoding="utf-8")
    assert api.scan_repository(str(root))["ok"]
    miss = api.impact("does/not/exist.py")
    assert miss["ok"] is False
    assert miss.get("mock") is not True


def test_copilot_event_bus_no_ema(tmp_path):
    root = tmp_path / "repo"
    for p in HA_PATHS:
        fp = root / p
        fp.parent.mkdir(parents=True, exist_ok=True)
        fp.write_text("# stub\n", encoding="utf-8")
    scan = api.scan_repository(str(root))
    assert scan["ok"]
    r = api.copilot_ask("add event bus tracing")
    assert r.get("ok") is not False or r.get("mode") == "unknown"
    blob = (r.get("answer") or "") + str(r.get("suggested_prompt") or "")
    assert "ema" not in blob.lower()


# --- BUG D: export includes trust metadata ------------------------------------------

def test_export_js_includes_trust_block():
    js_path = Path(__file__).resolve().parents[1] / "static" / "atlas_zero_friction.js"
    text = js_path.read_text(encoding="utf-8")
    assert "function zfTrustBlock" in text
    assert "zfTrustBlock(r)" in text
    assert text.count("zfTrustBlock(r)") >= 3


def test_plan_response_has_trust_fields_for_export():
    ctx = _ctx(["api/routes.py", "services/auth.py", "core/hub.py"])
    result = pe.plan_change("add rate limiting to the API", ctx)
    assert result["ok"] is True
    plan = result["plan"]
    assert plan.get("confidence")
    assert plan.get("graph_health") is not None


def test_investigate_response_has_trust_fields_for_export():
    ctx = _ctx(["dispatch/event.py", "listeners/handler.py"])
    result = pe.investigate_symptom("why are duplicate events being fired", ctx)
    assert result["ok"] is True
    plan = result["plan"]
    assert plan.get("confidence")
    assert plan.get("graph_health") is not None
