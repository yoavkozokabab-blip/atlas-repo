"""Phase 184B — final beta ship blockers (184A audit fixes)."""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from jarvis_desktop import api, product_info

STATIC = Path(__file__).resolve().parents[1] / "static"
ROOT = Path(__file__).resolve().parents[2]
VENDOR = STATIC / "vendor"

PHASE_VERSION_RE = re.compile(r"phase\d{3}[a-z0-9-]*", re.IGNORECASE)
UNPKG_RE = re.compile(r"https?://unpkg\.com/", re.IGNORECASE)

USER_FACING_STATIC = (
    "index.html", "about.html", "support.html", "quickstart.html", "changelog.html",
    "app.js", "atlas_zero_friction.js", "atlas_product.js", "graph_smoke.html", "studio.html",
)


def _fresh() -> None:
    api._STATE.clear()
    api._STATE.update({
        "path": None, "scan": None, "graph": None, "index": None, "risks": None,
        "demo_mode": False, "last_scope": {"mode": "entire_repo"},
        "scan_cache": {}, "scan_job": {"id": None, "cancelled": False, "stage": "idle"},
        "session_export": None, "repository_memory": None, "_current_memory": None,
    })


# --- Blocker 1: sample load leaves repository ready for Change Plan ---

def test_load_demo_mode_summary_ready_for_change_plan():
    _fresh()
    load = api.load_demo_mode("medium")
    assert load.get("ok"), load.get("error")
    summary = api.current_summary()
    assert summary.get("ok") is True
    plan = api.plan_change("Add structured logging to API handlers")
    assert plan.get("ok"), plan.get("error")
    assert "Scan required" not in (plan.get("error") or "")
    assert "needs a scan" not in (plan.get("error") or "").lower()


def test_finish_scan_session_does_not_clear_summary():
    app_js = (STATIC / "app.js").read_text(encoding="utf-8")
    assert "function finishScanSession" in app_js
    block = app_js.split("function finishScanSession")[1].split("async function loadDemoMode")[0]
    assert "STATE.summary = null" not in block


# --- Blocker 2: Copy for Claude clipboard payload ---

def test_copy_for_ai_falls_back_when_export_is_metadata_only():
    zf = (STATIC / "atlas_zero_friction.js").read_text(encoding="utf-8")
    assert "if (stripped.trim()) return stripped" in zf
    assert "return zfLegacyFullPromptBody(kind)" in zf


def test_copy_text_rejects_empty_payload():
    app_js = (STATIC / "app.js").read_text(encoding="utf-8")
    assert "Nothing to copy" in app_js
    assert "execCommand(\"copy\")" in app_js or "execCommand('copy')" in app_js


def test_change_plan_export_has_copyable_body():
    _fresh()
    api.load_demo_mode("medium")
    plan = api.plan_change("Add structured logging to API handlers")
    assert plan.get("ok"), plan.get("error")
    export = plan.get("export") or plan.get("export_minimal") or {}
    text = export.get("text") or ""
    assert text.strip()
    # Metadata-only lines must not be the sole payload (184A empty clipboard root cause).
    body_lines = [
        ln for ln in text.splitlines()
        if ln.strip() and not re.match(
            r"^(scan_id|scan_signature|memory_ref|generated_at|replay_warning|freshness_status|ref):",
            ln.strip(),
            re.I,
        )
    ]
    assert body_lines, "export text must contain non-metadata copy body"


def test_copy_for_ai_is_async_and_awaits_copy():
    zf = (STATIC / "atlas_zero_friction.js").read_text(encoding="utf-8")
    assert "async function copyForAi" in zf
    assert "await copyText" in zf


# --- Blocker 3: version strings ---

def test_product_version_is_semver():
    # RC-1 ships 1.0.0; the contract is a clean semver with no phase labels.
    assert re.fullmatch(r"\d+\.\d+\.\d+(-[0-9A-Za-z.]+)?", product_info.PRODUCT_VERSION)


def test_health_reports_product_version():
    _fresh()
    health = api.health()
    assert health.get("version") == product_info.PRODUCT_VERSION
    assert not PHASE_VERSION_RE.search(health.get("version") or "")


@pytest.mark.parametrize("rel", USER_FACING_STATIC)
def test_user_facing_static_has_no_phase_version_strings(rel: str):
    text = (STATIC / rel).read_text(encoding="utf-8")
    assert not PHASE_VERSION_RE.search(text), f"{rel} still contains internal phase version"


def test_installer_generated_version_matches_product():
    iss = (ROOT / "packaging" / "installer" / "generated_version.iss").read_text(encoding="utf-8")
    assert f'MyAppVersion "{product_info.PRODUCT_VERSION}"' in iss
    assert not PHASE_VERSION_RE.search(iss)


# --- Blocker 4: offline CDN ---

def test_vendor_assets_present():
    assert (VENDOR / "three.min.js").is_file()
    assert (VENDOR / "3d-force-graph.min.js").is_file()
    assert (VENDOR / "three.min.js").stat().st_size > 100_000
    assert (VENDOR / "3d-force-graph.min.js").stat().st_size > 100_000


@pytest.mark.parametrize("rel", ("index.html", "graph_smoke.html", "studio.html"))
def test_critical_pages_use_local_vendor_not_unpkg(rel: str):
    text = (STATIC / rel).read_text(encoding="utf-8")
    assert "vendor/three.min.js" in text or "vendor/3d-force-graph.min.js" in text
    assert not UNPKG_RE.search(text), f"{rel} still references unpkg.com"
