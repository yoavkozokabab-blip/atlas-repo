"""Deterministic impact analysis over the Phase 94A dependency graph (Phase 94B).

Read-only consumer of ``depgraph.build_graph`` output. Asserted impact uses only
``resolved`` edges; unresolved relationships are routed to separate channels.
"""

from __future__ import annotations

import json
import os
from collections import deque
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple

from .. import repository_understanding as ru
from . import depgraph

IMPACT_ENABLED = True
IMPACT_SCHEMA_VERSION = 1
WEIGHTS_VERSION = 1

DEFAULT_MAX_DEPTH = 6
HARD_MAX_DEPTH = 25
MAX_IMPACT_SET_SIZE = 5000
MAX_PATHS = 20
MAX_PATH_HOPS = 15

# Risk weights (fixed; reproduced in output via weights_version).
_RISK_WEIGHTS: Dict[str, float] = {
    "direct_fan_in": 0.20,
    "transitive_size": 0.25,
    "production_role_weight": 0.15,
    "subsystem_spread": 0.10,
    "entrypoint_reachability": 0.15,
    "cycle_membership": 0.05,
    "public_surface": 0.10,
}
_RISK_LOW = 0.35
_RISK_HIGH = 0.65

_CONFIDENCE_HIGH = 0.85
_CONFIDENCE_MEDIUM = 0.50
_CONFIDENCE_LOW = 0.20

_ROLE_WEIGHT = {
    "production_code": 1.0,
    "config": 0.5,
    "test": 0.3,
    "architecture_doc": 0.2,
    "general_doc": 0.1,
    "report_history": 0.0,
    "benchmark": 0.0,
    "dataset": 0.0,
    "generated": 0.0,
    "unknown": 0.2,
}

_IMPACT_EDGE_TYPES = ("imports", "calls", "references")


def _stable_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def _round(value: float) -> float:
    return round(float(value), 4)


def _norm_path(path: str) -> str:
    return path.replace("\\", "/").lstrip("./")


def _subsystem(path: str) -> str:
    parts = _norm_path(path).split("/")
    return parts[0] if len(parts) > 1 else "(root)"


def _node_path(nid: str, nodes_by_id: Dict[str, Dict[str, Any]]) -> Optional[str]:
    node = nodes_by_id.get(nid)
    if node:
        return node.get("path")
    if nid.startswith("module:"):
        return nid.split(":", 1)[1]
    if "::" in nid:
        return nid.split(":", 1)[1].split("::", 1)[0]
    return None


def _file_role(path: str, project_root: str) -> str:
    return ru.classify_file_role(_norm_path(path), ".py", project_root=project_root)


def _role_rank(role: str) -> int:
    return ru._ROLE_PRIORITY.get(role, 99)


def _build_node_index(graph: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    return {node["id"]: node for node in graph.get("nodes", [])}


def _build_reverse_indices(
    graph: Dict[str, Any],
) -> Tuple[
    Dict[str, List[Dict[str, Any]]],
    Dict[str, List[Dict[str, Any]]],
    Dict[str, List[Dict[str, Any]]],
]:
    reverse_imports: Dict[str, List[Dict[str, Any]]] = {}
    reverse_calls: Dict[str, List[Dict[str, Any]]] = {}
    reverse_references: Dict[str, List[Dict[str, Any]]] = {}

    for edge in graph.get("edges", []):
        if not edge.get("resolved"):
            continue
        etype = edge.get("type")
        target = edge.get("to")
        if not target or etype not in _IMPACT_EDGE_TYPES:
            continue
        bucket = {
            "imports": reverse_imports,
            "calls": reverse_calls,
            "references": reverse_references,
        }[etype]
        bucket.setdefault(target, []).append(edge)

    for bucket in (reverse_imports, reverse_calls, reverse_references):
        for key in bucket:
            bucket[key] = sorted(
                bucket[key],
                key=lambda e: (
                    e.get("from", ""),
                    int(e.get("line", 0)),
                    e.get("scope", ""),
                    e.get("kind", ""),
                ),
            )
    return reverse_imports, reverse_calls, reverse_references


def _module_nodes_for_dotted(
    graph: Dict[str, Any], dotted: str
) -> List[Dict[str, Any]]:
    return [
        n for n in graph.get("nodes", [])
        if n.get("type") == "module" and n.get("dotted") == dotted
    ]


def _nodes_in_file(graph: Dict[str, Any], path: str) -> List[str]:
    path = _norm_path(path)
    out: List[str] = []
    for node in graph.get("nodes", []):
        if node.get("path") == path and node.get("type") in ("module", "function", "class"):
            out.append(node["id"])
    mod_id = depgraph.node_id("module", path)
    if mod_id not in out and mod_id in _build_node_index(graph):
        out.append(mod_id)
    return sorted(set(out))


def _resolve_target(
    *,
    kind: str,
    file_path: Optional[str] = None,
    module: Optional[str] = None,
    function: Optional[str] = None,
    graph: Dict[str, Any],
    project_root: str,
) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    nodes_by_id = _build_node_index(graph)

    if kind == "file":
        if not file_path:
            return None, "file path required"
        path = _norm_path(file_path)
        mod_id = depgraph.node_id("module", path)
        if mod_id not in nodes_by_id:
            return None, "target file not found in graph"
        node = nodes_by_id[mod_id]
        return {
            "kind": "file",
            "id": mod_id,
            "path": path,
            "qualname": None,
            "dotted": node.get("dotted"),
            "role": _file_role(path, project_root),
            "subsystem": _subsystem(path),
            "node_ids": _nodes_in_file(graph, path),
        }, None

    if kind == "module":
        if not module:
            return None, "module name required"
        matches = _module_nodes_for_dotted(graph, module)
        if not matches:
            return None, "module not found in graph"
        if len(matches) > 1:
            return None, "module not uniquely mapped"
        node = matches[0]
        path = node["path"]
        return {
            "kind": "module",
            "id": node["id"],
            "path": path,
            "qualname": None,
            "dotted": module,
            "role": _file_role(path, project_root),
            "subsystem": _subsystem(path),
            "node_ids": [node["id"]],
        }, None

    if kind in ("function", "paths-to"):
        if not function or "::" not in function:
            return None, "function target must be path/to/file.py::qualname"
        path, qual = function.split("::", 1)
        path = _norm_path(path)
        fid = depgraph.node_id("function", path, qual)
        if fid not in nodes_by_id:
            return None, "target function not found in graph"
        return {
            "kind": "function" if kind == "function" else "paths-to",
            "id": fid,
            "path": path,
            "qualname": qual,
            "dotted": nodes_by_id.get(depgraph.node_id("module", path), {}).get("dotted"),
            "role": _file_role(path, project_root),
            "subsystem": _subsystem(path),
            "node_ids": [fid],
        }, None

    return None, "unknown target kind"


def _lift_to_file(nid: str, nodes_by_id: Dict[str, Dict[str, Any]]) -> Optional[str]:
    path = _node_path(nid, nodes_by_id)
    return _norm_path(path) if path else None


def _evidence_from_edge(edge: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "type": edge.get("type"),
        "from": edge.get("from"),
        "line": int(edge.get("line", 0)),
        "scope": edge.get("scope"),
        "kind": edge.get("kind"),
        "resolved": True,
    }


def _direct_modules_importing(
    target: Dict[str, Any],
    reverse_imports: Dict[str, List[Dict[str, Any]]],
    nodes_by_id: Dict[str, Dict[str, Any]],
    project_root: str,
) -> List[Dict[str, Any]]:
    mod_id = target["id"] if target["kind"] == "module" else depgraph.node_id("module", target["path"])
    out: List[Dict[str, Any]] = []
    for edge in reverse_imports.get(mod_id, []):
        src = edge["from"]
        node = nodes_by_id.get(src, {})
        out.append({
            "id": src,
            "dotted": node.get("dotted"),
            "path": node.get("path"),
            "line": int(edge.get("line", 0)),
            "role": _file_role(node.get("path", ""), project_root),
            "subsystem": _subsystem(node.get("path", "")),
            "evidence": [_evidence_from_edge(edge)],
        })
    return sorted(out, key=lambda item: (item.get("path") or "", item["line"], item["id"]))


def _direct_functions_dependent(
    target: Dict[str, Any],
    reverse_calls: Dict[str, List[Dict[str, Any]]],
    nodes_by_id: Dict[str, Dict[str, Any]],
    project_root: str,
) -> List[Dict[str, Any]]:
    fn_ids: Iterable[str]
    if target["kind"] == "function":
        fn_ids = [target["id"]]
    else:
        fn_ids = [
            nid for nid in target["node_ids"]
            if nid.startswith("function:")
        ]

    seen: Set[str] = set()
    out: List[Dict[str, Any]] = []
    for fn_id in sorted(fn_ids):
        for edge in reverse_calls.get(fn_id, []):
            src = edge["from"]
            if src in seen:
                continue
            seen.add(src)
            node = nodes_by_id.get(src, {})
            out.append({
                "id": src,
                "path": node.get("path"),
                "qualname": node.get("qualname"),
                "line": int(edge.get("line", 0)),
                "scope": edge.get("scope"),
                "role": _file_role(node.get("path", ""), project_root),
                "subsystem": _subsystem(node.get("path", "")),
                "evidence": [_evidence_from_edge(edge)],
            })
    return sorted(out, key=lambda item: (item.get("path") or "", item.get("qualname") or "", item["line"], item["id"]))


def _direct_files_dependent(
    target: Dict[str, Any],
    reverse_imports: Dict[str, List[Dict[str, Any]]],
    reverse_calls: Dict[str, List[Dict[str, Any]]],
    reverse_references: Dict[str, List[Dict[str, Any]]],
    nodes_by_id: Dict[str, Dict[str, Any]],
    project_root: str,
) -> List[Dict[str, Any]]:
    target_path = target["path"]
    mod_id = depgraph.node_id("module", target_path)
    by_file: Dict[str, Dict[str, Any]] = {}

    def add_file(path: str, via: str, edge: Dict[str, Any]) -> None:
        if not path or path == target_path:
            return
        role = _file_role(path, project_root)
        entry = by_file.setdefault(path, {
            "path": path,
            "role": role,
            "subsystem": _subsystem(path),
            "via": set(),
            "evidence": [],
        })
        entry["via"].add(via)
        entry["evidence"].append(_evidence_from_edge(edge))

    for edge in reverse_imports.get(mod_id, []):
        path = _lift_to_file(edge["from"], nodes_by_id)
        if path:
            add_file(path, "imports", edge)

    target_nodes = set(target["node_ids"])
    for rev_map, via in ((reverse_calls, "calls"), (reverse_references, "references")):
        for tgt in sorted(target_nodes):
            for edge in rev_map.get(tgt, []):
                path = _lift_to_file(edge["from"], nodes_by_id)
                if path:
                    add_file(path, via, edge)

    out: List[Dict[str, Any]] = []
    for path in sorted(by_file):
        item = by_file[path]
        out.append({
            "path": path,
            "role": item["role"],
            "subsystem": item["subsystem"],
            "via": sorted(item["via"]),
            "evidence": sorted(
                item["evidence"],
                key=lambda e: (e.get("type", ""), e.get("from", ""), e.get("line", 0)),
            ),
        })
    return out


def _transitive_closure(
    start_ids: Iterable[str],
    reverse_imports: Dict[str, List[Dict[str, Any]]],
    reverse_calls: Dict[str, List[Dict[str, Any]]],
    reverse_references: Dict[str, List[Dict[str, Any]]],
    *,
    max_depth: int,
    max_size: int,
) -> Tuple[Dict[str, Dict[str, Any]], bool]:
    rev_maps = (
        ("imports", reverse_imports),
        ("calls", reverse_calls),
        ("references", reverse_references),
    )
    visited: Dict[str, Dict[str, Any]] = {}
    truncated = False
    queue: deque[Tuple[int, str]] = deque((0, nid) for nid in sorted(set(start_ids)))

    while queue:
        depth, nid = queue.popleft()
        if nid in visited:
            continue
        if depth > max_depth:
            truncated = True
            continue
        if len(visited) >= max_size:
            truncated = True
            break
        visited[nid] = {"depth": depth}
        if depth == max_depth:
            continue
        for _etype, rev_map in rev_maps:
            for edge in rev_map.get(nid, []):
                src = edge["from"]
                if src not in visited:
                    queue.append((depth + 1, src))

    return visited, truncated


def _entrypoint_function_ids(
    graph: Dict[str, Any], project_root: str
) -> Set[str]:
    entry_names = set(ru._ENTRY_NAMES)
    out: Set[str] = set()
    for node in graph.get("nodes", []):
        if node.get("type") != "function":
            continue
        path = node.get("path", "")
        if os.path.basename(path) not in entry_names:
            continue
        if _file_role(path, project_root) != "production_code":
            continue
        out.add(node["id"])
    return out


def _execution_paths(
    target_fn_id: str,
    reverse_calls: Dict[str, List[Dict[str, Any]]],
    entrypoints: Set[str],
    *,
    max_paths: int = MAX_PATHS,
    max_hops: int = MAX_PATH_HOPS,
) -> Tuple[List[List[str]], bool]:
    paths: List[List[str]] = []
    truncated = False

    def dfs(current: str, path: List[str], visited: Set[str]) -> None:
        nonlocal truncated
        if len(paths) >= max_paths:
            truncated = True
            return
        if len(path) > max_hops:
            truncated = True
            return
        if current in entrypoints:
            paths.append(list(reversed(path)))
            return
        for edge in reverse_calls.get(current, []):
            caller = edge["from"]
            if caller in visited:
                continue
            visited.add(caller)
            path.append(caller)
            dfs(caller, path, visited)
            path.pop()
            visited.remove(caller)

    dfs(target_fn_id, [target_fn_id], {target_fn_id})
    paths.sort(key=lambda p: (len(p), p))
    return paths, truncated


def _collect_possible_additional_impact(
    target: Dict[str, Any],
    graph: Dict[str, Any],
    direct_files: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    target_path = target["path"]
    target_mod = target.get("dotted") or depgraph.node_id("module", target_path).split(":", 1)[1]
    possible: List[Dict[str, Any]] = []
    seen: Set[Tuple] = set()

    def add(file: str, line: int, reason: str, **extra: Any) -> None:
        key = (file, line, reason, extra.get("name"))
        if key in seen:
            return
        seen.add(key)
        item = {"file": _norm_path(file), "line": int(line), "reason": reason}
        item.update(extra)
        possible.append(item)

    for item in graph.get("unresolved", {}).get("calls_unresolved", []):
        if _norm_path(item.get("file", "")) == target_path:
            add(item["file"], item.get("line", 0), item.get("reason", "intra_file_unresolved"))

    for item in graph.get("unresolved", {}).get("references_unresolved", []):
        if _norm_path(item.get("file", "")) == target_path:
            add(
                item["file"],
                item.get("line", 0),
                item.get("kind", "references_unresolved"),
                name=item.get("name"),
            )

    target_dotted = target.get("dotted")
    if not target_dotted:
        stem = os.path.splitext(os.path.basename(target_path))[0]
        if stem != "__init__":
            target_dotted = stem

    for item in graph.get("unresolved", {}).get("imports_external", []):
        if item.get("reason") != "star_import":
            continue
        tgt = item.get("target", "")
        if tgt == target_dotted or tgt == target_path or tgt.endswith(f".{target_dotted}"):
            add(
                item.get("from_module", ""),
                item.get("line", 0),
                "star_import",
                name=tgt,
            )

    return sorted(possible, key=lambda x: (x["file"], x["line"], x["reason"], x.get("name", "")))


def _collect_unanalyzed(graph: Dict[str, Any]) -> List[str]:
    return sorted(_norm_path(p) for p in graph.get("parse_errors", []))


def _cycle_nodes(graph: Dict[str, Any]) -> Set[str]:
    out: Set[str] = set()
    for cycle in graph.get("statistics", {}).get("import_cycles", []):
        out.update(cycle)
    return out


def _compute_risk(
    *,
    target: Dict[str, Any],
    direct_files: List[Dict[str, Any]],
    direct_functions: List[Dict[str, Any]],
    transitive_nodes: Dict[str, Dict[str, Any]],
    nodes_by_id: Dict[str, Dict[str, Any]],
    execution_paths: List[List[str]],
    cycle_nodes: Set[str],
    project_root: str,
) -> Dict[str, Any]:
    direct_fan_in = len(direct_files) + len(direct_functions)
    transitive_size = max(0, len(transitive_nodes) - len(set(target["node_ids"])))

    prod_weight = 0.0
    roles: Set[str] = set()
    subsystems: Set[str] = set()
    cross_file = 0
    for item in direct_files:
        roles.add(item["role"])
        subsystems.add(item["subsystem"])
        prod_weight = max(prod_weight, _ROLE_WEIGHT.get(item["role"], 0.2))
    for item in direct_functions:
        roles.add(item["role"])
        subsystems.add(item["subsystem"])
        if item.get("scope") == "cross_file":
            cross_file += 1
        prod_weight = max(prod_weight, _ROLE_WEIGHT.get(item["role"], 0.2))

    entry_reach = 1.0 if execution_paths else 0.0
    in_cycle = 1.0 if target["id"] in cycle_nodes or any(
        nid in cycle_nodes for nid in target["node_ids"]
    ) else 0.0
    public_surface = min(1.0, cross_file / max(1, len(direct_functions)))

    norm_direct = min(1.0, direct_fan_in / 20.0)
    norm_trans = min(1.0, transitive_size / 100.0)
    norm_subsystems = min(1.0, len(subsystems) / 5.0)

    factors = [
        {"name": "direct_fan_in", "value": _round(norm_direct)},
        {"name": "transitive_size", "value": _round(norm_trans)},
        {"name": "production_role_weight", "value": _round(prod_weight)},
        {"name": "subsystem_spread", "value": _round(norm_subsystems)},
        {"name": "entrypoint_reachability", "value": _round(entry_reach)},
        {"name": "cycle_membership", "value": _round(in_cycle)},
        {"name": "public_surface", "value": _round(public_surface)},
    ]

    score = sum(
        _RISK_WEIGHTS[f["name"]] * f["value"] for f in factors
    )
    score = _round(score)
    if score < _RISK_LOW:
        bucket = "low"
    elif score < _RISK_HIGH:
        bucket = "medium"
    else:
        bucket = "high"

    return {"bucket": bucket, "score": score, "factors": factors}


def _compute_confidence(
    *,
    graph: Dict[str, Any],
    target: Dict[str, Any],
    possible: List[Dict[str, Any]],
    unanalyzed: List[str],
    direct_count: int,
) -> Dict[str, Any]:
    caveats: List[str] = []

    if graph.get("degraded"):
        return {"bucket": "unknown", "resolved_ratio": 0.0, "caveats": ["degraded graph"]}

    unresolved_near = len(possible)
    resolved = max(direct_count, 0)
    denom = resolved + unresolved_near
    resolved_ratio = _round(resolved / denom if denom else 1.0)

    if unanalyzed:
        caveats.append(f"{len(unanalyzed)} unanalyzed file(s) with parse errors")
    if any(p.get("reason") == "star_import" for p in possible):
        caveats.append("star_import in dependent frontier")
    if any("ambiguous" in p.get("reason", "") for p in possible):
        caveats.append("ambiguous import in frontier")
    if unresolved_near and direct_count == 0:
        caveats.append("no proven dependents; unresolved items present")

    bucket = "high"
    if graph.get("degraded") or unanalyzed or any(
        p.get("reason") == "star_import" for p in possible
    ):
        bucket = "medium"
        resolved_ratio = min(resolved_ratio, _CONFIDENCE_MEDIUM)
    elif resolved_ratio >= _CONFIDENCE_HIGH:
        bucket = "high"
    elif resolved_ratio >= _CONFIDENCE_MEDIUM:
        bucket = "medium"
    elif resolved_ratio >= _CONFIDENCE_LOW:
        bucket = "low"
    else:
        bucket = "unknown"

    if unresolved_near and direct_count == 0:
        bucket = "unknown"

    return {
        "bucket": bucket,
        "resolved_ratio": resolved_ratio,
        "caveats": sorted(caveats),
    }


def _module_import_indegree_check(
    module_id: str,
    reverse_imports: Dict[str, List[Dict[str, Any]]],
    graph: Dict[str, Any],
) -> bool:
    computed = len(reverse_imports.get(module_id, []))
    for item in graph.get("statistics", {}).get("top_imported_modules", []):
        if item.get("id") == module_id:
            return item.get("count") == computed
    return True


def analyze_impact(
    graph: Dict[str, Any],
    *,
    kind: str,
    file_path: Optional[str] = None,
    module: Optional[str] = None,
    function: Optional[str] = None,
    project_root: str = ".",
    max_depth: int = DEFAULT_MAX_DEPTH,
    include_transitive: bool = True,
    paths_only: bool = False,
) -> Dict[str, Any]:
    """Run impact analysis for one target against a built dependency graph."""
    project_root = os.path.abspath(project_root)
    max_depth = max(1, min(max_depth, HARD_MAX_DEPTH))

    if graph.get("schema_version") != depgraph.GRAPH_SCHEMA_VERSION:
        return _error_result(
            graph, kind, "graph schema_version mismatch; rebuild the graph",
            project_root=project_root,
        )

    target, err = _resolve_target(
        kind=kind,
        file_path=file_path,
        module=module,
        function=function,
        graph=graph,
        project_root=project_root,
    )
    if target is None:
        return _error_result(graph, kind, err or "target not found", project_root=project_root)

    if graph.get("degraded"):
        return {
            "schema_version": IMPACT_SCHEMA_VERSION,
            "weights_version": WEIGHTS_VERSION,
            "repository_root": graph.get("repository_root"),
            "target": _target_payload(target),
            "questions": _empty_questions(),
            "risk": {"bucket": "unknown", "score": 0.0, "factors": []},
            "confidence": {"bucket": "unknown", "resolved_ratio": 0.0, "caveats": ["degraded graph"]},
            "possible_additional_impact": [],
            "unanalyzed": _collect_unanalyzed(graph),
            "degraded": True,
            "error": "degraded graph",
        }

    nodes_by_id = _build_node_index(graph)
    reverse_imports, reverse_calls, reverse_references = _build_reverse_indices(graph)

    modules_importing = _direct_modules_importing(
        target, reverse_imports, nodes_by_id, project_root)
    functions_dependent = _direct_functions_dependent(
        target, reverse_calls, nodes_by_id, project_root)
    files_dependent = _direct_files_dependent(
        target, reverse_imports, reverse_calls, reverse_references,
        nodes_by_id, project_root,
    )

    possible = _collect_possible_additional_impact(target, graph, files_dependent)
    unanalyzed = _collect_unanalyzed(graph)

    transitive_nodes: Dict[str, Dict[str, Any]] = {}
    truncated = False
    if include_transitive and not paths_only:
        transitive_nodes, truncated = _transitive_closure(
            target["node_ids"],
            reverse_imports,
            reverse_calls,
            reverse_references,
            max_depth=max_depth,
            max_size=MAX_IMPACT_SET_SIZE,
        )

    execution_paths: List[List[str]] = []
    paths_truncated = False
    if target["kind"] in ("function", "paths-to") or paths_only:
        fn_id = target["id"] if target["kind"] != "file" else None
        if fn_id is None and target["kind"] == "file":
            fn_ids = [nid for nid in target["node_ids"] if nid.startswith("function:")]
            fn_id = fn_ids[0] if len(fn_ids) == 1 else None
        if fn_id:
            entrypoints = _entrypoint_function_ids(graph, project_root)
            execution_paths, paths_truncated = _execution_paths(
                fn_id, reverse_calls, entrypoints)

    cycle_nodes = _cycle_nodes(graph)
    direct_count = len(files_dependent) + len(modules_importing) + len(functions_dependent)

    risk = _compute_risk(
        target=target,
        direct_files=files_dependent,
        direct_functions=functions_dependent,
        transitive_nodes=transitive_nodes,
        nodes_by_id=nodes_by_id,
        execution_paths=execution_paths,
        cycle_nodes=cycle_nodes,
        project_root=project_root,
    )
    confidence = _compute_confidence(
        graph=graph,
        target=target,
        possible=possible,
        unanalyzed=unanalyzed,
        direct_count=direct_count,
    )

    mod_id = depgraph.node_id("module", target["path"])
    import_check_ok = _module_import_indegree_check(mod_id, reverse_imports, graph)

    return {
        "schema_version": IMPACT_SCHEMA_VERSION,
        "weights_version": WEIGHTS_VERSION,
        "repository_root": graph.get("repository_root"),
        "target": _target_payload(target),
        "questions": {
            "files_dependent": files_dependent,
            "functions_dependent": functions_dependent,
            "modules_importing": modules_importing,
            "execution_paths": execution_paths,
            "execution_paths_truncated": paths_truncated,
            "execution_paths_message": (
                "no resolved execution path found (call-graph coverage is partial)"
                if not execution_paths and target.get("qualname")
                else None
            ),
            "may_break": {
                "direct_count": direct_count,
                "transitive_count": max(0, len(transitive_nodes) - len(set(target["node_ids"]))),
                "truncated": truncated,
            },
            "import_indegree_check_ok": import_check_ok,
        },
        "risk": risk,
        "confidence": confidence,
        "possible_additional_impact": possible,
        "unanalyzed": unanalyzed,
        "degraded": False,
    }


def _target_payload(target: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "kind": target["kind"],
        "id": target["id"],
        "path": target["path"],
        "qualname": target.get("qualname"),
        "dotted": target.get("dotted"),
        "role": target.get("role"),
        "subsystem": target.get("subsystem"),
    }


def _empty_questions() -> Dict[str, Any]:
    return {
        "files_dependent": [],
        "functions_dependent": [],
        "modules_importing": [],
        "execution_paths": [],
        "execution_paths_truncated": False,
        "execution_paths_message": None,
        "may_break": {"direct_count": 0, "transitive_count": 0, "truncated": False},
        "import_indegree_check_ok": True,
    }


def _error_result(
    graph: Dict[str, Any],
    kind: str,
    message: str,
    *,
    project_root: str,
) -> Dict[str, Any]:
    return {
        "schema_version": IMPACT_SCHEMA_VERSION,
        "weights_version": WEIGHTS_VERSION,
        "repository_root": graph.get("repository_root") or os.path.abspath(project_root).replace("\\", "/"),
        "target": {"kind": kind, "id": None, "path": None, "qualname": None, "role": None, "subsystem": None},
        "questions": _empty_questions(),
        "risk": {"bucket": "unknown", "score": 0.0, "factors": []},
        "confidence": {"bucket": "unknown", "resolved_ratio": 0.0, "caveats": [message]},
        "possible_additional_impact": [],
        "unanalyzed": _collect_unanalyzed(graph),
        "degraded": bool(graph.get("degraded")),
        "error": message,
    }


def build_and_analyze(
    project_root: str,
    **kwargs: Any,
) -> Dict[str, Any]:
    """Build the dependency graph once, then analyze impact."""
    graph = depgraph.build_graph(project_root)
    return analyze_impact(graph, project_root=project_root, **kwargs)


def export_json(result: Dict[str, Any]) -> str:
    return _stable_json(result)


def format_summary(result: Dict[str, Any], *, top: int = 20) -> str:
    target = result.get("target", {})
    questions = result.get("questions", {})
    lines = [
        "IMPACT ANALYSIS",
        f"schema: {result.get('schema_version')}  weights: {result.get('weights_version')}",
        f"repository: {result.get('repository_root')}",
        "",
        "TARGET",
        f"- kind: {target.get('kind')}",
        f"- path: {target.get('path')}",
        f"- qualname: {target.get('qualname') or '(n/a)'}",
        f"- role: {target.get('role')}  subsystem: {target.get('subsystem')}",
    ]
    if result.get("error"):
        lines.extend(["", f"ERROR: {result['error']}"])

    lines.extend(["", "DIRECT IMPACT"])
    files_dep = questions.get("files_dependent", [])
    if not files_dep:
        lines.append("- files: (none proven)")
    else:
        for item in files_dep[:top]:
            ev = item.get("evidence") or [{}]
            line = ev[0].get("line", "?")
            lines.append(
                f"- file {item['path']}:{line} via={','.join(item.get('via', []))} "
                f"role={item.get('role')}"
            )
        if len(files_dep) > top:
            lines.append(f"- +{len(files_dep) - top} more files")

    mods = questions.get("modules_importing", [])
    lines.append("")
    lines.append("MODULES IMPORTING")
    if not mods:
        lines.append("- (none proven)")
    else:
        for item in mods[:top]:
            lines.append(f"- {item.get('dotted') or item.get('path')}:{item['line']} role={item.get('role')}")

    fns = questions.get("functions_dependent", [])
    lines.append("")
    lines.append("FUNCTIONS DEPENDENT")
    if not fns:
        lines.append("- (none proven)")
    else:
        for item in fns[:top]:
            lines.append(
                f"- {item.get('path')}::{item.get('qualname')}:{item['line']} "
                f"scope={item.get('scope')} role={item.get('role')}"
            )

    lines.extend(["", "TRANSITIVE IMPACT"])
    may = questions.get("may_break", {})
    lines.append(
        f"- direct={may.get('direct_count', 0)} transitive={may.get('transitive_count', 0)} "
        f"truncated={may.get('truncated', False)}"
    )

    lines.extend(["", "EXECUTION PATHS"])
    paths = questions.get("execution_paths") or []
    if paths:
        for path in paths[:top]:
            lines.append(f"- {' -> '.join(path)}")
        if questions.get("execution_paths_truncated"):
            lines.append("- (paths truncated)")
    else:
        msg = questions.get("execution_paths_message")
        lines.append(f"- {msg or 'no resolved path found (coverage is partial)'}")

    risk = result.get("risk", {})
    lines.extend([
        "",
        "RISK",
        f"- bucket: {risk.get('bucket')} score: {risk.get('score')}",
    ])
    for factor in (risk.get("factors") or [])[:5]:
        lines.append(f"- {factor.get('name')}: {factor.get('value')}")

    conf = result.get("confidence", {})
    lines.extend([
        "",
        "CONFIDENCE",
        f"- bucket: {conf.get('bucket')} resolved_ratio: {conf.get('resolved_ratio')}",
    ])
    for caveat in conf.get("caveats") or []:
        lines.append(f"- caveat: {caveat}")

    possible = result.get("possible_additional_impact") or []
    lines.extend(["", "POSSIBLE (UNVERIFIED)"])
    if not possible:
        lines.append("- (none)")
    else:
        for item in possible[:top]:
            extra = f" name={item['name']}" if item.get("name") else ""
            lines.append(f"- {item['file']}:{item['line']} reason={item['reason']}{extra}")

    unanalyzed = result.get("unanalyzed") or []
    lines.extend(["", "UNANALYZED"])
    if not unanalyzed:
        lines.append("- (none)")
    else:
        for path in unanalyzed[:top]:
            lines.append(f"- {path}")

    if result.get("degraded"):
        lines.extend(["", "DEGRADED: graph incomplete"])

    verdict = _verdict_line(result)
    if verdict:
        lines.extend(["", verdict])

    return "\n".join(lines) + "\n"


def _verdict_line(result: Dict[str, Any]) -> str:
    questions = result.get("questions", {})
    direct = questions.get("may_break", {}).get("direct_count", 0)
    possible = len(result.get("possible_additional_impact") or [])
    unanalyzed = len(result.get("unanalyzed") or [])
    conf = result.get("confidence", {}).get("bucket")
    if direct == 0 and (possible or unanalyzed or conf == "unknown"):
        return (
            f"VERDICT: no proven dependents; {possible} possible, {unanalyzed} unanalyzed "
            "— impact UNKNOWN"
        )
    return ""


def exit_code(result: Dict[str, Any]) -> int:
    if result.get("degraded") or result.get("error"):
        return 2
    bucket = result.get("confidence", {}).get("bucket")
    if bucket in ("unknown",):
        return 2
    return 0
