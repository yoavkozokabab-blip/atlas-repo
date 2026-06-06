"""Phase 174D — final trust-integrity ship blocker regressions."""
from __future__ import annotations

import base64
import io
import json
import os
import sys
import zipfile
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from jarvis_desktop import api
from jarvis_desktop import repository_memory as rm
from jarvis_desktop.install_support import _redact_support_text, data_dir
from jarvis_desktop import server


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


def _go_shallow_repo(tmp_path: Path) -> Path:
    root = tmp_path / "gorepo"
    (root / "cmd/server").mkdir(parents=True)
    (root / "pkg/events").mkdir(parents=True)
    (root / "hack").mkdir(parents=True)
    (root / "cmd/server/main.go").write_text("package main\nfunc main() {}\n", encoding="utf-8")
    (root / "pkg/events/bus.go").write_text("package events\n", encoding="utf-8")
    (root / "hack/boilerplate.py").write_text("x = 1\n", encoding="utf-8")
    return root


def _k8s_state():
    """Kubernetes-scale shallow graph (24860 files, 3 modules)."""
    modules = [
        "hack/boilerplate/boilerplate.py",
        "hack/verify-flags-underscore.py",
        "staging/src/k8s.io/kubectl/pkg/util/i18n/translations/extract.py",
    ]
    nodes = [
        {"id": f"n{i}", "type": "module", "path": p, "fan_in": 0}
        for i, p in enumerate(modules)
    ]
    return {
        "path": "/kubernetes",
        "scan": {
            "ok": True,
            "repo_name": "kubernetes",
            "repo_path": "/kubernetes",
            "subsystem_count": 0,
            "file_count": 24860,
            "module_count": 3,
            "dependency_edges": 0,
            "top_hubs": [],
            "top_risks": [],
            "graph_health": {"label": "healthy"},
        },
        "graph": {"nodes": nodes, "edges": []},
        "index": {
            "subsystems": [],
            "stats": {"roles": {"production_code": 3}},
            "files": [
                {"path": p, "ext": ".py", "role": "production_code"} for p in modules
            ] + [{"path": "pkg/kubelet/kubelet.go", "ext": ".go", "role": "production_code"}] * 100,
        },
        "risks": {"ranked_modules": []},
        "evidence_store": {
            "symbol_index": {
                "files": {
                    "hack/boilerplate/boilerplate.py": {
                        "symbols": [{"name": "ArgumentParser", "file_path": "hack/boilerplate/boilerplate.py", "line": 1}],
                        "imports": ["argparse"],
                        "calls": [],
                    }
                }
            }
        },
    }


# ---------------------------------------------------------------------------
# Blocker 1 — unsupported / shallow graph Build & Investigation
# ---------------------------------------------------------------------------

def test_go_shallow_build_generic_prompt_refuses(tmp_path):
    _fresh_state()
    root = _go_shallow_repo(tmp_path)
    assert api.scan_repository(str(root))["ok"]
    result = api.plan_change("add event bus tracing")
    assert result.get("ok") is False
    assert result.get("status") in ("unsupported_language_limited", "insufficient_evidence")
    assert result.get("confidence") == "low"
    plan = result.get("plan") or {}
    files = (plan.get("files_to_inspect_first") or []) + (plan.get("files_likely_to_modify") or [])
    if files:
        assert "hack/boilerplate.py" not in files


def test_go_shallow_investigation_generic_prompt_refuses(tmp_path):
    _fresh_state()
    root = _go_shallow_repo(tmp_path)
    assert api.scan_repository(str(root))["ok"]
    result = api.investigate_symptom("why are duplicate events being fired")
    assert result.get("ok") is False
    assert result.get("status") in ("unsupported_language_limited", "insufficient_evidence")
    assert result.get("confidence") == "low"


def test_kubernetes_build_generic_prompt_refuses():
    _fresh_state()
    api._STATE.update(_k8s_state())
    with patch("jarvis_desktop.api._planning_context", return_value={}), patch(
        "jarvis_desktop.planning_engine.plan_change",
        return_value={
            "ok": True,
            "plan": {
                "intent": "tracing",
                "files_to_inspect_first": ["hack/boilerplate/boilerplate.py"],
                "files_likely_to_modify": ["hack/boilerplate/boilerplate.py"],
            },
        },
    ):
        result = api.plan_change("add distributed tracing")
    assert result.get("ok") is False
    assert result.get("status") == "unsupported_language_limited"
    assert result.get("confidence") == "low"


def test_kubernetes_investigation_generic_prompt_refuses():
    _fresh_state()
    api._STATE.update(_k8s_state())
    with patch("jarvis_desktop.api._planning_context", return_value={}), patch(
        "jarvis_desktop.planning_engine.investigate_symptom",
        return_value={
            "ok": True,
            "plan": {
                "likely_modules": ["hack/boilerplate/boilerplate.py"],
                "hypotheses": [{"files_involved": ["hack/boilerplate/boilerplate.py"], "evidence": ["helper only"]}],
            },
        },
    ):
        result = api.investigate_symptom("scheduler pod crashes")
    assert result.get("ok") is False
    assert result.get("status") == "unsupported_language_limited"


def test_exact_file_with_real_graph_evidence_may_succeed(tmp_path):
    _fresh_state()
    root = tmp_path / "pyrepo"
    root.mkdir()
    (root / "core.py").write_text("def handler():\n    return 1\n", encoding="utf-8")
    (root / "api.py").write_text("from core import handler\n", encoding="utf-8")
    assert api.scan_repository(str(root))["ok"]

    target = "core.py"
    graph = api._STATE["graph"]
    api_id = next(n["id"] for n in graph["nodes"] if n.get("path") == "api.py" and n.get("type") == "module")
    core_id = next(n["id"] for n in graph["nodes"] if n.get("path") == target and n.get("type") == "module")
    api._STATE["graph"]["edges"] = [
        {"type": "imports", "from": api_id, "to": core_id, "resolved": True},
    ]
    api._STATE["evidence_store"] = {
        "symbol_index": {
            "files": {
                target: {
                    "symbols": [
                        {"name": "handler", "qualname": "handler", "file_path": target, "line": 1, "kind": "function"},
                        {"name": "helper", "qualname": "helper", "file_path": target, "line": 2, "kind": "function"},
                    ],
                    "imports": [],
                    "calls": [("handler", "helper", 2)],
                }
            }
        }
    }
    api._STATE["scan"]["graph_health"] = {"label": "unsupported_language_limited"}
    api._STATE["scan"]["file_count"] = 5000
    api._STATE["scan"]["module_count"] = 2

    with patch(
        "jarvis_desktop.planning_engine.plan_change",
        return_value={
            "ok": True,
            "plan": {
                "intent": "change",
                "files_to_inspect_first": [target],
                "repository_evidence": {
                    "file_evidences": [
                        {"path": target, "matching_symbols": ["handler"], "evidence_score": 80},
                    ],
                },
            },
        },
    ):
        result = api.plan_change(f"change {target}")
    assert result.get("ok") is True


# ---------------------------------------------------------------------------
# Blocker 2 — memory packet replay / staleness metadata
# ---------------------------------------------------------------------------

def test_memory_export_contains_replay_metadata(tmp_path):
    _fresh_state()
    root = tmp_path / "memrepo"
    root.mkdir()
    (root / "a.py").write_text("x = 1\n", encoding="utf-8")
    assert api.scan_repository(str(root))["ok"]
    pkt = api.session_export_packet()
    assert pkt.get("ok") is True
    text = pkt.get("text") or ""
    assert pkt.get("scan_id")
    assert pkt.get("scan_signature")
    assert "scan_signature:" in text
    assert pkt.get("freshness_status")
    assert "freshness_status:" in text
    assert pkt.get("replay_warning")
    assert "rescan or refresh before reuse" in (pkt.get("replay_warning") or text).lower()


def test_memory_text_includes_scan_signature_and_warning(tmp_path):
    _fresh_state()
    root = tmp_path / "m2"
    root.mkdir()
    (root / "a.py").write_text("a=1\n", encoding="utf-8")
    api.scan_repository(str(root))
    pkt = api.session_export_packet()
    assert "scan_signature:" in pkt["text"]
    assert "replay_warning:" in pkt["text"]


def test_old_memory_ref_rejected_after_refresh(tmp_path):
    _fresh_state()
    root = tmp_path / "m3"
    root.mkdir()
    (root / "a.py").write_text("x=1\n", encoding="utf-8")
    api.scan_repository(str(root))
    with patch(
        "jarvis_desktop.planning_engine.plan_change",
        return_value={"ok": True, "plan": {"files_to_inspect_first": ["a.py"], "files_likely_to_modify": ["a.py"]}},
    ):
        api.plan_change("change")
    old_ref = api._STATE["workflow_context"]["memory_ref"]
    (root / "a.py").write_text("x=9\n", encoding="utf-8")
    assert api.refresh_changed_files().get("ok") is True
    api._STATE["workflow_context"]["memory_ref"] = old_ref
    export = api.context_export()
    assert export.get("ok") is False
    assert export.get("status") == "memory_ref_stale"


# ---------------------------------------------------------------------------
# Blocker 3 — support bundle secret redaction
# ---------------------------------------------------------------------------

def test_redact_api_key_value():
    assert "LEAK_ME" not in _redact_support_text("api_key=LEAK_ME")
    assert "api_key=[REDACTED]" in _redact_support_text("api_key=LEAK_ME")


def test_redact_json_token_field():
    blob = '{"access_token": "super-secret-token", "ok": true}'
    out = _redact_support_text(blob)
    assert "super-secret-token" not in out
    assert "[REDACTED]" in out


def test_redact_bearer_header():
    out = _redact_support_text("Authorization: Bearer eyJhbGciOiJIUzI1NiJ9.payload.sig")
    assert "eyJ" not in out
    assert "[REDACTED]" in out


def test_support_bundle_does_not_contain_leak_me(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "jarvis_desktop.install_support.data_dir",
        lambda: str(tmp_path / "atlasdata"),
    )
    log_dir = tmp_path / "atlasdata"
    log_dir.mkdir(parents=True)
    secret_path = tmp_path / "customer_secret_repo"
    secret_path.mkdir()
    log_line = (
        f"Failure at {secret_path / 'app.py'} with SECRET_PHASE174D_LOG "
        f"and api_key=LEAK_ME Bearer sk-ant-leak-token"
    )
    (log_dir / "launcher.log").write_text(log_line, encoding="utf-8")

    _fresh_state()
    (secret_path / "main.py").write_text("x=1\n", encoding="utf-8")
    api.scan_repository(str(secret_path))

    _, bundle = server.dispatch("POST", "/api/system/support-bundle")
    assert bundle["ok"] is True
    raw = base64.b64decode(bundle["content_base64"])
    with zipfile.ZipFile(io.BytesIO(raw)) as zf:
        blob = zf.read("logs/launcher.log").decode("utf-8")
    assert "LEAK_ME" not in blob
    assert "sk-ant-leak-token" not in blob
    assert "api_key=[REDACTED]" in blob
    assert str(secret_path) not in blob or "[path-redacted]" in blob
