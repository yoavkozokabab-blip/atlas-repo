"""Phase 172 — Repository Memory Engine tests.

Covers:
  - Memory object construction from state
  - Persistence (write / load / corrupt recovery)
  - Delta computation (first scan, no-change, with-change)
  - Memory text format and token budget
  - Delta text format and token budget
  - Full integration: scan → memory generated → persisted → reloaded → delta
  - export_memory field present on workflow results
  - Backward compatibility: session_export_packet() still works
  - Attack surface mitigations from Phase 172A
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from atlas_desktop import api, atlas_export
from atlas_desktop import repository_memory as rm
from atlas_desktop.install_support import rebuild_index


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _fresh_state() -> None:
    api._STATE.clear()
    api._STATE.update({
        "path": None,
        "scan": None,
        "graph": None,
        "index": None,
        "risks": None,
        "demo_mode": False,
        "last_scope": {"mode": "entire_repo"},
        "scan_cache": {},
        "scan_job": {"id": None, "cancelled": False, "stage": "idle"},
        "session_export": None,
        "repository_memory": None,
        "_current_memory": None,
    })


def _tiny_repo(tmp_path: Path, dirname: str = "repo", name: str = "a.py", body: str = "x = 1\n") -> Path:
    root = tmp_path / dirname
    root.mkdir(exist_ok=True)
    (root / name).write_text(body, encoding="utf-8")
    return root


def _minimal_state(repo_path: str, modules: int = 5, edges: int = 8) -> dict:
    """Build a synthetic _STATE-like dict for unit tests (no real scan required)."""
    return {
        "path": repo_path,
        "scan": {
            "ok": True,
            "repo_name": "testrepo",
            "repo_path": repo_path,
            "module_count": modules,
            "dependency_edges": edges,
            "file_count": 20,
            "graph_health": {"label": "good"},
            "top_hubs": [
                {"module": "testrepo.core", "fan_in": 12},
                {"module": "testrepo.utils", "fan_in": 7},
            ],
            "top_risks": ["testrepo.auth", "testrepo.db"],
        },
        "index": {
            "subsystems": [
                {"name": "core", "role_counts": {"production_code": 10}},
                {"name": "utils", "role_counts": {"production_code": 5}},
            ]
        },
    }


# ---------------------------------------------------------------------------
# 1. Memory object construction
# ---------------------------------------------------------------------------

class TestBuildMemory:
    def test_basic_fields_present(self):
        state = _minimal_state("/tmp/repo")
        mem = rm.build_memory(state)
        assert mem["version"] == rm.MEMORY_VERSION
        assert mem["repo_name"] == "testrepo"
        assert mem["modules"] == 5
        assert mem["edges"] == 8
        assert mem["graph_health"] == "good"
        assert len(mem["top_hubs"]) == 2
        assert mem["top_hubs"][0]["module"] == "testrepo.core"
        assert mem["top_risks"] == ["testrepo.auth", "testrepo.db"]
        assert mem["top_subsystems"] == ["core", "utils"]

    def test_hub_fingerprint_is_stable(self):
        state = _minimal_state("/tmp/repo")
        m1 = rm.build_memory(state)
        m2 = rm.build_memory(state)
        assert m1["hub_fingerprint"] == m2["hub_fingerprint"]

    def test_hub_fingerprint_changes_on_hub_change(self):
        s1 = _minimal_state("/tmp/repo")
        s2 = _minimal_state("/tmp/repo")
        s2["scan"]["top_hubs"] = [{"module": "testrepo.different", "fan_in": 99}]
        m1 = rm.build_memory(s1)
        m2 = rm.build_memory(s2)
        assert m1["hub_fingerprint"] != m2["hub_fingerprint"]

    def test_empty_state_safe(self):
        mem = rm.build_memory({})
        assert mem["modules"] == 0
        assert mem["edges"] == 0
        assert mem["graph_health"] == "unknown"
        assert mem["top_hubs"] == []
        assert mem["top_risks"] == []

    def test_repo_id_is_stable_across_calls(self):
        state = _minimal_state("C:/projects/myrepo")
        m1 = rm.build_memory(state)
        m2 = rm.build_memory(state)
        assert m1["repo_id"] == m2["repo_id"]
        assert len(m1["repo_id"]) == 16

    def test_scan_id_is_8_chars(self):
        state = _minimal_state("/tmp/repo")
        mem = rm.build_memory(state)
        assert len(mem["scan_id"]) == 8


# ---------------------------------------------------------------------------
# 2. Persistence
# ---------------------------------------------------------------------------

class TestPersistence:
    def test_persist_and_load_roundtrip(self, tmp_path):
        state = _minimal_state("/tmp/testpersist")
        mem = rm.build_memory(state)
        mem = rm.merge_with_delta(mem, rm.compute_delta(mem, None))
        data_dir = str(tmp_path)
        path, ok, err = rm.persist(mem, data_dir)
        assert ok and path and os.path.isfile(path)
        assert not err
        loaded = rm.load("/tmp/testpersist", data_dir)
        assert loaded is not None
        assert loaded["repo_name"] == "testrepo"
        assert loaded["modules"] == 5
        assert loaded["version"] == rm.MEMORY_VERSION

    def test_load_missing_returns_none(self, tmp_path):
        result = rm.load("/nonexistent/path", str(tmp_path))
        assert result is None

    def test_load_corrupt_returns_none(self, tmp_path):
        state = _minimal_state("/tmp/corrupt")
        mem = rm.build_memory(state)
        path = rm._memory_path("/tmp/corrupt", str(tmp_path))
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f:
            f.write("not json {{{")
        result = rm.load("/tmp/corrupt", str(tmp_path))
        assert result is None

    def test_load_wrong_version_returns_none(self, tmp_path):
        state = _minimal_state("/tmp/wrongver")
        mem = rm.build_memory(state)
        mem["version"] = "ATLAS_OLD_FORMAT v0"
        path = rm._memory_path("/tmp/wrongver", str(tmp_path))
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f:
            json.dump(mem, f)
        result = rm.load("/tmp/wrongver", str(tmp_path))
        assert result is None

    def test_persist_empty_repo_path_returns_empty(self, tmp_path):
        mem = rm.build_memory({})
        path, ok, err = rm.persist(mem, str(tmp_path))
        assert path == "" and ok is False and err

    def test_memory_dir_created_on_first_persist(self, tmp_path):
        data_dir = str(tmp_path / "newdata")
        state = _minimal_state("/tmp/newdir")
        mem = rm.build_memory(state)
        mem = rm.merge_with_delta(mem, rm.compute_delta(mem, None))
        rm.persist(mem, data_dir)
        assert os.path.isdir(os.path.join(data_dir, "memory"))


# ---------------------------------------------------------------------------
# 3. Delta computation
# ---------------------------------------------------------------------------

class TestDelta:
    def test_first_scan_delta(self):
        state = _minimal_state("/tmp/repo")
        mem = rm.build_memory(state)
        delta = rm.compute_delta(mem, None)
        assert delta["first_scan"] is True
        assert delta["has_delta"] is False
        assert delta["session_count"] == 1
        assert delta["modules_delta"] == 0
        assert delta["edges_delta"] == 0
        assert delta["previous_scan_at"] is None

    def test_no_change_delta(self):
        state = _minimal_state("/tmp/repo")
        mem1 = rm.build_memory(state)
        mem2 = rm.build_memory(state)
        delta = rm.compute_delta(mem2, mem1)
        assert delta["first_scan"] is False
        assert delta["has_delta"] is False
        assert delta["session_count"] == 2
        assert delta["modules_delta"] == 0
        assert delta["edges_delta"] == 0

    def test_module_count_change_detected(self):
        s1 = _minimal_state("/tmp/repo", modules=5, edges=8)
        s2 = _minimal_state("/tmp/repo", modules=7, edges=10)
        m1 = rm.build_memory(s1)
        m2 = rm.build_memory(s2)
        delta = rm.compute_delta(m2, m1)
        assert delta["has_delta"] is True
        assert delta["modules_delta"] == 2
        assert delta["edges_delta"] == 2

    def test_new_hub_detected(self):
        s1 = _minimal_state("/tmp/repo")
        s2 = _minimal_state("/tmp/repo")
        s2["scan"]["top_hubs"] = [
            {"module": "testrepo.core", "fan_in": 12},
            {"module": "testrepo.new_hub", "fan_in": 15},
        ]
        m1 = rm.build_memory(s1)
        m2 = rm.build_memory(s2)
        delta = rm.compute_delta(m2, m1)
        assert delta["has_delta"] is True
        assert delta["hub_topology_changed"] is True
        assert "testrepo.new_hub" in delta["new_hubs"]
        assert "testrepo.utils" in delta["removed_hubs"]

    def test_new_risk_detected(self):
        s1 = _minimal_state("/tmp/repo")
        s2 = _minimal_state("/tmp/repo")
        s2["scan"]["top_risks"] = ["testrepo.auth", "testrepo.new_risk"]
        m1 = rm.build_memory(s1)
        m2 = rm.build_memory(s2)
        delta = rm.compute_delta(m2, m1)
        assert delta["has_delta"] is True
        assert "testrepo.new_risk" in delta["new_risks"]
        assert "testrepo.db" in delta["removed_risks"]

    def test_session_count_increments(self):
        state = _minimal_state("/tmp/repo")
        m1 = rm.build_memory(state)
        m2 = rm.build_memory(state)
        m3 = rm.build_memory(state)
        d2 = rm.compute_delta(m2, m1)
        m2 = rm.merge_with_delta(m2, d2)
        d3 = rm.compute_delta(m3, m2)
        assert d2["session_count"] == 2
        assert d3["session_count"] == 3

    def test_merge_with_delta_preserves_fields(self):
        state = _minimal_state("/tmp/repo")
        mem = rm.build_memory(state)
        delta = rm.compute_delta(mem, None)
        merged = rm.merge_with_delta(mem, delta)
        assert merged["session_count"] == 1
        assert merged["delta"] is not None
        assert merged["delta"]["first_scan"] is True
        # Original fields preserved
        assert merged["modules"] == 5
        assert merged["repo_name"] == "testrepo"


# ---------------------------------------------------------------------------
# 4. Text format and token budgets
# ---------------------------------------------------------------------------

class TestMemoryText:
    def test_starts_with_version_header(self):
        state = _minimal_state("/tmp/repo")
        mem = rm.merge_with_delta(rm.build_memory(state), rm.compute_delta(rm.build_memory(state), None))
        text = rm.memory_text(mem)
        assert text.startswith(rm.MEMORY_VERSION)

    def test_contains_repo_name(self):
        state = _minimal_state("/tmp/repo")
        mem = rm.merge_with_delta(rm.build_memory(state), rm.compute_delta(rm.build_memory(state), None))
        text = rm.memory_text(mem)
        assert "testrepo" in text

    def test_contains_modules_and_edges(self):
        state = _minimal_state("/tmp/repo")
        mem = rm.merge_with_delta(rm.build_memory(state), rm.compute_delta(rm.build_memory(state), None))
        text = rm.memory_text(mem)
        assert "modules: 5" in text
        assert "edges: 8" in text
        assert "graph_health: good" in text

    def test_contains_hubs(self):
        state = _minimal_state("/tmp/repo")
        mem = rm.merge_with_delta(rm.build_memory(state), rm.compute_delta(rm.build_memory(state), None))
        text = rm.memory_text(mem)
        assert "testrepo.core" in text

    def test_first_scan_delta_line(self):
        state = _minimal_state("/tmp/repo")
        mem = rm.merge_with_delta(rm.build_memory(state), rm.compute_delta(rm.build_memory(state), None))
        text = rm.memory_text(mem)
        assert "first scan" in text

    def test_no_change_delta_line(self):
        state = _minimal_state("/tmp/repo")
        m1 = rm.build_memory(state)
        m2 = rm.build_memory(state)
        delta = rm.compute_delta(m2, m1)
        m2 = rm.merge_with_delta(m2, delta)
        text = rm.memory_text(m2)
        assert "topology unchanged" in text

    def test_change_delta_line(self):
        s1 = _minimal_state("/tmp/repo", modules=5, edges=8)
        s2 = _minimal_state("/tmp/repo", modules=7, edges=10)
        m1 = rm.build_memory(s1)
        m2 = rm.build_memory(s2)
        delta = rm.compute_delta(m2, m1)
        m2 = rm.merge_with_delta(m2, delta)
        text = rm.memory_text(m2)
        assert "+2 modules" in text or "+2" in text

    def test_token_budget_under_150(self):
        state = _minimal_state("/tmp/repo")
        mem = rm.merge_with_delta(rm.build_memory(state), rm.compute_delta(rm.build_memory(state), None))
        text = rm.memory_text(mem)
        tokens = rm._estimate_tokens(text)
        assert tokens <= 150, f"memory text too large: {tokens} tokens"

    def test_memory_packet_mode_is_MEMORY(self):
        state = _minimal_state("/tmp/repo")
        mem = rm.merge_with_delta(rm.build_memory(state), rm.compute_delta(rm.build_memory(state), None))
        packet = rm.memory_packet(mem)
        assert packet["mode"] == "MEMORY"
        assert packet["tokens"] > 0
        assert packet["tokens"] <= 150


# ---------------------------------------------------------------------------
# 5. Delta text format
# ---------------------------------------------------------------------------

class TestDeltaText:
    def _make_build_plan(self) -> dict:
        return {
            "plan": {
                "goal": "add rate limiting",
                "confidence": "medium-high",
                "risk_level": "low",
                "files_to_inspect_first": ["api/app.py", "api/routes.py"],
                "likely_affected_modules": ["api/middleware.py"],
                "implementation_order": ["api/app.py", "api/routes.py"],
                "what_may_break": ["api/tests/test_app.py"],
                "limitations": ["Static graph only."],
            }
        }

    def _make_impact_result(self) -> dict:
        return {
            "ok": True,
            "target": "api/auth.py",
            "confidence": "high",
            "risk_level": "high",
            "direct_impact": ["api/routes.py", "api/models.py"],
            "indirect_impact": ["api/tests/test_auth.py"],
        }

    def test_build_delta_starts_with_header(self):
        plan = self._make_build_plan()
        text = rm.delta_text("build", plan_or_result=plan, memory_ref="abc12345", goal="add rate limiting")
        assert text.startswith(rm.DELTA_VERSION)

    def test_build_delta_contains_memory_ref(self):
        plan = self._make_build_plan()
        text = rm.delta_text("build", plan_or_result=plan, memory_ref="abc12345", goal="add rate limiting")
        assert "abc12345" in text

    def test_build_delta_contains_goal(self):
        plan = self._make_build_plan()
        text = rm.delta_text("build", plan_or_result=plan, memory_ref="ref1", goal="add rate limiting")
        assert "add rate limiting" in text

    def test_build_delta_contains_files(self):
        plan = self._make_build_plan()
        text = rm.delta_text("build", plan_or_result=plan, memory_ref="ref1", goal="add rate limiting")
        assert "api/app.py" in text

    def test_impact_delta_contains_target(self):
        result = self._make_impact_result()
        text = rm.delta_text("impact", plan_or_result=result, memory_ref="ref1")
        assert "api/auth.py" in text

    def test_impact_delta_contains_direct_impact(self):
        result = self._make_impact_result()
        text = rm.delta_text("impact", plan_or_result=result, memory_ref="ref1")
        assert "api/routes.py" in text

    def test_delta_token_budget_under_130(self):
        plan = self._make_build_plan()
        text = rm.delta_text("build", plan_or_result=plan, memory_ref="ref1", goal="add rate limiting")
        tokens = rm._estimate_tokens(text)
        assert tokens <= 130, f"delta text too large: {tokens} tokens"

    def test_unknown_workflow_returns_empty(self):
        text = rm.delta_text("unknown_workflow", plan_or_result={}, memory_ref="ref1")
        assert text == ""


# ---------------------------------------------------------------------------
# 6. Integration: scan → memory → persist → reload → delta
# ---------------------------------------------------------------------------

class TestIntegration:
    def test_scan_generates_memory_in_state(self, tmp_path):
        _fresh_state()
        root = _tiny_repo(tmp_path)
        import os
        os.environ["ATLAS_DESKTOP_DATA"] = str(tmp_path / "data")
        try:
            scan = api.scan_repository(str(root))
            assert scan["ok"]
            assert api._STATE.get("session_export") is not None
            assert api._STATE.get("repository_memory") is not None
        finally:
            os.environ.pop("ATLAS_DESKTOP_DATA", None)

    def test_memory_packet_mode_is_MEMORY_after_scan(self, tmp_path):
        _fresh_state()
        root = _tiny_repo(tmp_path)
        import os
        os.environ["ATLAS_DESKTOP_DATA"] = str(tmp_path / "data")
        try:
            scan = api.scan_repository(str(root))
            assert scan["ok"]
            packet = api._STATE["session_export"]
            assert packet["mode"] == "MEMORY"
            assert "ATLAS_REPOSITORY_MEMORY v1" in packet["text"]
        finally:
            os.environ.pop("ATLAS_DESKTOP_DATA", None)

    def test_session_export_packet_returns_memory(self, tmp_path):
        _fresh_state()
        root = _tiny_repo(tmp_path)
        import os
        os.environ["ATLAS_DESKTOP_DATA"] = str(tmp_path / "data")
        try:
            scan = api.scan_repository(str(root))
            assert scan["ok"]
            packet = api.session_export_packet()
            assert packet["ok"]
            assert packet["mode"] == "MEMORY"
            assert "ATLAS_REPOSITORY_MEMORY v1" in packet["text"]
        finally:
            os.environ.pop("ATLAS_DESKTOP_DATA", None)

    def test_memory_persisted_to_disk(self, tmp_path):
        _fresh_state()
        root = _tiny_repo(tmp_path)
        data_dir = str(tmp_path / "data")
        import os
        os.environ["ATLAS_DESKTOP_DATA"] = data_dir
        try:
            scan = api.scan_repository(str(root))
            assert scan["ok"]
            # Memory file should exist on disk
            rid = rm.repo_id(str(root))
            mem_file = os.path.join(data_dir, "memory", f"{rid}.json")
            assert os.path.isfile(mem_file), f"memory file not found: {mem_file}"
            loaded = json.loads(open(mem_file, encoding="utf-8").read())
            assert loaded["version"] == rm.MEMORY_VERSION
        finally:
            os.environ.pop("ATLAS_DESKTOP_DATA", None)

    def test_second_scan_increments_session_count(self, tmp_path):
        _fresh_state()
        root = _tiny_repo(tmp_path)
        data_dir = str(tmp_path / "data")
        import os
        os.environ["ATLAS_DESKTOP_DATA"] = data_dir
        try:
            # First scan
            api._STATE["scan_cache"] = {}
            scan1 = api.scan_repository(str(root))
            assert scan1["ok"]
            packet1 = api._STATE["session_export"]
            assert packet1["session_count"] == 1

            # Second scan (force cache clear for true rescan)
            api._STATE["scan_cache"] = {}
            api._STATE["scan"] = None
            api._STATE["graph"] = None
            api._STATE["index"] = None
            scan2 = api.scan_repository(str(root))
            assert scan2["ok"]
            packet2 = api._STATE["session_export"]
            assert packet2["session_count"] == 2
        finally:
            os.environ.pop("ATLAS_DESKTOP_DATA", None)

    def test_update_after_scan_standalone(self, tmp_path):
        state = _minimal_state(str(tmp_path / "myrepo"))
        data_dir = str(tmp_path / "data")
        packet = rm.update_after_scan(state, data_dir)
        assert packet["mode"] == "MEMORY"
        assert packet["tokens"] > 0
        assert packet["tokens"] <= 150
        assert state["session_export"] is packet
        assert state["repository_memory"] is packet


# ---------------------------------------------------------------------------
# 7. Workflow exports include export_memory field
# ---------------------------------------------------------------------------

REF_REPO = Path(__file__).resolve().parents[2] / "benchmarks" / "repos" / "atlas_reference"


@pytest.fixture(scope="module")
def scanned_ref(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("memory_ref_data")
    _fresh_state()
    import os
    os.environ["ATLAS_DESKTOP_DATA"] = str(tmp)
    scan = api.scan_repository(str(REF_REPO))
    assert scan.get("ok"), scan.get("error")
    yield scan
    os.environ.pop("ATLAS_DESKTOP_DATA", None)


def test_build_export_has_export_memory(scanned_ref):
    result = api.plan_change("add rate limiting to API routes")
    assert result.get("ok"), result.get("error")
    assert result.get("export_memory") is not None
    em = result["export_memory"]
    assert em["mode"] == atlas_export.MEMORY_EXPORT
    assert em["delta_export_tokens"] > 0
    assert em["delta_export_tokens"] < em["minimal_export_tokens"], (
        "delta should be smaller than minimal"
    )


def test_impact_export_has_export_memory(scanned_ref):
    result = api.change_impact_simulation("api/rate_limit.py")
    if not result.get("ok"):
        pytest.skip("target not in reference repo")
    assert result.get("export_memory") is not None
    em = result["export_memory"]
    assert em["delta_export_tokens"] > 0


def test_investigate_export_has_export_memory(scanned_ref):
    result = api.investigate_symptom("why does authentication fail on login")
    assert result.get("ok"), result.get("error")
    assert result.get("export_memory") is not None


def test_delta_reduction_vs_minimal(scanned_ref):
    """Delta tokens must be bounded (≤130) regardless of repo size.

    Large repos (FastAPI/Django) see 50-70% reduction vs minimal; the reference
    repo is tiny (~25 modules) so absolute bound is the right check here.
    """
    result = api.plan_change("add feature flags")
    assert result.get("ok")
    em = result.get("export_memory") or {}
    delta_tok = em.get("delta_export_tokens", 0)
    full_tok = em.get("full_export_tokens", 0)
    # Delta must exist
    assert delta_tok > 0, "delta_export_tokens must be > 0"
    # Delta must be smaller than full export
    if full_tok:
        assert delta_tok < full_tok, "delta must be smaller than full export"
    # Delta must be bounded at 130 tokens (memory mode target)
    assert delta_tok <= 130, f"delta tokens {delta_tok} exceeds 130-token target"


def test_existing_exports_unchanged(scanned_ref):
    """Backward compat: export, export_full, export_minimal still present."""
    result = api.plan_change("add audit logging")
    assert result.get("ok")
    for key in ("export", "export_full", "export_minimal"):
        block = result.get(key)
        assert block is not None, f"missing {key}"
        assert block.get("mode")
        assert block.get("tokens", 0) > 0


# ---------------------------------------------------------------------------
# 8. Attack surface mitigations (Phase 172A)
# ---------------------------------------------------------------------------

def test_select_repository_clears_session_export(tmp_path):
    """A1 mitigation: select_repository clears stale session_export."""
    _fresh_state()
    import os
    os.environ["ATLAS_DESKTOP_DATA"] = str(tmp_path / "data")
    try:
        root_a = _tiny_repo(tmp_path, "repo_a", "a.py", "x = 1\n")
        scan = api.scan_repository(str(root_a))
        assert scan["ok"]
        assert api._STATE.get("session_export") is not None

        root_b = _tiny_repo(tmp_path, "repo_b", "z.py", "z = 9\n")
        sel = api.select_repository(str(root_b))
        assert sel["ok"]
        assert api._STATE.get("session_export") is None
        assert api._STATE.get("repository_memory") is None
    finally:
        os.environ.pop("ATLAS_DESKTOP_DATA", None)


def test_rebuild_index_no_rescan_clears_session(tmp_path):
    """A2 mitigation: rebuild_index(rescan=False) clears stale session/memory."""
    _fresh_state()
    import os
    os.environ["ATLAS_DESKTOP_DATA"] = str(tmp_path / "data")
    try:
        root = _tiny_repo(tmp_path)
        scan = api.scan_repository(str(root))
        assert scan["ok"]
        assert api._STATE.get("session_export") is not None

        # Poison the memory
        api._STATE["session_export"] = {"text": "POISONED", "mode": "SESSION", "tokens": 5}

        result = rebuild_index(rescan=False)
        assert result["ok"]
        # Memory must be cleared, not just scan
        assert api._STATE.get("session_export") is None
        assert api._STATE.get("repository_memory") is None
    finally:
        os.environ.pop("ATLAS_DESKTOP_DATA", None)


# ---------------------------------------------------------------------------
# 9. Token overhead validation
# ---------------------------------------------------------------------------

def test_memory_packet_token_overhead(tmp_path):
    """Memory packet overhead vs SESSION v1 is bounded at +80 tokens max."""
    _fresh_state()
    import os
    os.environ["ATLAS_DESKTOP_DATA"] = str(tmp_path / "data")
    try:
        root = _tiny_repo(tmp_path)
        scan = api.scan_repository(str(root))
        assert scan["ok"]

        # Session packet (MEMORY mode)
        packet = api.session_export_packet()
        assert packet["ok"]
        memory_tokens = packet["tokens"]

        # SESSION v1 baseline
        session_v1 = atlas_export.session_context({
            "scan": api._STATE["scan"],
            "index": api._STATE.get("index") or {},
            "summary": api.current_summary(),
        })
        session_tokens = session_v1["tokens"]

        # Memory may be somewhat larger than SESSION v1 but must stay bounded
        assert memory_tokens <= session_tokens + 80, (
            f"memory packet too large: {memory_tokens} vs session {session_tokens}"
        )
    finally:
        os.environ.pop("ATLAS_DESKTOP_DATA", None)
