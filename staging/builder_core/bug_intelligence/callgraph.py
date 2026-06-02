"""Ephemeral, conservative intra-file call graph (Phase 93A — infrastructure).

Builds an analysis-time call graph for the functions defined in ONE file:
- nodes are functions keyed by a FunctionId ``(file, qualname)``;
- edges are *same-file direct* calls (a bare ``Name(...)`` call that
  resolves, unambiguously, to a module-level function defined in the same file);
- Phase 94D adds *proven* same-file method calls (``self`` / ``cls`` / a local
  instance of a file-local class / ``ClassName.method()``) when the callee method
  is defined in that class in the same file;
- every other call is marked UNRESOLVED — there is no guessing.

It also records, per call site, how the call's RESULT is used by the caller
(ignored / returned / null_checked / dereferenced / used_value). These are facts
only; no detector consumes them in Phase 93A. Nothing here is persisted.
"""

from __future__ import annotations

import ast
from collections import namedtuple
from typing import Any, Dict, List, Optional, Set

FunctionId = namedtuple("FunctionId", ["file", "qualname"])

# Phase 94D — resolve proven intra-file method calls (self/cls/instance/ClassName).
METHOD_RESOLUTION_ENABLED = True

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


def _build_class_method_index(tree: ast.AST) -> Dict[str, Dict[str, str]]:
    """Map class qualname -> {method_name: method_qualname} for same-file classes."""
    index: Dict[str, Dict[str, str]] = {}

    def visit_class(class_node: ast.ClassDef, prefix: str) -> None:
        qual = f"{prefix}.{class_node.name}" if prefix else class_node.name
        for child in ast.iter_child_nodes(class_node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                index.setdefault(qual, {})[child.name] = f"{qual}.{child.name}"
            elif isinstance(child, ast.ClassDef):
                visit_class(child, qual)

    for child in ast.iter_child_nodes(tree):
        if isinstance(child, ast.ClassDef):
            visit_class(child, "")
    return index


def _module_level_class_names(tree: ast.AST) -> Dict[str, str]:
    """Short class name -> class qualname (module-level classes only)."""
    out: Dict[str, str] = {}
    for child in ast.iter_child_nodes(tree):
        if isinstance(child, ast.ClassDef):
            out[child.name] = child.name
    return out


def _class_node_qualnames(tree: ast.AST) -> Dict[ast.ClassDef, str]:
    """Map each ``ClassDef`` node to its dotted qualname within the file."""
    out: Dict[ast.ClassDef, str] = {}

    def visit_class(class_node: ast.ClassDef, prefix: str) -> None:
        qual = f"{prefix}.{class_node.name}" if prefix else class_node.name
        out[class_node] = qual
        for child in ast.iter_child_nodes(class_node):
            if isinstance(child, ast.ClassDef):
                visit_class(child, qual)

    for child in ast.iter_child_nodes(tree):
        if isinstance(child, ast.ClassDef):
            visit_class(child, "")
    return out


def _visible_class_short_names(tree: ast.AST) -> Dict[str, str]:
    """Module-level short class name -> class qualname."""
    return dict(_module_level_class_names(tree))


def _visible_class_short_names_for_fn(
    fn_node: ast.AST,
    tree: ast.AST,
    class_node_quals: Dict[ast.ClassDef, str],
) -> Dict[str, str]:
    """Unambiguous class short names visible from ``fn_node``'s lexical scope."""
    out: Dict[str, str] = dict(_module_level_class_names(tree))
    ambiguous: Set[str] = set()

    enclosing_classes: List[ast.ClassDef] = []
    current: Optional[ast.AST] = fn_node
    while current is not None:
        if isinstance(current, ast.ClassDef):
            enclosing_classes.append(current)
        current = getattr(current, "_cg_parent", None)

    for class_node in reversed(enclosing_classes):
        prefix = class_node_quals.get(class_node, class_node.name)

        def visit_nested(node: ast.ClassDef, parent_qual: str) -> None:
            for child in ast.iter_child_nodes(node):
                if isinstance(child, ast.ClassDef):
                    short = child.name
                    fq = f"{parent_qual}.{child.name}"
                    if short in out and out[short] != fq:
                        ambiguous.add(short)
                    else:
                        out[short] = fq
                    visit_nested(child, fq)

        visit_nested(class_node, prefix)

    for short in ambiguous:
        out.pop(short, None)
    return out


def _enclosing_class_qual(caller_qual: str) -> Optional[str]:
    if "." not in caller_qual:
        return None
    return caller_qual.rsplit(".", 1)[0]


def _enclosing_class_qual_ast(
    fn_node: ast.AST, class_node_quals: Dict[ast.ClassDef, str]
) -> Optional[str]:
    current: Optional[ast.AST] = fn_node
    while current is not None:
        if isinstance(current, ast.ClassDef):
            return class_node_quals.get(current)
        current = getattr(current, "_cg_parent", None)
    return None


def _self_receiver_context(fn_node: ast.AST) -> bool:
    """True when ``self`` in a method call refers to an instance method receiver."""
    if _first_param_name(fn_node) == "self":
        return True
    current: Optional[ast.AST] = getattr(fn_node, "_cg_parent", None)
    while current is not None and not isinstance(current, ast.ClassDef):
        if isinstance(current, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if _first_param_name(current) == "self":
                return True
        current = getattr(current, "_cg_parent", None)
    return False


def _cls_receiver_context(fn_node: ast.AST) -> bool:
    """True when ``cls`` in a method call refers to a classmethod receiver."""
    if _first_param_name(fn_node) == "cls" or _is_classmethod(fn_node):
        return True
    current: Optional[ast.AST] = getattr(fn_node, "_cg_parent", None)
    while current is not None and not isinstance(current, ast.ClassDef):
        if isinstance(current, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if _first_param_name(current) == "cls" or _is_classmethod(current):
                return True
        current = getattr(current, "_cg_parent", None)
    return False


def _first_param_name(fn_node: ast.AST) -> Optional[str]:
    args = getattr(fn_node, "args", None)
    if args is None or not args.args:
        return None
    return args.args[0].arg


def _is_classmethod(fn_node: ast.AST) -> bool:
    for dec in fn_node.decorator_list:
        if isinstance(dec, ast.Name) and dec.id == "classmethod":
            return True
        if isinstance(dec, ast.Attribute) and dec.attr == "classmethod":
            return True
    return False


def _class_from_rhs(
    value: ast.AST,
    class_by_name: Dict[str, str],
    class_methods: Optional[Dict[str, Dict[str, str]]] = None,
) -> Optional[str]:
    if not isinstance(value, ast.Call):
        return None
    func = value.func
    if isinstance(func, ast.Name) and func.id in class_by_name:
        return class_by_name[func.id]
    if (
        class_methods is not None
        and isinstance(func, ast.Attribute)
        and isinstance(func.value, ast.Name)
    ):
        base = func.value.id
        if base in class_by_name:
            qual = f"{class_by_name[base]}.{func.attr}"
            if qual in class_methods:
                return qual
    return None


def _local_instance_bindings(
    fn_node: ast.AST,
    class_by_name: Dict[str, str],
    class_methods: Optional[Dict[str, Dict[str, str]]] = None,
) -> Dict[str, str]:
    """Variables proven to hold an instance of exactly one file-local class."""
    seen: Dict[str, Set[str]] = {}
    for node in _walk_local(fn_node):
        targets: List[str] = []
        rhs: Optional[ast.AST] = None
        if isinstance(node, ast.Assign):
            targets = [t.id for t in node.targets if isinstance(t, ast.Name)]
            rhs = node.value
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            targets = [node.target.id]
            rhs = node.value
        elif isinstance(node, ast.NamedExpr) and isinstance(node.target, ast.Name):
            targets = [node.target.id]
            rhs = node.value
        if not targets or rhs is None:
            continue
        cls = _class_from_rhs(rhs, class_by_name, class_methods)
        if cls is None:
            continue
        for name in targets:
            seen.setdefault(name, set()).add(cls)
    out: Dict[str, str] = {}
    for name, classes in seen.items():
        if len(classes) == 1:
            out[name] = next(iter(classes))
    return out


def _resolve_method_call(
    call: ast.Call,
    fn_node: ast.AST,
    caller_qual: str,
    class_methods: Dict[str, Dict[str, str]],
    class_by_name: Dict[str, str],
    instance_bindings: Dict[str, str],
    class_node_quals: Dict[ast.ClassDef, str],
) -> Optional[str]:
    if not isinstance(call.func, ast.Attribute):
        return None
    attr = call.func.attr
    receiver = call.func.value
    if not isinstance(receiver, ast.Name):
        return None

    class_qual: Optional[str] = None
    recv = receiver.id
    enclosing = _enclosing_class_qual_ast(fn_node, class_node_quals)

    if recv == "self" and _self_receiver_context(fn_node) and enclosing:
        class_qual = enclosing
    elif recv == "cls" and _cls_receiver_context(fn_node) and enclosing:
        class_qual = enclosing
    elif recv in instance_bindings:
        class_qual = instance_bindings[recv]
    elif recv in class_by_name:
        class_qual = class_by_name[recv]

    if class_qual is None:
        return None
    methods = class_methods.get(class_qual, {})
    return methods.get(attr)


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
    class_methods = _build_class_method_index(tree) if METHOD_RESOLUTION_ENABLED else {}
    class_node_quals = (
        _class_node_qualnames(tree) if METHOD_RESOLUTION_ENABLED else {}
    )

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
        visible_classes = (
            _visible_class_short_names_for_fn(fn_node, tree, class_node_quals)
            if METHOD_RESOLUTION_ENABLED else {}
        )
        instance_bindings = (
            _local_instance_bindings(fn_node, visible_classes, class_methods)
            if METHOD_RESOLUTION_ENABLED else {}
        )
        for n in _walk_local(fn_node):
            if not isinstance(n, ast.Call):
                continue
            callee = None
            resolved = False
            resolution = None
            if isinstance(n.func, ast.Name):
                name = n.func.id
                # resolve only an unshadowed, module-level, same-file function
                if name in module_level and name not in bound:
                    callee = module_level[name]
                    resolved = True
                    resolution = "module_level"
            elif METHOD_RESOLUTION_ENABLED:
                method_qual = _resolve_method_call(
                    n,
                    fn_node,
                    qual,
                    class_methods,
                    visible_classes,
                    instance_bindings,
                    class_node_quals,
                )
                if method_qual is not None and method_qual in qualnames.values():
                    callee = method_qual
                    resolved = True
                    resolution = "method"
            site: Dict[str, Any] = {
                "caller": qual,
                "callee": callee,
                "resolved": resolved,
                "line": getattr(n, "lineno", 0),
                "usage": _classify_usage(n, fn_node),
            }
            if resolution is not None:
                site["resolution"] = resolution
            call_sites.append(site)

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
