"""Phase 133 — Semantic and architecture-symbol impact target resolution."""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional, Set, Tuple

# Concept phrases (longest match first in resolver) -> path keyword hints.
CONCEPT_TARGET_MAP: Dict[str, Dict[str, Any]] = {
    "websocket support": {
        "keywords": ("websocket_api", "components/websocket", "websocket", "/ws.py"),
        "symbols": ("websocket_api", "WebSocketHandler", "async_handle"),
        "label": "websocket support",
    },
    "websocket": {
        "keywords": ("websocket_api", "components/websocket", "websocket"),
        "symbols": ("websocket_api", "WebSocketHandler"),
        "label": "websocket support",
    },
    "event bus": {
        "keywords": ("homeassistant/core.py", "/core.py", "helpers/event.py", "eventbus"),
        "symbols": ("EventBus", "async_fire", "async_listen"),
        "label": "event bus",
    },
    "event_bus": {
        "keywords": ("homeassistant/core.py", "/core.py", "helpers/event.py"),
        "symbols": ("EventBus", "async_fire", "async_listen"),
        "label": "event bus",
    },
    "authentication": {
        "keywords": ("/auth/", "auth_store", "auth_provider", "permissions"),
        "symbols": ("AuthStore", "auth_provider", "AuthProvider"),
        "label": "authentication",
    },
    "auth": {
        "keywords": ("/auth/", "auth_store", "auth_provider"),
        "symbols": ("AuthStore", "auth_provider"),
        "label": "authentication",
    },
    "automation": {
        "keywords": ("components/automation", "/automation/"),
        "symbols": ("async_setup_entry", "Automation"),
        "label": "automations",
    },
    "automations": {
        "keywords": ("components/automation", "/automation/"),
        "symbols": ("Automation",),
        "label": "automations",
    },
    "recorder": {
        "keywords": ("components/recorder", "/recorder/"),
        "symbols": ("Recorder", "async_setup_entry"),
        "label": "recorder/database",
    },
    "database": {
        "keywords": ("components/recorder", "/recorder/", "database", "storage"),
        "symbols": ("Recorder",),
        "label": "recorder/database",
    },
    "config entries": {
        "keywords": ("config_entries.py", "config_entry"),
        "symbols": ("ConfigEntry", "ConfigEntries"),
        "label": "config entries",
    },
    "config entry": {
        "keywords": ("config_entries.py", "config_entry"),
        "symbols": ("ConfigEntry",),
        "label": "config entries",
    },
    "state machine": {
        "keywords": ("/core.py", "statemachine", "state_machine"),
        "symbols": ("StateMachine",),
        "label": "state machine",
    },
}

# Generalizable architecture symbols (Home Assistant + similar async platforms).
ARCHITECTURE_SYMBOL_PATTERNS: Dict[str, Tuple[str, ...]] = {
    "event_bus": ("EventBus", "async_fire", "async_listen"),
    "websocket": ("websocket_api", "WebSocket", "websocket"),
    "config_entry": ("ConfigEntry", "async_setup_entry", "async_unload_entry"),
    "dispatcher": ("dispatcher_send", "dispatcher_connect"),
    "service_registry": ("ServiceRegistry", "async_register"),
    "state_machine": ("StateMachine",),
    "async_core": ("async_create_task", "async_add_executor_job"),
}


def _norm(p: str) -> str:
    return (p or "").replace("\\", "/").strip()


def _fan_in_map(graph: Dict[str, Any]) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for edge in graph.get("edges", []):
        if edge.get("type") != "imports" or not edge.get("resolved"):
            continue
        dst = edge.get("to")
        if dst:
            counts[dst] = counts.get(dst, 0) + 1
    return counts


def _score_module(
    path: str,
    *,
    keywords: Tuple[str, ...],
    fan_in: int,
    symbol_hits: int = 0,
) -> int:
    pl = _norm(path).lower()
    hits = sum(2 for k in keywords if k.lower() in pl)
    return hits * 100 + symbol_hits * 40 + fan_in


def resolve_concept_target(
    nodes: Dict[str, Dict[str, Any]],
    target: str,
    graph: Optional[Dict[str, Any]] = None,
    *,
    evidence_store: Optional[Dict[str, Any]] = None,
) -> Optional[Tuple[str, Dict[str, Any], str, List[str]]]:
    """Map a natural-language concept to the best module node + candidate paths."""
    low = " " + _norm(target).lower() + " "
    fan_in = _fan_in_map(graph or {})

    symbol_paths: Set[str] = set()
    if evidence_store:
        sym_index = (evidence_store.get("symbol_index") or {}).get("symbols") or []
        for entry in sym_index:
            name = str(entry.get("name") or "")
            qual = str(entry.get("qualname") or "")
            blob = f"{name} {qual}"
            for patterns in ARCHITECTURE_SYMBOL_PATTERNS.values():
                if any(p in blob for p in patterns):
                    fp = entry.get("file_path")
                    if fp:
                        symbol_paths.add(_norm(fp))

    for key in sorted(CONCEPT_TARGET_MAP, key=len, reverse=True):
        if key not in low:
            continue
        spec = CONCEPT_TARGET_MAP[key]
        kws = tuple(spec.get("keywords") or ())
        syms = tuple(spec.get("symbols") or ())
        scored: List[Tuple[int, str, Dict[str, Any]]] = []
        for nid, n in nodes.items():
            p = _norm(n.get("path"))
            pl = p.lower()
            kw_hits = sum(1 for k in kws if k.lower() in pl)
            sym_hits = sum(1 for s in syms if s in (n.get("dotted") or "") or s.lower() in pl)
            if p in symbol_paths:
                sym_hits += 2
            if not kw_hits and not sym_hits:
                continue
            score = _score_module(p, keywords=kws, fan_in=fan_in.get(nid, 0), symbol_hits=sym_hits)
            scored.append((score, nid, n))
        if scored:
            scored.sort(key=lambda x: -x[0])
            best_nid, best_node = scored[0][1], scored[0][2]
            candidates = [_norm(n["path"]) for _, _, n in scored[:16]]
            return best_nid, best_node, str(spec.get("label") or key), candidates
    return None


def resolve_architecture_symbol(
    symbol: str,
    nodes: Dict[str, Dict[str, Any]],
    evidence_store: Optional[Dict[str, Any]] = None,
) -> List[str]:
    """Resolve a class/function pattern name to repository file paths."""
    paths: List[str] = []
    needle = (symbol or "").strip()
    if not needle:
        return paths

    if evidence_store:
        for entry in (evidence_store.get("symbol_index") or {}).get("symbols") or []:
            name = str(entry.get("name") or "")
            qual = str(entry.get("qualname") or "")
            if needle in name or needle in qual:
                fp = entry.get("file_path")
                if fp:
                    paths.append(_norm(fp))

    low = needle.lower()
    for n in nodes.values():
        p = _norm(n.get("path"))
        if low in p.lower() or low in (n.get("dotted") or "").lower():
            paths.append(p)
    return list(dict.fromkeys(paths))
