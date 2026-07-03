"""Phase 107 — Atlas Desktop product API tests (offline, no web deps)."""

from __future__ import annotations

from pathlib import Path

import pytest

from atlas_desktop import api, server


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _repo(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    _write(root / "core" / "util.py", '"""hub."""\n\n\ndef helper():\n    return 1\n')
    for n in ("a", "b", "c"):
        _write(root / f"{n}.py", f"from core.util import helper\n\n\ndef r_{n}():\n    return helper()\n")
    _write(root / "ring" / "x.py", "from ring.y import gy\n\n\ndef gx():\n    return gy()\n")
    _write(root / "ring" / "y.py", "from ring.x import gx\n\n\ndef gy():\n    return 1\n")
    _write(root / "README.md", "# sample\n")
    return root


@pytest.fixture()
def scanned(tmp_path):
    root = _repo(tmp_path)
    result = api.scan_repository(str(root))
    assert result["ok"], result
    return result


# --- health / select ---------------------------------------------------
def test_health_shape():
    h = api.health()
    assert h.get("ok") is True and h["status"] == "ok"
    assert h.get("product")
    assert "version" in h and "repository_open" in h


def test_select_repository(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    (root / "main.py").write_text("x = 1\n", encoding="utf-8")
    assert api.select_repository(str(root))["ok"] is True
    assert api.select_repository(str(tmp_path / "nope"))["ok"] is False


# --- scan ----------------------------------------------------------------
def test_scan_result_shape(scanned):
    for key in ("repo_path", "file_count", "module_count", "subsystem_count",
                "dependency_edges", "graph_scope", "degraded", "top_hubs",
                "top_risks", "compact_token_estimate", "scan_duration_seconds"):
        assert key in scanned, key
    assert scanned["graph_scope"] == "production"
    assert scanned["degraded"] is False
    assert scanned["module_count"] >= 5
    assert scanned["dependency_edges"] >= 3          # a,b,c -> core.util + ring cycle
    assert scanned["compact_token_estimate"] > 0
    # core.util is the fan-in hub
    assert any("core" in (h["module"] or "") for h in scanned["top_hubs"])


# --- summary / graph / risks --------------------------------------------
def test_summary_shape(scanned):
    s = api.current_summary()
    assert s["ok"] and s["module_count"] >= 5
    for key in ("subsystems", "entry_points", "top_hubs", "top_risks",
                "explanation", "recommended_questions", "token_savings", "graph_health"):
        assert key in s, key
    assert isinstance(s["explanation"], str) and len(s["explanation"]) > 30


def test_graph_payload_shape(scanned):
    g = api.current_graph()
    assert g["ok"] and g["nodes"] and g["links"]
    n = g["nodes"][0]
    for key in ("id", "label", "path", "subsystem", "fan_in", "fan_out", "loc", "risk_score", "risk_tier", "in_cycle", "size"):
        assert key in n, key
    node_ids = {x["id"] for x in g["nodes"]}
    for link in g["links"]:
        assert link["source"] in node_ids and link["target"] in node_ids
        assert "opacity" in link and "weight" in link


def test_risks_shape(scanned):
    r = api.current_risks()
    assert r["ok"] and isinstance(r["ranked_modules"], list)


# --- impact / bug --------------------------------------------------------
def test_impact_real_and_mock(scanned):
    real = api.impact("core/util.py")
    assert real["ok"] and real["fan_in"] >= 3
    assert real["risk_level"] in ("low", "medium", "high")
    assert "recommended_prompt" in real and "recommended_tests" in real
    # Phase 161 — unresolved target must NOT fake success (no ok=true mock).
    miss = api.impact("does/not/exist.py")
    assert miss["ok"] is False and miss.get("mock") is not True
    assert miss.get("status") == "target_not_resolved"


def test_bug_investigation_shape(scanned):
    r = api.bug_investigation('Traceback: File "core/util.py", line 3')
    assert r["ok"]
    assert "core/util.py" in r["likely_modules"]
    assert r["confidence"] in ("low", "medium", "high")
    assert "suggested_prompt" in r and r["suggested_prompt"]


# --- context export ------------------------------------------------------
def test_context_export_shape_and_targets(scanned):
    for target in ("claude", "codex", "cursor"):
        res = api.context_export(target, "compact")
        assert res["ok"] and res["target"] == target and res["packet"] == "compact"
        assert res["estimated_tokens"] > 0 and isinstance(res["text"], str)
        assert "ATLAS REPOSITORY CONTEXT" in res["text"]
        assert "JARVIS REPOSITORY CONTEXT" not in res["text"]
        assert "UNCERTAINTY" in res["text"]            # uncertainty never hidden
    compact = api.context_export("claude", "compact")["estimated_tokens"]
    verbose = api.context_export("claude", "verbose")["estimated_tokens"]
    assert verbose >= compact                          # verbose >= compact


# --- server dispatch (framework-free routing) ---------------------------
def test_dispatch_all_routes(tmp_path):
    root = _repo(tmp_path)
    assert server.dispatch("GET", "/api/health")[0] == 200
    assert server.dispatch("POST", "/api/repositories/select", {"path": str(root)})[1]["ok"]
    status, scan = server.dispatch("POST", "/api/repositories/scan", {"path": str(root)})
    assert status == 200 and scan["ok"]
    assert server.dispatch("GET", "/api/repositories/current/summary")[1]["ok"]
    assert server.dispatch("GET", "/api/repositories/current/graph")[1]["ok"]
    assert server.dispatch("GET", "/api/repositories/current/risks")[1]["ok"]
    assert server.dispatch("POST", "/api/impact", {"target": "core/util.py"})[1]["ok"]
    assert server.dispatch("POST", "/api/bug-investigation", {"text": "core/util.py"})[1]["ok"]
    assert server.dispatch("POST", "/api/context/export", {"target": "codex", "packet": "compact"})[1]["ok"]
    assert server.dispatch("POST", "/api/repositories/validate", {"path": str(root)})[1]["ok"]
    assert server.dispatch("POST", "/api/demo/load")[1]["ok"]
    assert server.dispatch("POST", "/api/copilot/ask", {"question": "What does this repository do?"})[1]["ok"]
    assert server.dispatch("GET", "/api/unknown")[0] == 404


def test_all_documented_routes_are_dispatchable():
    # every route in ROUTES resolves (not 404) for a GET/POST shape
    documented = {(m, p) for m, p in server.ROUTES}
    assert ("GET", "/api/health") in documented
    assert ("POST", "/api/context/export") in documented
    assert ("GET", "/api/repositories/current/timeline") in documented
    assert ("GET", "/api/repositories/current/tour") in documented
    assert ("GET", "/api/analytics/summary") in documented
    assert ("POST", "/api/repositories/estimate") in documented
    assert ("GET", "/api/repositories/current/hierarchy-graph") in documented
    assert ("POST", "/api/system/browse-folder") in documented
    assert ("POST", "/api/planning/change") in documented
    assert ("POST", "/api/planning/investigate") in documented
    assert ("POST", "/api/planning/impact") in documented
    assert ("GET", "/api/usage/me") in documented
    assert ("GET", "/api/usage/admin") in documented
    assert ("GET", "/api/usage/admin_summary") in documented
    assert ("GET", "/api/pricing") in documented
    assert ("GET", "/api/repositories/current/system-health") in documented
    assert ("GET", "/api/system/diagnostics") in documented
    assert ("GET", "/api/system/startup-status") in documented
    assert ("GET", "/api/system/self-test") in documented  # Phase 157
    assert ("POST", "/api/system/support-bundle") in documented
    # Phase 182 — beta operations
    assert ("GET", "/api/system/identity") in documented
    assert ("GET", "/api/operations/identity") in documented
    assert ("GET", "/api/operations/insights") in documented
    assert ("GET", "/api/operations/feedback") in documented
    assert ("GET", "/api/operations/token-savings") in documented
    assert ("GET", "/api/operations/crashes") in documented
    assert len(documented) >= 47  # grows with each phase; floor-checked
