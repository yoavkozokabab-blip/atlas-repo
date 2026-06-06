"""Phase 174F — final two ship blockers + 174E attack suite replay."""
from __future__ import annotations

import base64
import io
import json
import os
import sys
import tempfile
import threading
import zipfile
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from jarvis_desktop import api
from jarvis_desktop import repository_memory as rm
from jarvis_desktop import server
from jarvis_desktop.install_support import _redact_support_text


def _fresh() -> None:
    api._STATE.clear()
    api._STATE.update({
        "path": None, "scan": None, "graph": None, "index": None, "risks": None,
        "demo_mode": False, "last_scope": {"mode": "entire_repo"},
        "scan_cache": {}, "scan_job": {"id": None, "cancelled": False, "stage": "idle"},
        "session_export": None, "repository_memory": None, "_current_memory": None,
    })


def _status(result: dict) -> str | None:
    return result.get("status") or result.get("code")


def _module_node_id(graph: dict, path: str) -> str:
    return next(
        n["id"] for n in graph["nodes"] if n.get("path") == path and n.get("type") == "module"
    )


def _go_shallow_repo(tmp_path: Path, *, rich_helper: bool = True) -> Path:
    root = tmp_path / "gorepo"
    (root / "cmd/server").mkdir(parents=True)
    (root / "pkg/events").mkdir(parents=True)
    (root / "hack").mkdir(parents=True)
    (root / "cmd/server/main.go").write_text("package main\nfunc main() {}\n", encoding="utf-8")
    (root / "pkg/events/bus.go").write_text("package events\n", encoding="utf-8")
    body = "def helper():\n    return 1\n" if rich_helper else "x = 1\n"
    (root / "hack/boilerplate.py").write_text(body, encoding="utf-8")
    return root


# --- Blocker 1: Build/Investigation parity on shallow Go repo ---

def test_a7_build_and_investigation_both_refuse_shallow_go(tmp_path):
    _fresh()
    root = _go_shallow_repo(tmp_path, rich_helper=True)
    assert api.scan_repository(str(root))["ok"]
    build = api.plan_change("add event bus tracing")
    inv = api.investigate_symptom("why are duplicate events being fired")
    assert build.get("ok") is False
    assert inv.get("ok") is False
    assert build.get("status") in ("insufficient_evidence", "unsupported_language_limited")
    assert inv.get("status") in ("insufficient_evidence", "unsupported_language_limited")
    assert build.get("confidence") == "low"
    assert inv.get("confidence") == "low"


def test_exact_import_evidence_still_allows_on_weak_label(tmp_path):
    _fresh()
    root = tmp_path / "py"
    root.mkdir()
    (root / "core.py").write_text("def handler():\n    return 1\n", encoding="utf-8")
    (root / "api.py").write_text("from core import handler\n", encoding="utf-8")
    assert api.scan_repository(str(root))["ok"]
    target = "core.py"
    graph = api._STATE["graph"]
    api_id = _module_node_id(graph, "api.py")
    core_id = _module_node_id(graph, target)
    api._STATE["graph"]["edges"] = [{"type": "imports", "from": api_id, "to": core_id, "resolved": True}]
    api._STATE["scan"]["graph_health"] = {"label": "unsupported_language_limited"}
    api._STATE["scan"]["file_count"] = 5000
    with patch(
        "jarvis_desktop.planning_engine.plan_change",
        return_value={
            "ok": True,
            "plan": {
                "files_to_inspect_first": [target],
                "repository_evidence": {
                    "file_evidences": [{"path": target, "matching_symbols": ["handler"], "evidence_score": 80}],
                },
            },
        },
    ):
        result = api.plan_change("change core.py")
    assert result.get("ok") is True


# --- Blocker 2: support bundle redaction ---

@pytest.mark.parametrize(
    "sample",
    [
        "Authorization: Bearer TESTTOKEN",
        "Authorization=Bearer TESTTOKEN",
        "api_key=TEST",
        "API_KEY=TEST",
        "token=TEST",
        "access_token=TEST",
        "refresh_token=TEST",
        "Bearer eyJhbGciOiJIUzI1NiJ9.payload.sig",
        "sk-ant-api03-abc123",
        "ghp_abcdefghijklmnopqrst",
        "BEARER_LEAK_ME",
        '{"access_token": "super-secret"}',
    ],
)
def test_redact_token_like_values(sample: str):
    out = _redact_support_text(sample)
    assert "TESTTOKEN" not in out
    assert "super-secret" not in out
    assert "LEAK_ME" not in out
    assert "abc123" not in out
    assert "[REDACTED]" in out


def test_support_bundle_no_secret_leaks(tmp_path, monkeypatch):
    data = tmp_path / "data"
    data.mkdir()
    monkeypatch.setattr("jarvis_desktop.install_support.data_dir", lambda: str(data))
    log = (
        f"Failure at {tmp_path / 'secret'} with SECRET_PHASE174F "
        f"and api_key=LEAK_ME token=LEAK2 Authorization: Bearer TESTTOKEN BEARER_LEAK_ME"
    )
    (data / "launcher.log").write_text(log, encoding="utf-8")
    _fresh()
    (tmp_path / "repo").mkdir()
    (tmp_path / "repo" / "a.py").write_text("x=1\n", encoding="utf-8")
    api.scan_repository(str(tmp_path / "repo"))
    _, bundle = server.dispatch("POST", "/api/system/support-bundle")
    raw = base64.b64decode(bundle["content_base64"])
    with zipfile.ZipFile(io.BytesIO(raw)) as zf:
        blob = zf.read("logs/launcher.log").decode("utf-8")
    assert "LEAK_ME" not in blob
    assert "TESTTOKEN" not in blob
    assert "BEARER_LEAK_ME" not in blob
    assert str(tmp_path / "secret") not in blob


# --- 174E attack suite replay (10 attacks) ---

def test_a1_repo_switch_without_rescan(tmp_path):
    _fresh()
    a = tmp_path / "a"
    b = tmp_path / "b"
    a.mkdir(); b.mkdir()
    (a / "a.py").write_text("x=1\n"); (b / "b.py").write_text("y=2\n")
    api.scan_repository(str(a))
    api.select_repository(str(b))
    assert _status(api.plan_change("x")) == "requires_rescan"
    assert _status(api.investigate_symptom("y")) == "requires_rescan"
    assert _status(api.change_impact_simulation("b.py")) == "requires_rescan"
    assert _status(api.context_export()) == "requires_rescan"


def test_a2_edit_scanned_file_export(tmp_path):
    _fresh()
    root = tmp_path / "r"
    root.mkdir()
    (root / "main.py").write_text("x=1\n", encoding="utf-8")
    api.scan_repository(str(root))
    (root / "main.py").write_text("x=9\n", encoding="utf-8")
    assert api.context_export().get("ok") is False
    assert api.session_export_packet().get("ok") is False


def test_a3_git_head_changed_export(tmp_path):
    _fresh()
    root = tmp_path / "gitr"
    root.mkdir()
    (root / "main.py").write_text("x=1\n")
    (root / ".git").mkdir()
    (root / ".git/HEAD").write_text("ref: refs/heads/main\n")
    refs = root / ".git/refs/heads"
    refs.mkdir(parents=True)
    (refs / "main").write_text("aaa\n")
    api.scan_repository(str(root))
    (refs / "main").write_text("bbb\n")
    assert api.context_export().get("status") == "stale_git_head_changed"


def test_a4_late_file_outside_2500_export(tmp_path):
    _fresh()
    root = tmp_path / "big"
    root.mkdir()
    for i in range(2510):
        d = root / f"m{i}"
        d.mkdir()
        (d / "f.py").write_text(f"v{i}=1\n", encoding="utf-8")
    (root / "z").mkdir(exist_ok=True)
    (root / "z/late.py").write_text("late=1\n", encoding="utf-8")
    api.scan_repository(str(root))
    (root / "z/late.py").write_text("late=9\n", encoding="utf-8")
    exp = api.context_export()
    assert exp.get("ok") is False
    assert exp.get("status") == "stale_outside_plan"


def test_a5_tampered_memory_json_reload(tmp_path):
    _fresh()
    root = tmp_path / "tamper"
    root.mkdir()
    (root / "a.py").write_text("x=1\n", encoding="utf-8")
    api.scan_repository(str(root))
    data_dir = str(tmp_path / "mem")
    rm.update_after_scan(api._STATE, data_dir, generated_by_version="t")
    mem_path = Path(rm._memory_path(str(root), data_dir))
    data = json.loads(mem_path.read_text(encoding="utf-8"))
    data["top_hubs"] = [{"module": "MALICIOUS_FAKE_HUB", "fan_in": 999}]
    data["memory_hash"] = "bad"
    mem_path.write_text(json.dumps(data), encoding="utf-8")
    _fresh()
    api.scan_repository(str(root))
    pkt = api.session_export_packet()
    assert "MALICIOUS_FAKE_HUB" not in (pkt.get("text") or "")


def test_a6_forced_memory_write_failure(tmp_path):
    _fresh()
    root = tmp_path / "mf"
    root.mkdir()
    (root / "a.py").write_text("x=1\n")
    with patch.object(rm, "persist", return_value=("", False, "disk full")):
        api.scan_repository(str(root))
    pkt = api.session_export_packet()
    assert pkt.get("memory_persistence_status") == "failed"
    assert api.beta_diagnostics()["trust_integrity"]["memory_persistence_status"] == "failed"


def test_a8_concurrent_scan_select_export(tmp_path):
    _fresh()
    a = tmp_path / "a"
    b = tmp_path / "b"
    a.mkdir(); b.mkdir()
    (a / "a.py").write_text("x=1\n"); (b / "b.py").write_text("y=2\n")
    api.scan_repository(str(a))
    leaks = []
    barrier = threading.Barrier(2)

    def work():
        barrier.wait()
        for _ in range(8):
            api.select_repository(str(b))
            api.scan_repository(str(b))
            pkt = api.session_export_packet()
            if pkt.get("ok"):
                sp = (api._STATE.get("scan") or {}).get("repo_path")
                if sp and os.path.abspath(sp) != os.path.abspath(str(b)):
                    leaks.append(sp)

    t1 = threading.Thread(target=work)
    t2 = threading.Thread(target=work)
    t1.start(); t2.start()
    t1.join(); t2.join()
    assert not leaks


def test_a9_export_replay_after_repo_change(tmp_path):
    _fresh()
    a = tmp_path / "a"
    b = tmp_path / "b"
    a.mkdir(); b.mkdir()
    (a / "a.py").write_text("x=1\n"); (b / "b.py").write_text("y=2\n")
    api.scan_repository(str(a))
    old = api.session_export_packet()
    api.select_repository(str(b))
    new = api.session_export_packet()
    assert new.get("ok") is False
    assert old.get("scan_id")
    assert old.get("scan_signature")
    assert "rescan or refresh" in (old.get("replay_warning") or old.get("text") or "").lower()


def test_a10_support_bundle_trust_redaction(tmp_path, monkeypatch):
    data = tmp_path / "data"
    data.mkdir()
    monkeypatch.setattr("jarvis_desktop.install_support.data_dir", lambda: str(data))
    (data / "launcher.log").write_text(
        f"Failure at {tmp_path / 'abs'} SECRET_X api_key=LEAK_ME token=LEAK Authorization: Bearer X BEARER_LEAK_ME\n",
        encoding="utf-8",
    )
    _fresh()
    (tmp_path / "r").mkdir()
    (tmp_path / "r" / "a.py").write_text("x=1\n")
    api.scan_repository(str(tmp_path / "r"))
    _, bundle = server.dispatch("POST", "/api/system/support-bundle")
    raw = base64.b64decode(bundle["content_base64"])
    with zipfile.ZipFile(io.BytesIO(raw)) as zf:
        diag = zf.read("diagnostics.json").decode("utf-8")
        log = zf.read("logs/launcher.log").decode("utf-8")
    assert "trust_integrity" in diag
    assert "LEAK_ME" not in log
    assert "BEARER_LEAK_ME" not in log
    assert str(tmp_path / "abs") not in log
