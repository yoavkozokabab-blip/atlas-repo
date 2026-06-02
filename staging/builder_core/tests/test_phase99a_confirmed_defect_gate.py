"""Phase 99F tests: design-compliant confirmed-defect gate."""

from __future__ import annotations

import os
import textwrap

import pytest

from builder_core.bug_intelligence import (
    confirmed_defect_gate as CDG,
    engine,
    engine_benchmark,
    verification_evidence as VE,
)

PROVEN = textwrap.dedent("""
    def helper(x) -> str:
        if x:
            return "a"
    def caller():
        return helper(1).upper()
""")

PROVEN_TEST = textwrap.dedent("""
    from m import helper

    def test_helper_non_none():
        assert helper(1) is not None
""")


def _analyze(src: str, **kwargs):
    return engine.analyze_source(textwrap.dedent(src), "m.py", **kwargs)


def _ir(result):
    return [f for f in result.findings if f.rule == "inconsistent_return"]


@pytest.fixture
def gate_on():
    old_gate = CDG.CONFIRMED_DEFECT_GATE_ENABLED
    CDG.CONFIRMED_DEFECT_GATE_ENABLED = True
    try:
        yield
    finally:
        CDG.CONFIRMED_DEFECT_GATE_ENABLED = old_gate


@pytest.fixture
def compliance_on():
    old_gate = CDG.CONFIRMED_DEFECT_GATE_ENABLED
    old_promo = VE.EVIDENCE_PROMOTION_ENABLED
    CDG.CONFIRMED_DEFECT_GATE_ENABLED = True
    VE.EVIDENCE_PROMOTION_ENABLED = True
    try:
        yield
    finally:
        CDG.CONFIRMED_DEFECT_GATE_ENABLED = old_gate
        VE.EVIDENCE_PROMOTION_ENABLED = old_promo


def test_gate_disabled_preserves_current_behavior():
    assert CDG.CONFIRMED_DEFECT_GATE_ENABLED is False
    assert VE.EVIDENCE_PROMOTION_ENABLED is False
    f = _ir(_analyze(PROVEN))[0]
    assert f.confirmed_defect_classification is None
    assert "confirmed_defect" not in f.tags


def test_gate_on_without_promotion_never_confirms(gate_on):
    res = _analyze(
        PROVEN,
        test_documents=[{"path": "tests/test_m.py", "content": PROVEN_TEST}],
    )
    gate = _ir(res)[0].confirmed_defect_classification
    assert gate is not None
    assert gate["classification"] != CDG.CLASS_CONFIRMED
    assert gate["criteria"]["c6"] is False


def test_proven_synthetic_confirmed(compliance_on):
    res = _analyze(
        PROVEN,
        test_documents=[{"path": "tests/test_m.py", "content": PROVEN_TEST}],
    )
    f = _ir(res)[0]
    gate = f.confirmed_defect_classification
    assert gate is not None
    assert all(gate["criteria"].values())
    assert gate["classification"] == CDG.CLASS_CONFIRMED
    assert gate["confirmation_bundle"] is not None
    assert gate["surfaced"] is True
    assert "confirmed_defect" in f.tags


def test_confirmed_emits_complete_bundle(compliance_on):
    gate = _ir(_analyze(
        PROVEN,
        test_documents=[{"path": "tests/test_m.py", "content": PROVEN_TEST}],
    ))[0].confirmed_defect_classification
    bundle = gate["confirmation_bundle"]
    assert bundle["expected_contract"]
    assert bundle["feasible_path"]
    assert bundle["executable_witness"]
    assert bundle["observable_consequence"]["resolved"] is True


def test_shadow_mode_computes_without_surfacing(compliance_on):
    old_shadow = CDG.CONFIRMED_DEFECT_SHADOW_MODE
    CDG.CONFIRMED_DEFECT_SHADOW_MODE = True
    try:
        f = _ir(_analyze(
            PROVEN,
            test_documents=[{"path": "tests/test_m.py", "content": PROVEN_TEST}],
        ))[0]
        gate = f.confirmed_defect_classification
        assert gate["classification"] == CDG.CLASS_CONFIRMED
        assert gate["surfaced"] is False
        assert "confirmed_defect" not in f.tags
    finally:
        CDG.CONFIRMED_DEFECT_SHADOW_MODE = old_shadow


def test_visible_guard_blocks_confirmation(compliance_on):
    gate = _ir(_analyze("""
        def helper(x) -> str:
            if x:
                return "a"
        def guarded():
            v = helper(1)
            if v is None:
                return ""
            return v
    """))[0].confirmed_defect_classification
    assert gate["classification"] == CDG.CLASS_REFUTED


def test_weak_contract_not_confirmed(compliance_on):
    gate = _ir(_analyze("""
        def helper(x):
            if x:
                return "a"
    """))[0].confirmed_defect_classification
    assert gate["classification"] != CDG.CLASS_CONFIRMED
    assert "weak_contract_only" in gate["design_blockers"]


def test_unresolved_consequence_not_confirmed(compliance_on):
    gate = _ir(_analyze("""
        def helper(x) -> str:
            if x:
                return "a"
    """))[0].confirmed_defect_classification
    assert gate["classification"] != CDG.CLASS_CONFIRMED
    assert "no_observable_consequence" in gate["design_blockers"]


def test_promotion_candidate_without_test_is_strong_suspect(compliance_on):
    gate = _ir(_analyze(PROVEN))[0].confirmed_defect_classification
    assert gate["classification"] == CDG.CLASS_STRONG_SUSPECT
    assert gate["criteria"]["c3"] is False


def test_refuting_evidence_blocks(compliance_on):
    gate = _ir(_analyze("""
        def helper(x) -> str | None:
            if x:
                return "a"
    """))[0].confirmed_defect_classification
    assert gate["classification"] != CDG.CLASS_CONFIRMED


@pytest.mark.parametrize("src", [
    """
    def helper(x) -> str:
        if x:
            return "a"
    def guarded():
        v = helper(1)
        if v is None:
            return ""
        return v
    """,
    """
    def helper(x):
        if x:
            return "a"
    def caller():
        return helper(1).upper()
    """,
    """
    def helper(x) -> str:
        if x:
            return "a"
    """,
])
def test_phase95e_rejected_shapes_do_not_confirm(compliance_on, src):
    gate = _ir(_analyze(src))[0].confirmed_defect_classification
    assert gate["classification"] != CDG.CLASS_CONFIRMED


def test_other_rules_not_classified(gate_on):
    res = _analyze("""
        def run():
            while True:
                items = []
                for x in items:
                    pass
                items.append(1)
    """)
    for finding in res.findings:
        if finding.rule != "inconsistent_return":
            assert finding.confirmed_defect_classification is None


def test_taxonomy_values(compliance_on):
    gate = _ir(_analyze(PROVEN))[0].confirmed_defect_classification
    assert gate["classification"] in CDG.CLASSIFICATIONS


def test_flag_off_after_engine_enrichment():
    res = _analyze(PROVEN)
    assert all(f.confirmed_defect_classification is None for f in res.findings)


def test_promotion_and_kind_unchanged(compliance_on):
    f = _ir(_analyze(PROVEN))[0]
    assert f.kind == "value_flow"
    assert f.confidence == "high"


def test_verification_overlay_has_impact_context(compliance_on):
    ve = _ir(_analyze(PROVEN))[0].verification_evidence
    assert ve["impact_context"]["resolved"] is True


def test_enablement_gates_unavailable_when_flags_off():
    report = CDG.evaluate_enablement_gates()
    assert report["available"] is False


def test_grounded_verdict_unchanged():
    res = _analyze("""
        def find(xs, t):
            for i, x in enumerate(xs):
                if x == t:
                    return i
    """)
    grounded = engine_benchmark.grounded_findings(res)
    assert all(f.rule != "inconsistent_return" for f in grounded)


def test_mini_quixbugs_benchmark_unchanged(tmp_path):
    root = tmp_path / "MiniQuixBugs"
    buggy = root / "python_programs"
    correct = root / "correct_python_programs"
    buggy.mkdir(parents=True)
    correct.mkdir()
    bfs = textwrap.dedent("""
        from collections import deque as Queue
        def breadth_first_search(startnode, goalnode):
            queue = Queue()
            queue.append(startnode)
            nodesseen = set()
            nodesseen.add(startnode)
            while True:
                node = queue.popleft()
                if node is goalnode:
                    return True
                queue.extend(n for n in node.successors if n not in nodesseen)
                nodesseen.update(node.successors)
            return False
    """)
    (buggy / "breadth_first_search.py").write_text(bfs, encoding="utf-8")
    (correct / "breadth_first_search.py").write_text(
        bfs.replace("while True:", "while queue:"), encoding="utf-8")
    report = engine_benchmark.evaluate_quixbugs_engine(str(root))
    assert report["true_positives"] == 1
    assert report["false_positives"] == 0


@pytest.mark.skipif(not os.path.isdir(r"C:\Repos\QuixBugs"), reason="QuixBugs absent")
def test_quixbugs_unchanged():
    report = engine_benchmark.evaluate_quixbugs_engine(r"C:\Repos\QuixBugs")
    assert report["true_positives"] == 12
    assert report["false_positives"] == 0


@pytest.mark.skipif(not engine_benchmark._PAIRS_ROOT.is_dir(), reason="holdout absent")
def test_holdout_unchanged():
    report = engine_benchmark.evaluate_holdout_engine()
    assert report["false_positives"] == 0
    assert report["true_positives"] >= 2
