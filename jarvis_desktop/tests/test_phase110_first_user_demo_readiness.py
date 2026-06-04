"""Phase 110 — first user demo readiness."""

from __future__ import annotations

from pathlib import Path

import pytest

from jarvis_desktop import api, server


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _repo(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    _write(root / "core" / "util.py", "def helper():\n    return 1\n")
    _write(root / "a.py", "from core.util import helper\n")
    return root


@pytest.fixture(autouse=True)
def reset_state():
    api._STATE.update(
        {"path": None, "scan": None, "graph": None, "index": None, "risks": None, "demo_mode": False}
    )
    yield


def test_validate_empty_path():
    res = api.validate_repository_path("")
    assert res["ok"] is False
    assert res["code"] == "empty_path"


def test_validate_invalid_path(tmp_path):
    missing = tmp_path / "does-not-exist"
    res = api.validate_repository_path(str(missing))
    assert res["ok"] is False
    assert res["code"] == "not_found"


def test_validate_no_code_repo(tmp_path):
    empty = tmp_path / "docs_only"
    empty.mkdir()
    (empty / "readme.txt").write_text("hello", encoding="utf-8")
    res = api.validate_repository_path(str(empty))
    assert res["ok"] is False
    assert res["code"] == "no_code_files"


def test_validate_valid_repo(tmp_path):
    root = _repo(tmp_path)
    res = api.validate_repository_path(str(root))
    assert res["ok"] is True
    assert res["code_files"] >= 1


def test_scan_success_payload(tmp_path):
    root = _repo(tmp_path)
    scan = api.scan_repository(str(root))
    assert scan["ok"] is True
    for key in (
        "file_count",
        "module_count",
        "dependency_edges",
        "top_risk_module",
        "top_risk_score",
        "suggested_next_actions",
        "validation_warnings",
    ):
        assert key in scan, key
    assert isinstance(scan["suggested_next_actions"], list)
    assert len(scan["suggested_next_actions"]) >= 3


def test_demo_mode_loads_sample_graph():
    res = api.load_demo_mode()
    assert res["ok"] is True
    assert res["demo_mode"] is True
    assert res["repo_name"].startswith("Atlas Demo")
    assert res.get("demo_pack") == "small"
    assert res["module_count"] >= 3
    graph = api.current_graph("module")
    assert graph["ok"] and graph["node_count"] >= 3
    assert api._STATE.get("demo_mode") is True


def test_copilot_requires_scan():
    res = api.copilot_ask("What does this repository do?")
    assert res["ok"] is False
    assert "scan" in res["error"].lower()


def test_context_export_requires_scan():
    res = api.context_export("claude", "compact")
    assert res["ok"] is False


def test_validate_and_demo_routes(tmp_path):
    root = _repo(tmp_path)
    status, payload = server.dispatch("POST", "/api/repositories/validate", {"path": str(root)})
    assert status == 200 and payload["ok"]
    status, demo = server.dispatch("POST", "/api/demo/load")
    assert status == 200 and demo["ok"] and demo["demo_mode"]


def test_select_rejects_invalid_path():
    res = api.select_repository("")
    assert res["ok"] is False
    assert res["code"] == "empty_path"
