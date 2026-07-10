"""P0 regression tests: repository state must persist into fresh MCP sessions.

Covers the two launch-blocking failure modes:
1. False-stale validation — the persisted scan signature and the fresh live
   walk hashed different manifests, so identical repos looked changed.
2. Missing restore — a fresh ``Atlas.exe --mcp`` process never loaded the
   persisted scan and every tool returned ``requires_scan``.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from atlas_desktop import api, data_paths, persistence as persist, trust_integrity as ti
from atlas_desktop import mcp_server as mcp
from atlas_desktop.mcp_server import runtime

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))


def _fresh_state() -> None:
    api._STATE.clear()
    api._STATE.update(
        {
            "path": None,
            "scan": None,
            "graph": None,
            "index": None,
            "risks": None,
            "demo_mode": False,
            "scan_cache": {},
            "session_export": None,
            "repository_memory": None,
            "_current_memory": None,
            "scan_job": {"id": None, "cancelled": False, "stage": "idle"},
            "last_scope": {"mode": "entire_repo"},
        }
    )
    api._PERSISTENCE_BOOTSTRAPPED = False
    runtime._reset_restore_status()


@pytest.fixture()
def data_dir(tmp_path, monkeypatch):
    d = tmp_path / "atlas_data"
    d.mkdir()
    monkeypatch.setenv("ATLAS_DESKTOP_DATA", str(d))
    data_paths.reset_desktop_data_dir_cache()
    _fresh_state()
    yield str(d)
    data_paths.reset_desktop_data_dir_cache()
    _fresh_state()


def _make_repo(root, name="repo_a", extra=None):
    repo = root / name
    (repo / "app").mkdir(parents=True)
    (repo / "app" / "__init__.py").write_text("", encoding="utf-8")
    (repo / "app" / "auth.py").write_text(
        "class AuthStore:\n    def login(self, token):\n        return token\n",
        encoding="utf-8",
    )
    (repo / "app" / "routes.py").write_text(
        "from app.auth import AuthStore\n\nhandler = AuthStore()\n",
        encoding="utf-8",
    )
    for rel, body in (extra or {}).items():
        p = repo / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(body, encoding="utf-8")
    return str(repo)


# ---------------------------------------------------------------------------
# 1. Deterministic signatures
# ---------------------------------------------------------------------------

def test_same_file_set_in_different_order_same_signature(tmp_path):
    repo = _make_repo(tmp_path)
    files = [{"path": "app/auth.py"}, {"path": "app/routes.py"}, {"path": "app/__init__.py"}]
    scope = {"mode": "entire_repo"}
    a = ti.compute_signature_v2(repo, scope, indexed_files=files, include_content_hash=True)
    b = ti.compute_signature_v2(repo, scope, indexed_files=list(reversed(files)), include_content_hash=True)
    assert a["signature"] == b["signature"]


def test_walk_and_recomputed_walk_agree(tmp_path):
    """The persisted (scan-time) walk and a later validation walk of an
    unchanged repo must produce the identical signature."""
    repo = _make_repo(tmp_path)
    scope = {"mode": "entire_repo"}
    first = ti.compute_signature_v2(repo, scope, include_content_hash=True)
    second = ti.compute_signature_v2(repo, scope, include_content_hash=True)
    assert first["signature"] == second["signature"]
    assert first["version"] == 3


def test_added_removed_changed_file_invalidates(tmp_path):
    repo = _make_repo(tmp_path)
    scope = {"mode": "entire_repo"}
    base = ti.compute_signature_v2(repo, scope, include_content_hash=True)["signature"]

    added = os.path.join(repo, "app", "new_module.py")
    with open(added, "w", encoding="utf-8") as fh:
        fh.write("VALUE = 1\n")
    assert ti.compute_signature_v2(repo, scope, include_content_hash=True)["signature"] != base

    os.remove(added)
    assert ti.compute_signature_v2(repo, scope, include_content_hash=True)["signature"] == base

    target = os.path.join(repo, "app", "auth.py")
    with open(target, "a", encoding="utf-8") as fh:
        fh.write("# changed\n")
    assert ti.compute_signature_v2(repo, scope, include_content_hash=True)["signature"] != base

    os.remove(target)
    assert ti.compute_signature_v2(repo, scope, include_content_hash=True)["signature"] != base


def test_irrelevant_files_do_not_invalidate(tmp_path):
    repo = _make_repo(tmp_path)
    scope = {"mode": "entire_repo"}
    base = ti.compute_signature_v2(repo, scope, include_content_hash=True)["signature"]
    for rel in ("junk.log", "state.tmp", "x.cache", "y.lock"):
        with open(os.path.join(repo, rel), "w", encoding="utf-8") as fh:
            fh.write("noise")
    os.makedirs(os.path.join(repo, "__pycache__"), exist_ok=True)
    with open(os.path.join(repo, "__pycache__", "auth.cpython-313.pyc"), "wb") as fh:
        fh.write(b"\x00")
    assert ti.compute_signature_v2(repo, scope, include_content_hash=True)["signature"] == base


def test_unchanged_repo_valid_after_simulated_restart(tmp_path, data_dir):
    repo = _make_repo(tmp_path)
    scan = api.scan_repository(repo, None)
    assert scan["ok"]
    record = persist.load_scan_state(data_dir, persist._repo_memory.repo_id(repo))["record"]
    _fresh_state()  # simulated process restart
    validation = persist.validate_scan_state(record, repo)
    assert validation["status"] == "valid", validation


# ---------------------------------------------------------------------------
# 2/4. Fresh-session restore with graph, index, evidence, and memory
# ---------------------------------------------------------------------------

def test_fresh_session_restores_full_state(tmp_path, data_dir):
    repo = _make_repo(tmp_path)
    scan = api.scan_repository(repo, None)
    assert scan["ok"]
    _fresh_state()

    health = mcp.call_tool("atlas_health", {})
    p = health["persistence"]
    assert p["status"] == "restored", health
    assert p["validation"] == "valid"
    assert p["graph_rebuilt"] is False
    assert p["data_dir"]

    assert api._STATE.get("graph"), "dependency graph missing after restore"
    assert api._STATE.get("index"), "index missing after restore"
    assert api._STATE.get("evidence_store"), "evidence store missing after restore"
    assert api._STATE.get("repository_memory") or api._STATE.get("_current_memory"), (
        "repository memory missing after restore"
    )
    assert os.path.normcase(str(api._STATE.get("path"))) == os.path.normcase(repo)

    rel = mcp.call_tool("atlas_find_relevant_files", {"task": "fix login token handling"})
    assert rel["ok"] is True
    assert any("auth" in f["path"] for f in rel["recommended_files"])


def test_active_repo_wins_with_multiple_repos(tmp_path, data_dir):
    repo_a = _make_repo(tmp_path, "repo_a")
    repo_b = _make_repo(tmp_path, "repo_b", extra={"app/billing.py": "RATE = 2\n"})
    assert api.scan_repository(repo_a, None)["ok"]
    _fresh_state()
    assert api.scan_repository(repo_b, None)["ok"]  # b is now the active repo
    _fresh_state()

    health = mcp.call_tool("atlas_health", {})
    p = health["persistence"]
    assert p["status"] == "restored"
    assert os.path.normcase(p["restored_repo_path"]) == os.path.normcase(repo_b)


def test_multiple_repos_without_active_requires_selection(tmp_path, data_dir):
    repo_a = _make_repo(tmp_path, "repo_a")
    repo_b = _make_repo(tmp_path, "repo_b", extra={"app/billing.py": "RATE = 2\n"})
    assert api.scan_repository(repo_a, None)["ok"]
    _fresh_state()
    assert api.scan_repository(repo_b, None)["ok"]
    persist.set_active_repo_id(data_dir, "")  # active repo unknown
    _fresh_state()

    res = mcp.call_tool("atlas_find_relevant_files", {"task": "anything"})
    assert res["ok"] is False
    assert res["code"] == "repository_selection_required"
    ids = {r["repo_id"] for r in res["repositories"]}
    assert len(ids) == 2


def test_stale_repo_reports_reason_and_rescan_recovers(tmp_path, data_dir):
    repo = _make_repo(tmp_path)
    assert api.scan_repository(repo, None)["ok"]
    _fresh_state()
    with open(os.path.join(repo, "app", "auth.py"), "a", encoding="utf-8") as fh:
        fh.write("# repo changed after persist\n")

    res = mcp.call_tool("atlas_find_relevant_files", {"task": "anything"})
    assert res["ok"] is False
    assert res["code"] == "stale_scan"

    # Explicit rescan recovers.
    scan = mcp.call_tool("atlas_scan_repo", {"repo_path": repo})
    assert scan["ok"] is True
    rel = mcp.call_tool("atlas_find_relevant_files", {"task": "fix login token handling"})
    assert rel["ok"] is True


def test_corrupted_sidecar_requires_rescan(tmp_path, data_dir):
    repo = _make_repo(tmp_path)
    assert api.scan_repository(repo, None)["ok"]
    rid = persist._repo_memory.repo_id(repo)
    graph_path = os.path.join(data_dir, "scans", rid, "graph.json")
    assert os.path.isfile(graph_path)
    with open(graph_path, "w", encoding="utf-8") as fh:
        fh.write("{corrupted json !!")
    _fresh_state()

    res = mcp.call_tool("atlas_find_relevant_files", {"task": "anything"})
    assert res["ok"] is False
    assert res["code"] == "requires_scan"
    assert "sidecar_missing" in res["error"]


def test_no_persisted_scans_still_requires_scan(data_dir):
    res = mcp.call_tool("atlas_find_relevant_files", {"task": "anything"})
    assert res["ok"] is False
    assert res["code"] == "requires_scan"


# ---------------------------------------------------------------------------
# 6. True fresh-process end-to-end over MCP stdio.
# The Claude, Cursor, and Codex configs all launch the identical command
# (Atlas --mcp), so the parametrization documents that all three launch paths
# exercise this exact process boundary.
# ---------------------------------------------------------------------------

def _jsonrpc_client(env):
    proc = subprocess.Popen(
        [sys.executable, "-m", "atlas_desktop.mcp_server"],
        cwd=REPO_ROOT,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        env=env,
    )
    counter = {"id": 0}

    def call(method, params=None):
        counter["id"] += 1
        msg = {"jsonrpc": "2.0", "id": counter["id"], "method": method}
        if params is not None:
            msg["params"] = params
        proc.stdin.write(json.dumps(msg) + "\n")
        proc.stdin.flush()
        line = proc.stdout.readline()
        if not line:
            raise RuntimeError(f"no response; stderr: {proc.stderr.read()[:2000]}")
        return json.loads(line)

    def tool(name, args):
        resp = call("tools/call", {"name": name, "arguments": args})
        return json.loads(resp["result"]["content"][0]["text"])

    return proc, call, tool


@pytest.mark.parametrize("agent", ["claude", "cursor", "codex"])
def test_fresh_mcp_process_restores_scan(tmp_path, data_dir, agent):
    repo = _make_repo(tmp_path, f"repo_{agent}")
    # Process 1: scan and persist, then exit (this pytest process).
    assert api.scan_repository(repo, None)["ok"]
    _fresh_state()

    env = dict(os.environ)
    env["ATLAS_DESKTOP_DATA"] = data_dir
    proc, call, tool = _jsonrpc_client(env)
    try:
        init = call("initialize", {"protocolVersion": "2024-11-05", "capabilities": {}})
        assert init["result"]["serverInfo"]["name"]

        started = time.perf_counter()
        health = tool("atlas_health", {})
        health_secs = time.perf_counter() - started
        p = health["persistence"]
        assert p["status"] == "restored", health
        assert p["graph_rebuilt"] is False
        assert os.path.normcase(p["restored_repo_path"]) == os.path.normcase(repo)

        rel = tool("atlas_find_relevant_files", {"task": "fix login token handling"})
        assert rel["ok"] is True, rel
        assert any("auth" in f["path"] for f in rel["recommended_files"])
        # Restore must be materially faster than a rescan of even this tiny repo.
        assert health_secs < 10
    finally:
        proc.kill()
