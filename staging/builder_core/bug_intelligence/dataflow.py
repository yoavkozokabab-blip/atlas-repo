"""Intraprocedural Data Flow Analysis — a FACT layer (Phase 86).

This module emits *facts* about Python functions, never *findings*. It is the
representation layer recommended by the Phase 85 generalization strategy: it
lets bug reasoning operate over value behavior (def-use, container
mutation/consumption, loop-guard dependencies, recursion argument changes)
instead of over function names and variable shapes.

Design rules:
- No function-name matching anywhere. Facts are derived purely from structure.
- No bug rules, no Finding objects, no severities. Facts only.
- Read-only; AST-based; intraprocedural; Python only.
- A single uncomputable function degrades to empty facts, never crashes.

Public API:
    analyze_source(text, path="<source>") -> dict   # {"module", "functions": [...]}
    analyze_file(path)                    -> dict
    find_unguarded_consumption_loops(facts) -> list # fact-pattern query (NOT a rule)

The headline demonstration (see find_unguarded_consumption_loops): the QuixBugs
BFS bug is representable, without names, as a loop that
    consumes a container
    AND whose guard does not depend on that container
    AND has no explicit empty-container exit before the consumption.
"""

from __future__ import annotations

import ast
import os
from typing import Any, Dict, List, Optional, Set, Tuple

# Container method classification (name-agnostic: about behavior, not algorithms).
GROW_OPS = {"append", "appendleft", "extend", "add", "update", "insert", "push"}
CONSUME_OPS = {"pop", "popleft", "popright", "remove", "discard", "popitem"}
KNOWN_CONTAINER_CTORS = {
    "list": "list", "dict": "dict", "set": "set", "frozenset": "set",
    "tuple": "tuple", "deque": "deque", "Queue": "deque", "LifoQueue": "deque",
    "defaultdict": "dict", "OrderedDict": "dict", "Counter": "dict",
}
_MAX_NODES = 20000  # safety cap; oversized functions degrade to empty facts


# ---------------------------------------------------------------------------
# AST helpers
# ---------------------------------------------------------------------------
def _name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        owner = _name(node.value)
        return f"{owner}.{node.attr}" if owner else node.attr
    try:
        return ast.unparse(node)
    except Exception:
        return ""


def _unparse(node: Optional[ast.AST]) -> str:
    if node is None:
        return ""
    try:
        return ast.unparse(node)
    except Exception:
        return ""


def _walk_local(node: ast.AST):
    """Yield all descendants of ``node`` WITHOUT descending into nested
    function/lambda definitions (so a function's facts exclude inner scopes)."""
    for child in ast.iter_child_nodes(node):
        yield child
        if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
            continue
        yield from _walk_local(child)


def _names_in(node: ast.AST) -> List[str]:
    return [n.id for n in ast.walk(node) if isinstance(n, ast.Name)]


def _return_kind(value: Optional[ast.AST]) -> str:
    if value is None:
        return "none"
    if isinstance(value, ast.Constant):
        if isinstance(value.value, bool):
            return "bool"
        if value.value is None:
            return "none"
        return type(value.value).__name__
    if isinstance(value, ast.List):
        return "list"
    if isinstance(value, ast.Tuple):
        return "tuple"
    if isinstance(value, ast.Dict):
        return "dict"
    if isinstance(value, ast.Set):
        return "set"
    return "value"


# ---------------------------------------------------------------------------
# Container mutation
# ---------------------------------------------------------------------------
def _mutation(call: ast.AST) -> Optional[Dict[str, Any]]:
    """If ``call`` is a container mutation, return its fact, else None."""
    if not (isinstance(call, ast.Call) and isinstance(call.func, ast.Attribute)):
        return None
    container = _name(call.func.value)
    op = call.func.attr
    if op in GROW_OPS:
        return {"container": container, "op": op, "grows": True,
                "consumes": False, "order": None, "line": call.lineno}
    if op in CONSUME_OPS:
        order = None
        if op == "popleft":
            order = "fifo"
        elif op == "pop":
            if not call.args:
                order = "lifo"
            elif (len(call.args) == 1 and isinstance(call.args[0], ast.Constant)
                  and call.args[0].value == 0):
                order = "fifo"
            elif (len(call.args) == 1 and isinstance(call.args[0], ast.Constant)
                  and call.args[0].value == -1):
                order = "lifo"
            else:
                order = "unknown"
        return {"container": container, "op": op, "grows": False,
                "consumes": True, "order": order, "line": call.lineno}
    return None


def _local_mutations(node: ast.AST) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for n in _walk_local(node):
        m = _mutation(n)
        if m:
            out.append(m)
    return out


# ---------------------------------------------------------------------------
# Emptiness-guard detection
# ---------------------------------------------------------------------------
def _emptiness_targets(test: ast.AST) -> Set[str]:
    """Container names that ``test`` checks for emptiness/falsiness."""
    targets: Set[str] = set()

    def add_len_arg(call: ast.AST):
        if (isinstance(call, ast.Call) and isinstance(call.func, ast.Name)
                and call.func.id == "len" and call.args):
            targets.add(_name(call.args[0]))

    # not C   /   not len(C)
    if isinstance(test, ast.UnaryOp) and isinstance(test.op, ast.Not):
        operand = test.operand
        if isinstance(operand, ast.Name):
            targets.add(operand.id)
        else:
            add_len_arg(operand)
        return targets

    # len(C) == 0 / len(C) < 1 / 0 == len(C) / C == [] / C == {} / C == set()
    if isinstance(test, ast.Compare):
        operands = [test.left, *test.comparators]
        for o in operands:
            add_len_arg(o)
        # C compared to an empty literal
        names = [o for o in operands if isinstance(o, ast.Name)]
        empties = [
            o for o in operands
            if (isinstance(o, (ast.List, ast.Dict, ast.Set)) and not getattr(o, "elts", getattr(o, "keys", [1])))
            or (isinstance(o, ast.Call) and isinstance(o.func, ast.Name)
                and o.func.id in ("set", "list", "dict") and not o.args)
        ]
        if names and empties:
            for n in names:
                targets.add(n.id)
    return targets


def _body_exits(body: List[ast.stmt]) -> bool:
    for stmt in body:
        for n in [stmt, *list(_walk_local(stmt))]:
            if isinstance(n, (ast.Return, ast.Break, ast.Raise, ast.Continue)):
                return True
    return False


def _guard_events(loop: ast.AST) -> List[Tuple[str, int]]:
    """(container, lineno) for emptiness-exit guards inside the loop body."""
    events: List[Tuple[str, int]] = []
    for n in _walk_local(loop):
        if isinstance(n, ast.If) and _body_exits(n.body):
            for c in _emptiness_targets(n.test):
                events.append((c, n.lineno))
    return events


# ---------------------------------------------------------------------------
# Loops
# ---------------------------------------------------------------------------
def _loop_facts(loop: ast.AST) -> Dict[str, Any]:
    is_while = isinstance(loop, ast.While)
    if is_while:
        guard = _unparse(loop.test)
        guard_vars = sorted(set(_names_in(loop.test)))
        iter_expr = ""
        iter_vars: List[str] = []
    else:  # for / async for
        guard = ""
        guard_vars = []
        iter_expr = _unparse(loop.iter)
        iter_vars = sorted(set(_names_in(loop.iter)))

    mutations = _local_mutations(loop)
    grows = sorted({m["container"] for m in mutations if m["grows"]})
    consumes = sorted({m["container"] for m in mutations if m["consumes"]})
    mutates = sorted({m["container"] for m in mutations})
    orders = sorted({m["order"] for m in mutations if m["consumes"] and m["order"]})

    # termination depends on a consumed container if the guard reads it
    dep_vars = set(guard_vars) if is_while else set(iter_vars)
    termination_depends = bool(set(consumes) & dep_vars)

    # explicit empty-exit before the first consume, per consumed container
    guard_events = _guard_events(loop)
    consume_first: Dict[str, int] = {}
    for m in mutations:
        if m["consumes"]:
            c = m["container"]
            consume_first[c] = min(consume_first.get(c, m["line"]), m["line"])
    guarded_before: Set[str] = set()
    for c, first_line in consume_first.items():
        if any(gc == c and gl < first_line for gc, gl in guard_events):
            guarded_before.add(c)
    has_empty_guard_before_consume = bool(consumes) and set(consumes) <= guarded_before

    body_reads = sorted({
        n.id for n in _walk_local(loop)
        if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load)
    })
    body_writes = sorted({
        n.id for n in _walk_local(loop)
        if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store)
    })
    has_break = any(isinstance(n, ast.Break) for n in _walk_local(loop))
    has_return = any(isinstance(n, ast.Return) for n in _walk_local(loop))

    # Derived FACT (not a rule): the name-agnostic shape of the BFS bug.
    unguarded_consumption = (
        bool(consumes)
        and not termination_depends
        and not has_empty_guard_before_consume
    )

    return {
        "type": "while" if is_while else "for",
        "line": loop.lineno,
        "guard": guard if is_while else iter_expr,
        "guard_vars": guard_vars if is_while else iter_vars,
        "mutates": mutates,
        "grows": grows,
        "consumes": consumes,
        "consume_order": orders,
        "termination_depends_on_consumed_container": termination_depends,
        "has_empty_guard_before_consume": has_empty_guard_before_consume,
        "unguarded_consumption": unguarded_consumption,
        "body_reads": body_reads,
        "body_writes": body_writes,
        "has_break": has_break,
        "has_return": has_return,
    }


# ---------------------------------------------------------------------------
# Containers (function level)
# ---------------------------------------------------------------------------
def _container_facts(fn: ast.AST) -> List[Dict[str, Any]]:
    mutations = _local_mutations(fn)
    names = sorted({m["container"] for m in mutations})

    created_as: Dict[str, str] = {}
    created_line: Dict[str, int] = {}
    for n in _walk_local(fn):
        if isinstance(n, ast.Assign) and len(n.targets) == 1 and isinstance(n.targets[0], ast.Name):
            target = n.targets[0].id
            kind = _container_kind(n.value)
            if kind:
                created_as.setdefault(target, kind)
                created_line.setdefault(target, n.lineno)

    out: List[Dict[str, Any]] = []
    for name in names:
        muts = [m for m in mutations if m["container"] == name]
        consume_orders = sorted({m["order"] for m in muts if m["consumes"] and m["order"]})
        if consume_orders == ["fifo"]:
            behavior = "fifo"
        elif consume_orders == ["lifo"]:
            behavior = "lifo"
        elif len(consume_orders) > 1:
            behavior = "mixed"
        else:
            behavior = "unknown"
        out.append({
            "name": name,
            "created_as": created_as.get(name, "unknown"),
            "created_line": created_line.get(name, None),
            "grown": any(m["grows"] for m in muts),
            "consumed": any(m["consumes"] for m in muts),
            "consume_behavior": behavior,
            "mutations": [
                {"op": m["op"], "line": m["line"], "grows": m["grows"],
                 "consumes": m["consumes"], "order": m["order"]}
                for m in muts
            ],
        })
    return out


def _container_kind(value: ast.AST) -> Optional[str]:
    if isinstance(value, (ast.List, ast.ListComp)):
        return "list"
    if isinstance(value, (ast.Set, ast.SetComp)):
        return "set"
    if isinstance(value, (ast.Dict, ast.DictComp)):
        return "dict"
    if isinstance(value, ast.Call) and isinstance(value.func, ast.Name):
        return KNOWN_CONTAINER_CTORS.get(value.func.id)
    return None


# ---------------------------------------------------------------------------
# Recursion
# ---------------------------------------------------------------------------
def _classify_arg_change(param: str, arg: ast.AST) -> str:
    if isinstance(arg, ast.Name):
        return "same" if arg.id == param else "unknown"
    if isinstance(arg, ast.BinOp) and isinstance(arg.left, ast.Name) and arg.left.id == param:
        if isinstance(arg.op, (ast.Sub, ast.FloorDiv, ast.Div, ast.RShift)):
            return "shrink"
        if isinstance(arg.op, (ast.Add, ast.Mult, ast.LShift, ast.Pow)):
            return "grow"
    if isinstance(arg, ast.Subscript) and isinstance(arg.value, ast.Name) and arg.value.id == param:
        if isinstance(arg.slice, ast.Slice):
            return "shrink"
    return "unknown"


def _recursion_facts(fn: ast.AST, params: List[str]) -> Dict[str, Any]:
    calls: List[Dict[str, Any]] = []
    for n in _walk_local(fn):
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == fn.name:
            changes = []
            for idx, arg in enumerate(n.args):
                param = params[idx] if idx < len(params) else f"arg{idx}"
                changes.append({"param": param, "change": _classify_arg_change(param, arg)})
            calls.append({
                "line": n.lineno,
                "args": [_unparse(a) for a in n.args],
                "arg_changes": changes,
                "shrinks_any_arg": any(c["change"] == "shrink" for c in changes),
            })
    has_base_case = any(
        isinstance(n, ast.If) and any(isinstance(c, ast.Return) for c in _walk_local(n))
        for n in _walk_local(fn)
    )
    return {
        "is_recursive": bool(calls),
        "calls": calls,
        "shrinks_any_arg": any(c["shrinks_any_arg"] for c in calls),
        "has_base_case": has_base_case,
    }


# ---------------------------------------------------------------------------
# Def-use
# ---------------------------------------------------------------------------
def _def_use_facts(fn: ast.AST, params: List[str]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], Dict[str, Any]]:
    defs: List[Dict[str, Any]] = []
    uses: List[Dict[str, Any]] = []

    for p in params:
        defs.append({"name": p, "line": fn.lineno, "kind": "param"})

    for n in _walk_local(fn):
        if isinstance(n, ast.Name):
            if isinstance(n.ctx, ast.Store):
                defs.append({"name": n.id, "line": n.lineno, "kind": "assign"})
            elif isinstance(n.ctx, ast.Load):
                uses.append({"name": n.id, "line": n.lineno})
        elif isinstance(n, ast.ExceptHandler) and n.name:
            defs.append({"name": n.name, "line": n.lineno, "kind": "except"})

    summary: Dict[str, Any] = {}
    for d in defs:
        summary.setdefault(d["name"], {"defs": [], "uses": []})
        summary[d["name"]]["defs"].append(d["line"])
    for u in uses:
        summary.setdefault(u["name"], {"defs": [], "uses": []})
        summary[u["name"]]["uses"].append(u["line"])
    for name, rec in summary.items():
        rec["defs"] = sorted(set(rec["defs"]))
        rec["uses"] = sorted(set(rec["uses"]))
        rec["defined"] = bool(rec["defs"])
        rec["used"] = bool(rec["uses"])
    return defs, uses, summary


# ---------------------------------------------------------------------------
# Function + module
# ---------------------------------------------------------------------------
def _function_facts(fn: ast.AST) -> Dict[str, Any]:
    params: List[str] = []
    a = fn.args
    for group in (a.posonlyargs, a.args, a.kwonlyargs):
        params.extend(arg.arg for arg in group)
    if a.vararg:
        params.append(a.vararg.arg)
    if a.kwarg:
        params.append(a.kwarg.arg)

    loops = [
        _loop_facts(n) for n in _walk_local(fn)
        if isinstance(n, (ast.While, ast.For, ast.AsyncFor))
    ]
    returns = [
        {"line": n.lineno, "expr": _unparse(n.value), "kind": _return_kind(n.value),
         "is_constant": isinstance(n.value, ast.Constant)}
        for n in _walk_local(fn) if isinstance(n, ast.Return)
    ]
    branches = [
        {"line": n.lineno, "test": _unparse(n.test), "test_vars": sorted(set(_names_in(n.test)))}
        for n in _walk_local(fn) if isinstance(n, ast.If)
    ]
    calls = [
        {"func": _name(n.func), "line": n.lineno}
        for n in _walk_local(fn) if isinstance(n, ast.Call)
    ]
    defs, uses, def_use = _def_use_facts(fn, params)

    return {
        "name": fn.name,
        "line": fn.lineno,
        "params": params,
        "containers": _container_facts(fn),
        "loops": loops,
        "returns": returns,
        "branches": branches,
        "calls": calls,
        "recursion": _recursion_facts(fn, params),
        "defs": defs,
        "uses": uses,
        "def_use": def_use,
    }


def analyze_source(text: str, path: str = "<source>") -> Dict[str, Any]:
    """Return data-flow facts for all functions defined in ``text``."""
    try:
        tree = ast.parse(text)
    except SyntaxError as exc:
        return {"module": path, "parse_error": f"{type(exc).__name__}: {exc.msg}",
                "functions": []}

    functions: List[Dict[str, Any]] = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if sum(1 for _ in ast.walk(node)) > _MAX_NODES:
                functions.append({"name": node.name, "line": node.lineno,
                                  "skipped": "too_large", "loops": [], "containers": [],
                                  "returns": [], "branches": [], "calls": [],
                                  "recursion": {"is_recursive": False, "calls": [],
                                                "shrinks_any_arg": False, "has_base_case": False},
                                  "defs": [], "uses": [], "def_use": {}, "params": []})
                continue
            try:
                functions.append(_function_facts(node))
            except Exception:
                functions.append({"name": node.name, "line": node.lineno,
                                  "error": "analysis_failed", "loops": [], "containers": [],
                                  "returns": [], "branches": [], "calls": [],
                                  "recursion": {"is_recursive": False, "calls": [],
                                                "shrinks_any_arg": False, "has_base_case": False},
                                  "defs": [], "uses": [], "def_use": {}, "params": []})
    return {"module": path, "parse_error": "", "functions": functions}


def analyze_file(path: str) -> Dict[str, Any]:
    try:
        with open(path, "r", encoding="utf-8-sig", errors="ignore") as fh:
            text = fh.read()
    except OSError as exc:
        return {"module": path, "parse_error": f"OSError: {exc}", "functions": []}
    return analyze_source(text, path=os.path.basename(path))


# ---------------------------------------------------------------------------
# Fact-pattern query (demonstration — explicitly NOT a registered bug rule)
# ---------------------------------------------------------------------------
def find_unguarded_consumption_loops(facts: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Return loops whose facts match the name-agnostic BFS-bug shape:

        a container is consumed inside the loop
        AND the loop guard does not depend on that container
        AND there is no explicit empty-container exit before consumption.

    This is a *query over facts*, used for demonstration/validation. It returns
    plain fact dictionaries; it creates no Finding and registers no rule.
    """
    hits: List[Dict[str, Any]] = []
    for fn in facts.get("functions", []):
        for loop in fn.get("loops", []):
            if loop.get("unguarded_consumption"):
                hits.append({
                    "function": fn["name"],
                    "loop_line": loop["line"],
                    "consumed_containers": loop["consumes"],
                    "guard": loop["guard"],
                    "guard_vars": loop["guard_vars"],
                    "reasons": [
                        f"container(s) {loop['consumes']} are consumed in the loop body",
                        f"loop guard '{loop['guard']}' does not read {loop['consumes']} "
                        f"(guard_vars={loop['guard_vars']})",
                        "no empty-container exit precedes the consumption",
                    ],
                })
    return hits


def find_unbounded_frontier_loops(facts: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Stricter, higher-precision variant of the unguarded-consumption query.

    Returns loops that both GROW and CONSUME the same container while the loop
    guard does not depend on it and no empty-exit precedes the consumption — the
    self-expanding worklist shape (BFS/DFS/graph frontier). This is the fact
    pattern the Phase 87 ``unguarded_container_consumption`` finding consumes.

    Purely structural: no function/variable/file name is used to decide a hit.
    """
    hits: List[Dict[str, Any]] = []
    for fn in facts.get("functions", []):
        for loop in fn.get("loops", []):
            # Only `while` loops have container-independent termination risk. A
            # `for` loop always terminates by exhausting its (finite) iterator,
            # so popping an auxiliary container inside it is not a
            # non-termination bug (e.g. RPN / shunting-yard stacks). Restricting
            # to `while` removes those false positives while keeping the BFS bug.
            if loop.get("type") != "while":
                continue
            if not loop.get("unguarded_consumption"):
                continue
            frontier = sorted(set(loop.get("consumes", [])) & set(loop.get("grows", [])))
            if not frontier:
                continue
            hits.append({
                "function": fn.get("name", ""),
                "loop_line": loop["line"],
                "frontier_containers": frontier,
                "guard": loop["guard"],
                "guard_vars": loop["guard_vars"],
                "consume_order": loop.get("consume_order", []),
            })
    return hits
