"""Deterministic repository dependency graph (Phase 94A).

Assembles a structure-only graph from existing static resolvers:
``module_map``, ``imports``, ``callgraph``, and ``cross_file``. No LLM, no
semantic edges, no guessing — unresolved relationships are explicit annotations.

Ephemeral (in-memory / explicit export only); schema is cache-ready but Phase 94
does not implement incremental disk caching.
"""

from __future__ import annotations

import ast
import json
import os
import time
from typing import Any, Callable, Dict, Iterable, List, Optional, Set, Tuple

from . import callgraph, cross_file, imports, module_map

GRAPH_SCHEMA_VERSION = 1
NODE_TYPES = ("repository", "module", "class", "function")
EDGE_TYPES = ("contains", "imports", "calls", "references")

_MAX_FILES = cross_file._MAX_FILES
_MAX_FUNCTIONS = cross_file._MAX_FUNCTIONS

# Phase 100G — dependency-graph scope. ``production`` reuses the RU-2 role
# classifier to keep only production source files, so generated/runtime/data/
# benchmark/report files do not push the graph over the cap. ``full`` is the
# legacy behavior (every Python file). ``graph_scope`` on the result is
# ``production``/``full`` when built cleanly, or ``degraded`` if still over cap.
PRODUCTION_SCOPE = "production"
FULL_SCOPE = "full"
DEGRADED_SCOPE = "degraded"
GRAPH_SCOPES = (PRODUCTION_SCOPE, FULL_SCOPE)

# Phase 115B — graph detail tiers (import-only vs full interprocedural graph).
DETAIL_FULL = "full"
DETAIL_IMPORTS = "imports"
DETAIL_LEVELS = (DETAIL_FULL, DETAIL_IMPORTS)


def _canonical_cycle(cycle: Iterable[str]) -> Tuple[str, ...]:
    """Canonical cycle identity independent of start position and direction."""
    nodes = list(cycle)
    if len(nodes) > 1 and nodes[0] == nodes[-1]:
        nodes = nodes[:-1]
    if not nodes:
        return tuple()
    rotations = [tuple(nodes[index:] + nodes[:index]) for index in range(len(nodes))]
    reversed_nodes = list(reversed(nodes))
    rotations.extend(
        tuple(reversed_nodes[index:] + reversed_nodes[:index])
        for index in range(len(reversed_nodes))
    )
    return min(rotations)


def _closed_cycle(cycle: Iterable[str]) -> List[str]:
    key = _canonical_cycle(cycle)
    return [*key, key[0]] if key else []


def _production_scope_filter(
    root_abs: str,
    candidates: List[Tuple[str, str]],
    *,
    include_tests: bool,
) -> Tuple[List[Tuple[str, str]], Dict[str, int]]:
    """Keep production source files only, reusing the RU-2 role classifier.

    Returns ``(kept, excluded_by_role)``. ``.py`` under a top-level data tree
    (``data/``, ``fixtures/`` …) classifies as ``production_code`` by role yet is
    not first-party source (e.g. a vendored evaluation corpus), so it is excluded
    by location and reported as ``dataset_tree`` in the diagnostics.
    """
    from .. import repository_understanding as ru

    dataset_parts = ru._DATASET_PARTS
    kept: List[Tuple[str, str]] = []
    excluded: Dict[str, int] = {}
    for abs_path, rel in candidates:
        rel_posix = rel.replace("\\", "/")
        role = ru.classify_file_role(rel_posix, ".py", project_root=root_abs)
        segments = rel_posix.lower().split("/")
        in_data_tree = bool(segments) and segments[0] in dataset_parts
        allowed_role = role == "production_code" or (include_tests and role == "test")
        if allowed_role and not in_data_tree:
            kept.append((abs_path, rel_posix))
        else:
            key = "dataset_tree" if in_data_tree else role
            excluded[key] = excluded.get(key, 0) + 1
    return kept, excluded


def _stable_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def node_id(kind: str, *parts: str) -> str:
    if kind == "repository":
        return f"repository:{parts[0]}"
    if kind == "module":
        return f"module:{parts[0]}"
    if kind in ("class", "function"):
        return f"{kind}:{parts[0]}::{parts[1]}"
    raise ValueError(f"unknown node kind {kind!r}")


def _file_package(rel_path: str) -> str:
    return ".".join(rel_path.split("/")[:-1])


def _line_count(text: str) -> int:
    return len(text.splitlines()) if text else 0


def _compute_structure_qualnames(tree: ast.AST) -> Dict[ast.AST, str]:
    """Qualnames for ``ClassDef`` and function nodes (module-relative dotted names).

    ``callgraph._compute_qualnames`` indexes functions only; the dependency graph
    also needs class nodes for ``contains`` and ``references`` edges.
    """
    out: Dict[ast.AST, str] = {}

    def visit(node: ast.AST, prefix: str) -> None:
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                q = f"{prefix}{child.name}"
                out[child] = q
                visit(child, q + ".")
            else:
                visit(child, prefix)

    visit(tree, "")
    return out


def _collect_files(root: str) -> List[Tuple[str, str]]:
    from . import engine

    root = os.path.abspath(root)
    out: List[Tuple[str, str]] = []
    for abs_path, rel in engine._collect_python_files(root):
        try:
            with open(abs_path, "r", encoding="utf-8-sig", errors="ignore") as handle:
                out.append((rel, handle.read()))
        except OSError:
            continue
    return out


def _build_indexes(
    parsed: List[Tuple[str, ast.AST]],
    mm: Dict[str, Any],
) -> Tuple[Dict[str, Dict[str, Tuple[str, str]]], Dict[str, Dict[str, Tuple[str, str]]]]:
    fn_index: Dict[str, Dict[str, Tuple[str, str]]] = {}
    cls_index: Dict[str, Dict[str, Tuple[str, str]]] = {}
    for rel, tree in parsed:
        mod = mm["path_to_module"].get(rel)
        if mod is None:
            continue
        struct_qn = _compute_structure_qualnames(tree)
        for child in ast.iter_child_nodes(tree):
            if isinstance(child, ast.ClassDef):
                cls_index.setdefault(mod, {})[child.name] = (rel, struct_qn[child])
            elif isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                fn_index.setdefault(mod, {})[child.name] = (rel, struct_qn[child])
    return fn_index, cls_index


def _resolve_imported_symbol(
    name: str,
    it: Dict[str, Any],
    mm: Dict[str, Any],
    fn_index: Dict[str, Dict[str, Tuple[str, str]]],
    cls_index: Dict[str, Dict[str, Tuple[str, str]]],
) -> Optional[Tuple[str, str, str]]:
    if name not in it["direct"] or name in it["ambiguous"]:
        return None
    mod, qual = it["direct"][name]
    if mod not in mm["module_to_path"]:
        return None
    if qual in fn_index.get(mod, {}):
        file, q = fn_index[mod][qual]
        return ("function", file, q)
    if qual in cls_index.get(mod, {}):
        file, q = cls_index[mod][qual]
        return ("class", file, q)
    return None


def _contains_parent(
    qual: str,
    rel: str,
    qn_map: Dict[ast.AST, str],
    fn_node: ast.AST,
) -> Tuple[str, str]:
    """Return (parent_kind, parent_id) for a function/method node."""
    if "." in qual:
        class_name = qual.rsplit(".", 1)[0]
        return "class", node_id("class", rel, class_name)
    return "module", node_id("module", rel)


def _class_parent(rel: str, qual: str) -> str:
    if "." in qual:
        outer = qual.rsplit(".", 1)[0]
        return node_id("class", rel, outer)
    return node_id("module", rel)


def _deadline_exceeded(deadline: Optional[float]) -> bool:
    return deadline is not None and time.monotonic() >= deadline


def _append_module_import_edges(
    rel: str,
    tree: ast.AST,
    mod_nid: str,
    mm: Dict[str, Any],
    edges: List[Dict[str, Any]],
    unresolved: Dict[str, List[Dict[str, Any]]],
) -> None:
    """Append resolved/unresolved import edges for one module (shared by full + imports detail)."""
    for node in getattr(tree, "body", []):
        line = getattr(node, "lineno", 1)
        if isinstance(node, ast.Import):
            for alias in node.names:
                target_mod = alias.name
                tgt_path = mm["module_to_path"].get(target_mod)
                if tgt_path is not None:
                    edges.append({
                        "type": "imports",
                        "from": mod_nid,
                        "to": node_id("module", tgt_path),
                        "line": line,
                        "resolved": True,
                        "target_module": target_mod,
                    })
                else:
                    unresolved["imports_external"].append({
                        "from_module": rel,
                        "line": line,
                        "target": target_mod,
                        "reason": "third_party_or_unknown_module",
                    })
        elif isinstance(node, ast.ImportFrom):
            level = node.level or 0
            if level == 0:
                base = node.module
            else:
                base_pkg = imports._base_pkg_for_relative(_file_package(rel), level)
                if base_pkg is None:
                    continue
                if node.module:
                    base = f"{base_pkg}.{node.module}" if base_pkg else node.module
                else:
                    for alias in node.names:
                        if alias.name == "*":
                            continue
                        sub = f"{base_pkg}.{alias.name}" if base_pkg else alias.name
                        tgt_path = mm["module_to_path"].get(sub)
                        if tgt_path is not None:
                            edges.append({
                                "type": "imports",
                                "from": mod_nid,
                                "to": node_id("module", tgt_path),
                                "line": line,
                                "resolved": True,
                                "target_module": sub,
                            })
                        else:
                            unresolved["imports_external"].append({
                                "from_module": rel,
                                "line": line,
                                "target": sub,
                                "reason": "third_party_or_unknown_module",
                            })
                    continue
            if base is None:
                continue
            tgt_path = mm["module_to_path"].get(base)
            if tgt_path is not None:
                edges.append({
                    "type": "imports",
                    "from": mod_nid,
                    "to": node_id("module", tgt_path),
                    "line": line,
                    "resolved": True,
                    "target_module": base,
                })
            else:
                for alias in node.names:
                    if alias.name == "*":
                        unresolved["imports_external"].append({
                            "from_module": rel,
                            "line": line,
                            "target": base,
                            "reason": "star_import",
                        })
                    else:
                        unresolved["imports_external"].append({
                            "from_module": rel,
                            "line": line,
                            "target": f"{base}.{alias.name}",
                            "reason": "third_party_or_unknown_module",
                        })


def _finalize_graph(
    root: str,
    nodes: Dict[str, Dict[str, Any]],
    edges: List[Dict[str, Any]],
    unresolved: Dict[str, List[Dict[str, Any]]],
    parse_errors: List[str],
    *,
    partial: bool = False,
    timed_out: bool = False,
    detail: str = DETAIL_FULL,
) -> Dict[str, Any]:
    edge_list = _dedupe_edges(edges)
    node_list = [nodes[k] for k in sorted(nodes)]
    stats = compute_statistics(node_list, edge_list, unresolved)
    out: Dict[str, Any] = {
        "schema_version": GRAPH_SCHEMA_VERSION,
        "repository_root": root,
        "nodes": node_list,
        "edges": edge_list,
        "unresolved": unresolved,
        "statistics": stats,
        "parse_errors": sorted(parse_errors),
        "graph_detail": detail,
    }
    if partial or timed_out:
        out["jarvis_partial"] = True
        out["degraded"] = True
        out["degraded_reason"] = "time_budget_exceeded" if timed_out else "partial_build"
    if timed_out:
        out["jarvis_timed_out"] = True
    return out


def _build_imports_detail_graph(
    root: str,
    file_list: List[Tuple[str, str]],
    *,
    deadline: Optional[float] = None,
    on_progress: Optional[Callable[[str, int, int], None]] = None,
) -> Dict[str, Any]:
    """Module-level import graph only — no call/cross-file/reference expansion."""
    repo_nid = node_id("repository", root)
    nodes: Dict[str, Dict[str, Any]] = {
        repo_nid: {
            "id": repo_nid,
            "type": "repository",
            "root": root,
            "python_files": len(file_list),
        }
    }
    edges: List[Dict[str, Any]] = []
    unresolved: Dict[str, List[Dict[str, Any]]] = {
        "imports_external": [],
        "calls_unresolved": [],
        "references_unresolved": [],
    }
    parse_errors: List[str] = []
    parsed: List[Tuple[str, ast.AST]] = []
    text_by_rel = dict(file_list)
    total = len(file_list)

    for idx, (rel, text) in enumerate(file_list):
        if _deadline_exceeded(deadline):
            return _finalize_graph(
                root, nodes, edges, unresolved, parse_errors,
                partial=True, timed_out=True, detail=DETAIL_IMPORTS,
            )
        if on_progress and idx % 50 == 0:
            on_progress("parse_imports", idx, total)
        try:
            parsed.append((rel, ast.parse(text)))
        except SyntaxError as exc:
            parse_errors.append(rel)
            mod_nid = node_id("module", rel)
            nodes[mod_nid] = {
                "id": mod_nid,
                "type": "module",
                "path": rel,
                "dotted": module_map.path_to_dotted(rel),
                "is_package": rel.endswith("__init__.py"),
                "parse_ok": False,
                "line_count": _line_count(text),
                "parse_error": f"{type(exc).__name__}: {exc.msg}",
            }
            edges.append({
                "type": "contains",
                "from": repo_nid,
                "to": mod_nid,
                "line": 1,
                "resolved": True,
            })

    mm = module_map.build_module_map([rel for rel, _ in parsed])
    for idx, (rel, tree) in enumerate(parsed):
        if _deadline_exceeded(deadline):
            return _finalize_graph(
                root, nodes, edges, unresolved, parse_errors,
                partial=True, timed_out=True, detail=DETAIL_IMPORTS,
            )
        if on_progress and idx % 50 == 0:
            on_progress("import_edges", idx, len(parsed))
        text = text_by_rel.get(rel, "")
        mod_nid = node_id("module", rel)
        dotted = mm["path_to_module"].get(rel) or module_map.path_to_dotted(rel)
        nodes[mod_nid] = {
            "id": mod_nid,
            "type": "module",
            "path": rel,
            "dotted": dotted,
            "is_package": rel.endswith("__init__.py"),
            "parse_ok": True,
            "line_count": _line_count(text),
        }
        edges.append({
            "type": "contains",
            "from": repo_nid,
            "to": mod_nid,
            "line": 1,
            "resolved": True,
        })
        _append_module_import_edges(rel, tree, mod_nid, mm, edges, unresolved)

    if on_progress:
        on_progress("import_edges", len(parsed), len(parsed))
    return _finalize_graph(root, nodes, edges, unresolved, parse_errors, detail=DETAIL_IMPORTS)


def build_graph_from_files(
    repository_root: str,
    files: Iterable[Tuple[str, str]],
    *,
    detail: str = DETAIL_FULL,
    deadline: Optional[float] = None,
    on_progress: Optional[Callable[[str, int, int], None]] = None,
) -> Dict[str, Any]:
    """Build a dependency graph from ``(rel_path, text)`` pairs."""
    root = os.path.abspath(repository_root).replace("\\", "/")
    file_list = sorted((rel.replace("\\", "/"), text) for rel, text in files)
    if len(file_list) > _MAX_FILES:
        return _degraded_graph(root, "too_many_files", len(file_list))
    if detail == DETAIL_IMPORTS:
        return _build_imports_detail_graph(
            root, file_list, deadline=deadline, on_progress=on_progress,
        )

    text_by_rel = dict(file_list)
    nodes: Dict[str, Dict[str, Any]] = {}
    edges: List[Dict[str, Any]] = []
    unresolved: Dict[str, List[Dict[str, Any]]] = {
        "imports_external": [],
        "calls_unresolved": [],
        "references_unresolved": [],
    }

    repo_nid = node_id("repository", root)
    nodes[repo_nid] = {
        "id": repo_nid,
        "type": "repository",
        "root": root,
        "python_files": len(file_list),
    }

    parsed: List[Tuple[str, ast.AST]] = []
    parse_errors: List[str] = []
    total_files = len(file_list)
    for idx, (rel, text) in enumerate(file_list):
        if _deadline_exceeded(deadline):
            return _finalize_graph(
                root, nodes, edges, unresolved, parse_errors,
                partial=True, timed_out=True, detail=DETAIL_FULL,
            )
        if on_progress and idx % 25 == 0:
            on_progress("parse", idx, total_files)
        try:
            parsed.append((rel, ast.parse(text)))
        except SyntaxError as exc:
            parse_errors.append(rel)
            mod_nid = node_id("module", rel)
            nodes[mod_nid] = {
                "id": mod_nid,
                "type": "module",
                "path": rel,
                "dotted": module_map.path_to_dotted(rel),
                "is_package": rel.endswith("__init__.py"),
                "parse_ok": False,
                "line_count": _line_count(text),
                "parse_error": f"{type(exc).__name__}: {exc.msg}",
            }
            edges.append({
                "type": "contains",
                "from": repo_nid,
                "to": mod_nid,
                "line": 1,
                "resolved": True,
            })

    mm = module_map.build_module_map([rel for rel, _ in parsed])
    fn_index, cls_index = _build_indexes(parsed, mm)

    qualnames_by_rel: Dict[str, Dict[ast.AST, str]] = {
        rel: callgraph._compute_qualnames(tree) for rel, tree in parsed
    }
    total_funcs = sum(len(qn) for qn in qualnames_by_rel.values())
    if total_funcs > _MAX_FUNCTIONS:
        return _degraded_graph(root, "too_many_functions", total_funcs)

    project_context = cross_file.build_project_context_from_parsed(parsed, mm) or {}
    cross_edges = project_context.get("resolved_edges", [])

    for file_idx, (rel, tree) in enumerate(parsed):
        if _deadline_exceeded(deadline):
            return _finalize_graph(
                root, nodes, edges, unresolved, parse_errors,
                partial=True, timed_out=True, detail=DETAIL_FULL,
            )
        if on_progress and file_idx % 10 == 0:
            on_progress("expand", file_idx, len(parsed))
        text = text_by_rel[rel]
        mod_nid = node_id("module", rel)
        dotted = mm["path_to_module"].get(rel) or module_map.path_to_dotted(rel)
        nodes[mod_nid] = {
            "id": mod_nid,
            "type": "module",
            "path": rel,
            "dotted": dotted,
            "is_package": rel.endswith("__init__.py"),
            "parse_ok": True,
            "line_count": _line_count(text),
        }
        edges.append({
            "type": "contains",
            "from": repo_nid,
            "to": mod_nid,
            "line": 1,
            "resolved": True,
        })

        qn_map = qualnames_by_rel[rel]
        struct_qn = _compute_structure_qualnames(tree)
        class_nodes: Dict[str, str] = {}
        function_nodes: Dict[str, str] = {}

        for child in ast.iter_child_nodes(tree):
            if isinstance(child, ast.ClassDef):
                qual = struct_qn[child]
                cid = node_id("class", rel, qual)
                class_nodes[qual] = cid
                bases = []
                for base in child.bases:
                    if isinstance(base, ast.Name):
                        bases.append(base.id)
                    elif isinstance(base, ast.Attribute):
                        bases.append(cross_file._dotted(base))
                    else:
                        try:
                            bases.append(ast.unparse(base))
                        except Exception:
                            bases.append("...")
                nodes[cid] = {
                    "id": cid,
                    "type": "class",
                    "path": rel,
                    "qualname": qual,
                    "line": child.lineno,
                    "bases": bases,
                }
                edges.append({
                    "type": "contains",
                    "from": _class_parent(rel, qual),
                    "to": cid,
                    "line": child.lineno,
                    "resolved": True,
                })

        for fn_node, qual in sorted(qn_map.items(), key=lambda kv: kv[1]):
            if not isinstance(fn_node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            fid = node_id("function", rel, qual)
            function_nodes[qual] = fid
            parent_kind, parent_id = _contains_parent(qual, rel, qn_map, fn_node)
            params = [a.arg for a in fn_node.args.args]
            decos = []
            for dec in fn_node.decorator_list:
                if isinstance(dec, ast.Name):
                    decos.append(dec.id)
                elif isinstance(dec, ast.Attribute):
                    decos.append(dec.attr)
                else:
                    try:
                        decos.append(ast.unparse(dec))
                    except Exception:
                        decos.append("...")
            nodes[fid] = {
                "id": fid,
                "type": "function",
                "path": rel,
                "qualname": qual,
                "line": fn_node.lineno,
                "params": params,
                "is_async": isinstance(fn_node, ast.AsyncFunctionDef),
                "decorators": decos,
            }
            edges.append({
                "type": "contains",
                "from": parent_id,
                "to": fid,
                "line": fn_node.lineno,
                "resolved": True,
            })

        it = imports.build_import_table(tree, _file_package(rel))
        _append_module_import_edges(rel, tree, mod_nid, mm, edges, unresolved)

        cg = callgraph.build_call_graph(tree, rel)
        for caller_qual, callees in sorted(cg.get("edges", {}).items()):
            caller_nid = node_id("function", rel, caller_qual)
            for callee_qual in callees:
                callee_nid = node_id("function", rel, callee_qual)
                matches = [
                    cs for cs in cg["call_sites"]
                    if cs["caller"] == caller_qual and cs["callee"] == callee_qual and cs["resolved"]
                ]
                line = min(cs["line"] for cs in matches)
                usage = matches[0]["usage"]
                edges.append({
                    "type": "calls",
                    "from": caller_nid,
                    "to": callee_nid,
                    "line": line,
                    "resolved": True,
                    "usage": usage,
                    "scope": "intra_file",
                })
        for cs in cg.get("call_sites", []):
            if not cs["resolved"]:
                unresolved["calls_unresolved"].append({
                    "file": rel,
                    "caller": cs["caller"],
                    "line": cs["line"],
                    "reason": "intra_file_unresolved",
                })

        for edge in cross_edges:
            if edge["caller_file"] != rel:
                continue
            caller_nid = node_id("function", rel, edge["caller"])
            callee_nid = node_id("function", edge["callee_file"], edge["callee"])
            edges.append({
                "type": "calls",
                "from": caller_nid,
                "to": callee_nid,
                "line": edge["line"],
                "resolved": True,
                "usage": edge.get("usage", callgraph.UNKNOWN_USAGE),
                "scope": "cross_file",
            })

        if project_context.get("per_file", {}).get(rel):
            for item in project_context["per_file"][rel].get("unresolved", []):
                unresolved["calls_unresolved"].append({
                    "file": rel,
                    "line": item["line"],
                    "reason": item["reason"],
                })

        for child in ast.walk(tree):
            if isinstance(child, ast.ClassDef):
                cid = class_nodes.get(struct_qn.get(child))
                if not cid:
                    continue
                for base in child.bases:
                    if isinstance(base, ast.Name):
                        target = _resolve_imported_symbol(
                            base.id, it, mm, fn_index, cls_index)
                        if target is None:
                            unresolved["references_unresolved"].append({
                                "file": rel,
                                "line": base.lineno,
                                "kind": "base_class",
                                "name": base.id,
                            })
                            continue
                        tgt_kind, tgt_file, tgt_qual = target
                        if tgt_kind != "class":
                            continue
                        edges.append({
                            "type": "references",
                            "from": cid,
                            "to": node_id("class", tgt_file, tgt_qual),
                            "line": base.lineno,
                            "resolved": True,
                            "kind": "base_class",
                        })

            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                owner_nid = (
                    node_id("function", rel, qn_map[child])
                    if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef))
                    else class_nodes.get(struct_qn[child])
                )
                if not owner_nid:
                    continue
                for dec in child.decorator_list:
                    if not isinstance(dec, ast.Name):
                        continue
                    target = _resolve_imported_symbol(
                        dec.id, it, mm, fn_index, cls_index)
                    if target is None:
                        unresolved["references_unresolved"].append({
                            "file": rel,
                            "line": dec.lineno,
                            "kind": "decorator",
                            "name": dec.id,
                        })
                        continue
                    tgt_kind, tgt_file, tgt_qual = target
                    edges.append({
                        "type": "references",
                        "from": owner_nid,
                        "to": node_id(tgt_kind, tgt_file, tgt_qual),
                        "line": dec.lineno,
                        "resolved": True,
                        "kind": "decorator",
                    })

    if on_progress:
        on_progress("expand", len(parsed), len(parsed))
    return _finalize_graph(root, nodes, edges, unresolved, parse_errors, detail=DETAIL_FULL)


def _degraded_graph(root: str, reason: str, count: int) -> Dict[str, Any]:
    repo_nid = node_id("repository", root)
    nodes = [{
        "id": repo_nid,
        "type": "repository",
        "root": root,
        "degraded": True,
        "degraded_reason": reason,
        "degraded_count": count,
    }]
    stats = compute_statistics(nodes, [], {"imports_external": [], "calls_unresolved": [], "references_unresolved": []})
    return {
        "schema_version": GRAPH_SCHEMA_VERSION,
        "repository_root": root,
        "nodes": nodes,
        "edges": [],
        "unresolved": {"imports_external": [], "calls_unresolved": [], "references_unresolved": []},
        "statistics": stats,
        "parse_errors": [],
        "degraded": True,
        "degraded_reason": reason,
        "degraded_count": count,
    }


def _dedupe_edges(edges: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    seen: Set[Tuple] = set()
    out: List[Dict[str, Any]] = []
    for edge in sorted(edges, key=_edge_sort_key):
        key = (
            edge["type"], edge["from"], edge.get("to"), edge.get("line"),
            edge.get("target_module"), edge.get("kind"), edge.get("scope"),
        )
        if key in seen:
            continue
        seen.add(key)
        out.append(edge)
    return out


def _edge_sort_key(edge: Dict[str, Any]) -> tuple:
    return (
        edge.get("type", ""),
        edge.get("from", ""),
        edge.get("to", ""),
        int(edge.get("line", 0)),
        edge.get("target_module", ""),
        edge.get("kind", ""),
        edge.get("scope", ""),
    )


def compute_statistics(
    nodes: List[Dict[str, Any]],
    edges: List[Dict[str, Any]],
    unresolved: Dict[str, List[Dict[str, Any]]],
) -> Dict[str, Any]:
    node_counts = {kind: 0 for kind in NODE_TYPES}
    for node in nodes:
        kind = node.get("type")
        if kind in node_counts:
            node_counts[kind] += 1

    edge_counts = {kind: 0 for kind in EDGE_TYPES}
    import_targets: Dict[str, int] = {}
    call_targets: Dict[str, int] = {}
    for edge in edges:
        et = edge.get("type")
        if et in edge_counts:
            edge_counts[et] += 1
        if et == "imports" and edge.get("resolved") and edge.get("to"):
            import_targets[edge["to"]] = import_targets.get(edge["to"], 0) + 1
        if et == "calls" and edge.get("resolved") and edge.get("to"):
            call_targets[edge["to"]] = call_targets.get(edge["to"], 0) + 1

    components = _largest_components(nodes, edges)
    import_edges = [e for e in edges if e.get("type") == "imports" and e.get("resolved")]
    # Cycle enumeration is exponential on dense import graphs; skip on large repos.
    if len(import_edges) > 3000:
        import_cycles: List[List[str]] = []
    elif len(import_edges) > 800:
        import_cycles = _import_cycles_bounded(import_edges, max_cycles=80)
    else:
        import_cycles = _import_cycles(edges)

    return {
        "node_counts": node_counts,
        "edge_counts": edge_counts,
        "total_nodes": len(nodes),
        "total_edges": len(edges),
        "top_imported_modules": _top_items(import_targets, nodes, "module"),
        "top_called_functions": _top_items(call_targets, nodes, "function"),
        "largest_components": components,
        "import_cycles": import_cycles,
        "unresolved_counts": {
            key: len(unresolved.get(key, []))
            for key in ("imports_external", "calls_unresolved", "references_unresolved")
        },
    }


def _top_items(counts: Dict[str, int], nodes: List[Dict[str, Any]], kind: str) -> List[Dict[str, Any]]:
    by_id = {n["id"]: n for n in nodes}
    ranked = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
    out: List[Dict[str, Any]] = []
    for nid, count in ranked[:10]:
        node = by_id.get(nid, {})
        out.append({
            "id": nid,
            "count": count,
            "path": node.get("path"),
            "qualname": node.get("qualname"),
            "dotted": node.get("dotted"),
        })
    return out


def _largest_components(
    nodes: List[Dict[str, Any]],
    edges: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    parent: Dict[str, str] = {n["id"]: n["id"] for n in nodes}

    def find(x: str) -> str:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a: str, b: str) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[rb] = ra

    for edge in edges:
        src = edge.get("from")
        dst = edge.get("to")
        if src in parent and dst in parent:
            union(src, dst)

    sizes: Dict[str, int] = {}
    for nid in parent:
        root = find(nid)
        sizes[root] = sizes.get(root, 0) + 1

    ranked = sorted(sizes.items(), key=lambda kv: (-kv[1], kv[0]))
    return [{"root": root, "size": size} for root, size in ranked[:10]]


def _import_cycles_bounded(
    import_edges: List[Dict[str, Any]],
    *,
    max_cycles: int = 120,
) -> List[List[str]]:
    """Collect import cycles up to ``max_cycles`` (avoids blow-up on huge repos)."""
    if max_cycles <= 0:
        return []
    adj: Dict[str, Set[str]] = {}
    for edge in import_edges:
        adj.setdefault(edge["from"], set()).add(edge["to"])
    cycles: List[List[str]] = []
    seen: Set[Tuple[str, ...]] = set()
    stack: List[str] = []
    on_stack: Set[str] = set()

    def dfs(node: str) -> bool:
        if len(cycles) >= max_cycles:
            return True
        on_stack.add(node)
        stack.append(node)
        for nxt in sorted(adj.get(node, ())):
            if nxt in on_stack:
                idx = stack.index(nxt)
                cycle = stack[idx:] + [nxt]
                key = _canonical_cycle(cycle)
                if key not in seen:
                    seen.add(key)
                    cycles.append(_closed_cycle(key))
                    if len(cycles) >= max_cycles:
                        return True
            elif nxt not in on_stack and dfs(nxt):
                return True
        stack.pop()
        on_stack.remove(node)
        return False

    for start in sorted(adj):
        if dfs(start):
            break
    cycles.sort(key=lambda c: c[0])
    return cycles


def _import_cycles(edges: List[Dict[str, Any]]) -> List[List[str]]:
    adj: Dict[str, Set[str]] = {}
    for edge in edges:
        if edge.get("type") != "imports" or not edge.get("resolved"):
            continue
        adj.setdefault(edge["from"], set()).add(edge["to"])

    cycles: List[List[str]] = []
    seen: Set[Tuple[str, ...]] = set()
    stack: List[str] = []
    on_stack: Set[str] = set()

    def dfs(node: str) -> None:
        on_stack.add(node)
        stack.append(node)
        for nxt in sorted(adj.get(node, ())):
            if nxt in on_stack:
                idx = stack.index(nxt)
                cycle = stack[idx:] + [nxt]
                key = _canonical_cycle(cycle)
                if key not in seen:
                    seen.add(key)
                    cycles.append(_closed_cycle(key))
            elif nxt not in on_stack:
                dfs(nxt)
        stack.pop()
        on_stack.remove(node)

    for start in sorted(adj):
        dfs(start)
    cycles.sort(key=lambda c: c[0])
    return cycles


def build_graph(
    repository_root: str,
    *,
    scope: str = PRODUCTION_SCOPE,
    include_tests: bool = False,
    detail: str = DETAIL_FULL,
    time_budget_sec: Optional[float] = None,
    on_progress: Optional[Callable[[str, int, int], None]] = None,
) -> Dict[str, Any]:
    """Build a dependency graph under ``repository_root``.

    ``scope='production'`` (default) reuses the RU-2 role classifier to keep only
    first-party production source, so generated/runtime/data/benchmark/report
    files do not push the graph over the cap. ``scope='full'`` is the legacy
    every-file behavior. ``include_tests=True`` additionally keeps test files.

    The result carries a ``graph_scope`` field (``production``/``full``/
    ``degraded``) and a ``scope_diagnostics`` block.
    """
    from . import engine

    root_abs = os.path.abspath(repository_root).replace("\\", "/")
    candidates = list(engine._collect_python_files(root_abs))
    total_candidates = len(candidates)

    if scope == FULL_SCOPE:
        kept = candidates
        excluded_by_role: Dict[str, int] = {}
    else:
        kept, excluded_by_role = _production_scope_filter(
            root_abs, candidates, include_tests=include_tests
        )

    deadline = (
        time.monotonic() + float(time_budget_sec)
        if time_budget_sec is not None and time_budget_sec > 0
        else None
    )
    files: List[Tuple[str, str]] = []
    timed_out_reading = False
    for abs_path, rel in kept:
        if _deadline_exceeded(deadline):
            timed_out_reading = True
            break
        try:
            with open(abs_path, "r", encoding="utf-8-sig", errors="ignore") as handle:
                files.append((rel.replace("\\", "/"), handle.read()))
        except OSError:
            continue

    graph = build_graph_from_files(
        repository_root,
        files,
        detail=detail,
        deadline=deadline,
        on_progress=on_progress,
    )
    if timed_out_reading and not graph.get("jarvis_timed_out"):
        graph["jarvis_timed_out"] = True
        graph["jarvis_partial"] = True
        graph["degraded"] = True
        graph["degraded_reason"] = "time_budget_exceeded"
    degraded = bool(graph.get("degraded"))
    graph["graph_scope"] = (
        DEGRADED_SCOPE if degraded else (FULL_SCOPE if scope == FULL_SCOPE else PRODUCTION_SCOPE)
    )
    graph["scope_diagnostics"] = {
        "requested_scope": scope,
        "include_tests": include_tests,
        "total_candidate_files": total_candidates,
        "files_kept": len(files),
        "files_excluded": total_candidates - len(files),
        "excluded_by_role": dict(sorted(excluded_by_role.items())),
        "degraded": degraded,
        "cap_files": _MAX_FILES,
        "cap_functions": _MAX_FUNCTIONS,
        "graph_detail": detail,
        "time_budget_sec": time_budget_sec,
    }
    return graph


def export_json(graph: Dict[str, Any]) -> str:
    return _stable_json(graph)


def format_summary(graph: Dict[str, Any]) -> str:
    stats = graph.get("statistics", {})
    nc = stats.get("node_counts", {})
    ec = stats.get("edge_counts", {})
    lines = [
        "DEPENDENCY GRAPH SUMMARY",
        f"schema: {graph.get('schema_version')}",
        f"repository: {graph.get('repository_root')}",
        "",
        "NODES",
        f"- total: {stats.get('total_nodes', 0)}",
    ]
    for kind in NODE_TYPES:
        lines.append(f"- {kind}: {nc.get(kind, 0)}")
    lines.extend([
        "",
        "EDGES",
        f"- total: {stats.get('total_edges', 0)}",
    ])
    for kind in EDGE_TYPES:
        lines.append(f"- {kind}: {ec.get(kind, 0)}")
    ur = stats.get("unresolved_counts", {})
    lines.extend([
        "",
        "UNRESOLVED",
        f"- imports_external: {ur.get('imports_external', 0)}",
        f"- calls_unresolved: {ur.get('calls_unresolved', 0)}",
        f"- references_unresolved: {ur.get('references_unresolved', 0)}",
    ])
    lines.extend(["", "TOP IMPORTED MODULES"])
    top_imp = stats.get("top_imported_modules") or []
    if not top_imp:
        lines.append("- (none)")
    else:
        for item in top_imp:
            label = item.get("dotted") or item.get("path") or item.get("id")
            lines.append(f"- {label}: {item['count']}")
    lines.extend(["", "TOP CALLED FUNCTIONS"])
    top_call = stats.get("top_called_functions") or []
    if not top_call:
        lines.append("- (none)")
    else:
        for item in top_call:
            label = item.get("qualname") or item.get("id")
            path = item.get("path", "")
            lines.append(f"- {path}::{label}: {item['count']}")
    lines.extend(["", "LARGEST COMPONENTS"])
    comps = stats.get("largest_components") or []
    if not comps:
        lines.append("- (none)")
    else:
        for comp in comps[:5]:
            lines.append(f"- size={comp['size']} root={comp['root']}")
    cycles = stats.get("import_cycles") or []
    lines.extend(["", "IMPORT CYCLES"])
    if not cycles:
        lines.append("- (none)")
    else:
        for cycle in cycles[:5]:
            lines.append(f"- {' -> '.join(cycle)}")
    if graph.get("degraded"):
        lines.extend(["", f"DEGRADED: {graph.get('degraded_reason', 'unknown')}"])
    return "\n".join(lines) + "\n"
