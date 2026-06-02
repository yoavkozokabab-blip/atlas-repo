"""Cross-file interprocedural resolution (Phase 93C — infrastructure only).

Builds an ephemeral, project-scoped cross-file call graph from an explicit import
table and callable export index (no name-only guessing). Resolves ONLY:
- a directly-imported callable symbol call ``func()`` (single candidate),
- a ``module.func()`` call through an imported module handle (single candidate),
- an explicit, unambiguous package ``__init__.py`` re-export, and
- a project class constructor only when it has an explicit ``__init__`` method.
Everything else is UNRESOLVED, with an explicit reason (star / ambiguous /
third-party / symbol-not-found / shadowed / dynamic).

The result is written to the parallel ``interproc.cross_file`` fact namespace and
is consumed by NO detector. Activated only in project mode (analyze_repository).
A single feature flag disables all of it.
"""

from __future__ import annotations

import ast
from typing import Any, Dict, List, Optional, Tuple

from . import callgraph, export_index, imports, module_map

# Feature flag — set to False to remove ALL cross-file behavior.
CROSS_FILE_ENABLED = True

# Phase 94E — explicit callable module exports and package re-exports.
EXPORT_INDEX_ENABLED = True

# safety caps (degrade to no cross-file context if exceeded)
_MAX_FILES = 5000
_MAX_FUNCTIONS = 50000


def _dotted(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        owner = _dotted(node.value)
        return f"{owner}.{node.attr}" if owner else ""
    return ""


def _file_package(rel_path: str) -> str:
    parts = rel_path.split("/")[:-1]  # directory of the file
    return ".".join(parts)


def _resolve_call(call: ast.Call, it: Dict[str, Any], mm: Dict[str, Any],
                  index: Dict[str, Dict[str, Tuple[str, str]]], bound: set
                  ) -> Tuple[Optional[Tuple[str, str]], Optional[str]]:
    """Return (FunctionId(callee_file, callee_qual), None) if resolved cross-file,
    else (None, reason) when it *looks* cross-file but is unresolved, else
    (None, None) when it is not a cross-file call at all."""
    f = call.func
    if isinstance(f, ast.Name):
        name = f.id
        if name in it["direct"]:
            if name in it["ambiguous"]:
                return None, "ambiguous_import"
            if name in bound:
                return None, "shadowed"
            mod, qual = it["direct"][name]
            tgt = mm["module_to_path"].get(mod)
            if tgt is None:
                return None, "third_party_or_unknown_module"
            funcs = index.get(mod, {})
            if qual in funcs:
                return funcs[qual], None
            return None, "symbol_not_found"
        if name in it["ambiguous"]:
            return None, "ambiguous_import"
        if it["has_star"] and name not in bound:
            return None, "star_import"
        return None, None  # not imported -> intra/local/unknown, not a cross-file edge
    if isinstance(f, ast.Attribute):
        base = _dotted(f.value)
        if not base:
            return None, "dynamic_or_complex"
        if base.split(".")[0] in bound:
            return None, "shadowed"
        if base in it["handles"]:
            mod = it["handles"][base]
            tgt = mm["module_to_path"].get(mod)
            if tgt is None:
                return None, "third_party_or_unknown_module"
            funcs = index.get(mod, {})
            if f.attr in funcs:
                return funcs[f.attr], None
            return None, "symbol_not_found"
        return None, None  # attribute on unknown object (e.g. a method) -> not cross-file
    return None, None


def build_project_context(files: List[Tuple[str, str]]) -> Optional[Dict[str, Any]]:
    """``files`` = list of (rel_path, text). Returns the project cross-file context
    or None when disabled / unbuildable."""
    if not CROSS_FILE_ENABLED:
        return None
    if len(files) > _MAX_FILES:
        return None

    parsed: List[Tuple[str, ast.AST]] = []
    for rel, text in files:
        try:
            parsed.append((rel, ast.parse(text)))
        except SyntaxError:
            continue
    if not parsed:
        return None

    mm = module_map.build_module_map([rel for rel, _ in parsed])

    # Legacy module-level function index remains available as an instant
    # rollback path for the additive Phase 94E export index.
    legacy_index: Dict[str, Dict[str, Tuple[str, str]]] = {}
    qn_by_file: Dict[str, Dict[ast.AST, str]] = {}
    total_funcs = 0
    for rel, tree in parsed:
        qn = callgraph._compute_qualnames(tree)
        qn_by_file[rel] = qn
        total_funcs += len(qn)
        mod = mm["path_to_module"].get(rel)
        if mod is None:
            continue
        for child in ast.iter_child_nodes(tree):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                legacy_index.setdefault(mod, {})[child.name] = (rel, child.name)
    if total_funcs > _MAX_FUNCTIONS:
        return None
    export_data = (
        export_index.build_export_index(parsed, mm)
        if EXPORT_INDEX_ENABLED
        else {"exports": legacy_index, "ambiguous": {}}
    )
    index = export_data["exports"]

    resolved: List[Dict[str, Any]] = []
    per_file_out: Dict[str, List[Dict[str, Any]]] = {rel: [] for rel, _ in parsed}
    per_file_unres: Dict[str, List[Dict[str, Any]]] = {rel: [] for rel, _ in parsed}

    for rel, tree in parsed:
        it = imports.build_import_table(tree, _file_package(rel))
        callgraph._attach_parents(tree)
        for fn_node, caller_qual in qn_by_file[rel].items():
            bound = callgraph._bound_names(fn_node)
            for n in callgraph._walk_local(fn_node):
                if not isinstance(n, ast.Call):
                    continue
                target, reason = _resolve_call(n, it, mm, index, bound)
                if target is not None:
                    usage = callgraph._classify_usage(n, fn_node)
                    edge = {
                        "caller_file": rel, "caller": caller_qual,
                        "callee_file": target[0], "callee": target[1],
                        "line": getattr(n, "lineno", 0), "usage": usage,
                    }
                    resolved.append(edge)
                    per_file_out[rel].append({
                        "callee_file": target[0], "callee": target[1],
                        "line": edge["line"], "usage": usage,
                    })
                elif reason is not None:
                    per_file_unres[rel].append({"line": getattr(n, "lineno", 0), "reason": reason})

    # global usage aggregation keyed by callee (callee_file, callee_qual)
    usage_global: Dict[Tuple[str, str], Dict[str, bool]] = {}
    for e in resolved:
        key = (e["callee_file"], e["callee"])
        agg = usage_global.setdefault(key, {"uses_return": False, "null_checked": False, "dereferenced": False})
        if e["usage"] != callgraph.IGNORED:
            agg["uses_return"] = True
        if e["usage"] == callgraph.NULL_CHECKED:
            agg["null_checked"] = True
        if e["usage"] == callgraph.DEREFERENCED:
            agg["dereferenced"] = True

    # per-file slice (what each file's analysis attaches under interproc.cross_file)
    per_file: Dict[str, Dict[str, Any]] = {}
    for rel, _ in parsed:
        ubc = {cq: dict(agg) for (cf, cq), agg in usage_global.items() if cf == rel}
        per_file[rel] = {
            "enabled": True,
            "usage_by_callee": ubc,            # how THIS file's functions are used by cross-file callers
            "outgoing": per_file_out[rel],      # resolved cross-file calls made from this file
            "unresolved": per_file_unres[rel],  # explicit cross-file UNRESOLVED reasons
        }

    return {
        "enabled": True,
        "per_file": per_file,
        "module_map": dict(mm["path_to_module"]),
        "export_index": index,
        "export_ambiguous": export_data["ambiguous"],
        "resolved_edges": resolved,
        "usage_global": {f"{cf}::{cq}": dict(agg) for (cf, cq), agg in usage_global.items()},
    }


def slice_for(context: Optional[Dict[str, Any]], rel_path: str) -> Optional[Dict[str, Any]]:
    if not context:
        return None
    return context.get("per_file", {}).get(rel_path)
