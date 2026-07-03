"""Phase 109 — interactive repository copilot."""

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
    return root


@pytest.fixture()
def scanned(tmp_path):
    api._STATE.update({"path": None, "scan": None, "graph": None, "index": None, "risks": None})
    result = api.scan_repository(str(_repo(tmp_path)))
    assert result["ok"], result
    return result


def _expect_shape(payload: dict) -> None:
    for key in (
        "mode",
        "answer",
        "evidence",
        "files",
        "risk_level",
        "suggested_prompt",
        "copy_targets",
        "confidence",
        "limitations",
    ):
        assert key in payload, key
    assert set(payload["copy_targets"]) == {"claude", "codex", "cursor"}


def test_copilot_route_shape(scanned):
    status, payload = server.dispatch(
        "POST",
        "/api/copilot/ask",
        {"question": "What does this repository do?", "target": "none", "packet": "compact"},
    )
    assert status == 200
    assert payload["ok"] is True
    _expect_shape(payload)


def test_question_routing_repository_understanding(scanned):
    res = api.copilot_ask("What does this repository do?")
    assert res["ok"] and res["mode"] == "repository_understanding"
    assert res["answer"]


def test_question_routing_risk(scanned):
    res = api.copilot_ask("What are the top architectural risks?")
    assert res["ok"] and res["mode"] == "risk"
    assert "score" in res["answer"].lower() or res["files"]


def test_question_routing_impact(scanned):
    res = api.copilot_ask("What breaks if I change core/util.py?")
    assert res["ok"] and res["mode"] == "impact"
    assert res["risk_level"] in {"low", "medium", "high", "unknown"}
    assert "core/util.py" in res["answer"] or "core/util.py" in res["files"]


def test_question_routing_cycles(scanned):
    res = api.copilot_ask("Show import cycles")
    assert res["ok"] and res["mode"] == "cycles"
    assert "cycle" in res["answer"].lower()


def test_question_routing_context_export(scanned):
    res = api.copilot_ask("Generate a Claude prompt for this repo")
    assert res["ok"] and res["mode"] == "context_export"
    assert res["copy_targets"]["claude"]
    assert res["suggested_prompt"]


def test_unknown_question_fallback(scanned):
    res = api.copilot_ask("xyzzy plugh")
    assert res["ok"] and res["mode"] == "unknown"
    assert res["confidence"] == "low"


def test_classify_copilot_question():
    assert api.classify_copilot_question("What are the top architectural risks?") == "risk"
    assert api.classify_copilot_question("Who imports core/util.py?") == "dependency"
    assert api.classify_copilot_question("Generate a Codex prompt") == "context_export"


def test_node_prompt_generation():
    prompts = api.node_copilot_prompts({"path": "core/util.py", "label": "core.util"})
    assert len(prompts) == 4
    assert any("Who imports" in item for item in prompts)


def test_copilot_without_scan():
    api._STATE.update({"path": None, "scan": None, "graph": None, "index": None, "risks": None})
    res = api.copilot_ask("What does this repository do?")
    assert res["ok"] is False


def test_frontend_copilot_markers_exist():
    app_js = Path(__file__).resolve().parents[1] / "static" / "app.js"
    text = app_js.read_text(encoding="utf-8")
    for marker in (
        "sendCopilotQuestion",
        "/api/copilot/ask",
        "renderCopilotAnswer",
        "nodeCopilotQuestions",
        "toggleGraphEdges",
    ):
        assert marker in text
