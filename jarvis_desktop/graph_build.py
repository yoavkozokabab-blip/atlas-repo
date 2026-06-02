"""Desktop scan graph build policy — budgets, detail levels, lazy full graph."""

from __future__ import annotations

import os
import time
from typing import Any, Callable, Dict, List, Optional

from builder_core.bug_intelligence import depgraph, jsdepgraph

# Time budgets (seconds) for graph construction during desktop scan.
BUDGET_PRESCAN_MAX_SEC = 5.0
BUDGET_HIERARCHY_IMPORTS_SEC = 60.0
BUDGET_FULL_MODULE_SEC = 180.0
BUDGET_JS_TS_SEC = 55.0

DETAIL_IMPORTS = depgraph.DETAIL_IMPORTS
DETAIL_FULL = depgraph.DETAIL_FULL


def graph_build_plan(*, massive_mode: bool, code_files: int, estimated_modules: int) -> Dict[str, Any]:
    """Choose graph detail level and time budget for a repository scan."""
    if massive_mode or code_files > 2500 or estimated_modules > 2000:
        return {
            "detail": DETAIL_IMPORTS,
            "time_budget_sec": BUDGET_HIERARCHY_IMPORTS_SEC,
            "lazy_full": True,
            "tier": "massive",
        }
    if code_files > 800 or estimated_modules > 600:
        return {
            "detail": DETAIL_FULL,
            "time_budget_sec": BUDGET_FULL_MODULE_SEC,
            "lazy_full": False,
            "tier": "medium",
        }
    return {
        "detail": DETAIL_FULL,
        "time_budget_sec": None,
        "lazy_full": False,
        "tier": "small",
    }


def _language_breakdown(graph: Dict[str, Any]) -> Dict[str, Any]:
    py = ts = js = 0
    for node in graph.get("nodes", []):
        if node.get("type") != "module":
            continue
        lang = node.get("language")
        if lang == "typescript":
            ts += 1
        elif lang == "javascript":
            js += 1
        else:
            py += 1
    return {
        "python_modules": py,
        "typescript_modules": ts,
        "javascript_modules": js,
        "external_package_imports": int(graph.get("external_package_count") or 0),
        "unresolved_imports": int(graph.get("unresolved_import_count") or 0),
    }


def merge_graphs(py_graph: Dict[str, Any], js_graph: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Merge Python depgraph + JS/TS import graphs into one depgraph-shaped payload."""
    if not js_graph or not js_graph.get("nodes"):
        merged = dict(py_graph)
        merged["language_breakdown"] = _language_breakdown(merged)
        return merged

    py_nodes = [n for n in py_graph.get("nodes", []) if n.get("type") != "repository"]
    js_nodes = [n for n in js_graph.get("nodes", []) if n.get("type") != "repository"]
    nodes_by_id: Dict[str, Dict[str, Any]] = {}
    for node in py_nodes + js_nodes:
        nodes_by_id[node["id"]] = node

    repo = py_graph.get("repository_root") or js_graph.get("repository_root")
    repo_nid = depgraph.node_id("repository", str(repo).replace("\\", "/"))
    repo_node = {
        "id": repo_nid,
        "type": "repository",
        "root": str(repo).replace("\\", "/"),
        "python_files": py_graph.get("scope_diagnostics", {}).get("files_kept", 0),
        "javascript_files": js_graph.get("scope_diagnostics", {}).get("files_kept", 0),
    }

    edges: List[Dict[str, Any]] = []
    seen: set = set()
    for edge in list(py_graph.get("edges", [])) + list(js_graph.get("edges", [])):
        key = (
            edge.get("type"),
            edge.get("from"),
            edge.get("to"),
            edge.get("line"),
            edge.get("target_module"),
        )
        if key in seen:
            continue
        seen.add(key)
        edges.append(edge)

    node_list = [repo_node] + [nodes_by_id[k] for k in sorted(nodes_by_id)]
    unresolved = {
        "imports_external": (
            list(py_graph.get("unresolved", {}).get("imports_external", []))
            + list(js_graph.get("unresolved", {}).get("imports_external", []))
        ),
        "calls_unresolved": list(py_graph.get("unresolved", {}).get("calls_unresolved", [])),
        "references_unresolved": list(py_graph.get("unresolved", {}).get("references_unresolved", [])),
    }
    stats = depgraph.compute_statistics(node_list, edges, unresolved)
    merged: Dict[str, Any] = {
        "schema_version": depgraph.GRAPH_SCHEMA_VERSION,
        "repository_root": repo,
        "nodes": node_list,
        "edges": depgraph._dedupe_edges(edges),
        "unresolved": unresolved,
        "statistics": stats,
        "parse_errors": sorted(
            set(py_graph.get("parse_errors", [])) | set(js_graph.get("parse_errors", []))
        ),
        "graph_scope": py_graph.get("graph_scope") or js_graph.get("graph_scope"),
        "graph_detail": py_graph.get("graph_detail") or js_graph.get("graph_detail"),
        "scope_diagnostics": {
            "python": py_graph.get("scope_diagnostics", {}),
            "javascript": js_graph.get("scope_diagnostics", {}),
            "multilang": True,
        },
        "degraded": bool(py_graph.get("degraded")) or bool(js_graph.get("degraded")),
        "jarvis_timed_out": bool(py_graph.get("jarvis_timed_out")) or bool(js_graph.get("jarvis_timed_out")),
        "jarvis_partial": bool(py_graph.get("jarvis_partial")) or bool(js_graph.get("jarvis_partial")),
        "external_package_count": int(js_graph.get("external_package_count") or 0),
        "unresolved_import_count": (
            int(py_graph.get("unresolved_import_count") or 0)
            + int(js_graph.get("unresolved_import_count") or 0)
        ),
    }
    merged["language_breakdown"] = _language_breakdown(merged)
    return merged


def build_scan_graph(
    repository_root: str,
    *,
    massive_mode: bool,
    code_files: int,
    estimated_modules: int,
    on_progress: Optional[Callable[[str, int, int], None]] = None,
) -> Dict[str, Any]:
    """Build dependency graph for desktop scan under tiered budgets (Python + JS/TS)."""
    plan = graph_build_plan(
        massive_mode=massive_mode,
        code_files=code_files,
        estimated_modules=estimated_modules,
    )
    started = time.time()

    def _progress(phase: str, current: int, total: int) -> None:
        if on_progress:
            on_progress(phase, current, total)

    py_graph = depgraph.build_graph(
        repository_root,
        detail=plan["detail"],
        time_budget_sec=plan["time_budget_sec"],
        on_progress=_progress,
    )

    js_graph: Optional[Dict[str, Any]] = None
    js_candidates = jsdepgraph.count_js_ts_candidates(repository_root)
    if js_candidates > 0:
        js_budget = plan["time_budget_sec"] or BUDGET_JS_TS_SEC
        if massive_mode:
            js_budget = min(float(js_budget), BUDGET_JS_TS_SEC)
        js_graph = jsdepgraph.build_graph(
            repository_root,
            time_budget_sec=js_budget,
            on_progress=_progress,
        )

    graph = merge_graphs(py_graph, js_graph)
    elapsed = round(time.time() - started, 3)
    graph["jarvis_graph_build"] = {
        **plan,
        "elapsed_sec": elapsed,
        "timed_out": bool(graph.get("jarvis_timed_out")),
        "partial": bool(graph.get("jarvis_partial")),
        "js_candidates": js_candidates,
        "js_files_kept": (js_graph or {}).get("scope_diagnostics", {}).get("files_kept", 0),
    }
    return graph


def build_full_module_graph(
    repository_root: str,
    *,
    time_budget_sec: float = BUDGET_FULL_MODULE_SEC,
    on_progress: Optional[Callable[[str, int, int], None]] = None,
) -> Dict[str, Any]:
    """Lazy/on-demand full module graph (Python full + JS/TS imports)."""
    def _progress(phase: str, current: int, total: int) -> None:
        if on_progress:
            on_progress(phase, current, total)

    py_graph = depgraph.build_graph(
        repository_root,
        detail=DETAIL_FULL,
        time_budget_sec=time_budget_sec,
        on_progress=_progress,
    )
    js_graph = None
    if jsdepgraph.count_js_ts_candidates(repository_root) > 0:
        js_graph = jsdepgraph.build_graph(
            repository_root,
            time_budget_sec=min(time_budget_sec, BUDGET_JS_TS_SEC),
            on_progress=_progress,
        )
    return merge_graphs(py_graph, js_graph)
