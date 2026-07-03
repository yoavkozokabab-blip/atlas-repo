"""Semantic and architecture-symbol impact target resolution."""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional, Set, Tuple

from .concept_lexicon import LEXICON, match_concept, score_module_for_concept

# Concept phrase -> resolution spec (longest match wins).
CONCEPT_TARGET_MAP: Dict[str, Dict[str, Any]] = {
    "websocket support": {
        "keywords": ("websocket_api", "components/websocket_api", "websocket", "/ws.py"),
        "symbols": ("websocket_api", "WebSocketAPI", "WebSocketHandler", "async_handle"),
        "anchor_paths": ("components/websocket_api",),
        "related_paths": ("/auth/", "session"),
        "label": "websocket support",
    },
    "websocket": {
        "keywords": ("websocket_api", "components/websocket_api", "websocket"),
        "symbols": ("websocket_api", "WebSocketAPI", "WebSocketHandler"),
        "anchor_paths": ("components/websocket_api",),
        "related_paths": ("/auth/", "session"),
        "label": "websocket support",
    },
    "event bus": {
        "keywords": ("homeassistant/core.py", "/core.py", "helpers/event.py", "eventbus"),
        "symbols": ("EventBus", "async_fire", "async_listen", "async_listen_once"),
        "anchor_paths": ("homeassistant/core.py", "helpers/event.py"),
        "related_paths": ("components/automation", "helpers/service"),
        "label": "event bus",
    },
    "event_bus": {
        "keywords": ("homeassistant/core.py", "/core.py", "helpers/event.py"),
        "symbols": ("EventBus", "async_fire", "async_listen"),
        "anchor_paths": ("homeassistant/core.py", "helpers/event.py"),
        "related_paths": ("components/automation", "helpers/service"),
        "label": "event bus",
    },
    "service registry": {
        "keywords": ("helpers/service.py", "/services.py", "serviceregistry", "service_registry"),
        "symbols": ("ServiceRegistry", "async_register", "async_call", "async_services"),
        "anchor_paths": ("helpers/service.py", "homeassistant/helpers/service.py"),
        "label": "service registry",
    },
    "service_registry": {
        "keywords": ("helpers/service.py", "serviceregistry"),
        "symbols": ("ServiceRegistry", "async_register"),
        "anchor_paths": ("helpers/service.py",),
        "label": "service registry",
    },
    "authentication": {
        "keywords": ("/auth/", "auth_store", "auth_provider", "permissions"),
        "symbols": ("AuthStore", "AuthProvider", "auth_provider", "async_validate_access_token"),
        "anchor_paths": ("homeassistant/auth/", "/auth/"),
        "label": "authentication",
    },
    "auth": {
        "keywords": ("/auth/", "auth_store", "auth_provider"),
        "symbols": ("AuthStore", "AuthProvider", "auth_provider"),
        "anchor_paths": ("homeassistant/auth/", "/auth/"),
        "label": "authentication",
    },
    "automation": {
        "keywords": ("components/automation", "/automation/"),
        "symbols": ("Automation", "async_setup_entry", "async_turn_on"),
        "anchor_paths": ("components/automation",),
        "label": "automations",
    },
    "automations": {
        "keywords": ("components/automation", "/automation/"),
        "symbols": ("Automation",),
        "anchor_paths": ("components/automation",),
        "label": "automations",
    },
    "recorder": {
        "keywords": ("components/recorder", "/recorder/"),
        "symbols": ("Recorder", "async_setup", "get_instance", "purge"),
        "anchor_paths": ("components/recorder",),
        "label": "recorder/database",
    },
    "database": {
        "keywords": ("components/recorder", "/recorder/", "database", "storage"),
        "symbols": ("Recorder",),
        "anchor_paths": ("components/recorder",),
        "label": "recorder/database",
    },
    "config entries": {
        "keywords": ("config_entries.py", "config_entry"),
        "symbols": ("ConfigEntry", "ConfigEntries", "async_setup_entry", "async_unload_entry"),
        "anchor_paths": ("config_entries.py",),
        "label": "config entries",
    },
    "config entry": {
        "keywords": ("config_entries.py", "config_entry"),
        "symbols": ("ConfigEntry", "ConfigEntries"),
        "anchor_paths": ("config_entries.py",),
        "label": "config entries",
    },
    "state machine": {
        "keywords": ("/core.py", "statemachine", "state_machine"),
        "symbols": ("StateMachine", "async_set", "async_available"),
        "anchor_paths": ("homeassistant/core.py", "/core.py"),
        "label": "state machine",
    },
    "state_machine": {
        "keywords": ("/core.py", "statemachine"),
        "symbols": ("StateMachine",),
        "anchor_paths": ("homeassistant/core.py",),
        "label": "state machine",
    },
}

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


def _load_symbol_index(evidence_store: Optional[Dict[str, Any]]):
    if not evidence_store:
        return None
    raw = evidence_store.get("symbol_index")
    if not raw:
        return None
    try:
        from atlas_desktop.evidence_engine.symbol_index import SymbolIndex

        return SymbolIndex.from_dict(raw)
    except Exception:
        return None


def _symbols_for_patterns(
    evidence_store: Optional[Dict[str, Any]],
    patterns: Tuple[str, ...],
) -> List[Dict[str, Any]]:
    idx = _load_symbol_index(evidence_store)
    if not idx or not patterns:
        return []
    hits = idx.find_in_source(patterns)
    out: List[Dict[str, Any]] = []
    seen: Set[Tuple[str, str]] = set()
    for rec in hits:
        key = (rec.file_path, rec.qualname or rec.name)
        if key in seen:
            continue
        seen.add(key)
        out.append(
            {
                "name": rec.name,
                "qualname": rec.qualname or rec.name,
                "file_path": _norm(rec.file_path),
                "line": rec.line,
                "kind": rec.kind,
            }
        )
    return out


def _match_concept_key(query: str) -> Optional[str]:
    low = " " + _norm(query).lower() + " "
    for key in sorted(CONCEPT_TARGET_MAP, key=len, reverse=True):
        if f" {key} " in low or low.strip() == key:
            return key
    return None


def _score_module_path(
    path: str,
    *,
    keywords: Tuple[str, ...],
    anchor_paths: Tuple[str, ...],
    fan_in: int,
    symbol_files: Set[str],
    is_anchor: bool,
) -> int:
    # Phase 134.2 — wrap the path in slashes so segment-anchored keywords like
    # "/auth/" match BOTH nested layouts (homeassistant/auth/__init__.py) and
    # top-level packages (auth/middleware.py). Previously a leading-slash keyword
    # silently failed on top-level-package repos.
    pl = f"/{_norm(path).lower()}/"
    kw_hits = sum(2 for k in keywords if k.lower() in pl)
    anchor_hits = sum(4 for a in anchor_paths if a.lower() in pl)
    sym_bonus = 80 if path in symbol_files else 0
    anchor_bonus = 120 if is_anchor else 0
    return kw_hits * 10 + anchor_hits + sym_bonus + anchor_bonus + fan_in


def resolve_semantic_target(
    nodes: Dict[str, Dict[str, Any]],
    query: str,
    graph: Optional[Dict[str, Any]] = None,
    *,
    evidence_store: Optional[Dict[str, Any]] = None,
) -> Optional[Dict[str, Any]]:
    """Resolve a natural-language architecture concept to real modules + symbols."""
    key = _match_concept_key(query)
    if not key:
        # Phase 137 — fall back to the framework-agnostic lexicon so concepts not
        # in the HA-tuned catalogue still resolve from the repo's own structure.
        return resolve_generic_concept(nodes, query, graph, evidence_store=evidence_store)

    spec = CONCEPT_TARGET_MAP[key]
    kws = tuple(spec.get("keywords") or ())
    syms = tuple(spec.get("symbols") or ())
    anchors = tuple(spec.get("anchor_paths") or ())
    related = tuple(spec.get("related_paths") or ())
    label = str(spec.get("label") or key)

    fan_in = _fan_in_map(graph or {})
    symbol_records = _symbols_for_patterns(evidence_store, syms)
    symbol_files = {_norm(s["file_path"]) for s in symbol_records if s.get("file_path")}

    scored: List[Tuple[int, str, Dict[str, Any]]] = []
    seen_paths: Set[str] = set()
    # Phase 134.2 — when a concept has path keywords/anchors, a module qualifies
    # only via a PATH signal (keyword/anchor/related). Symbol hits are a tiebreak
    # bonus, NOT a qualifier. Concept symbols often include ubiquitous lifecycle
    # methods (async_setup_entry, async_register) that match every integration; a
    # symbol-only qualifier let those flood out the real target (e.g. recorder /
    # config_entries resolving to random components).
    has_path_signals = bool(kws or anchors or related)

    for nid, n in nodes.items():
        p = _norm(n.get("path"))
        if not p:
            continue
        pl = f"/{p.lower()}/"  # slash-wrapped: segment-anchored keywords match any layout
        kw_hit = any(k.lower() in pl for k in kws)
        anchor_hit = any(a.lower() in pl for a in anchors)
        sym_hit = p in symbol_files
        rel_hit = any(r.lower() in pl for r in related)
        path_signal = kw_hit or anchor_hit or rel_hit
        qualifies = path_signal or (sym_hit and not has_path_signals)
        if not qualifies:
            continue
        # Symbol-index membership only confers the strong anchor bonus when it is
        # the ONLY available signal (no path keywords for this concept).
        is_anchor = anchor_hit or (sym_hit and not has_path_signals)
        score = _score_module_path(
            p,
            keywords=kws,
            anchor_paths=anchors,
            fan_in=fan_in.get(nid, 0),
            symbol_files=symbol_files,
            is_anchor=is_anchor,
        )
        if rel_hit and not is_anchor:
            score = max(score, 40)
        scored.append((score, nid, n))
        seen_paths.add(p)

    # Fall back to symbol-only files (not in graph) ONLY when there were no
    # path-signal candidates — i.e. the concept could not be located by path.
    if not scored:
        for fp in symbol_files:
            if fp in seen_paths:
                continue
            scored.append((90, fp, {"path": fp, "dotted": "", "id": fp}))

    if not scored and not symbol_records:
        return None

    scored.sort(key=lambda x: (-x[0], _norm(x[2].get("path"))))
    modules_out: List[Dict[str, Any]] = []
    for score, nid, n in scored[:24]:
        path = _norm(n.get("path"))
        modules_out.append(
            {
                "path": path,
                "node_id": nid if nid in nodes else None,
                "dotted": n.get("dotted") or "",
                "score": score,
                "fan_in": fan_in.get(nid, 0) if nid in nodes else 0,
                "is_anchor": any(a.lower() in path.lower() for a in anchors) or path in symbol_files,
            }
        )

    primary = modules_out[0] if modules_out else {}
    primary_nid = primary.get("node_id") or primary.get("path")
    primary_node = nodes.get(primary_nid, {"path": primary.get("path"), "dotted": primary.get("dotted"), "id": primary_nid})

    return {
        "concept": key,
        "label": label,
        "query": query,
        "primary_path": primary.get("path") or "",
        "primary_node_id": primary_nid,
        "primary_node": primary_node,
        "modules": modules_out,
        "module_paths": [m["path"] for m in modules_out if m.get("path")],
        "symbols": symbol_records[:32],
        "symbol_names": sorted({s["qualname"] for s in symbol_records}),
        "related_paths": list(related),
    }


def _concept_label(concept_id: str) -> str:
    return concept_id.replace("_", " ")


# Minimum score for a module to count as a generic-concept match (a filename
# word or directory hit). Below this the signal is too weak to be trustworthy.
_GENERIC_MIN_SCORE = 50


def resolve_generic_concept(
    nodes: Dict[str, Dict[str, Any]],
    query: str,
    graph: Optional[Dict[str, Any]] = None,
    *,
    evidence_store: Optional[Dict[str, Any]] = None,
) -> Optional[Dict[str, Any]]:
    """Phase 137 — resolve a cross-cutting concept from the repository's OWN
    structure (filenames, directories, mined symbols). Framework-agnostic: a
    concept resolves only if matching modules actually exist, so repos that lack
    a concept honestly resolve to nothing."""
    concept_id = match_concept(query)
    if not concept_id:
        return None
    spec = LEXICON[concept_id]
    label = _concept_label(concept_id)
    syms = tuple(spec.get("symbols") or ())

    fan_in = _fan_in_map(graph or {})
    symbol_records = _symbols_for_patterns(evidence_store, syms)
    symbol_files = {_norm(s["file_path"]) for s in symbol_records if s.get("file_path")}

    scored: List[Tuple[int, str, Dict[str, Any]]] = []
    for nid, n in nodes.items():
        p = _norm(n.get("path"))
        if not p:
            continue
        score = score_module_for_concept(
            p, spec, symbol_file=(p in symbol_files), fan_in=fan_in.get(nid, 0)
        )
        if score >= _GENERIC_MIN_SCORE:
            scored.append((score, nid, n))

    # Symbol-only files (not in the module graph) when nothing matched by path.
    if not scored and symbol_files:
        for fp in symbol_files:
            scored.append((70, fp, {"path": fp, "dotted": "", "id": fp}))

    if not scored:
        return None

    scored.sort(key=lambda x: (-x[0], _norm(x[2].get("path"))))
    modules_out: List[Dict[str, Any]] = []
    for score, nid, n in scored[:24]:
        path = _norm(n.get("path"))
        modules_out.append({
            "path": path,
            "node_id": nid if nid in nodes else None,
            "dotted": n.get("dotted") or "",
            "score": score,
            "fan_in": fan_in.get(nid, 0) if nid in nodes else 0,
            "is_anchor": score >= 110 or path in symbol_files,
        })

    # Confidence reflects how strong the strongest signal is (a filename match is
    # high-confidence; a weak directory-only hit is low).
    top = modules_out[0]["score"] if modules_out else 0
    confidence = "high" if top >= 110 else ("medium-high" if top >= 70 else "medium")

    primary = modules_out[0] if modules_out else {}
    primary_nid = primary.get("node_id") or primary.get("path")
    primary_node = nodes.get(
        primary_nid,
        {"path": primary.get("path"), "dotted": primary.get("dotted"), "id": primary_nid},
    )
    return {
        "concept": concept_id,
        "label": label,
        "query": query,
        "primary_path": primary.get("path") or "",
        "primary_node_id": primary_nid,
        "primary_node": primary_node,
        "modules": modules_out,
        "module_paths": [m["path"] for m in modules_out if m.get("path")],
        "symbols": symbol_records[:32],
        "symbol_names": sorted({s["qualname"] for s in symbol_records}),
        "related_paths": [],
        "confidence": confidence,
        "generic": True,
    }


def find_symbols(
    evidence_store: Optional[Dict[str, Any]],
    patterns: Tuple[str, ...],
) -> List[Dict[str, Any]]:
    """Public wrapper for symbol lookup used by impact engine."""
    return _symbols_for_patterns(evidence_store, patterns)


def resolve_concept_target(
    nodes: Dict[str, Dict[str, Any]],
    target: str,
    graph: Optional[Dict[str, Any]] = None,
    *,
    evidence_store: Optional[Dict[str, Any]] = None,
) -> Optional[Tuple[str, Dict[str, Any], str, List[str]]]:
    """Backward-compatible wrapper → (node_id, node, label, candidate_paths)."""
    payload = resolve_semantic_target(nodes, target, graph, evidence_store=evidence_store)
    if not payload:
        return None
    nid = payload["primary_node_id"]
    node = payload["primary_node"]
    if nid not in nodes and payload["primary_path"]:
        found = next(
            ((i, n) for i, n in nodes.items() if _norm(n.get("path")) == payload["primary_path"]),
            None,
        )
        if found:
            nid, node = found
    candidates = list(payload.get("module_paths") or [])
    return nid, node, payload["label"], candidates


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

    for rec in _symbols_for_patterns(evidence_store, (needle,)):
        fp = rec.get("file_path")
        if fp:
            paths.append(_norm(fp))

    low = needle.lower()
    for n in nodes.values():
        p = _norm(n.get("path"))
        if low in p.lower() or low in (n.get("dotted") or "").lower():
            paths.append(p)
    return list(dict.fromkeys(paths))
