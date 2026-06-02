"""Deterministic logic-bug detectors (AST + control-flow heuristics).

Each detector takes a parsed module and the source lines and yields Findings.
The detectors are intentionally conservative and *explanatory*: every Finding
carries a human-readable reason, not just a label.

No detector mutates the tree or the source.
"""

from __future__ import annotations

import ast
from typing import Dict, List, Optional

from .findings import Finding

# Names that are dangerous to shadow because shadowing silently breaks later use.
_SHADOWABLE_BUILTINS = {
    "list", "dict", "set", "tuple", "str", "int", "float", "bool", "bytes",
    "len", "sum", "min", "max", "sorted", "reversed", "map", "filter", "range",
    "id", "type", "input", "next", "iter", "all", "any", "zip", "enumerate",
    "open", "format", "hash", "object", "vars",
}
_MUTATING_METHODS = {
    "add", "append", "clear", "discard", "extend", "insert", "pop",
    "remove", "reverse", "sort", "update",
}
_GRAPH_WORDS = ("successor", "neighbor", "neighbour", "adjacent", "edges", "children")


# ---------------------------------------------------------------------------
# Small AST helpers
# ---------------------------------------------------------------------------
def _line(lines: List[str], lineno: int) -> str:
    if 1 <= lineno <= len(lines):
        return lines[lineno - 1].strip()[:240]
    return ""


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


def attach_parents(tree: ast.AST) -> None:
    for parent in ast.walk(tree):
        for child in ast.iter_child_nodes(parent):
            child._bi_parent = parent  # type: ignore[attr-defined]


def enclosing_function(node: ast.AST) -> Optional[str]:
    cur = getattr(node, "_bi_parent", None)
    while cur is not None:
        if isinstance(cur, (ast.FunctionDef, ast.AsyncFunctionDef)):
            return cur.name
        cur = getattr(cur, "_bi_parent", None)
    return None


def iter_functions(tree: ast.AST):
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            yield node


def _const_value(node: ast.AST):
    return node.value if isinstance(node, ast.Constant) else _SENTINEL


_SENTINEL = object()


# ---------------------------------------------------------------------------
# Detectors
# ---------------------------------------------------------------------------
def detect_suspicious_conditionals(tree: ast.AST, lines: List[str]) -> List[Finding]:
    out: List[Finding] = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.If, ast.While)):
            test = node.test
            if isinstance(test, ast.Constant) and isinstance(test.value, bool):
                kind = type(node).__name__.lower()
                out.append(Finding(
                    rule="suspicious_conditional",
                    title=f"Constant {kind} condition",
                    severity="medium" if isinstance(node, ast.If) else "high",
                    confidence="high",
                    line=node.lineno,
                    function=enclosing_function(node),
                    message=(
                        f"The {kind} condition is the constant {test.value!r}, so the "
                        f"branch is taken unconditionally (or never). A real predicate "
                        f"was likely intended here."
                    ),
                    evidence=_line(lines, node.lineno),
                ))
        if isinstance(node, ast.Compare) and len(node.comparators) == 1:
            left, right = node.left, node.comparators[0]
            if ast.dump(left) == ast.dump(right):
                out.append(Finding(
                    rule="suspicious_conditional",
                    title="Comparison of an expression with itself",
                    severity="medium",
                    confidence="high",
                    line=node.lineno,
                    function=enclosing_function(node),
                    message=(
                        "Both sides of this comparison are identical, so the result is "
                        "constant. One side was probably meant to be a different value."
                    ),
                    evidence=_line(lines, node.lineno),
                ))
    return out


def detect_reversed_comparison(tree: ast.AST, lines: List[str]) -> List[Finding]:
    """Heuristic: a min/max-style function whose selecting comparison points the
    wrong way (a classic source of reversed-comparison bugs)."""
    out: List[Finding] = []
    for fn in iter_functions(tree):
        low = fn.name.lower()
        wants_smaller = any(w in low for w in ("min", "smallest", "lowest", "least"))
        wants_larger = any(w in low for w in ("max", "largest", "highest", "greatest"))
        if not (wants_smaller or wants_larger):
            continue
        for node in ast.walk(fn):
            if not isinstance(node, ast.Compare) or len(node.ops) != 1:
                continue
            op = node.ops[0]
            if wants_smaller and isinstance(op, (ast.Gt, ast.GtE)):
                out.append(Finding(
                    rule="reversed_comparison",
                    title=f"Possibly reversed comparison in '{fn.name}'",
                    severity="medium",
                    confidence="low",
                    line=node.lineno,
                    function=fn.name,
                    message=(
                        f"'{fn.name}' looks like it should select the smaller value, but "
                        f"this comparison uses '>'/'>='. If it guards the selection, the "
                        f"larger value may be chosen instead."
                    ),
                    evidence=_line(lines, node.lineno),
                ))
                break
            if wants_larger and isinstance(op, (ast.Lt, ast.LtE)):
                out.append(Finding(
                    rule="reversed_comparison",
                    title=f"Possibly reversed comparison in '{fn.name}'",
                    severity="medium",
                    confidence="low",
                    line=node.lineno,
                    function=fn.name,
                    message=(
                        f"'{fn.name}' looks like it should select the larger value, but "
                        f"this comparison uses '<'/'<='. The smaller value may be chosen."
                    ),
                    evidence=_line(lines, node.lineno),
                ))
                break
    return out


def detect_duplicated_branches(tree: ast.AST, lines: List[str]) -> List[Finding]:
    out: List[Finding] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.If) and node.orelse:
            # ignore elif chains (orelse is a single If) for the body-equality check
            body_dump = ast.dump(ast.Module(body=node.body, type_ignores=[]))
            else_dump = ast.dump(ast.Module(body=node.orelse, type_ignores=[]))
            if body_dump == else_dump and node.body:
                out.append(Finding(
                    rule="duplicated_branches",
                    title="if and else branches are identical",
                    severity="high",
                    confidence="high",
                    line=node.lineno,
                    function=enclosing_function(node),
                    message=(
                        "The 'if' body and the 'else' body are byte-for-byte identical, so "
                        "the condition has no effect. One branch was probably meant to differ."
                    ),
                    evidence=_line(lines, node.lineno),
                ))
        if isinstance(node, ast.IfExp):
            if ast.dump(node.body) == ast.dump(node.orelse):
                out.append(Finding(
                    rule="duplicated_branches",
                    title="Ternary returns the same value on both sides",
                    severity="medium",
                    confidence="high",
                    line=node.lineno,
                    function=enclosing_function(node),
                    message=(
                        "Both arms of this conditional expression are identical; the "
                        "condition cannot change the result."
                    ),
                    evidence=_line(lines, node.lineno),
                ))
    return out


def detect_impossible_conditions(tree: ast.AST, lines: List[str]) -> List[Finding]:
    out: List[Finding] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.BoolOp):
            continue
        dumps = [ast.dump(v) for v in node.values]
        # term AND/OR not(term)
        for i, v in enumerate(node.values):
            if isinstance(v, ast.UnaryOp) and isinstance(v.op, ast.Not):
                inner = ast.dump(v.operand)
                if inner in dumps:
                    is_and = isinstance(node.op, ast.And)
                    out.append(Finding(
                        rule="impossible_condition",
                        title="Contradictory boolean condition" if is_and
                        else "Tautological boolean condition",
                        severity="high" if is_and else "medium",
                        confidence="high",
                        line=node.lineno,
                        function=enclosing_function(node),
                        message=(
                            "Condition contains both X and not-X. With 'and' it is always "
                            "False (dead branch); with 'or' it is always True."
                        ),
                        evidence=_line(lines, node.lineno),
                    ))
                    break
        # numeric contradiction: name > a AND name < b with a >= b
        if isinstance(node.op, ast.And):
            bounds: Dict[str, List[tuple]] = {}
            for v in node.values:
                if (isinstance(v, ast.Compare) and len(v.ops) == 1
                        and isinstance(v.left, ast.Name)
                        and isinstance(v.comparators[0], ast.Constant)
                        and isinstance(v.comparators[0].value, (int, float))):
                    bounds.setdefault(v.left.id, []).append(
                        (v.ops[0], v.comparators[0].value))
            for var, constraints in bounds.items():
                lo = None
                hi = None
                for op, val in constraints:
                    if isinstance(op, (ast.Gt, ast.GtE)):
                        lo = val if lo is None else max(lo, val)
                    elif isinstance(op, (ast.Lt, ast.LtE)):
                        hi = val if hi is None else min(hi, val)
                if lo is not None and hi is not None and lo >= hi:
                    out.append(Finding(
                        rule="impossible_condition",
                        title=f"Unsatisfiable range for '{var}'",
                        severity="high",
                        confidence="medium",
                        line=node.lineno,
                        function=enclosing_function(node),
                        message=(
                            f"This requires '{var}' > {lo} and '{var}' < {hi} at once, which "
                            f"no value satisfies. The branch can never run."
                        ),
                        evidence=_line(lines, node.lineno),
                    ))
    return out


def detect_mutation_while_iterating(tree: ast.AST, lines: List[str]) -> List[Finding]:
    out: List[Finding] = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.For, ast.AsyncFor)):
            iter_name = _name(node.iter)
            if not iter_name:
                continue
            for child in ast.walk(node):
                if (isinstance(child, ast.Call)
                        and isinstance(child.func, ast.Attribute)
                        and _name(child.func.value) == iter_name
                        and child.func.attr in _MUTATING_METHODS):
                    out.append(Finding(
                        rule="mutation_while_iterating",
                        title=f"Mutating '{iter_name}' while iterating it",
                        severity="high",
                        confidence="high",
                        line=child.lineno,
                        function=enclosing_function(child),
                        message=(
                            f"The loop iterates '{iter_name}' but calls "
                            f"{child.func.attr}() on it inside the loop. Mutating a "
                            f"collection during iteration skips elements or raises."
                        ),
                        evidence=_line(lines, child.lineno),
                    ))
    return out


def detect_recursion(tree: ast.AST, lines: List[str]) -> List[Finding]:
    out: List[Finding] = []
    for fn in iter_functions(tree):
        nodes = list(ast.walk(fn))
        recursive = any(
            isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
            and n.func.id == fn.name
            for n in nodes
        )
        if not recursive:
            continue
        guarded_return = any(
            isinstance(n, ast.If)
            and any(isinstance(c, ast.Return) for c in ast.walk(n))
            for n in nodes
        )
        if not guarded_return:
            out.append(Finding(
                rule="recursion_no_termination",
                title=f"Recursion without an obvious base case in '{fn.name}'",
                severity="high",
                confidence="medium",
                line=fn.lineno,
                function=fn.name,
                message=(
                    f"'{fn.name}' calls itself but has no conditional (if-guarded) return "
                    f"that stops the recursion. This risks infinite recursion / stack "
                    f"overflow."
                ),
                evidence=_line(lines, fn.lineno),
            ))
    return out


def _return_shape(node: ast.Return) -> str:
    v = node.value
    if v is None:
        return "none"
    if isinstance(v, ast.Constant):
        if isinstance(v.value, bool):
            return "bool"
        if v.value is None:
            return "none"
        return type(v.value).__name__
    if isinstance(v, ast.List):
        return "list"
    if isinstance(v, ast.Tuple):
        return "tuple"
    if isinstance(v, ast.Dict):
        return "dict"
    if isinstance(v, ast.Set):
        return "set"
    return "value"


def detect_return_consistency(tree: ast.AST, lines: List[str]) -> List[Finding]:
    out: List[Finding] = []
    for fn in iter_functions(tree):
        returns = [n for n in ast.walk(fn) if isinstance(n, ast.Return)]
        shapes = {_return_shape(r) for r in returns}
        value_returns = [r for r in returns if _return_shape(r) != "none"]
        if len(shapes) > 1:
            out.append(Finding(
                rule="inconsistent_return",
                title=f"Inconsistent return types in '{fn.name}'",
                severity="medium",
                confidence="medium",
                line=fn.lineno,
                function=fn.name,
                message=(
                    f"'{fn.name}' returns differing kinds of values "
                    f"({', '.join(sorted(shapes))}). Callers cannot rely on a stable "
                    f"return type; this often signals a missed case."
                ),
                evidence=_line(lines, fn.lineno),
            ))
        # value-returns nested in branches but function can fall off the end → implicit None
        if value_returns:
            last = fn.body[-1] if fn.body else None
            falls_through = not isinstance(last, (ast.Return, ast.Raise))
            nested = any(
                getattr(r, "_bi_parent", None) is not fn for r in value_returns
            )
            if falls_through and nested and "none" not in shapes:
                out.append(Finding(
                    rule="inconsistent_return",
                    title=f"'{fn.name}' may fall through to an implicit None",
                    severity="medium",
                    confidence="low",
                    line=fn.lineno,
                    function=fn.name,
                    message=(
                        f"'{fn.name}' returns a value inside a branch but can also reach the "
                        f"end of the function without returning, yielding None. A missing "
                        f"final return is a common logic bug."
                    ),
                    evidence=_line(lines, fn.lineno),
                ))
    return out


def _walk_statement_lists(node: ast.AST):
    for _field, value in ast.iter_fields(node):
        if isinstance(value, list) and value and all(isinstance(i, ast.stmt) for i in value):
            yield value
            for item in value:
                yield from _walk_statement_lists(item)
        elif isinstance(value, ast.AST):
            yield from _walk_statement_lists(value)


def detect_unreachable(tree: ast.AST, lines: List[str]) -> List[Finding]:
    out: List[Finding] = []
    for body in _walk_statement_lists(tree):
        terminated_at = None
        for stmt in body:
            if terminated_at is not None:
                out.append(Finding(
                    rule="unreachable_code",
                    title="Unreachable statement",
                    severity="medium",
                    confidence="high",
                    line=stmt.lineno,
                    function=enclosing_function(stmt),
                    message=(
                        f"This statement follows an unconditional "
                        f"{terminated_at} on line earlier in the same block and can never "
                        f"execute."
                    ),
                    evidence=_line(lines, stmt.lineno),
                ))
                break
            if isinstance(stmt, (ast.Return, ast.Raise, ast.Break, ast.Continue)):
                terminated_at = type(stmt).__name__.lower()
    return out


def _has_len_plus_one(node: ast.AST) -> bool:
    if not isinstance(node, ast.BinOp) or not isinstance(node.op, ast.Add):
        return False
    pieces = (node.left, node.right)
    has_one = any(isinstance(p, ast.Constant) and p.value == 1 for p in pieces)
    has_len = any(
        isinstance(p, ast.Call) and isinstance(p.func, ast.Name) and p.func.id == "len"
        for p in pieces
    )
    return has_one and has_len


def detect_off_by_one(tree: ast.AST, lines: List[str]) -> List[Finding]:
    out: List[Finding] = []
    for node in ast.walk(tree):
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                and node.func.id == "range"):
            if any(_has_len_plus_one(a) for a in node.args):
                out.append(Finding(
                    rule="off_by_one",
                    title="range(len(...) + 1) overruns the sequence",
                    severity="high",
                    confidence="high",
                    line=node.lineno,
                    function=enclosing_function(node),
                    message=(
                        "Iterating range(len(seq) + 1) produces a final index equal to "
                        "len(seq), which is out of bounds when used to index seq."
                    ),
                    evidence=_line(lines, node.lineno),
                ))
            # range(1, len(x)) skips index 0 (sometimes intentional → low confidence)
            if (len(node.args) >= 2 and isinstance(node.args[0], ast.Constant)
                    and node.args[0].value == 1
                    and isinstance(node.args[1], ast.Call)
                    and isinstance(node.args[1].func, ast.Name)
                    and node.args[1].func.id == "len"):
                out.append(Finding(
                    rule="off_by_one",
                    title="Loop starts at index 1 and may skip the first element",
                    severity="medium",
                    confidence="low",
                    line=node.lineno,
                    function=enclosing_function(node),
                    message=(
                        "range(1, len(seq)) skips index 0. If the first element should be "
                        "processed, this is an off-by-one."
                    ),
                    evidence=_line(lines, node.lineno),
                ))
        if isinstance(node, ast.Compare):
            operands = [node.left, *node.comparators]
            has_len = any(
                isinstance(o, ast.Call) and isinstance(o.func, ast.Name)
                and o.func.id == "len" for o in operands
            )
            if has_len and any(isinstance(op, (ast.LtE, ast.GtE)) for op in node.ops):
                out.append(Finding(
                    rule="off_by_one",
                    title="Inclusive bound against len(...)",
                    severity="medium",
                    confidence="medium",
                    line=node.lineno,
                    function=enclosing_function(node),
                    message=(
                        "An inclusive comparison (<= or >=) against len(...) typically lets "
                        "an index reach len, which is one past the last valid position."
                    ),
                    evidence=_line(lines, node.lineno),
                ))
    return out


def detect_exception_swallowing(tree: ast.AST, lines: List[str]) -> List[Finding]:
    out: List[Finding] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.ExceptHandler):
            continue
        body = node.body
        only_pass = len(body) == 1 and isinstance(body[0], ast.Pass)
        only_continue = len(body) == 1 and isinstance(body[0], ast.Continue)
        if only_pass:
            out.append(Finding(
                rule="exception_swallowed",
                title="Exception silently swallowed",
                severity="high",
                confidence="high",
                line=node.lineno,
                function=enclosing_function(node),
                message=(
                    "This except handler does nothing but 'pass', hiding the error. A "
                    "failure here will be invisible and the program continues in a bad state."
                ),
                evidence=_line(lines, node.lineno),
            ))
        elif only_continue:
            out.append(Finding(
                rule="exception_swallowed",
                title="Exception swallowed by 'continue'",
                severity="medium",
                confidence="medium",
                line=node.lineno,
                function=enclosing_function(node),
                message=(
                    "The handler only continues the loop, discarding the exception. Real "
                    "errors are indistinguishable from normal control flow."
                ),
                evidence=_line(lines, node.lineno),
            ))
    return out


def detect_shadowing(tree: ast.AST, lines: List[str]) -> List[Finding]:
    out: List[Finding] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
            if node.id in _SHADOWABLE_BUILTINS:
                out.append(Finding(
                    rule="shadowed_name",
                    title=f"Shadowing builtin '{node.id}'",
                    severity="low",
                    confidence="medium",
                    line=node.lineno,
                    function=enclosing_function(node),
                    message=(
                        f"Assigning to '{node.id}' shadows the builtin of the same name. "
                        f"Later calls to {node.id}(...) in scope will fail or behave wrongly."
                    ),
                    evidence=_line(lines, node.lineno),
                ))
    # loop/comprehension variable shadowing a function parameter
    for fn in iter_functions(tree):
        params = {a.arg for a in fn.args.args} | {a.arg for a in fn.args.posonlyargs} \
            | {a.arg for a in fn.args.kwonlyargs}
        for node in ast.walk(fn):
            target = None
            if isinstance(node, (ast.For, ast.AsyncFor)) and isinstance(node.target, ast.Name):
                target = node.target.id
            elif isinstance(node, ast.comprehension) and isinstance(node.target, ast.Name):
                target = node.target.id
            if target and target in params:
                out.append(Finding(
                    rule="shadowed_name",
                    title=f"Loop variable shadows parameter '{target}'",
                    severity="medium",
                    confidence="low",
                    line=getattr(node, "lineno", fn.lineno),
                    function=fn.name,
                    message=(
                        f"The loop variable '{target}' shadows the parameter '{target}' of "
                        f"'{fn.name}'. The original argument is no longer reachable inside "
                        f"the loop."
                    ),
                    evidence=_line(lines, getattr(node, "lineno", fn.lineno)),
                ))
    return out


def detect_unused(tree: ast.AST, lines: List[str]) -> List[Finding]:
    out: List[Finding] = []
    # unused calculation: a pure expression used as a bare statement
    for node in ast.walk(tree):
        if isinstance(node, ast.Expr) and isinstance(
                node.value, (ast.BinOp, ast.BoolOp, ast.Compare, ast.UnaryOp)):
            out.append(Finding(
                rule="unused_result",
                title="Computed value is discarded",
                severity="medium",
                confidence="medium",
                line=node.lineno,
                function=enclosing_function(node),
                message=(
                    "This expression computes a value that is neither stored nor returned. "
                    "A missing assignment (=) or 'return' is the usual cause."
                ),
                evidence=_line(lines, node.lineno),
            ))
    # assigned-but-never-read within a function
    for fn in iter_functions(tree):
        nodes = list(ast.walk(fn))
        params = {a.arg for a in fn.args.args} | {a.arg for a in fn.args.posonlyargs} \
            | {a.arg for a in fn.args.kwonlyargs}
        assigned = {
            n.id for n in nodes
            if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store)
        }
        loaded = {
            n.id for n in nodes
            if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load)
        }
        for name in sorted(assigned - loaded - params):
            if not name.startswith("_"):
                out.append(Finding(
                    rule="unused_variable",
                    title=f"Variable '{name}' is assigned but never used",
                    severity="low",
                    confidence="medium",
                    line=fn.lineno,
                    function=fn.name,
                    message=(
                        f"'{fn.name}' assigns '{name}' but never reads it. The computed "
                        f"value is lost — possibly the wrong variable is used elsewhere."
                    ),
                    evidence=_line(lines, fn.lineno),
                ))
    return out


# ---------------------------------------------------------------------------
# Algorithm / name mismatch — the high-value, explanatory detector
# ---------------------------------------------------------------------------
def _pop_calls(fn: ast.AST):
    """Yield (node, kind) for .pop() calls: kind in {'stack', 'queue', 'other'}."""
    for n in ast.walk(fn):
        if (isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                and n.func.attr in ("pop", "popleft")):
            if n.func.attr == "popleft":
                yield n, "queue"
            elif not n.args:
                yield n, "stack"  # list.pop() removes from the END → LIFO
            elif (len(n.args) == 1 and isinstance(n.args[0], ast.Constant)
                  and n.args[0].value == 0):
                yield n, "queue"  # pop(0) removes from the FRONT → FIFO
            else:
                yield n, "other"


def _func_text(fn: ast.AST, lines: List[str]) -> str:
    start = fn.lineno - 1
    end = getattr(fn, "end_lineno", fn.lineno)
    return "\n".join(lines[start:end]).lower()


def detect_algorithm_mismatch(tree: ast.AST, lines: List[str], file_stem: str) -> List[Finding]:
    out: List[Finding] = []
    for fn in iter_functions(tree):
        low = fn.name.lower()
        stem = file_stem.lower()
        text = _func_text(fn, lines)
        names = low + " " + stem

        # --- Breadth-first search --------------------------------------
        # NOTE (Phase 87): the name-bound BFS branch (queue-as-stack,
        # while-True termination, missing-visited) was retired. BFS frontier
        # termination is now detected name-free by
        # detect_unguarded_container_consumption (dataflow-backed). The
        # name-matched queue-as-stack / visited heuristics are not replaced
        # (we are not chasing recall in this phase).

        # --- Depth-first search ----------------------------------------
        if "depth_first" in names or low == "dfs" or stem == "dfs":
            queue_pops = [n for n, k in _pop_calls(fn) if k == "queue"]
            if queue_pops:
                line = queue_pops[0].lineno
                out.append(Finding(
                    rule="algorithm_mismatch",
                    title=f"'{fn.name}' consumes its frontier FIFO",
                    severity="high",
                    confidence="high",
                    line=line,
                    function=fn.name,
                    message=(
                        f"'{fn.name}' is named for depth-first search but removes from the "
                        f"front of the frontier (pop(0)/popleft, FIFO) on line {line}. DFS "
                        f"needs LIFO (stack) order or recursion; as written it behaves like BFS."
                    ),
                    evidence=_line(lines, line),
                ))

        # --- Binary search ---------------------------------------------
        elif "binary_search" in names or "bisect" in names:
            text_l = text
            has_mid = "// 2" in text_l or "//2" in text_l or ">> 1" in text_l or ">>1" in text_l
            if not has_mid:
                out.append(Finding(
                    rule="algorithm_mismatch",
                    title=f"'{fn.name}' lacks a midpoint computation",
                    severity="medium",
                    confidence="medium",
                    line=fn.lineno,
                    function=fn.name,
                    message=(
                        f"'{fn.name}' is named for binary search but computes no midpoint "
                        f"(no //2 or >>1). Without halving the range it cannot achieve "
                        f"logarithmic search and may be a linear scan."
                    ),
                    evidence=_line(lines, fn.lineno),
                ))

        # --- factorial / fibonacci / gcd small structural checks --------
        elif "factorial" in names:
            if not any(isinstance(n, ast.BinOp) and isinstance(n.op, ast.Mult)
                       for n in ast.walk(fn)):
                out.append(_simple_mismatch(fn, lines, "factorial", "multiplication (*)"))
        elif "fibonacci" in names or low == "fib":
            if not any(isinstance(n, ast.BinOp) and isinstance(n.op, ast.Add)
                       for n in ast.walk(fn)):
                out.append(_simple_mismatch(fn, lines, "Fibonacci", "addition (+)"))
        elif low == "gcd" or "greatest_common" in names:
            if not any(isinstance(n, ast.BinOp) and isinstance(n.op, ast.Mod)
                       for n in ast.walk(fn)):
                out.append(_simple_mismatch(fn, lines, "GCD", "a modulo (%) step"))

    return [f for f in out if f is not None]


def _simple_mismatch(fn, lines, label, expectation) -> Finding:
    return Finding(
        rule="algorithm_mismatch",
        title=f"'{fn.name}' missing expected {label} operation",
        severity="medium",
        confidence="low",
        line=fn.lineno,
        function=fn.name,
        message=(
            f"'{fn.name}' is named like a {label} routine but does not use {expectation}, "
            f"which that algorithm normally requires. Worth confirming it is implemented "
            f"correctly."
        ),
        evidence=_line(lines, fn.lineno),
    )


# ---------------------------------------------------------------------------
# Dataflow-backed, name-free frontier-termination detector (Phase 87)
# ---------------------------------------------------------------------------
def detect_unguarded_container_consumption(tree: ast.AST, lines: List[str]) -> List[Finding]:
    """Name-free replacement for the retired BFS algorithm_mismatch branch.

    Uses the Phase 86 dataflow fact layer: flags a loop that grows AND consumes
    the same container while the loop guard does not depend on that container
    and no empty-container exit precedes the consumption. No function name,
    variable name, or file name is used to decide a hit.
    """
    from . import dataflow  # lazy import to avoid package-init ordering issues

    out: List[Finding] = []
    facts = dataflow.analyze_source("\n".join(lines))
    for hit in dataflow.find_unbounded_frontier_loops(facts):
        line = hit["loop_line"]
        out.append(Finding(
            rule="unguarded_container_consumption",
            title="Loop consumes a container with no empty-container guard",
            severity="high",
            confidence="high",
            line=line,
            function=hit.get("function") or None,
            message=(
                "A loop grows and consumes the same container every iteration, but its "
                "guard does not depend on that container and no empty-container check "
                "precedes the consumption. When the container empties before the loop's "
                "other exit condition, the consume operation fails (dequeue/pop from an "
                "empty container) instead of terminating. The loop should stop when the "
                "container is empty."
            ),
            evidence=_line(lines, line),
        ))
    return out


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------
ALL_DETECTORS = [
    detect_suspicious_conditionals,
    detect_reversed_comparison,
    detect_duplicated_branches,
    detect_impossible_conditions,
    detect_mutation_while_iterating,
    detect_recursion,
    detect_return_consistency,
    detect_unreachable,
    detect_off_by_one,
    detect_exception_swallowing,
    detect_shadowing,
    detect_unused,
    detect_unguarded_container_consumption,
]


def run_all(tree: ast.AST, lines: List[str], file_stem: str) -> List[Finding]:
    attach_parents(tree)
    findings: List[Finding] = []
    for detector in ALL_DETECTORS:
        try:
            findings.extend(detector(tree, lines))
        except Exception:
            # a single detector must never crash the whole analysis
            continue
    try:
        findings.extend(detect_algorithm_mismatch(tree, lines, file_stem))
    except Exception:
        pass
    return findings
