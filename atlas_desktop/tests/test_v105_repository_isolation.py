"""v1.0.5 P0 — one authoritative repository context; results never leak.

Behavior-level proof with two isolated fixtures:

  Repository A: only_a.py defining unique_a_symbol
  Repository B: only_b.py defining unique_b_symbol

Contracts proven here:
  1. Ask/Impact/Plan/Investigate on A never return B artifacts (and vice versa).
  2. Every workflow response carries a context_binding naming the repository
     and scan that produced it.
  3. Switching repositories atomically drops all derived state, and a result
     bound to the previous repository is detectably stale (the UI discards it).
  4. Demo -> real and real -> demo transitions never carry results across.
  5. A mutated repository fails freshness (stale scan revisions are rejected).
  6. The MCP runtime follows the same authoritative selected repository.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from atlas_desktop import api


def _fresh() -> None:
    api._STATE.clear()
    api._PERSISTENCE_BOOTSTRAPPED = False
    api._STATE.update({
        "path": None, "scan": None, "graph": None, "index": None, "risks": None,
        "demo_mode": False, "last_scope": {"mode": "entire_repo"},
        "scan_cache": {}, "scan_job": {"id": None, "cancelled": False, "stage": "idle"},
        "session_export": None, "repository_memory": None, "_current_memory": None,
    })


@pytest.fixture
def data_dir(tmp_path, monkeypatch):
    d = tmp_path / "atlas_data"
    d.mkdir()
    monkeypatch.setenv("ATLAS_DESKTOP_DATA", str(d))
    from atlas_desktop.data_paths import reset_desktop_data_dir_cache
    reset_desktop_data_dir_cache()
    return str(d)


def _repo_a(tmp_path: Path) -> str:
    r = tmp_path / "repo_a"
    r.mkdir()
    (r / "only_a.py").write_text(
        "def unique_a_symbol():\n    return 'a'\n", encoding="utf-8"
    )
    for i in range(6):
        (r / f"a_user{i}.py").write_text(
            "import only_a\n\ndef caller():\n    return only_a.unique_a_symbol()\n",
            encoding="utf-8",
        )
    return str(r)


def _repo_b(tmp_path: Path) -> str:
    r = tmp_path / "repo_b"
    r.mkdir()
    (r / "only_b.py").write_text(
        "def unique_b_symbol():\n    return 'b'\n", encoding="utf-8"
    )
    for i in range(6):
        (r / f"b_user{i}.py").write_text(
            "import only_b\n\ndef caller():\n    return only_b.unique_b_symbol()\n",
            encoding="utf-8",
        )
    return str(r)


def _run_all_workflows(symbol_file: str, symbol: str) -> dict:
    return {
        "ask": api.copilot_ask(f"Where is {symbol} implemented?"),
        "impact": api.change_impact_simulation(symbol_file),
        "plan": api.plan_change(f"Refactor {symbol} to accept an argument"),
        "investigate": api.investigate_symptom(f"{symbol} raises TypeError at startup"),
    }


def _assert_no_foreign_artifacts(results: dict, foreign_terms: tuple) -> None:
    for name, result in results.items():
        blob = json.dumps(result, default=str).lower()
        for term in foreign_terms:
            assert term.lower() not in blob, (
                f"{name} response leaked foreign repository artifact {term!r}"
            )


def test_workflows_on_a_never_return_b(data_dir, tmp_path):
    _fresh()
    a = _repo_a(tmp_path)
    _repo_b(tmp_path)  # exists on disk but is never selected
    assert api.scan_repository(a)["ok"]
    results = _run_all_workflows("only_a.py", "unique_a_symbol")
    _assert_no_foreign_artifacts(results, ("only_b", "unique_b_symbol", "repo_b"))


def test_workflows_on_b_never_return_a(data_dir, tmp_path):
    _fresh()
    _repo_a(tmp_path)
    b = _repo_b(tmp_path)
    assert api.scan_repository(b)["ok"]
    results = _run_all_workflows("only_b.py", "unique_b_symbol")
    _assert_no_foreign_artifacts(results, ("only_a", "unique_a_symbol", "repo_a"))


def test_every_workflow_response_carries_context_binding(data_dir, tmp_path):
    _fresh()
    a = _repo_a(tmp_path)
    assert api.scan_repository(a)["ok"]
    results = _run_all_workflows("only_a.py", "unique_a_symbol")
    expected_path = os.path.abspath(a)
    for name, result in results.items():
        binding = result.get("context_binding")
        assert isinstance(binding, dict), f"{name} response is missing context_binding"
        assert binding["repo_path"].lower() == expected_path.lower(), name
        assert binding["repo_id"], name
        assert binding["demo_mode"] is False, name


def test_switch_invalidates_state_and_marks_prior_results_stale(data_dir, tmp_path):
    _fresh()
    a = _repo_a(tmp_path)
    b = _repo_b(tmp_path)
    assert api.scan_repository(a)["ok"]
    result_a = api.change_impact_simulation("only_a.py")
    assert result_a["ok"]
    binding_a = result_a["context_binding"]

    # Atomic switch: selecting B drops every scan-derived surface at once.
    sel = api.select_repository(b)
    assert sel["ok"] and sel["requires_rescan"]
    for key in ("scan", "graph", "index", "risks", "evidence_store"):
        assert not api._STATE.get(key), f"{key} survived a repository switch"

    # The old result stays attached to A: its binding can never satisfy the
    # newly selected repository (this is the contract the UI guard enforces).
    assert binding_a["repo_path"].lower() == os.path.abspath(a).lower()
    assert binding_a["repo_path"].lower() != os.path.abspath(b).lower()

    assert api.scan_repository(b)["ok"]
    result_b = api.change_impact_simulation("only_b.py")
    assert result_b["ok"]
    assert result_b["context_binding"]["repo_path"].lower() == os.path.abspath(b).lower()
    assert result_b["context_binding"]["repo_id"] != binding_a["repo_id"]
    # Asking B about A's symbol must not produce grounded A evidence.
    ask = api.copilot_ask("Where is unique_a_symbol implemented?")
    blob = json.dumps(ask, default=str).lower()
    assert "only_a" not in blob and "repo_a" not in blob


def test_demo_to_real_clears_demo_results(data_dir, tmp_path):
    _fresh()
    demo = api.load_demo_mode("small")
    if not demo.get("ok"):
        pytest.skip("bundled demo pack unavailable in this checkout")
    assert api._STATE.get("demo_mode") is True
    demo_files = {f.get("path", "") for f in (api._STATE.get("index") or {}).get("files", [])}
    assert demo_files

    a = _repo_a(tmp_path)
    sel = api.select_repository(a)
    assert sel["ok"]
    assert api._STATE.get("demo_mode") is False
    assert not api._STATE.get("scan"), "demo scan survived switching to a real repository"
    assert api.scan_repository(a)["ok"]
    results = _run_all_workflows("only_a.py", "unique_a_symbol")
    demo_markers = tuple(m for m in demo_files if m)[:20] + ("atlas demo",)
    _assert_no_foreign_artifacts(results, demo_markers)
    for result in results.values():
        assert result.get("context_binding", {}).get("demo_mode") is False


def test_real_to_demo_clears_real_results(data_dir, tmp_path):
    _fresh()
    a = _repo_a(tmp_path)
    assert api.scan_repository(a)["ok"]
    demo = api.load_demo_mode("small")
    if not demo.get("ok"):
        pytest.skip("bundled demo pack unavailable in this checkout")
    assert api._STATE.get("demo_mode") is True
    summary = api.current_summary()
    assert summary["ok"]
    assert summary["repo_name"].startswith("Atlas Demo")
    ask = api.copilot_ask("Where is unique_a_symbol implemented?")
    blob = json.dumps(ask, default=str).lower()
    assert "only_a" not in blob and "repo_a" not in blob
    assert ask["context_binding"]["demo_mode"] is True


def test_mutated_repository_fails_freshness(data_dir, tmp_path):
    _fresh()
    a = _repo_a(tmp_path)
    assert api.scan_repository(a)["ok"]
    from atlas_desktop import trust_integrity as ti
    assert ti.verify_scan_fresh(api._STATE) is None  # fresh right after scan
    (Path(a) / "only_a.py").write_text(
        "def unique_a_symbol():\n    return 'changed'\n", encoding="utf-8"
    )
    refusal = ti.verify_scan_fresh(api._STATE)
    assert refusal is not None and refusal.get("ok") is False


def test_mcp_runtime_follows_selected_repository(data_dir, tmp_path):
    _fresh()
    a = _repo_a(tmp_path)
    b = _repo_b(tmp_path)
    from atlas_desktop.mcp_server import runtime
    assert api.scan_repository(a)["ok"]
    assert runtime._current_repo().lower() == os.path.abspath(a).lower()
    assert api.scan_repository(b)["ok"]
    assert runtime._current_repo().lower() == os.path.abspath(b).lower()
