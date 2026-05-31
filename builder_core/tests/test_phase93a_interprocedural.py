"""Phase 93A tests: interprocedural infrastructure (no findings, not consumed).

Pin the call-graph conservatism, the result-usage facts, the summary lattices +
monotone propagation, and the additive/disableable wiring. Assert that the layer
emits no findings and changes no benchmark.
"""

from __future__ import annotations

import ast
import os
import textwrap

import pytest

from builder_core.bug_intelligence import (
    callgraph, summaries, facts, engine, engine_benchmark,
)


def _cg(src: str):
    return callgraph.build_call_graph(ast.parse(textwrap.dedent(src)), "m.py")


def _summ(src: str):
    s = textwrap.dedent(src)
    cg = callgraph.build_call_graph(ast.parse(s), "m.py")
    return cg, summaries.compute_summaries(facts.extract_module_facts(s, "m.py"), cg)


# ---------------------------------------------------------------------------
# 1. Function identity / qualname
# ---------------------------------------------------------------------------
def test_qualnames_module_method_nested():
    cg = _cg("""
        def top():
            def inner():
                pass
            return inner
        class C:
            def method(self):
                pass
    """)
    quals = set(cg["functions"])
    assert {"top", "top.inner", "C.method"} <= quals
    assert cg["functions"]["C.method"]["id"] == ("m.py", "C.method")


# ---------------------------------------------------------------------------
# 2. Resolution: same-file direct only, unresolved explicit, no guessing
# ---------------------------------------------------------------------------
def test_same_file_direct_call_resolved():
    cg = _cg("""
        def a():
            return b()
        def b():
            return 1
    """)
    assert cg["edges"].get("a") == ["b"]


def test_method_call_is_unresolved():
    cg = _cg("""
        def a(o):
            return o.method()
    """)
    assert cg["edges"].get("a") is None
    assert cg["unresolved_count"] == 1


def test_unknown_name_is_unresolved():
    cg = _cg("""
        def a():
            return external_helper()
    """)
    assert "a" not in cg["edges"]
    assert cg["unresolved_count"] == 1


def test_shadowed_name_is_unresolved():
    # `b` is a parameter here, so b() must NOT resolve to the module function b
    cg = _cg("""
        def a(b):
            return b()
        def b():
            return 1
    """)
    assert "a" not in cg["edges"]
    assert cg["unresolved_count"] == 1


# ---------------------------------------------------------------------------
# 5. Caller result-usage facts
# ---------------------------------------------------------------------------
def test_usage_null_checked():
    cg = _cg("""
        def t():
            r = f()
            if r is None:
                return 0
            return r
        def f():
            return 1
    """)
    assert cg["usage_by_callee"]["f"]["null_checked"] is True
    assert cg["usage_by_callee"]["f"]["uses_return"] is True


def test_usage_dereferenced():
    cg = _cg("""
        def t():
            return f().attr
        def f():
            return 1
    """)
    assert cg["usage_by_callee"]["f"]["dereferenced"] is True


def test_usage_ignored():
    cg = _cg("""
        def t():
            f()
        def f():
            return 1
    """)
    assert cg["usage_by_callee"]["f"]["uses_return"] is False


# ---------------------------------------------------------------------------
# 3+4. Summaries + monotone propagation
# ---------------------------------------------------------------------------
def test_nullability_base():
    _, s = _summ("""
        def maybe(x):
            if x:
                return x
        def always(x):
            return x
    """)
    assert s["maybe"]["return_nullability"] == "maybe_none"
    assert s["always"]["return_nullability"] == "definite_value"


def test_nullability_propagates_through_resolved_return_call():
    _, s = _summ("""
        def leaf(x):
            if x:
                return x
        def wrapper():
            return leaf(1)
    """)
    # wrapper returns leaf() -> inherits maybe_none
    assert s["wrapper"]["return_nullability"] == "maybe_none"


def test_nullability_widens_to_unknown_on_unresolved_return_call():
    _, s = _summ("""
        def wrapper(o):
            return o.method()
    """)
    assert s["wrapper"]["return_nullability"] == "unknown"


def test_may_raise_explicit():
    _, s = _summ("""
        def r():
            raise ValueError('x')
        def pure(a, b):
            return a + b
    """)
    assert s["r"]["may_raise"] == "may_raise"
    assert s["pure"]["may_raise"] == "no_raise"


def test_may_raise_propagates_and_widens():
    _, s = _summ("""
        def leaf():
            raise IndexError()
        def calls_leaf():
            return leaf()
        def calls_unknown(o):
            return o.go()
    """)
    assert s["calls_leaf"]["may_raise"] == "may_raise"     # proven via callee
    assert s["calls_unknown"]["may_raise"] == "unknown"    # widened on ambiguity


def test_taint_signature_present():
    _, s = _summ("""
        def f(a, b):
            return a
    """)
    sig = s["f"]["taint_signature"]
    assert "params_to_return" in sig and "reaches_sink" in sig
    assert "a" in sig["params_to_return"]


def test_propagation_is_deterministic():
    src = """
        def leaf(x):
            if x:
                return x
        def w1():
            return leaf(1)
        def w2():
            return w1()
    """
    _, a = _summ(src)
    _, b = _summ(src)
    assert a == b  # stable across runs


def test_recursion_terminates():
    # a cycle must not hang the worklist
    _, s = _summ("""
        def ping(n):
            return pong(n)
        def pong(n):
            return ping(n)
    """)
    assert set(s) == {"ping", "pong"}  # computed without hanging


# ---------------------------------------------------------------------------
# 6. Wiring: additive, findings-free, disableable
# ---------------------------------------------------------------------------
def test_engine_attaches_interproc_facts():
    res = engine.analyze_source(textwrap.dedent("""
        def a():
            return b()
        def b():
            return 1
    """), "m.py")
    assert "interproc" in res.facts
    assert "call_graph" in res.facts["interproc"]
    assert "summaries" in res.facts["interproc"]


def test_engine_emits_no_interproc_findings():
    res = engine.analyze_source(textwrap.dedent("""
        def a():
            return b()
        def b():
            return 1
    """), "m.py")
    # the layer introduces no new kind and no finding tied to interproc
    assert all(f.kind != "interproc" for f in res.findings)
    assert all("interproc" not in (f.rule or "") for f in res.findings)


def test_disable_by_emptying_augmenters(monkeypatch):
    monkeypatch.setattr(engine, "_fact_augmenters", [])
    res = engine.analyze_source(textwrap.dedent("""
        def a():
            return b()
        def b():
            return 1
    """), "m.py")
    assert "interproc" not in res.facts  # cleanly disabled


# ---------------------------------------------------------------------------
# Benchmark parity (layer changes nothing measurable)
# ---------------------------------------------------------------------------
@pytest.mark.skipif(not os.path.isdir(r"C:\Repos\QuixBugs"), reason="QuixBugs absent")
def test_quixbugs_unchanged():
    r = engine_benchmark.evaluate_quixbugs_engine(r"C:\Repos\QuixBugs")
    assert r["true_positives"] == 12 and r["false_positives"] == 0


@pytest.mark.skipif(not engine_benchmark._PAIRS_ROOT.is_dir(), reason="holdout absent")
def test_holdout_unchanged():
    r = engine_benchmark.evaluate_holdout_engine()
    assert r["true_positives"] == 2 and r["false_positives"] == 0
