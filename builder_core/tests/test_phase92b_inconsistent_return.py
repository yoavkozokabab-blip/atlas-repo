"""Phase 92B tests: fact-backed inconsistent_return behind a promote/quarantine gate.

The detector fires only on a genuine missing-return (value return on some path +
no explicit None return + can fall through to implicit None). It was QUARANTINED
(kind=pattern, excluded from the benchmark verdict) because it produced one false
positive on the QuixBugs correct file `next_permutation.py`. These tests pin both
the detector's intrinsic behavior and the quarantine outcome.
"""

from __future__ import annotations

import os
import textwrap

import pytest

from builder_core.bug_intelligence import (
    engine, engine_benchmark, fact_detectors, facts,
)

QUIXBUGS = r"C:\Repos\QuixBugs"


def _fires(src: str) -> list:
    mf = facts.extract_module_facts(textwrap.dedent(src), "x.py")
    return fact_detectors.detect_inconsistent_return(mf, "x.py")


# ---------------------------------------------------------------------------
# Intrinsic detector behavior (kind-independent)
# ---------------------------------------------------------------------------
def test_genuine_missing_return_fires():
    found = _fires("""
        def find(xs, t):
            for i, x in enumerate(xs):
                if x == t:
                    return i
    """)
    assert len(found) == 1
    assert found[0].rule == "inconsistent_return"
    assert found[0].category == "logic_bug"


def test_value_or_false_does_not_fire():
    assert _fires("""
        def lookup(d, k):
            if k in d:
                return d[k]
            return False
    """) == []


def test_value_or_none_does_not_fire():
    assert _fires("""
        def g(x):
            if x:
                return 1
            return None
    """) == []


def test_bare_return_does_not_fire():
    assert _fires("""
        def g(x):
            if not x:
                return
            return compute(x)
    """) == []


def test_all_paths_return_does_not_fire():
    assert _fires("""
        def h(x):
            if x:
                return 1
            else:
                return 2
    """) == []


def test_while_true_no_fallthrough_does_not_fire():
    assert _fires("""
        def loop(q):
            while True:
                v = q.pop()
                if v is None:
                    return v
    """) == []


def test_renamed_function_and_vars_same_result():
    named = """
        def find(xs, t):
            for i, x in enumerate(xs):
                if x == t:
                    return i
    """
    renamed = """
        def f1(p0, p1):
            for v0, v1 in enumerate(p0):
                if v1 == p1:
                    return v0
    """
    assert len(_fires(named)) == len(_fires(renamed)) == 1


# ---------------------------------------------------------------------------
# return_summary facts
# ---------------------------------------------------------------------------
def test_return_summary_fact_present():
    mf = facts.extract_module_facts(textwrap.dedent("""
        def find(xs, t):
            for i, x in enumerate(xs):
                if x == t:
                    return i
    """), "x.py")
    rs = mf["functions"][0]["return_summary"]
    assert rs == {"has_value_return": True, "has_none_return": False, "can_fall_through": True}


# ---------------------------------------------------------------------------
# Engine integration: quarantined + no inflation
# ---------------------------------------------------------------------------
def test_engine_dedup_does_not_inflate():
    res = engine.analyze_source(textwrap.dedent("""
        def find(xs, t):
            for i, x in enumerate(xs):
                if x == t:
                    return i
    """), "x.py")
    ir = [f for f in res.findings if f.rule == "inconsistent_return"]
    assert len(ir) == 1  # one finding per function, not inflated by two sources


def test_detector_is_quarantined_kind_pattern():
    assert fact_detectors.INCONSISTENT_RETURN_KIND == "pattern"


def test_quarantined_finding_excluded_from_verdict():
    res = engine.analyze_source(textwrap.dedent("""
        def find(xs, t):
            for i, x in enumerate(xs):
                if x == t:
                    return i
    """), "x.py")
    grounded = engine_benchmark.grounded_findings(res)
    assert all(f.rule != "inconsistent_return" for f in grounded)


# ---------------------------------------------------------------------------
# Benchmark verdict: 0 FP preserved by the quarantine
# ---------------------------------------------------------------------------
@pytest.mark.skipif(not os.path.isdir(QUIXBUGS), reason="QuixBugs not present")
def test_quixbugs_verdict_zero_fp_and_parity():
    report = engine_benchmark.evaluate_quixbugs_engine(QUIXBUGS)
    assert report["false_positives"] == 0
    assert report["true_positives"] == 12  # quarantine keeps parity (no 13th via FP rule)


@pytest.mark.skipif(not engine_benchmark._PAIRS_ROOT.is_dir(), reason="holdout corpus absent")
def test_holdout_verdict_zero_fp():
    report = engine_benchmark.evaluate_holdout_engine()
    assert report["false_positives"] == 0


@pytest.mark.skipif(
    not os.path.isfile(os.path.join(QUIXBUGS, "correct_python_programs", "next_permutation.py")),
    reason="QuixBugs not present",
)
def test_next_permutation_fp_is_the_quarantine_reason():
    # Documents WHY the detector is quarantined: it fires on a CORRECT file.
    path = os.path.join(QUIXBUGS, "correct_python_programs", "next_permutation.py")
    with open(path, "r", encoding="utf-8-sig", errors="ignore") as fh:
        text = fh.read()
    mf = facts.extract_module_facts(text, "next_permutation.py")
    assert fact_detectors.detect_inconsistent_return(mf, "next_permutation.py"), \
        "expected the raw detector to (false-)fire on correct next_permutation.py"
