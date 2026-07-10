"""Regression tests for deterministic MCP repository alias resolution.

A benchmark agent asked to scan `controlled_atlas_reference` must get exactly
the repository defined in benchmarks/agent_atlas_comparison/repositories.json.
Unknown aliases must fail loudly, and nothing may ever silently substitute a
demo or example repository.
"""

from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from atlas_desktop import api, mcp_server as mcp
from atlas_desktop.mcp_server import runtime

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))


def _fresh() -> None:
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


def _write_manifest(tmp_path, repositories, source_path=None):
    manifest = tmp_path / "repositories.json"
    manifest.write_text(
        json.dumps(
            {
                "source_checkout": {"path": source_path or REPO_ROOT},
                "repositories": repositories,
            }
        ),
        encoding="utf-8",
    )
    return str(manifest)


def test_controlled_atlas_reference_resolves_from_manifest(monkeypatch):
    """The benchmark alias resolves to exactly the manifest path and scans it."""
    _fresh()
    monkeypatch.delenv("ATLAS_BENCH_REPOSITORIES", raising=False)
    expected = os.path.abspath(os.path.join(REPO_ROOT, "benchmarks", "repos", "atlas_reference"))
    assert os.path.isdir(expected), "benchmark reference repo missing from checkout"

    result = mcp.call_tool("atlas_scan_repo", {"repo_path": "controlled_atlas_reference"})
    assert result["ok"] is True
    assert os.path.normcase(result["repo_path"]) == os.path.normcase(expected)
    assert "docs" not in result["repo_path"].replace("\\", "/").split("/")
    assert result["scan"]["file_count"] > 0


def test_unknown_alias_fails_loudly_without_scanning(monkeypatch):
    _fresh()
    monkeypatch.delenv("ATLAS_BENCH_REPOSITORIES", raising=False)
    result = mcp.call_tool("atlas_scan_repo", {"repo_path": "definitely_not_a_real_alias"})
    assert result["ok"] is False
    assert result["code"] == "unknown_repository_alias"
    assert "controlled_atlas_reference" in result.get("known_ids", [])
    assert api._STATE.get("scan") is None, "a failed alias lookup must not scan anything"


def test_demo_repo_is_never_a_fallback(monkeypatch):
    """An auth-flavored alias that is not in the manifest must error — it must
    never resolve to docs/demo/auth_demo_repo or any other example repo."""
    _fresh()
    monkeypatch.delenv("ATLAS_BENCH_REPOSITORIES", raising=False)
    demo_dir = os.path.join(REPO_ROOT, "docs", "demo", "auth_demo_repo")
    assert os.path.isdir(demo_dir), "precondition: the demo repo exists in the checkout"

    result = mcp.call_tool("atlas_scan_repo", {"repo_path": "auth_demo_repo"})
    assert result["ok"] is False
    assert result["code"] == "unknown_repository_alias"
    assert api._STATE.get("scan") is None
    assert api._STATE.get("path") in (None, "")


def test_known_alias_without_local_path_fails(monkeypatch, tmp_path):
    """A manifest entry with no local checkout (source=github, path=null) must
    fail loudly instead of scanning a same-named local directory."""
    _fresh()
    manifest = _write_manifest(
        tmp_path,
        [{"id": "requests", "source": "github", "path": None}],
    )
    monkeypatch.setenv("ATLAS_BENCH_REPOSITORIES", manifest)
    # Adversarial same-named directory in CWD must NOT be silently used.
    (tmp_path / "requests").mkdir()
    monkeypatch.chdir(tmp_path)

    result = mcp.call_tool("atlas_scan_repo", {"repo_path": "requests"})
    assert result["ok"] is False
    assert result["code"] == "repository_alias_unresolvable"
    assert api._STATE.get("scan") is None


def test_alias_resolving_to_missing_dir_fails(monkeypatch, tmp_path):
    _fresh()
    manifest = _write_manifest(
        tmp_path,
        [{"id": "ghost_repo", "source": "local", "path": "does/not/exist"}],
        source_path=str(tmp_path),
    )
    monkeypatch.setenv("ATLAS_BENCH_REPOSITORIES", manifest)
    result = mcp.call_tool("atlas_scan_repo", {"repo_path": "ghost_repo"})
    assert result["ok"] is False
    assert result["code"] == "repository_alias_unresolvable"


def test_explicit_paths_still_work(tmp_path, monkeypatch):
    """Absolute filesystem paths bypass alias resolution entirely."""
    _fresh()
    monkeypatch.delenv("ATLAS_BENCH_REPOSITORIES", raising=False)
    (tmp_path / "app").mkdir()
    (tmp_path / "app" / "main.py").write_text("def run():\n    return 1\n", encoding="utf-8")
    result = mcp.call_tool("atlas_scan_repo", {"repo_path": str(tmp_path)})
    assert result["ok"] is True
    assert os.path.normcase(result["repo_path"]) == os.path.normcase(str(tmp_path))


def test_manifest_lookup_is_deterministic():
    """Direct unit check: resolution goes through _resolve_repository_alias and
    returns the manifest path for the benchmark alias."""
    resolved, err = runtime._resolve_repository_alias("controlled_atlas_reference")
    assert err is None
    expected = os.path.abspath(os.path.join(REPO_ROOT, "benchmarks", "repos", "atlas_reference"))
    assert os.path.normcase(resolved) == os.path.normcase(expected)
