"""Phase 128 — Knowledge depth and authority upgrade."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from atlas_desktop import api
from atlas_desktop.atlas_knowledge.engine import get_engine
from atlas_desktop.atlas_knowledge.loader import knowledge_root, load_concepts_from_disk
from atlas_desktop.atlas_knowledge.quality import (
    is_shallow_generated,
    quality_confidence_boost,
    quality_rank,
    quality_ui_label,
)

DEEP_CONCEPT_IDS = (
    "ema",
    "jwt",
    "oauth2",
    "rate_limiting",
    "stripe_billing",
    "webhook_receiver",
    "database_migration",
    "feature_flags",
    "ci_cd_pipeline",
    "secrets_management",
    "retry_backoff",
    "retry_queue",
    "structured_logging",
    "observability",
)


def test_phase128_manifest_counts():
    manifest = json.loads(
        (knowledge_root() / "curated_manifest_phase128.json").read_text(encoding="utf-8")
    )
    assert manifest["total"] >= 150
    assert manifest["stats"]["source_backed"] >= 50


def test_curated_yaml_overrides_pack_template():
    get_engine().reload()
    rec = get_engine().get("jwt")
    assert rec is not None
    assert rec.concept_quality_score == "source_backed"
    assert "RFC 7519" in rec.description
    assert rec.when_to_use
    assert rec.implementation_strategies
    assert not is_shallow_generated(rec.concept_quality_score)

    # Pack-only concept stays template-tagged
    shallow = get_engine().get("networking_network_dns_0")
    assert shallow is not None
    assert shallow.concept_quality_score == "generated_template"
    assert is_shallow_generated(shallow.concept_quality_score)


def test_source_backed_ranks_above_generated():
    assert quality_rank("source_backed") > quality_rank("generated_template")
    assert quality_confidence_boost("source_backed") > quality_confidence_boost("generated_template")


def test_quality_ui_labels():
    assert quality_ui_label("generated_template") == "Local generated"
    assert quality_ui_label("source_backed") == "Source-backed"
    assert quality_ui_label("curated_deep") == "Curated"


def test_deep_concepts_have_authority_fields():
    get_engine().reload()
    engine = get_engine()
    for cid in DEEP_CONCEPT_IDS:
        rec = engine.get(cid)
        assert rec is not None, cid
        assert rec.concept_quality_score in ("source_backed", "curated_deep"), cid
        assert len(rec.description) > 40, cid
        assert rec.failure_modes, cid
        assert rec.verification, cid
        assert rec.testing, cid
        if rec.concept_quality_score == "source_backed":
            assert rec.references, cid
            assert any(
                any(tok in r for tok in ("RFC", "https://", "docs.", "spec.", "OWASP", "Stripe"))
                for r in rec.references
            ), f"{cid} references: {rec.references}"


def test_knowledge_block_exposes_quality():
    get_engine().reload()
    engine = get_engine()
    m = engine.match_text("configure JWT bearer auth", mode="build")
    cls = engine.classify_request("configure JWT bearer auth", mode="build")
    block = engine.knowledge_block(cls)
    assert block["applied"]
    assert block["concept_quality_score"] == "source_backed"
    assert block["knowledge_quality_label"] == "Source-backed"
    assert block["knowledge_depth_warning"] is False


def test_investigate_warns_on_template_only(trading_scan):
    get_engine().reload()
    res = api.investigate_symptom("network dns resolution failure in production")
    assert res["ok"]
    lim = " ".join(res.get("limitations") or []).lower()
    dk = res["plan"].get("domain_knowledge") or {}
    if dk.get("concept_quality_score") == "generated_template" or dk.get("knowledge_depth_warning"):
        assert "template" in lim or "generated" in lim or "official" in lim


def test_build_plan_prefers_source_backed_quality(trading_scan):
    res = api.plan_change("add OAuth2 authorization code flow with PKCE")
    assert res["ok"]
    dk = res["plan"].get("domain_knowledge") or {}
    assert dk.get("applied")
    assert dk.get("concept_id") == "oauth2"
    assert dk.get("concept_quality_score") == "source_backed"
    assert "Source-backed" in (res["formatted"] or "") or "source_backed" in (res["formatted"] or "").lower()
    assert "DOMAIN KNOWLEDGE" in res["prompts"]["claude"]
    assert "Knowledge quality" in res["prompts"]["claude"]


def test_shallow_pack_concept_still_matches_with_lower_signal():
    get_engine().reload()
    engine = get_engine()
    m = engine.match_text("network dns", mode="investigate")
    assert m.concept_id
    rec = engine.get(m.concept_id)
    assert rec is not None
    if rec.concept_quality_score == "generated_template":
        cls = engine.classify_request("network dns", mode="investigate")
        assert any("template" in u.lower() for u in cls.unknowns)


def test_curated_concept_count_on_disk():
    concepts_dir = knowledge_root() / "concepts"
    yaml_files = list(concepts_dir.rglob("*.yaml"))
    assert len(yaml_files) >= 150


@pytest.fixture()
def trading_scan(tmp_path):
    api._STATE.update({"path": None, "scan": None, "graph": None, "index": None, "risks": None, "scan_cache": {}})
    root = tmp_path / "t"
    (root / "indicators").mkdir(parents=True)
    (root / "indicators" / "ema.py").write_text("def ema():\n    pass\n", encoding="utf-8")
    api.scan_repository(str(root))
    get_engine().reload()
    return root
