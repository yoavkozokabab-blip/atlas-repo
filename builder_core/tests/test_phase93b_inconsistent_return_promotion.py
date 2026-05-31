"""Phase 93B tests: interprocedural promotion of inconsistent_return.

Promotion (kind=value_flow, verdict-eligible) requires unambiguous
interprocedural evidence: >=1 resolved caller dereferences the result and no
caller null-checks it. Mixed / no-deref / unresolved -> quarantined (pattern).
"""

from __future__ import annotations

import os
import textwrap

import pytest

from builder_core.bug_intelligence import engine, engine_benchmark, fact_detectors

QUIXBUGS = r"C:\Repos\QuixBugs"


def _ir(src: str):
    res = engine.analyze_source(textwrap.dedent(src), "m.py")
    return [f for f in res.findings if f.rule == "inconsistent_return"]


def _kinds(src: str):
    return {f.kind for f in _ir(src)}


# A function with the Phase 92B missing-return shape, varying caller usage.
LEAF = """
    def leaf(x):
        for i in x:
            if i:
                return i
"""


# ---------------------------------------------------------------------------
# Promotion
# ---------------------------------------------------------------------------
def test_promote_when_caller_derefs_and_no_null_check():
    src = LEAF + """
        def caller():
            r = leaf([1])
            return r.attr
    """
    ir = _ir(src)
    leaf = [f for f in ir if f.function == "leaf"]
    assert leaf and leaf[0].kind == "value_flow"   # promoted
    assert leaf[0].confidence == "high"


def test_quarantine_when_caller_null_checks():
    src = LEAF + """
        def caller():
            r = leaf([1])
            if r is None:
                return 0
            return r.attr
    """
    leaf = [f for f in _ir(src) if f.function == "leaf"]
    assert leaf and leaf[0].kind == "pattern"      # contract -> quarantined


def test_quarantine_when_mixed_evidence():
    # one caller derefs, another null-checks -> mixed -> quarantine
    src = LEAF + """
        def derefs():
            return leaf([1]).attr
        def checks():
            r = leaf([2])
            if not r:
                return 0
            return r
    """
    leaf = [f for f in _ir(src) if f.function == "leaf"]
    assert leaf and leaf[0].kind == "pattern"


def test_quarantine_when_no_caller():
    # leaf is never called in-file -> unresolved -> quarantine
    leaf = [f for f in _ir(LEAF) if f.function == "leaf"]
    assert leaf and leaf[0].kind == "pattern"


def test_quarantine_when_caller_only_uses_value():
    src = LEAF + """
        def caller():
            r = leaf([1])
            return r + 1
    """
    leaf = [f for f in _ir(src) if f.function == "leaf"]
    assert leaf and leaf[0].kind == "pattern"


def test_unresolved_caller_does_not_promote():
    # the call is via an attribute (unresolved) -> no resolved-caller evidence
    src = LEAF + """
        def caller(obj):
            return obj.leaf([1]).attr
    """
    leaf = [f for f in _ir(src) if f.function == "leaf"]
    assert leaf and leaf[0].kind == "pattern"


# ---------------------------------------------------------------------------
# Promoted finding enters the verdict; dedup keeps the promoted one
# ---------------------------------------------------------------------------
def test_promoted_finding_is_verdict_eligible():
    src = LEAF + """
        def caller():
            return leaf([1]).attr
    """
    res = engine.analyze_source(textwrap.dedent(src), "m.py")
    grounded = engine_benchmark.grounded_findings(res)
    assert any(f.rule == "inconsistent_return" and f.kind == "value_flow" for f in grounded)


def test_dedup_keeps_promoted_over_legacy_pattern():
    src = LEAF + """
        def caller():
            return leaf([1]).attr
    """
    res = engine.analyze_source(textwrap.dedent(src), "m.py")
    leaf_ir = [f for f in res.findings if f.rule == "inconsistent_return" and f.function == "leaf"]
    assert len(leaf_ir) == 1                # not inflated
    assert leaf_ir[0].kind == "value_flow"  # promoted survives the legacy pattern


def test_kill_switch_forces_quarantine(monkeypatch):
    monkeypatch.setattr(fact_detectors, "INTERPROC_PROMOTION_ENABLED", False)
    src = LEAF + """
        def caller():
            return leaf([1]).attr
    """
    leaf = [f for f in _ir(src) if f.function == "leaf"]
    assert leaf and leaf[0].kind == "pattern"   # globally disabled -> never promote


# ---------------------------------------------------------------------------
# Benchmarks: promotion is 0-FP; parity preserved on these corpora
# ---------------------------------------------------------------------------
@pytest.mark.skipif(not os.path.isdir(QUIXBUGS), reason="QuixBugs absent")
def test_quixbugs_zero_fp_and_parity():
    r = engine_benchmark.evaluate_quixbugs_engine(QUIXBUGS)
    assert r["false_positives"] == 0
    assert r["true_positives"] == 12


@pytest.mark.skipif(not engine_benchmark._PAIRS_ROOT.is_dir(), reason="holdout absent")
def test_holdout_zero_fp_and_parity():
    r = engine_benchmark.evaluate_holdout_engine()
    assert r["false_positives"] == 0
    assert r["true_positives"] == 2


@pytest.mark.skipif(
    not os.path.isfile(os.path.join(QUIXBUGS, "correct_python_programs", "next_permutation.py")),
    reason="QuixBugs absent",
)
def test_next_permutation_no_longer_promotes():
    # The Phase 92B false positive is now quarantined by the interproc gate
    # (no in-file deref-caller), so it cannot enter the verdict.
    path = os.path.join(QUIXBUGS, "correct_python_programs", "next_permutation.py")
    with open(path, "r", encoding="utf-8-sig", errors="ignore") as fh:
        res = engine.analyze_source(fh.read(), "next_permutation.py")
    promoted = [f for f in res.findings
                if f.rule == "inconsistent_return" and f.kind == "value_flow"]
    assert promoted == []
