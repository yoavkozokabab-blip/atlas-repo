"""Phase 179 — final beta ship blockers (closes 175E findings)."""

from __future__ import annotations

import base64
import io
import json
import os
import re
import sys
import zipfile
from pathlib import Path
from unittest.mock import MagicMock

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from atlas_desktop import api, first_impression as fi, planning_engine, product_info, server
from atlas_desktop.install_support import _redact_support_text

STATIC = Path(__file__).resolve().parents[1] / "static"
ROOT = Path(__file__).resolve().parents[2]

PHASE_LABEL_RE = re.compile(r"Phase\s+\d", re.IGNORECASE)
JARVIS_RE = re.compile(r"jarvis", re.IGNORECASE)

SECRET_SAMPLES = [
    "api_key=LEAK_API_KEY",
    "token=LEAK_TOKEN",
    "Authorization: Bearer LEAK_BEARER",
    "Bearer LEAK_BEARER2",
    "JWT LEAK_JWT_TOKEN",
    "sk-ant-api03-LEAK_ANTHROPIC_KEY",
    "sk-proj-LEAK_OPENAI_KEY_abcdefghij",
    "ghp_LEAKGITHUBPAT1234567890",
    "github_pat_11LEAKGITHUBPAT",
]

FORBIDDEN_IN_BUNDLE = (
    "api_key=", "token=", "Authorization:", "Bearer ",
    "JWT ", "LEAK_", "sk-ant-", "ghp_", "github_pat_",
)


def _fresh() -> None:
    api._STATE.clear()
    api._STATE.update({
        "path": None, "scan": None, "graph": None, "index": None, "risks": None,
        "demo_mode": False, "last_scope": {"mode": "entire_repo"},
        "scan_cache": {}, "scan_job": {"id": None, "cancelled": False, "stage": "idle"},
        "session_export": None, "repository_memory": None, "_current_memory": None,
    })


# --- 175E blocker 1: JWT + full secret marker redaction ---

@pytest.mark.parametrize("sample", SECRET_SAMPLES)
def test_redact_support_text_removes_secret_markers(sample: str):
    out = _redact_support_text(sample)
    assert "[REDACTED]" in out
    for marker in FORBIDDEN_IN_BUNDLE:
        assert marker.lower() not in out.lower(), f"marker {marker!r} survived in {out!r}"


def test_support_bundle_redacts_jwt_in_launcher_log(tmp_path, monkeypatch):
    data = tmp_path / "data"
    data.mkdir()
    monkeypatch.setattr("atlas_desktop.install_support.data_dir", lambda: str(data))
    log = " | ".join(SECRET_SAMPLES)
    (data / "launcher.log").write_text(log, encoding="utf-8")
    _fresh()
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "a.py").write_text("x=1\n", encoding="utf-8")
    api.scan_repository(str(repo))
    _, bundle = server.dispatch("POST", "/api/system/support-bundle")
    raw = base64.b64decode(bundle["content_base64"])
    with zipfile.ZipFile(io.BytesIO(raw)) as zf:
        blob = zf.read("logs/launcher.log").decode("utf-8")
    assert "LEAK_" not in blob
    for marker in FORBIDDEN_IN_BUNDLE:
        assert marker.lower() not in blob.lower()


# --- 175E blocker 2: no phase labels / JARVIS in shipped static ---

STATIC_ASSETS = tuple(
    p.relative_to(STATIC).as_posix()
    for p in sorted(STATIC.rglob("*"))
    if p.suffix.lower() in {".html", ".js", ".css"}
)


@pytest.mark.parametrize("rel", STATIC_ASSETS)
def test_shipped_static_has_no_phase_labels(rel: str):
    text = (STATIC / rel).read_text(encoding="utf-8")
    assert not PHASE_LABEL_RE.search(text), f"{rel} still contains internal phase label"


@pytest.mark.parametrize("rel", STATIC_ASSETS)
def test_shipped_static_has_no_jarvis_branding(rel: str):
    text = (STATIC / rel).read_text(encoding="utf-8")
    assert not JARVIS_RE.search(text), f"{rel} still contains JARVIS/jarvis reference"


# --- Beta workflow: sample → scan → change plan → export ---

def test_beta_workflow_sample_to_copy_payload():
    _fresh()
    load = api.load_demo_mode("medium")
    assert load.get("ok"), load.get("error")
    assert api._STATE.get("demo_mode") is True

    request = "Add structured logging to API handlers"
    plan_res = api.plan_change(request)
    assert plan_res.get("ok"), plan_res.get("error")
    plan = plan_res["plan"]
    assert plan.get("implementation_order")
    assert plan_res.get("formatted")

    export = plan_res.get("export") or {}
    assert export.get("text")
    assert "Goal:" in export["text"] or request in export["text"]

    mem = api.session_export_packet()
    assert mem.get("ok") is not False or mem.get("text")


# --- Empty sections must not appear in outputs ---

def test_change_plan_markdown_omits_empty_role_sections():
    plan = {
        "goal": "Add logging",
        "intent": "add",
        "confidence": "medium",
        "domain_knowledge": {
            "applied": True,
            "concept_name": "observability",
            "concept_title": "Logging",
            "domain_label": "Platform",
            "feature_type": "cross-cutting",
            "concept_understanding": "Structured logs help ops.",
            "why_this_matters": "Debuggability.",
            "knowledge_risks": ["Blind spots"],
            "file_roles": {"must_inspect": [], "likely_modify": [], "verify_only": []},
        },
        "implementation_order": ["Step 1"],
        "files_to_inspect_first": ["api/handlers.py"],
    }
    md = planning_engine.format_change_plan_markdown(plan)
    for label in ("MUST inspect", "LIKELY modify", "VERIFY only"):
        assert label not in md


def test_workflow_outputs_have_no_empty_role_placeholders():
    _fresh()
    api.load_demo_mode("medium")
    build = api.plan_change("Add structured logging to API handlers")
    inv = api.investigate_symptom("API requests fail intermittently under load")
    imp = api.change_impact_simulation("api/handlers.py")
    for res, key in ((build, "formatted"), (inv, "formatted")):
        assert res.get("ok"), res.get("error")
        md = res.get(key) or ""
        assert "MUST inspect:\n- (none)" not in md
        assert "LIKELY modify:\n- (none)" not in md
        assert "VERIFY only:\n- (none)" not in md
    assert imp.get("ok"), imp.get("error")
    exp = (imp.get("export") or {}).get("text") or ""
    assert "Direct impact" in exp


# --- Impossible scores ---

def test_evidence_scores_never_exceed_100():
    _fresh()
    api.load_demo_mode("medium")
    build = api.plan_change("Add structured logging to API handlers")
    inv = api.investigate_symptom("API requests fail intermittently under load")
    assert build.get("ok")
    rev = (build.get("plan") or {}).get("repository_evidence") or {}
    if rev.get("confidence_score") is not None:
        assert 0 <= rev["confidence_score"] <= 100
    for fe in rev.get("file_evidences") or []:
        assert 0 <= fi.cap_evidence_score(fe.get("evidence_score", 0)) <= 100
    assert inv.get("ok")
    for h in (inv.get("plan") or {}).get("hypotheses") or []:
        score = h.get("evidence_score_100", h.get("evidence_score", 0))
        assert 0 <= fi.cap_evidence_score(score) <= 100


# --- Update banner + feedback flows ---

def test_update_check_disabled_by_default():
    _, data = server.dispatch("GET", "/api/product/update-check")
    assert data["ok"] is True
    assert data["configured"] is False
    assert data["update_available"] is False


def test_update_check_available_when_configured(monkeypatch):
    monkeypatch.setenv("ATLAS_UPDATE_CHECK_URL", "https://updates.example/version.json")
    payload = json.dumps({"version": "0.2.0-beta"}).encode("utf-8")

    class _Resp:
        def read(self):
            return payload
        status = 200

    monkeypatch.setattr("urllib.request.urlopen", lambda *a, **k: _Resp())
    data = product_info.check_for_update()
    assert data["configured"] is True
    assert data["update_available"] is True
    product_js = (STATIC / "atlas_product.js").read_text(encoding="utf-8")
    assert "updateBanner" in (STATIC / "index.html").read_text(encoding="utf-8")
    assert "updateBanner" in product_js
    assert "update_available" in product_js


def test_feedback_local_submission():
    _, result = server.dispatch("POST", "/api/feedback", {
        "category": "bug",
        "message": "Copy button confusing on first run",
        "page": "index.html",
    })
    assert result["ok"] is True
    assert result["remote_sent"] is False
    assert "saved" in result["message"].lower() or "locally" in result["message"].lower()
    fb_js = (STATIC / "feedback.js").read_text(encoding="utf-8")
    assert "/api/feedback" in fb_js
    assert "AtlasFeedback" in fb_js


def test_feedback_remote_when_url_configured(monkeypatch):
    monkeypatch.setenv("ATLAS_FEEDBACK_URL", "https://feedback.example/atlas")
    sent = {}

    class _Resp:
        status = 200

    def fake_urlopen(req, timeout=10):
        sent["body"] = json.loads(req.data.decode("utf-8"))
        return _Resp()

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    _, result = server.dispatch("POST", "/api/feedback", {
        "category": "general",
        "message": "Great first impression",
        "email": "beta@example.com",
    })
    assert result["ok"] is True
    assert result["remote_sent"] is True
    assert sent["body"]["message"] == "Great first impression"


# --- Regression: prior gate suites still pass marker ---

def test_atlas_desktop_data_env_alias(tmp_path, monkeypatch):
    target = tmp_path / "atlas_data"
    monkeypatch.setenv("ATLAS_DESKTOP_DATA", str(target))
    from atlas_desktop.data_paths import reset_desktop_data_dir_cache, desktop_data_dir
    reset_desktop_data_dir_cache()
    assert os.path.abspath(desktop_data_dir()) == os.path.abspath(str(target))
    reset_desktop_data_dir_cache()
