"""Phase 127 — Atlas Knowledge Engine."""

from __future__ import annotations

from pathlib import Path

import pytest

from jarvis_desktop import api, domain_knowledge as dk
from jarvis_desktop.atlas_knowledge.engine import get_engine
from jarvis_desktop.atlas_knowledge.loader import knowledge_root, load_concepts_from_disk
from jarvis_desktop.atlas_knowledge.retrieval import RETRIEVAL_BLOCKLIST, RetrievalPolicy
from jarvis_desktop.atlas_knowledge.validator import validate_catalog


def test_knowledge_root_structure():
    root = knowledge_root()
    assert (root / "concepts").is_dir()
    assert (root / "packs").is_dir()
    assert (root / "taxonomy" / "domains.json").is_file()
    assert (root / "cache").is_dir()
    assert (root / "indexes").is_dir()


def test_catalog_scale():
    get_engine().reload()
    count = get_engine().concept_count
    assert count >= 1000, f"expected 1000+ concepts, got {count}"


def test_ema_local_no_retrieval():
    engine = get_engine()
    m = engine.match_text("add ema indicator", mode="build")
    assert m.concept_id == "ema"
    assert m.source == "local"
    policy = RetrievalPolicy(knowledge_root() / "cache", enabled=True)
    assert not policy.should_retrieve("add ema indicator", local_score=m.score, matched_id="ema", threshold=2.0)
    assert "ema" in RETRIEVAL_BLOCKLIST


def test_jwt_has_rfc_references():
    rec = get_engine().get("jwt")
    assert rec is not None
    assert any("RFC" in r for r in rec.references)
    assert any("lookahead" in r.lower() or "algorithm" in r.lower() for r in rec.risks)


def test_build_plan_domain_prompt_section(trading_scan):
    res = api.plan_change("add EMA indicator with configurable period")
    assert res["ok"]
    assert res["plan"].get("domain_knowledge", {}).get("applied")
    assert "DOMAIN KNOWLEDGE" in res["prompts"]["claude"]
    assert "warmup" in res["prompts"]["claude"].lower() or "lookahead" in res["prompts"]["claude"].lower()
    blob = res["formatted"].lower()
    assert "detected concept" in blob or "ema" in blob


def test_investigate_backtest_uses_knowledge(trading_scan):
    res = api.investigate_symptom("backtest is much better than paper trading")
    assert res["ok"]
    dk_block = res["plan"].get("domain_knowledge") or {}
    assert dk_block.get("applied")
    assert "DOMAIN KNOWLEDGE" in res["prompts"]["claude"] or dk_block.get("failure_modes")


def test_catalog_validates_core_concepts():
    engine = get_engine()
    for cid in ("ema", "jwt", "authentication", "stripe_billing"):
        rec = engine.get(cid)
        assert rec is not None, cid
        from jarvis_desktop.atlas_knowledge.schema import validate_concept

        ok, errs = validate_concept(rec)
        assert ok, f"{cid}: {errs}"


def test_no_hallucinated_paths(trading_scan):
    res = api.plan_change("add ema indicator")
    allowed = {
        n["path"]
        for n in (api._STATE.get("graph") or {}).get("nodes", [])
        if n.get("type") == "module" and n.get("path")
    }
    roles = res["plan"]["domain_knowledge"].get("file_roles") or {}
    for path in (roles.get("must_inspect") or []):
        assert path in allowed


@pytest.fixture()
def trading_scan(tmp_path):
    api._STATE.update({"path": None, "scan": None, "graph": None, "index": None, "risks": None, "scan_cache": {}})
    root = tmp_path / "t"
    (root / "indicators").mkdir(parents=True)
    (root / "indicators" / "ema.py").write_text("def ema():\n    pass\n", encoding="utf-8")
    (root / "services").mkdir()
    (root / "services" / "backtest.py").write_text("def run():\n    pass\n", encoding="utf-8")
    api.scan_repository(str(root))
    get_engine().reload()
    return root
