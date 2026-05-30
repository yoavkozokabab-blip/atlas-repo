"""Value-aware intraprocedural data-flow core (Phase 89).

Produces value-level FACTS for a single Python function:
  - minimal CFG (basic blocks + edges)
  - assignment definitions, variable uses, reaching definitions
  - branch conditions
  - return values
  - container state (maybe_empty / non_empty / unknown; grows / shrinks / consumed)
  - nullability (definitely_none / definitely_not_none / maybe_none / unknown)
  - integer interval hints (exact / lower / upper / unknown)
  - taint (source / propagated / sanitized / untainted) + dangerous-sink observations

It emits facts only. The security layer (`security.py`) turns the taint/sink
facts into findings. Intraprocedural, Python-AST only, read-only, deterministic,
no LLM. A single uncomputable function degrades to partial facts, never crashes.
"""

from __future__ import annotations

import ast
import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple

# Container method behavior (name-agnostic).
GROW_OPS = {"append", "appendleft", "extend", "add", "update", "insert", "push"}
SHRINK_OPS = {"pop", "popleft", "popright", "remove", "discard", "popitem", "clear"}
CONSUME_OPS = {"pop", "popleft", "popright", "remove", "discard", "popitem"}

# Taint sources / sanitizers (declarative, intraprocedural).
SOURCE_CALLS = {"input"}                       # builtins returning external data
SOURCE_READ_METHODS = {"read", "readline", "readlines", "recv"}
SOURCE_NAMES = {"request"}                      # common web request object
SANITIZER_CALLS = {"int", "float", "len", "bool"}   # numeric / length -> not a string payload
SANITIZER_DOTTED = {"shlex.quote", "html.escape", "os.path.basename", "shutil.quote"}

_MAX_NODES = 20000


# ---------------------------------------------------------------------------
# Abstract value
# ---------------------------------------------------------------------------
@dataclass
class AV:
    null: str = "unknown"          # definitely_none / definitely_not_none / maybe_none / unknown
    taint: str = "untainted"       # source / propagated / sanitized / untainted
    interval: Dict[str, Any] = field(default_factory=lambda: {"kind": "unknown"})
    container: str = "unknown"     # maybe_empty / non_empty / unknown

    def copy(self) -> "AV":
        return AV(self.null, self.taint, dict(self.interval), self.container)

    @property
    def tainted(self) -> bool:
        return self.taint in ("source", "propagated")


def _join_null(a: str, b: str) -> str:
    if a == b:
        return a
    order = {"definitely_none", "definitely_not_none", "maybe_none", "unknown"}
    if a == "unknown" or b == "unknown":
        return "unknown"
    # none + not-none, or either + maybe -> maybe_none
    return "maybe_none"


def _join_taint(a: str, b: str) -> str:
    if a == b:
        return a
    if "source" in (a, b) or "propagated" in (a, b):
        return "propagated"
    if "sanitized" in (a, b):
        return "sanitized"
    return "untainted"


def join_av(a: AV, b: AV) -> AV:
    return AV(
        null=_join_null(a.null, b.null),
        taint=_join_taint(a.taint, b.taint),
        interval={"kind": "unknown"},
        container=a.container if a.container == b.container else "unknown",
    )


def join_env(a: Dict[str, AV], b: Dict[str, AV]) -> Dict[str, AV]:
    out: Dict[str, AV] = {}
    for k in set(a) | set(b):
        if k in a and k in b:
            out[k] = join_av(a[k], b[k])
        else:
            out[k] = (a.get(k) or b.get(k)).copy()
    return out


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------
def _dotted(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        owner = _dotted(node.value)
        return f"{owner}.{node.attr}" if owner else node.attr
    return ""


def _unparse(node: Optional[ast.AST]) -> str:
    if node is None:
        return ""
    try:
        return ast.unparse(node)
    except Exception:
        return ""


def _line_text(lines: List[str], lineno: int) -> str:
    if 1 <= lineno <= len(lines):
        return lines[lineno - 1].strip()[:240]
    return ""


def _terminates(stmts: List[ast.stmt]) -> bool:
    return bool(stmts) and isinstance(stmts[-1], (ast.Return, ast.Raise, ast.Break, ast.Continue))


def _names_loaded(node: ast.AST) -> List[ast.Name]:
    return [n for n in ast.walk(node) if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load)]


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
    return "value"


# ---------------------------------------------------------------------------
# Reaching definitions (structured walk over the function)
# ---------------------------------------------------------------------------
def _record_uses(node: ast.AST, state: Dict[str, Set[int]], out: Dict[int, Dict[str, List[int]]]) -> None:
    for name in _names_loaded(node):
        out.setdefault(name.lineno, {})[name.id] = sorted(state.get(name.id, set()))


def _rd_walk(stmts: List[ast.stmt], state: Dict[str, Set[int]], out: Dict[int, Dict[str, List[int]]]) -> Dict[str, Set[int]]:
    for stmt in stmts:
        if isinstance(stmt, ast.Assign):
            _record_uses(stmt.value, state, out)
            for tgt in stmt.targets:
                for n in ast.walk(tgt):
                    if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store):
                        state[n.id] = {stmt.lineno}
        elif isinstance(stmt, ast.AugAssign):
            _record_uses(stmt.value, state, out)
            if isinstance(stmt.target, ast.Name):
                _record_uses(ast.Name(id=stmt.target.id, ctx=ast.Load(), lineno=stmt.lineno, col_offset=0), state, out)
                state[stmt.target.id] = {stmt.lineno}
        elif isinstance(stmt, ast.AnnAssign):
            if stmt.value is not None:
                _record_uses(stmt.value, state, out)
            if isinstance(stmt.target, ast.Name):
                state[stmt.target.id] = {stmt.lineno}
        elif isinstance(stmt, (ast.Return, ast.Expr, ast.Assert, ast.Raise, ast.Delete)):
            if getattr(stmt, "value", None) is not None or isinstance(stmt, (ast.Expr, ast.Assert, ast.Raise, ast.Delete)):
                _record_uses(stmt, state, out)
        elif isinstance(stmt, ast.If):
            _record_uses(stmt.test, state, out)
            s_then = _rd_walk(stmt.body, {k: set(v) for k, v in state.items()}, out)
            s_else = _rd_walk(stmt.orelse, {k: set(v) for k, v in state.items()}, out)
            merged: Dict[str, Set[int]] = {}
            for k in set(s_then) | set(s_else):
                merged[k] = set(s_then.get(k, set())) | set(s_else.get(k, set()))
            state = merged
        elif isinstance(stmt, (ast.For, ast.AsyncFor)):
            _record_uses(stmt.iter, state, out)
            if isinstance(stmt.target, ast.Name):
                state[stmt.target.id] = {stmt.lineno}
            s_body = _rd_walk(stmt.body, {k: set(v) for k, v in state.items()}, out)
            for k in set(s_body) | set(state):
                state[k] = set(state.get(k, set())) | set(s_body.get(k, set()))
            _rd_walk(stmt.orelse, {k: set(v) for k, v in state.items()}, out)
        elif isinstance(stmt, ast.While):
            _record_uses(stmt.test, state, out)
            s_body = _rd_walk(stmt.body, {k: set(v) for k, v in state.items()}, out)
            for k in set(s_body) | set(state):
                state[k] = set(state.get(k, set())) | set(s_body.get(k, set()))
            _rd_walk(stmt.orelse, {k: set(v) for k, v in state.items()}, out)
        elif isinstance(stmt, (ast.With, ast.AsyncWith)):
            for item in stmt.items:
                _record_uses(item.context_expr, state, out)
                if item.optional_vars is not None and isinstance(item.optional_vars, ast.Name):
                    state[item.optional_vars.id] = {stmt.lineno}
            state = _rd_walk(stmt.body, state, out)
        elif isinstance(stmt, ast.Try):
            state = _rd_walk(stmt.body, state, out)
            for handler in stmt.handlers:
                _rd_walk(handler.body, {k: set(v) for k, v in state.items()}, out)
            state = _rd_walk(stmt.orelse, state, out)
            state = _rd_walk(stmt.finalbody, state, out)
        # nested defs are intentionally skipped (intraprocedural)
    return state


# ---------------------------------------------------------------------------
# Minimal CFG (basic blocks + edges, best-effort)
# ---------------------------------------------------------------------------
def _build_cfg(fn: ast.AST) -> List[Dict[str, Any]]:
    blocks: List[Dict[str, Any]] = []

    def new_block(kind: str = "seq") -> int:
        blocks.append({"id": len(blocks), "kind": kind, "lines": [], "succ": []})
        return len(blocks) - 1

    def link(a: int, b: int) -> None:
        if b not in blocks[a]["succ"]:
            blocks[a]["succ"].append(b)

    def build_seq(stmts: List[ast.stmt], cur: int) -> List[int]:
        for stmt in stmts:
            if isinstance(stmt, ast.If):
                blocks[cur]["lines"].append(stmt.lineno)
                blocks[cur]["kind"] = "branch"
                then_b = new_block("seq")
                link(cur, then_b)
                then_exits = build_seq(stmt.body, then_b)
                if stmt.orelse:
                    else_b = new_block("seq")
                    link(cur, else_b)
                    else_exits = build_seq(stmt.orelse, else_b)
                else:
                    else_exits = [cur]
                merge = new_block("merge")
                for e in then_exits + ([] if else_exits == [cur] else else_exits):
                    link(e, merge)
                if else_exits == [cur]:
                    link(cur, merge)
                cur = merge
            elif isinstance(stmt, (ast.For, ast.AsyncFor, ast.While)):
                header = new_block("loop_header")
                blocks[header]["lines"].append(stmt.lineno)
                link(cur, header)
                body_b = new_block("seq")
                link(header, body_b)
                body_exits = build_seq(stmt.body, body_b)
                for e in body_exits:
                    link(e, header)
                after = new_block("seq")
                link(header, after)
                cur = after
            elif isinstance(stmt, (ast.With, ast.AsyncWith, ast.Try)):
                blocks[cur]["lines"].append(stmt.lineno)
                body = stmt.body
                cur_exits = build_seq(body, cur)
                cur = cur_exits[0] if cur_exits else cur
            else:
                blocks[cur]["lines"].append(stmt.lineno)
                if isinstance(stmt, (ast.Return, ast.Raise, ast.Break, ast.Continue)):
                    return []  # terminates this path
        return [cur]

    try:
        entry = new_block("entry")
        build_seq(fn.body, entry)
    except Exception:
        if not blocks:
            new_block("entry")
    return blocks


# ---------------------------------------------------------------------------
# Flow analyzer: nullability / interval / taint / container + null-deref + sinks
# ---------------------------------------------------------------------------
class FlowAnalyzer:
    def __init__(self, fn: ast.AST, lines: List[str]):
        self.fn = fn
        self.lines = lines
        self.value_findings: List[Dict[str, Any]] = []
        self.sinks: List[Dict[str, Any]] = []
        self.sources: List[Dict[str, Any]] = []
        self._deref_seen: Set[Tuple[int, str]] = set()
        # summaries (joined across paths)
        self.null_summary: Dict[str, str] = {}
        self.taint_summary: Dict[str, str] = {}
        self.interval_summary: Dict[str, Dict[str, Any]] = {}

    # -- env entry ------------------------------------------------------
    def initial_env(self) -> Dict[str, AV]:
        env: Dict[str, AV] = {}
        a = self.fn.args
        params: List[ast.arg] = [*a.posonlyargs, *a.args, *a.kwonlyargs]
        defaults = list(a.defaults)
        # map trailing defaults to args
        pos = [*a.posonlyargs, *a.args]
        default_for: Dict[str, Optional[ast.AST]] = {}
        if defaults:
            for arg, dflt in zip(pos[len(pos) - len(defaults):], defaults):
                default_for[arg.arg] = dflt
        for kwarg, dflt in zip(a.kwonlyargs, a.kw_defaults):
            default_for[kwarg.arg] = dflt
        for arg in params:
            av = AV(null="unknown", taint="source")  # params are untrusted (security)
            dflt = default_for.get(arg.arg)
            if isinstance(dflt, ast.Constant) and dflt.value is None:
                av.null = "maybe_none"
            env[arg.arg] = av
            self.sources.append({"line": self.fn.lineno, "kind": "parameter", "name": arg.arg})
        if a.vararg:
            env[a.vararg.arg] = AV(null="definitely_not_none", taint="source")
        if a.kwarg:
            env[a.kwarg.arg] = AV(null="definitely_not_none", taint="source")
        return env

    def run(self) -> None:
        env = self.initial_env()
        self.walk(self.fn.body, env)

    # -- statement walk -------------------------------------------------
    def walk(self, stmts: List[ast.stmt], env: Dict[str, AV]) -> Dict[str, AV]:
        for stmt in stmts:
            env = self.exec_stmt(stmt, env)
        return env

    def exec_stmt(self, stmt: ast.stmt, env: Dict[str, AV]) -> Dict[str, AV]:
        if isinstance(stmt, ast.Assign):
            av = self.eval(stmt.value, env)
            for tgt in stmt.targets:
                if isinstance(tgt, ast.Name):
                    env[tgt.id] = av.copy()
                    self._record_summary(tgt.id, av)
            return env
        if isinstance(stmt, ast.AnnAssign) and stmt.value is not None:
            av = self.eval(stmt.value, env)
            if isinstance(stmt.target, ast.Name):
                env[stmt.target.id] = av.copy()
                self._record_summary(stmt.target.id, av)
            return env
        if isinstance(stmt, ast.AugAssign):
            self.eval(stmt.value, env)
            if isinstance(stmt.target, ast.Name):
                cur = env.get(stmt.target.id, AV())
                env[stmt.target.id] = AV(null="definitely_not_none", taint=cur.taint)
            return env
        if isinstance(stmt, ast.Expr):
            self.eval(stmt.value, env)
            return env
        if isinstance(stmt, ast.Return):
            if stmt.value is not None:
                self.eval(stmt.value, env)
            return env
        if isinstance(stmt, (ast.Assert, ast.Raise, ast.Delete)):
            self.eval(stmt, env)
            return env
        if isinstance(stmt, ast.If):
            self.eval(stmt.test, env)
            env_then, env_else = self.narrow(env, stmt.test)
            out_then = self.walk(stmt.body, env_then)
            out_else = self.walk(stmt.orelse, env_else) if stmt.orelse else env_else
            if _terminates(stmt.body) and not _terminates(stmt.orelse):
                return out_else
            if _terminates(stmt.orelse) and not _terminates(stmt.body):
                return out_then
            return join_env(out_then, out_else)
        if isinstance(stmt, (ast.For, ast.AsyncFor)):
            self.eval(stmt.iter, env)
            body_env = {k: v.copy() for k, v in env.items()}
            if isinstance(stmt.target, ast.Name):
                body_env[stmt.target.id] = self._range_target_av(stmt.iter, env)
                self._record_summary(stmt.target.id, body_env[stmt.target.id])
            self.walk(stmt.body, body_env)
            if stmt.orelse:
                self.walk(stmt.orelse, {k: v.copy() for k, v in env.items()})
            return env
        if isinstance(stmt, ast.While):
            self.eval(stmt.test, env)
            body_env, _ = self.narrow(env, stmt.test)
            self.walk(stmt.body, {k: v.copy() for k, v in body_env.items()})
            return env
        if isinstance(stmt, (ast.With, ast.AsyncWith)):
            for item in stmt.items:
                av = self.eval(item.context_expr, env)
                if isinstance(item.optional_vars, ast.Name):
                    env[item.optional_vars.id] = av.copy()
                    self._record_summary(item.optional_vars.id, av)
            return self.walk(stmt.body, env)
        if isinstance(stmt, ast.Try):
            out = self.walk(stmt.body, env)
            for handler in stmt.handlers:
                self.walk(handler.body, {k: v.copy() for k, v in env.items()})
            out = self.walk(stmt.orelse, out) if stmt.orelse else out
            out = self.walk(stmt.finalbody, out) if stmt.finalbody else out
            return out
        # ignore nested defs (intraprocedural), imports, etc.
        return env

    # -- narrowing on branch conditions ---------------------------------
    def narrow(self, env: Dict[str, AV], test: ast.AST) -> Tuple[Dict[str, AV], Dict[str, AV]]:
        t = {k: v.copy() for k, v in env.items()}
        f = {k: v.copy() for k, v in env.items()}

        def set_null(target_env, name, value):
            if name in target_env:
                target_env[name] = target_env[name].copy()
                target_env[name].null = value

        # x is None / x is not None
        if isinstance(test, ast.Compare) and len(test.ops) == 1 and isinstance(test.left, ast.Name):
            name = test.left.id
            comp = test.comparators[0]
            if isinstance(comp, ast.Constant) and comp.value is None:
                if isinstance(test.ops[0], ast.Is):
                    set_null(t, name, "definitely_none"); set_null(f, name, "definitely_not_none")
                elif isinstance(test.ops[0], ast.IsNot):
                    set_null(t, name, "definitely_not_none"); set_null(f, name, "definitely_none")
        # if x:  (truthy) -> not none in true branch
        elif isinstance(test, ast.Name):
            set_null(t, test.id, "definitely_not_none")
            if test.id in t:
                t[test.id].container = "non_empty"
        # if not x:
        elif isinstance(test, ast.UnaryOp) and isinstance(test.op, ast.Not) and isinstance(test.operand, ast.Name):
            set_null(f, test.operand.id, "definitely_not_none")
        # isinstance(x, ...) -> not none in true branch
        elif (isinstance(test, ast.Call) and isinstance(test.func, ast.Name)
              and test.func.id == "isinstance" and test.args and isinstance(test.args[0], ast.Name)):
            set_null(t, test.args[0].id, "definitely_not_none")
        return t, f

    # -- expression evaluation -----------------------------------------
    def eval(self, node: Optional[ast.AST], env: Dict[str, AV]) -> AV:
        if node is None:
            return AV()
        method = getattr(self, "_eval_" + type(node).__name__, None)
        if method is not None:
            return method(node, env)
        # generic: walk children for deref/sink side effects
        for child in ast.iter_child_nodes(node):
            self.eval(child, env)
        return AV()

    def _eval_Constant(self, node: ast.Constant, env) -> AV:
        if node.value is None:
            return AV(null="definitely_none")
        if isinstance(node.value, bool):
            return AV(null="definitely_not_none")
        if isinstance(node.value, int):
            return AV(null="definitely_not_none", interval={"kind": "exact", "exact": node.value,
                                                            "lower": node.value, "upper": node.value})
        return AV(null="definitely_not_none")

    def _eval_Name(self, node: ast.Name, env) -> AV:
        if node.id in SOURCE_NAMES:
            self.sources.append({"line": node.lineno, "kind": "request_object", "name": node.id})
            return AV(null="definitely_not_none", taint="source")
        return env.get(node.id, AV()).copy()

    def _eval_List(self, node, env) -> AV:
        t = "untainted"
        for el in node.elts:
            if self.eval(el, env).tainted:
                t = "propagated"
        return AV(null="definitely_not_none", taint=t,
                  container="non_empty" if node.elts else "maybe_empty")

    _eval_Set = _eval_List

    def _eval_Tuple(self, node, env) -> AV:
        for el in node.elts:
            self.eval(el, env)
        return AV(null="definitely_not_none")

    def _eval_Dict(self, node, env) -> AV:
        for k in node.keys:
            if k is not None:
                self.eval(k, env)
        for v in node.values:
            self.eval(v, env)
        return AV(null="definitely_not_none",
                  container="non_empty" if node.keys else "maybe_empty")

    def _eval_BinOp(self, node, env) -> AV:
        a = self.eval(node.left, env)
        b = self.eval(node.right, env)
        taint = _join_taint(a.taint, b.taint)
        interval = {"kind": "unknown"}
        if (a.interval.get("kind") == "exact" and b.interval.get("kind") == "exact"
                and isinstance(node.op, (ast.Add, ast.Sub, ast.Mult))):
            x, y = a.interval["exact"], b.interval["exact"]
            val = x + y if isinstance(node.op, ast.Add) else (x - y if isinstance(node.op, ast.Sub) else x * y)
            interval = {"kind": "exact", "exact": val, "lower": val, "upper": val}
        return AV(null="definitely_not_none", taint=taint, interval=interval)

    def _eval_BoolOp(self, node, env) -> AV:
        t = "untainted"
        for v in node.values:
            if self.eval(v, env).tainted:
                t = "propagated"
        return AV(null="unknown", taint=t)

    def _eval_Compare(self, node, env) -> AV:
        self.eval(node.left, env)
        for c in node.comparators:
            self.eval(c, env)
        return AV(null="definitely_not_none")

    def _eval_UnaryOp(self, node, env) -> AV:
        self.eval(node.operand, env)
        return AV(null="definitely_not_none")

    def _eval_JoinedStr(self, node, env) -> AV:
        t = "untainted"
        for v in node.values:
            av = self.eval(v, env)
            if av.tainted:
                t = "propagated"
        return AV(null="definitely_not_none", taint=t)

    def _eval_FormattedValue(self, node, env) -> AV:
        return self.eval(node.value, env)

    def _eval_Attribute(self, node, env) -> AV:
        base = self.eval(node.value, env)
        self._check_deref(node.value, env)
        # request.args etc. stays tainted
        if isinstance(node.value, ast.Name) and node.value.id in SOURCE_NAMES:
            return AV(null="definitely_not_none", taint="source")
        if _dotted(node) == "sys.argv":
            self.sources.append({"line": node.lineno, "kind": "sys.argv", "name": "sys.argv"})
            return AV(null="definitely_not_none", taint="source")
        return AV(null="unknown", taint="propagated" if base.tainted else "untainted")

    def _eval_Subscript(self, node, env) -> AV:
        base = self.eval(node.value, env)
        self._check_deref(node.value, env)
        self.eval(node.slice, env)
        dotted = _dotted(node.value)
        if dotted in ("os.environ",) or (isinstance(node.value, ast.Name) and node.value.id in SOURCE_NAMES):
            self.sources.append({"line": node.lineno, "kind": dotted or "request", "name": dotted})
            return AV(null="definitely_not_none", taint="source")
        return AV(null="unknown", taint="propagated" if base.tainted else "untainted")

    def _eval_IfExp(self, node, env) -> AV:
        self.eval(node.test, env)
        a = self.eval(node.body, env)
        b = self.eval(node.orelse, env)
        return join_av(a, b)

    def _eval_Call(self, node: ast.Call, env) -> AV:
        callee = _dotted(node.func)
        short = callee.split(".")[-1]
        # evaluate args first (collect taint, derefs, nested sinks)
        arg_avs = [self.eval(a, env) for a in node.args]
        for kw in node.keywords:
            if kw.value is not None:
                self.eval(kw.value, env)
        if isinstance(node.func, ast.Attribute):
            # evaluate the receiver so chained calls (a().b()) and taint on the
            # receiver are accounted for, and check it for a null dereference.
            self.eval(node.func.value, env)
            self._check_deref(node.func.value, env)

        any_arg_tainted = any(av.tainted for av in arg_avs)

        # --- sources ---------------------------------------------------
        if short in SOURCE_CALLS:
            self.sources.append({"line": node.lineno, "kind": f"{short}()", "name": short})
            return AV(null="definitely_not_none", taint="source")
        if short in SOURCE_READ_METHODS:
            base_t = arg_avs and False
            recv = node.func.value if isinstance(node.func, ast.Attribute) else None
            recv_av = self.eval(recv, env) if recv is not None else AV()
            return AV(null="definitely_not_none", taint="propagated" if recv_av.tainted else "source")
        if callee in ("os.getenv",) or callee in ("os.environ.get",):
            self.sources.append({"line": node.lineno, "kind": callee, "name": callee})
            return AV(null="maybe_none", taint="source")

        # --- sanitizers ------------------------------------------------
        if short in SANITIZER_CALLS or callee in SANITIZER_DOTTED:
            return AV(null="definitely_not_none", taint="sanitized")

        # --- dangerous sinks ------------------------------------------
        self._maybe_sink(node, callee, short, arg_avs, env)

        # --- container-ish constructors -------------------------------
        if short in ("list", "dict", "set", "deque", "tuple", "frozenset", "OrderedDict",
                     "defaultdict", "Counter", "Queue", "LifoQueue"):
            return AV(null="definitely_not_none",
                      container="maybe_empty" if not node.args else "unknown")
        if short in ("get",):  # dict.get(...) may return None
            return AV(null="maybe_none",
                      taint="propagated" if any_arg_tainted else "untainted")
        if callee in ("re.match", "re.search", "re.fullmatch"):
            return AV(null="maybe_none")
        if short == "open":
            # file object; carries taint of the path argument
            return AV(null="definitely_not_none",
                      taint="propagated" if any_arg_tainted else "untainted")

        # generic call: unknown null, propagate taint
        return AV(null="unknown", taint="propagated" if any_arg_tainted else "untainted")

    # -- sinks ----------------------------------------------------------
    def _maybe_sink(self, node, callee: str, short: str, arg_avs, env) -> None:
        first_tainted = bool(arg_avs) and arg_avs[0].tainted
        any_tainted = any(av.tainted for av in arg_avs)
        ev = _line_text(self.lines, node.lineno)

        if short in ("eval", "exec") and isinstance(node.func, ast.Name):
            self.sinks.append({"category": "code_injection", "line": node.lineno,
                               "callee": short, "tainted": any_tainted, "shell_true": False,
                               "sanitized": False, "evidence": ev})
        elif callee == "os.system":
            self.sinks.append({"category": "command_injection", "line": node.lineno,
                               "callee": callee, "tainted": any_tainted, "shell_true": False,
                               "sanitized": False, "evidence": ev})
        elif short in ("call", "run", "Popen", "check_output", "check_call") and "subprocess" in callee or callee.startswith("subprocess"):
            shell_true = any(
                (kw.arg == "shell" and isinstance(kw.value, ast.Constant) and kw.value.value is True)
                for kw in node.keywords
            )
            self.sinks.append({"category": "command_injection", "line": node.lineno,
                               "callee": callee, "tainted": any_tainted, "shell_true": shell_true,
                               "sanitized": False, "evidence": ev})
        elif short in ("execute", "executemany"):
            self.sinks.append({"category": "sql_injection", "line": node.lineno,
                               "callee": callee, "tainted": first_tainted, "shell_true": False,
                               "sanitized": False, "evidence": ev})
        elif short == "open":
            self.sinks.append({"category": "path_traversal", "line": node.lineno,
                               "callee": callee, "tainted": first_tainted, "shell_true": False,
                               "sanitized": arg_avs and arg_avs[0].taint == "sanitized", "evidence": ev})
        elif callee in ("pickle.load", "pickle.loads", "cPickle.load", "cPickle.loads", "marshal.load", "marshal.loads"):
            self.sinks.append({"category": "unsafe_deserialization", "line": node.lineno,
                               "callee": callee, "tainted": any_tainted, "shell_true": False,
                               "sanitized": False, "evidence": ev, "deser": "pickle"})
        elif callee in ("yaml.load",):
            safe = any(kw.arg == "Loader" for kw in node.keywords)
            self.sinks.append({"category": "unsafe_deserialization", "line": node.lineno,
                               "callee": callee, "tainted": any_tainted, "shell_true": False,
                               "sanitized": safe, "evidence": ev, "deser": "yaml"})
        elif callee in ("hashlib.md5", "hashlib.sha1") or short in ("md5", "sha1"):
            self.sinks.append({"category": "weak_crypto", "line": node.lineno,
                               "callee": callee or short, "tainted": False, "shell_true": False,
                               "sanitized": False, "evidence": ev, "algo": short})
        elif callee == "hashlib.new" and node.args and isinstance(node.args[0], ast.Constant) \
                and str(node.args[0].value).lower() in ("md5", "sha1"):
            self.sinks.append({"category": "weak_crypto", "line": node.lineno,
                               "callee": "hashlib.new", "tainted": False, "shell_true": False,
                               "sanitized": False, "evidence": ev, "algo": str(node.args[0].value).lower()})

    # -- null deref -----------------------------------------------------
    def _check_deref(self, base: ast.AST, env: Dict[str, AV]) -> None:
        if not isinstance(base, ast.Name):
            return
        av = env.get(base.id)
        if av is None:
            return
        if av.null in ("maybe_none", "definitely_none"):
            key = (base.lineno, base.id)
            if key in self._deref_seen:
                return
            self._deref_seen.add(key)
            self.value_findings.append({
                "category": "null_dereference",
                "line": base.lineno,
                "var": base.id,
                "null_state": av.null,
                "evidence": _line_text(self.lines, base.lineno),
            })

    def _range_target_av(self, iter_node: ast.AST, env) -> AV:
        if isinstance(iter_node, ast.Call) and isinstance(iter_node.func, ast.Name) and iter_node.func.id == "range":
            args = iter_node.args
            lower, upper_expr = 0, None
            if len(args) == 1:
                upper_expr = f"{_unparse(args[0])} - 1"
            elif len(args) >= 2:
                lower = args[0].value if isinstance(args[0], ast.Constant) and isinstance(args[0].value, int) else 0
                upper_expr = f"{_unparse(args[1])} - 1"
            return AV(null="definitely_not_none",
                      interval={"kind": "bounded", "lower": lower, "upper_expr": upper_expr or "unknown"})
        return AV(null="definitely_not_none")

    def _record_summary(self, name: str, av: AV) -> None:
        self.null_summary[name] = _join_null(self.null_summary.get(name, av.null), av.null) if name in self.null_summary else av.null
        self.taint_summary[name] = _join_taint(self.taint_summary.get(name, av.taint), av.taint) if name in self.taint_summary else av.taint
        if av.interval.get("kind") != "unknown":
            self.interval_summary[name] = av.interval


# ---------------------------------------------------------------------------
# Container state (creation + mutation)
# ---------------------------------------------------------------------------
def _container_state(fn: ast.AST) -> Dict[str, Dict[str, Any]]:
    out: Dict[str, Dict[str, Any]] = {}
    created_empty: Dict[str, bool] = {}
    created: Set[str] = set()

    for n in ast.walk(fn):
        if isinstance(n, ast.Assign) and len(n.targets) == 1 and isinstance(n.targets[0], ast.Name):
            name = n.targets[0].id
            v = n.value
            if isinstance(v, (ast.List, ast.Set)):
                created.add(name); created_empty[name] = not v.elts
            elif isinstance(v, ast.Dict):
                created.add(name); created_empty[name] = not v.keys
            elif isinstance(v, ast.Call) and isinstance(v.func, ast.Name) and v.func.id in (
                    "list", "dict", "set", "deque", "frozenset", "OrderedDict", "Counter", "defaultdict"):
                created.add(name); created_empty[name] = not v.args

    top_level_expr_lines = {s.value.lineno for s in fn.body
                            if isinstance(s, ast.Expr) and isinstance(s.value, ast.Call)}

    grows: Dict[str, bool] = {}
    shrinks: Dict[str, bool] = {}
    consumed: Dict[str, bool] = {}
    unconditional_grow: Dict[str, bool] = {}
    for n in ast.walk(fn):
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and isinstance(n.func.value, ast.Name):
            cname = n.func.value.id
            op = n.func.attr
            if op in GROW_OPS:
                grows[cname] = True
                if n.lineno in top_level_expr_lines:
                    unconditional_grow[cname] = True
            if op in SHRINK_OPS:
                shrinks[cname] = True
            if op in CONSUME_OPS:
                consumed[cname] = True

    names = created | set(grows) | set(shrinks) | set(consumed)
    for name in sorted(names):
        if name in created:
            if created_empty.get(name, False):
                state = "non_empty" if unconditional_grow.get(name) else "maybe_empty"
            else:
                state = "non_empty"
        else:
            state = "unknown"
        out[name] = {
            "state": state,
            "grows": grows.get(name, False),
            "shrinks": shrinks.get(name, False),
            "consumed": consumed.get(name, False),
        }
    return out


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def analyze_function(fn: ast.AST, lines: List[str]) -> Dict[str, Any]:
    a = fn.args
    params = [arg.arg for arg in [*a.posonlyargs, *a.args, *a.kwonlyargs]]

    # reaching definitions
    rd_out: Dict[int, Dict[str, List[int]]] = {}
    rd_state: Dict[str, Set[int]] = {p: {fn.lineno} for p in params}
    try:
        _rd_walk(fn.body, rd_state, rd_out)
    except Exception:
        pass

    definitions: List[Dict[str, Any]] = [{"name": p, "line": fn.lineno, "kind": "param"} for p in params]
    uses: List[Dict[str, Any]] = []
    branch_conditions: List[Dict[str, Any]] = []
    returns: List[Dict[str, Any]] = []
    for n in ast.walk(fn):
        if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store):
            definitions.append({"name": n.id, "line": n.lineno, "kind": "assign"})
        elif isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load):
            uses.append({"name": n.id, "line": n.lineno})
        elif isinstance(n, (ast.If, ast.While)):
            branch_conditions.append({"line": n.lineno, "test": _unparse(n.test),
                                      "vars": sorted({x.id for x in _names_loaded(n.test)})})
        elif isinstance(n, ast.Return):
            returns.append({"line": n.lineno, "expr": _unparse(n.value),
                            "kind": _return_kind(n.value),
                            "is_constant": isinstance(n.value, ast.Constant)})

    flow = FlowAnalyzer(fn, lines)
    try:
        flow.run()
    except Exception:
        pass

    nullability = {
        "summary": flow.null_summary,
        "derefs_flagged": flow.value_findings,
    }
    taint = {
        "summary": flow.taint_summary,
        "sources": flow.sources,
        "sinks": flow.sinks,
    }

    return {
        "name": fn.name,
        "line": fn.lineno,
        "params": params,
        "cfg_blocks": _build_cfg(fn),
        "definitions": definitions,
        "uses": uses,
        "reaching_definitions": rd_out,
        "branch_conditions": branch_conditions,
        "returns": returns,
        "container_state": _container_state(fn),
        "nullability": nullability,
        "intervals": flow.interval_summary,
        "taint": taint,
        "value_findings": flow.value_findings,
        "sink_observations": flow.sinks,
        "source_observations": flow.sources,
    }


def analyze_source(text: str, path: str = "<source>") -> Dict[str, Any]:
    try:
        tree = ast.parse(text)
    except SyntaxError as exc:
        return {"module": path, "parse_error": f"{type(exc).__name__}: {exc.msg}", "functions": []}
    lines = text.splitlines()
    functions: List[Dict[str, Any]] = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if sum(1 for _ in ast.walk(node)) > _MAX_NODES:
                continue
            try:
                functions.append(analyze_function(node, lines))
            except Exception:
                continue
    return {"module": path, "parse_error": "", "functions": functions}
