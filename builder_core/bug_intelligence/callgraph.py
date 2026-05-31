"""Ephemeral, conservative intra-file call graph (Phase 93A — infrastructure).

Builds an analysis-time call graph for the functions defined in ONE file:
- nodes are functions keyed by a FunctionId ``(file, qualname)``;
- edges are *same-file direct* calls only (a bare ``Name(...)`` call that
  resolves, unambiguously, to a module-level function defined in the same file);
- every call that is not such a direct, unshadowed, module-level call is marked
  UNRESOLVED — there is no guessing.

It also records, per call site, how the call's RESULT is used by the caller
(ignored / returned / null_checked / dereferenced / used_value). These are facts
only; no detector consumes them in Phase 93A. Nothing here is persisted.
"""

from __future__ import annotations

import ast
from collections import namedtuple
from typing import Any, Dict, List, Optional

FunctionId = namedtuple("FunctionId", ["file", "qualname"])

# call-site result-usage classes
IGNORED = "ignored"
RETURNED = "returned"
NULL_CHECKED = "null_checked"
DEREFERENCED = "dereferenced"
USED_VALUE = "used_value"
UNKNOWN_USAGE = "unknown"


# ---------------------------------------------------------------------------
# AST helpers
# ---------------------------------------------------------------------------
def _attach_parents(tree: ast.AST) -> None:
    for parent in ast.walk(tree):
        for child in ast.iter_child_nodes(parent):
            child._cg_parent = parent  # type: ignore[attr-defined]


def _walk_local(node: ast.AST):
    """Descendants of ``node`` that are NOT inside a nested function/lambda."""
    for child in ast.iter_child_nodes(node):
        yield child
        if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
            continue
        yield from _walk_local(child)


def _compute_qualnames(tree: ast.AST) -> Dict[ast.AST, str]:
    out: Dict[ast.AST, str] = {}

    def visit(node: ast.AST, prefix: str) -> None:
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                q = f"{prefix}{child.name}"
                out[child] = q
                visit(child, q + ".")
            elif isinstance(child, ast.ClassDef):
                visit(child, f"{prefix}{child.name}.")
            else:
                visit(child, prefix)

    visit(tree, "")
    return out


def _bound_names(fn: ast.AST) -> set:
    """Names bound locally in ``fn`` (params, assignments, nested def/class)."""
    names = set()
    a = fn.args
    for grp in (a.posonlyargs, a.args, a.kwonlyargs):
        names.update(arg.arg for arg in grp)
    if a.vararg:
        names.add(a.vararg.arg)
    if a.kwarg:
        names.add(a.kwarg.arg)
    for n in _walk_local(fn):
        if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store):
            names.add(n.id)
        elif isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.add(n.name)
    return names


# ---------------------------------------------------------------------------
# Result-usage classification
# ---------------------------------------------------------------------------
def _compares_none(cmp: ast.Compare) -> bool:
    operands = [cmp.left, *cmp.comparators]
    has_none = any(isinstance(o, ast.Constant) and o.value is None for o in operands)
    rel_op = any(isinstance(op, (ast.Is, ast.IsNot, ast.Eq, ast.NotEq)) for op in cmp.ops)
    return has_none and rel_op


def _is_null_check_context(node: ast.AST, parent: Optional[ast.AST]) -> bool:
    if parent is None:
        return False
    if isinstance(parent, ast.Compare) and _compares_none(parent):
        return True
    if isinstance(parent, ast.UnaryOp) and isinstance(parent.op, ast.Not):
        return True
    if isinstance(parent, ast.BoolOp):
        return True
    if isinstance(parent, (ast.If, ast.While, ast.IfExp)) and getattr(parent, "test", None) is node:
        return True
    return False


def _is_deref_context(node: ast.AST, parent: Optional[ast.AST]) -> bool:
    if parent is None:
        return False
    if isinstance(parent, ast.Attribute) and parent.value is node:
        return True
    if isinstance(parent, ast.Subscript) and parent.value is node:
        return True
    if isinstance(parent, ast.Call) and parent.func is node:
        return True
    return False


def _classify_var_usage(var: str, fn: ast.AST) -> str:
    null_checked = False
    deref = False
    for n in _walk_local(fn):
        if isinstance(n, ast.Name) and n.id == var and isinstance(n.ctx, ast.Load):
            p = getattr(n, "_cg_parent", None)
            if _is_null_check_context(n, p):
                null_checked = True
            elif _is_deref_context(n, p):
                deref = True
    if null_checked:
        return NULL_CHECKED
    if deref:
        return DEREFERENCED
    return USED_VALUE


def _classify_usage(call: ast.Call, fn: ast.AST) -> str:
    p = getattr(call, "_cg_parent", None)
    if p is None:
        return UNKNOWN_USAGE
    if isinstance(p, ast.Expr) and p.value is call:
        return IGNORED
    if isinstance(p, ast.Return) and p.value is call:
        return RETURNED
    if _is_deref_context(call, p):
        return DEREFERENCED
    if isinstance(p, ast.Compare):
        return NULL_CHECKED if _compares_none(p) else USED_VALUE
    if isinstance(p, ast.UnaryOp) and isinstance(p.op, ast.Not):
        return NULL_CHECKED
    if isinstance(p, ast.BoolOp):
        return NULL_CHECKED
    if isinstance(p, (ast.If, ast.While, ast.IfExp)) and getattr(p, "test", None) is call:
        return NULL_CHECKED
    if isinstance(p, (ast.Assign, ast.AnnAssign)) and getattr(p, "value", None) is call:
        targets = p.targets if isinstance(p, ast.Assign) else [p.target]
        names = [t.id for t in targets if isinstance(t, ast.Name)]
        if len(names) == 1:
            return _classify_var_usage(names[0], fn)
        return USED_VALUE
    return USED_VALUE


# ---------------------------------------------------------------------------
# Build
# ---------------------------------------------------------------------------
def build_call_graph(tree: ast.AST, file: str) -> Dict[str, Any]:
    _attach_parents(tree)
    qualnames = _compute_qualnames(tree)

    # module-level functions only are resolvable targets (same-file direct calls)
    module_level: Dict[str, str] = {}
    for child in ast.iter_child_nodes(tree):
        if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
            module_level.setdefault(child.name, qualnames[child])

    functions: Dict[str, Dict[str, Any]] = {}
    call_sites: List[Dict[str, Any]] = []

    for fn_node, qual in sorted(qualnames.items(), key=lambda kv: kv[1]):
        functions[qual] = {
            "id": (file, qual),
            "qualname": qual,
            "line": getattr(fn_node, "lineno", 0),
            "has_raise": any(isinstance(n, ast.Raise) for n in _walk_local(fn_node)),
        }
        bound = _bound_names(fn_node)
        for n in _walk_local(fn_node):
            if not isinstance(n, ast.Call):
                continue
            callee = None
            resolved = False
            if isinstance(n.func, ast.Name):
                name = n.func.id
                # resolve only an unshadowed, module-level, same-file function
                if name in module_level and name not in bound:
                    callee = module_level[name]
                    resolved = True
            # everything else (attribute calls, shadowed/unknown names) stays UNRESOLVED
            call_sites.append({
                "caller": qual,
                "callee": callee,
                "resolved": resolved,
                "line": getattr(n, "lineno", 0),
                "usage": _classify_usage(n, fn_node),
            })

    # derived indices (deterministic ordering)
    edges: Dict[str, List[str]] = {}
    callers_of: Dict[str, List[str]] = {}
    return_calls: Dict[str, List[Dict[str, Any]]] = {}
    usage_by_callee: Dict[str, Dict[str, bool]] = {}

    for cs in call_sites:
        caller, callee = cs["caller"], cs["callee"]
        if cs["resolved"] and callee is not None:
            edges.setdefault(caller, [])
            if callee not in edges[caller]:
                edges[caller].append(callee)
            callers_of.setdefault(callee, [])
            if caller not in callers_of[callee]:
                callers_of[callee].append(caller)
            agg = usage_by_callee.setdefault(
                callee, {"uses_return": False, "null_checked": False, "dereferenced": False})
            if cs["usage"] != IGNORED:
                agg["uses_return"] = True
            if cs["usage"] == NULL_CHECKED:
                agg["null_checked"] = True
            if cs["usage"] == DEREFERENCED:
                agg["dereferenced"] = True
        if cs["usage"] == RETURNED:
            return_calls.setdefault(caller, []).append(
                {"callee": callee, "resolved": cs["resolved"]})

    for d in (edges, callers_of):
        for k in d:
            d[k] = sorted(d[k])

    return {
        "file": file,
        "functions": functions,
        "call_sites": call_sites,
        "edges": edges,
        "callers_of": callers_of,
        "return_calls": return_calls,
        "usage_by_callee": usage_by_callee,
        "unresolved_count": sum(1 for cs in call_sites if not cs["resolved"]),
    }
