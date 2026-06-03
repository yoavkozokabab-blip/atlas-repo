"""Tests for semantic target resolution (Phase 134+)."""

from __future__ import annotations

from jarvis_desktop.impact_engine import target_resolver as tr
from jarvis_desktop.impact_engine.engine import analyze_impact


def _ha_nodes():
    return {
        "core": {"id": "core", "type": "module", "path": "homeassistant/core.py", "dotted": "homeassistant.core"},
        "event": {"id": "event", "type": "module", "path": "homeassistant/helpers/event.py", "dotted": "homeassistant.helpers.event"},
        "ws": {"id": "ws", "type": "module", "path": "homeassistant/components/websocket_api/__init__.py", "dotted": "homeassistant.components.websocket_api"},
        "auth": {"id": "auth", "type": "module", "path": "homeassistant/auth/auth_store.py", "dotted": "homeassistant.auth.auth_store"},
        "cfg": {"id": "cfg", "type": "module", "path": "homeassistant/config_entries.py", "dotted": "homeassistant.config_entries"},
        "auto": {"id": "auto", "type": "module", "path": "homeassistant/components/automation/__init__.py"},
        "rec": {"id": "rec", "type": "module", "path": "homeassistant/components/recorder/__init__.py"},
        "svc": {"id": "svc", "type": "module", "path": "homeassistant/helpers/service.py"},
        "consumer": {"id": "consumer", "type": "module", "path": "homeassistant/components/light/__init__.py"},
    }


def _ha_graph():
    return {
        "nodes": list(_ha_nodes().values()),
        "edges": [
            {"type": "imports", "from": "consumer", "to": "core", "resolved": True},
            {"type": "imports", "from": "ws", "to": "auth", "resolved": True},
            {"type": "imports", "from": "auto", "to": "event", "resolved": True},
        ],
    }


def _evidence_store():
    sym = {
        "name": "EventBus",
        "qualname": "EventBus",
        "kind": "class",
        "line": 10,
        "decorators": [],
        "bases": [],
        "file_path": "homeassistant/core.py",
    }
    return {
        "symbol_index": {
            "project_root": "/repo",
            "files": {
                "homeassistant/core.py": {
                    "symbols": [
                        {**sym, "file_path": "homeassistant/core.py"},
                        {"name": "async_fire", "qualname": "EventBus.async_fire", "kind": "method", "line": 20, "decorators": [], "bases": [], "file_path": "homeassistant/core.py"},
                        {"name": "StateMachine", "qualname": "StateMachine", "kind": "class", "line": 30, "decorators": [], "bases": [], "file_path": "homeassistant/core.py"},
                    ],
                    "imports": [],
                    "calls": [],
                },
                "homeassistant/helpers/event.py": {
                    "symbols": [{"name": "async_listen", "qualname": "async_listen", "kind": "function", "line": 5, "decorators": [], "bases": [], "file_path": "homeassistant/helpers/event.py"}],
                    "imports": [],
                    "calls": [],
                },
                "homeassistant/components/websocket_api/__init__.py": {
                    "symbols": [{"name": "WebSocketAPI", "qualname": "WebSocketAPI", "kind": "class", "line": 1, "decorators": [], "bases": [], "file_path": "homeassistant/components/websocket_api/__init__.py"}],
                    "imports": [],
                    "calls": [],
                },
                "homeassistant/config_entries.py": {
                    "symbols": [{"name": "ConfigEntry", "qualname": "ConfigEntry", "kind": "class", "line": 1, "decorators": [], "bases": [], "file_path": "homeassistant/config_entries.py"}],
                    "imports": [],
                    "calls": [],
                },
                "homeassistant/helpers/service.py": {
                    "symbols": [{"name": "ServiceRegistry", "qualname": "ServiceRegistry", "kind": "class", "line": 1, "decorators": [], "bases": [], "file_path": "homeassistant/helpers/service.py"}],
                    "imports": [],
                    "calls": [],
                },
                "homeassistant/auth/auth_store.py": {
                    "symbols": [{"name": "AuthStore", "qualname": "AuthStore", "kind": "class", "line": 1, "decorators": [], "bases": [], "file_path": "homeassistant/auth/auth_store.py"}],
                    "imports": [],
                    "calls": [],
                },
                "homeassistant/components/automation/__init__.py": {
                    "symbols": [{"name": "Automation", "qualname": "Automation", "kind": "class", "line": 1, "decorators": [], "bases": [], "file_path": "homeassistant/components/automation/__init__.py"}],
                    "imports": [],
                    "calls": [],
                },
                "homeassistant/components/recorder/__init__.py": {
                    "symbols": [{"name": "Recorder", "qualname": "Recorder", "kind": "class", "line": 1, "decorators": [], "bases": [], "file_path": "homeassistant/components/recorder/__init__.py"}],
                    "imports": [],
                    "calls": [],
                },
            },
        }
    }


CONCEPTS = (
    "event bus",
    "websocket support",
    "config entries",
    "automation",
    "recorder",
    "auth",
    "service registry",
    "state machine",
)


def test_all_concepts_resolve_modules_and_symbols():
    nodes = _ha_nodes()
    graph = _ha_graph()
    store = _evidence_store()
    for concept in CONCEPTS:
        payload = tr.resolve_semantic_target(nodes, concept, graph, evidence_store=store)
        assert payload, f"failed to resolve {concept!r}"
        assert payload["module_paths"], concept
        assert payload["symbols"], concept
        assert payload["primary_path"]


def test_event_bus_impact_returns_resolved_payload():
    state = {"graph": _ha_graph(), "index": {"files": []}, "evidence_store": _evidence_store()}
    res = analyze_impact("impact of changing the event bus", state)
    assert res.get("ok")
    assert not res.get("mock")
    assert "core.py" in res["target"]
    assert len(res.get("resolved_modules") or []) >= 2
    assert any(s.get("name") == "EventBus" for s in res.get("resolved_symbols") or [])
    assert res.get("architectural_blast_radius", 0) >= 1
    assert "homeassistant/components/light" in " ".join(res.get("direct_impact") or [])


def test_websocket_impact_includes_auth_blast():
    state = {"graph": _ha_graph(), "index": {"files": []}, "evidence_store": _evidence_store()}
    res = analyze_impact("remove websocket support", state)
    assert res.get("ok")
    paths = " ".join((res.get("resolved_modules") or []) + (res.get("affected_files") or [])).lower()
    assert "websocket_api" in paths
    assert any("auth" in p for p in (res.get("resolved_modules") or []))
