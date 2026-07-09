"""Phase 185 — public demonstration blockers (Claude detection, MCP proof, website)."""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

from atlas_desktop import agent_integrations as ai

ROOT = Path(__file__).resolve().parents[2]
LANDING = ROOT / "websites" / "atlas-web"
REPORTS = ROOT / "reports"
EVIDENCE = REPORTS / "phase185_claude_desktop_demo_evidence.json"

REQUIRED_ROUTES = {
    "/",
    "/download",
    "/pricing",
    "/contact",
    "/privacy",
    "/terms",
}

PLACEHOLDER_PATTERNS = (
    "coming soon",
    "ahead of public launch",
    "preliminary summary",
    "lorem ipsum",
    "TODO",
    "FIXME",
    "href=\"#\"",
    "href='#'",
)


def test_claude_discovery_returns_multiple_sources(tmp_path, monkeypatch):
    appdata = tmp_path / "Roaming"
    local = tmp_path / "Local"
    monkeypatch.setenv("APPDATA", str(appdata))
    monkeypatch.setenv("LOCALAPPDATA", str(local))
    discovered = ai.discover_claude_desktop_config_paths()
    sources = {d["source"] for d in discovered}
    assert "appdata_roaming" in sources
    assert "localappdata_claude" in sources
    assert "localappdata_claude" in sources


def test_claude_status_exposes_discovered_paths(monkeypatch, tmp_path):
    appdata = tmp_path / "Roaming"
    cfg = appdata / "Claude" / "claude_desktop_config.json"
    cfg.parent.mkdir(parents=True)
    cfg.write_text("{}", encoding="utf-8")
    monkeypatch.setenv("APPDATA", str(appdata))
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "Local"))
    status = ai.claude_config_status()
    assert status["config_path"] == str(cfg)
    assert isinstance(status["discovered_paths"], list)
    assert status["config_source"] == "appdata_roaming"


def test_phase185_mcp_demo_evidence_exists():
    if not EVIDENCE.is_file():
        pytest.skip("Run scripts/phase185_claude_demo_proof.py first")
    data = json.loads(EVIDENCE.read_text(encoding="utf-8"))
    assert data["question"] == "What breaks if I change services/auth.py?"
    trace = data.get("tool_trace") or []
    assert len(trace) >= 3
    names = [t["tool"] for t in trace]
    assert "atlas_scan_repo" in names
    assert "atlas_find_file" in names
    assert "atlas_find_relevant_files" in names
    for step in trace:
        assert step.get("response", {}).get("ok") is True
    blob = json.dumps(trace).lower()
    assert "auth" in blob


def test_required_marketing_routes_exist():
    for route in REQUIRED_ROUTES:
        if route == "/":
            assert (LANDING / "app" / "page.tsx").is_file()
            continue
        segment = route.strip("/")
        assert (LANDING / "app" / segment / "page.tsx").is_file(), route


def test_no_placeholder_links_or_copy_in_marketing_pages():
    app_dir = LANDING / "app"
    files = list(app_dir.rglob("*.tsx"))
    combined = "\n".join(f.read_text(encoding="utf-8") for f in files)
    low = combined.lower()
    for pattern in PLACEHOLDER_PATTERNS:
        assert pattern.lower() not in low, f"found placeholder pattern: {pattern}"


def test_internal_route_links_are_known():
    known = {
        "/",
        "/download",
        "/download/atlas",
        "/pricing",
        "/contact",
        "/privacy",
        "/terms",
        "/features",
        "/faq",
        "/docs",
        "/login",
        "/security",
        "/eula",
        "/refund",
        "/cancellation",
        "/account",
        "/account/downloads",
        "/account/billing",
        "/account/settings",
        "/account/delete",
        "/admin",
        "/checkout/plan/pro",
        "/billing/success",
        "/billing/cancelled",
    }
    combined = "\n".join(p.read_text(encoding="utf-8") for p in (LANDING / "app").rglob("*.tsx"))
    hrefs = set(re.findall(r'href="(/[^"#?]*)"', combined))
    unknown = sorted(h for h in hrefs if h not in known and not h.startswith("/checkout/plan/"))
    assert not unknown, f"unknown internal links: {unknown}"


def test_phase185_report_exists():
    report = REPORTS / "phase185_public_demonstration.md"
    if not report.is_file():
        pytest.skip("historical phase report not shipped in the product repo")
    text = report.read_text(encoding="utf-8")
    assert "PASS" in text or "FAIL" in text or "BLOCKED" in text
