"""Phase 174B — user-initiated targeted file refresh (no full-repo rescan).

Updates only changed files Atlas recommended, their graph neighbors, symbols,
and evidence. Never runs automatically.
"""

from __future__ import annotations

import os
import time
from typing import Any, Dict, List, Optional, Set

from builder_core.bug_intelligence import depgraph

from .evidence_engine import EvidenceStore
from .evidence_engine.ast_scanner import scan_python_file
from .evidence_engine.call_graph import CallGraph, build_call_graph
from .evidence_engine.symbol_index import SymbolIndex


def _norm(path: str) -> str:
    return (path or "").replace("\\", "/").strip()


def _module_node_id(path: str) -> str:
    return depgraph.node_id("module", _norm(path))


def _read_file(root: str, rel: str) -> str:
    try:
        with open(os.path.join(root, rel.replace("/", os.sep)), encoding="utf-8-sig", errors="ignore") as fh:
            return fh.read()
    except OSError:
        return ""


def _neighbor_module_paths(graph: Dict[str, Any], paths: List[str]) -> Set[str]:
    """Direct importers/importees of changed modules."""
    target_ids = {_module_node_id(p) for p in paths}
    neighbors: Set[str] = set()
    for edge in graph.get("edges") or []:
        if edge.get("type") != "imports":
            continue
        src = edge.get("from") or ""
        dst = edge.get("to") or ""
        if src in target_ids or dst in target_ids:
            for nid in (src, dst):
                if nid.startswith("module:"):
                    neighbors.add(nid.split(":", 1)[1])
    return neighbors | {_norm(p) for p in paths}


def _update_index_files(index: Dict[str, Any], root: str, paths: List[str]) -> None:
    from . import api as _api
    from builder_core import repository_understanding

    by_path = {_norm(f.get("path", "")): f for f in (index.get("files") or [])}
    for rel in paths:
        rel = _norm(rel)
        abs_path = os.path.join(root, rel.replace("/", os.sep))
        if not os.path.isfile(abs_path):
            continue
        ext = os.path.splitext(rel)[1].lower()
        role = repository_understanding.classify_file_role(rel, ext, project_root=root)
        try:
            size = os.path.getsize(abs_path)
        except OSError:
            continue
        text = _read_file(root, rel) if ext == ".py" and size < 400_000 else ""
        entry = {
            "path": rel,
            "role": role,
            "category": repository_understanding.legacy_category(role, rel),
            "ext": ext,
            "size": size,
            "lines": (text.count("\n") + 1) if text else 0,
        }
        by_path[rel] = entry
    index["files"] = sorted(by_path.values(), key=lambda x: x.get("path", ""))


def _merge_partial_graph(
    graph: Dict[str, Any],
    partial: Dict[str, Any],
    touched_paths: Set[str],
) -> None:
    """Replace nodes/edges for touched modules only."""
    touched_ids = {_module_node_id(p) for p in touched_paths}
    graph["nodes"] = [
        n for n in (graph.get("nodes") or [])
        if not (n.get("type") == "module" and n.get("id") in touched_ids)
    ]
    graph["edges"] = [
        e for e in (graph.get("edges") or [])
        if not (e.get("from") in touched_ids or e.get("to") in touched_ids)
    ]
    existing_ids = {n.get("id") for n in graph["nodes"]}
    for node in partial.get("nodes") or []:
        if node.get("type") == "module" and node.get("id") not in existing_ids:
            graph["nodes"].append(node)
            existing_ids.add(node.get("id"))
    seen = {
        (e.get("type"), e.get("from"), e.get("to"), e.get("line"), e.get("target_module"))
        for e in graph["edges"]
    }
    for edge in partial.get("edges") or []:
        key = (
            edge.get("type"),
            edge.get("from"),
            edge.get("to"),
            edge.get("line"),
            edge.get("target_module"),
        )
        if key not in seen:
            seen.add(key)
            graph["edges"].append(edge)
    stats = depgraph.compute_statistics(
        graph["nodes"],
        graph["edges"],
        graph.get("unresolved") or {"imports_external": [], "calls_unresolved": [], "references_unresolved": []},
    )
    graph["statistics"] = stats


def _refresh_evidence(
    state: Dict[str, Any],
    root: str,
    paths: List[str],
) -> None:
    raw = state.get("evidence_store") or {}
    if not raw:
        return
    store = EvidenceStore.from_dict(raw)
    py_paths = [p for p in paths if _norm(p).endswith(".py")]
    for rel in py_paths:
        rel = _norm(rel)
        if rel in store.symbol_index.files:
            store.symbol_index.remove_file(rel)
        abs_path = os.path.join(root, rel.replace("/", os.sep))
        if os.path.isfile(abs_path):
            store.symbol_index.add_scan(scan_python_file(abs_path, rel))
    store.call_graph = build_call_graph(store.symbol_index, state.get("graph"))
    store.built_at = time.strftime("%Y-%m-%dT%H:%M:%S")
    state["evidence_store"] = store.to_dict()


def refresh_files(state: Dict[str, Any], files: List[str]) -> Dict[str, Any]:
    """User-initiated targeted refresh — never called automatically."""
    from . import repository_memory as rm
    from . import trust_integrity as ti

    scan = state.get("scan") or {}
    path = state.get("path") or scan.get("repo_path")
    graph = state.get("graph")
    index = state.get("index")
    if not scan or not path or not graph or not index:
        return {"ok": False, "error": "Scan required before targeted refresh.", "status": "requires_rescan"}

    root = os.path.abspath(str(path))
    targets = sorted({_norm(f) for f in files if f})
    if not targets:
        return {"ok": False, "error": "No files to refresh.", "status": "no_files"}

    scope = set(_neighbor_module_paths(graph, targets))
    py_scope = sorted(p for p in scope if p.endswith(".py"))
    file_pairs = [(p, _read_file(root, p)) for p in py_scope]
    detail = graph.get("graph_detail") or depgraph.DETAIL_IMPORTS
    partial = depgraph.build_graph_from_files(root, file_pairs, detail=detail)

    _merge_partial_graph(graph, partial, scope)
    _update_index_files(index, root, list(scope))

    ti.update_file_manifest(state, list(scope))
    sig_v2 = ti.compute_signature_v2(
        root,
        scan.get("scope") or state.get("last_scope") or {"mode": "entire_repo"},
        indexed_files=index.get("files"),
        include_content_hash=True,
    )
    scan["signature_v2"] = sig_v2
    scan["cache"] = {**(scan.get("cache") or {}), "signature": sig_v2["signature"]}

    _refresh_evidence(state, root, list(scope))

    gen = int(state.get("refresh_generation") or 0) + 1
    state["refresh_generation"] = gen

    try:
        from . import api as _api
        packet = rm.update_after_scan(
            state,
            _api._desktop_data_dir(),
            generated_by_version=_api.PRODUCT_VERSION,
        )
        new_ref = packet.get("scan_id") or rm.get_memory_ref(state)
        state["active_memory_ref"] = new_ref
        mem = state.get("_current_memory") or {}
        if mem:
            mem["refresh_generation"] = gen
            mem["memory_hash"] = rm.compute_memory_hash(mem)
        wf = state.get("workflow_context") or {}
        if wf:
            wf = dict(wf)
            wf["memory_ref"] = new_ref
            wf["scan_id"] = new_ref
            wf["scan_signature"] = sig_v2.get("signature")
            wf["refresh_generation"] = gen
            wf["refreshed_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            state["workflow_context"] = wf
    except Exception as exc:
        return {
            "ok": False,
            "error": f"Memory update failed after refresh: {exc}",
            "status": "memory_update_failed",
            "refreshed_files": targets,
        }

    staleness = ti.assess_staleness(state)
    return {
        "ok": True,
        "status": "refreshed",
        "refreshed_files": targets,
        "neighbor_files": sorted(scope - set(targets)),
        "refresh_generation": gen,
        "active_memory_ref": state.get("active_memory_ref"),
        "trust_status": staleness,
    }
