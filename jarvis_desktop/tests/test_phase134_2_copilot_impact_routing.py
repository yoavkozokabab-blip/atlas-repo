"""Phase 134.2 — Copilot impact prompts route through the semantic resolver.

These tests exercise the SAME entrypoint the UI Copilot uses
(`/api/copilot/ask` via server.dispatch / api.copilot_ask), not the impact
engine directly — that is the layer that was failing.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from jarvis_desktop import api, server  # noqa: E402

REF_REPO = Path(__file__).resolve().parents[2] / "benchmarks" / "repos" / "atlas_reference"
HA_REPO = Path(os.environ.get("ATLAS_HA_REPO",
               str(Path(__file__).resolve().parents[2] / "external_repos" / "home_assistant")))


# --------------------------------------------------------------------------
# Pure parser / intent (no scan)
# --------------------------------------------------------------------------

class TestConceptExtraction:
    @pytest.mark.parametrize("question,expected", [
        ("what breaks if I remove event bus", "event bus"),
        ("what breaks if I remove websocket support", "websocket support"),
        ("what breaks if I remove config entries", "config entries"),
        ("what breaks if I remove recorder", "recorder"),
        ("what breaks if I disable automations", "automations"),
        ("what happens if I change the cache layer", "cache layer"),
        ("impact of changing the event bus", "event bus"),
        ("what depends on the registry", "registry"),
        ("remove authentication", "authentication"),
        ("impact of changing auth/login.py", "auth/login.py"),
    ])
    def test_extracts_bare_concept(self, question, expected):
        assert api._extract_impact_concept(question) == expected

    def test_does_not_pass_whole_sentence(self):
        assert api._extract_impact_concept("what breaks if I remove event bus") != \
            "what breaks if i remove event bus"

    @pytest.mark.parametrize("q", [
        "what breaks if I remove event bus", "remove the recorder",
        "what depends on websocket support", "impact of changing core.py",
    ])
    def test_routes_to_impact_intent(self, q):
        assert api.classify_copilot_question(q) == "impact"


# --------------------------------------------------------------------------
# Full Copilot route on a small repo (top-level packages) — proves the route +
# layout-agnostic resolver without a slow Home Assistant scan.
# --------------------------------------------------------------------------

@pytest.fixture(scope="module")
def ref_scanned():
    api._STATE.update({"path": None, "scan": None, "graph": None, "index": None,
                       "risks": None, "evidence_store": None, "scan_cache": {}, "architecture": None})
    assert api.scan_repository(str(REF_REPO)).get("ok")
    yield


def _ask(prompt):
    _, r = server.dispatch("POST", "/api/copilot/ask",
                           {"question": prompt, "target": "none", "packet": "compact"})
    return r


class TestCopilotRouteRefRepo:
    def test_concept_prompt_no_fallback(self, ref_scanned):
        r = _ask("what breaks if I remove authentication")
        assert r["mode"] == "impact"
        assert "Name a file" not in r["answer"]
        assert "target not in graph" not in r["answer"].lower()
        assert r.get("semantic_label") == "authentication"
        assert r.get("resolved_modules"), "resolved_modules must be non-empty"
        assert any("auth" in m for m in r["resolved_modules"])
        assert (r.get("direct_impact") or r.get("indirect_impact"))

    def test_path_prompt_still_works(self, ref_scanned):
        r = _ask("what breaks if I change auth/middleware.py")
        assert r["mode"] == "impact"
        assert "Name a file" not in r["answer"]
        assert r.get("target") and "middleware" in r["target"]

    def test_response_has_semantic_fields(self, ref_scanned):
        r = _ask("what breaks if I remove authentication")
        for field in ("semantic_label", "resolved_modules", "resolved_symbols",
                      "direct_impact", "indirect_impact", "architectural_blast_radius"):
            assert field in r, f"missing UI field: {field}"


# --------------------------------------------------------------------------
# Home Assistant — the exact user-facing prompts (opt-in, slow).
# --------------------------------------------------------------------------

HA_PROMPTS = [
    ("what breaks if I remove websocket support", ("websocket_api", "websocket")),
    ("what breaks if I remove event bus", ("core.py", "event")),
    ("what breaks if I remove config entries", ("config_entries", "config_entry")),
    ("what breaks if I remove recorder", ("recorder",)),
    ("what breaks if I remove authentication", ("auth",)),
    ("what breaks if I disable automations", ("automation",)),
]


@pytest.mark.skipif(not HA_REPO.is_dir() or os.environ.get("ATLAS_RUN_HA") != "1",
                    reason="set ATLAS_RUN_HA=1 (and have the HA checkout) for the slow Copilot route test")
class TestCopilotRouteHomeAssistant:
    @pytest.fixture(scope="class")
    def ha_scanned(self):
        api._STATE.update({"path": None, "scan": None, "graph": None, "index": None,
                           "risks": None, "evidence_store": None, "scan_cache": {}, "architecture": None})
        assert api.scan_repository(str(HA_REPO)).get("ok")
        yield

    @pytest.mark.parametrize("prompt,needles", HA_PROMPTS)
    def test_exact_prompt_resolves(self, ha_scanned, prompt, needles):
        r = _ask(prompt)
        assert r["mode"] == "impact"
        assert "Name a file" not in r["answer"], f"fallback for {prompt!r}"
        assert "target not in graph" not in r["answer"].lower()
        assert r.get("semantic_label"), f"no semantic_label for {prompt!r}"
        assert r.get("resolved_modules"), f"no resolved_modules for {prompt!r}"
        assert (r.get("direct_impact") or r.get("indirect_impact")), f"no impact for {prompt!r}"
        blob = " ".join(r.get("resolved_modules", []) + [r.get("target", "")]).lower()
        assert any(n in blob for n in needles), f"{prompt!r} -> {blob[:120]}"
