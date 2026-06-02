"""Phase 96C tests: contract-enriched review packets (no promotion)."""

from __future__ import annotations

import os
import textwrap

import pytest

from builder_core.bug_intelligence import (
    contract_enrichment,
    engine,
    engine_benchmark,
    fact_detectors,
)
from builder_core.real_repo_validation import harness as H


def _analyze(src: str, file: str = "m.py"):
    return engine.analyze_source(textwrap.dedent(src), file)


def _ir_findings(result):
    return [f for f in result.findings if f.rule == "inconsistent_return"]


def test_inconsistent_return_gets_contract_review_packet():
    res = _analyze("""
        def helper(x) -> str:
            if x:
                return "a"
        def caller():
            return helper(1).upper()
    """)
    ir = _ir_findings(res)
    assert len(ir) == 1
    f = ir[0]
    assert f.contract_review is not None
    assert f.contract_review["review_packet_status"] == "review_lead_only"
    assert "review_lead_only" in f.tags
    assert "confirmed_bug" not in f.tags
    assert "confirmed_defect" not in f.tags


def test_return_contract_evidence_explicit_type_hint_only():
    res = _analyze("""
        def helper(x) -> str:
            if x:
                return "a"
        def noop():
            pass
    """)
    f = _ir_findings(res)[0]
    ev = f.contract_review["return_contract_evidence"]
    assert ev
    assert all("type_hint" in item["sources"] for item in ev)
    assert all(item["confidence"] == "explicit" for item in ev)


def test_caller_behavior_evidence_strong_only():
    res = _analyze("""
        def helper(x) -> str:
            if x:
                return "a"
        def caller():
            return helper(1).upper()
    """)
    f = _ir_findings(res)[0]
    ev = f.contract_review["caller_behavior_evidence"]
    assert ev
    assert all("caller_behavior" in item["sources"] for item in ev)
    assert all(item["confidence"] == "inferred_strong" for item in ev)


def test_conflicting_weak_caller_and_quarantine():
    res = _analyze("""
        def helper(x) -> str:
            if x:
                return "a"
        def guarded():
            v = helper(1)
            if v is None:
                return ""
            return v
    """)
    f = _ir_findings(res)[0]
    assert f.kind == "pattern"
    conflicts = f.contract_review["conflicting_evidence"]
    assert any(
        c.get("conflict_reason") in (
            "mixed_or_null_checking_callers",
            "optional_return_signal",
        )
        for c in conflicts
    )
    assert any(c.get("conflict_reason") == "interprocedural_gate_not_met" for c in conflicts)


def test_why_not_confirmed_present():
    res = _analyze("""
        def find(xs, t):
            for i, x in enumerate(xs):
                if x == t:
                    return i
    """)
    f = _ir_findings(res)[0]
    why = f.contract_review["why_not_confirmed"]
    assert why
    assert any("not a confirmed defect" in w.lower() for w in why)
    assert any("callee_behavior" in w for w in why)


def test_promotion_unchanged_with_enrichment():
    src = textwrap.dedent("""
        def helper(x) -> str:
            if x:
                return "a"
        def caller():
            return helper(1).upper()
    """)
    assert fact_detectors.INTERPROC_PROMOTION_ENABLED is True
    res = _analyze(src)
    f = _ir_findings(res)[0]
    assert f.kind == "value_flow"
    assert f.confidence == "high"


def test_other_rules_not_enriched():
    res = _analyze("""
        def run():
            while True:
                items = []
                for x in items:
                    pass
                items.append(1)
    """)
    for f in res.findings:
        if f.rule != "inconsistent_return":
            assert f.contract_review is None


def test_finding_record_exports_contract_review():
    res = _analyze("""
        def helper(x) -> str:
            if x:
                return "a"
    """)
    f = _ir_findings(res)[0]
    record = H.finding_record(f, {"id": "repo", "path": ".", "commit": "x"})
    assert record.get("contract_review") is not None
    assert record["contract_review"]["review_packet_status"] == "review_lead_only"


def test_reviewer_packet_includes_contract_review(tmp_path):
    res = _analyze("""
        def helper(x) -> str:
            if x:
                return "a"
        def caller():
            return helper(1).upper()
    """)
    f = _ir_findings(res)[0]
    record = H.finding_record(f, {"id": "repo", "path": str(tmp_path), "commit": "x"})
    out = tmp_path / "packets"
    out.mkdir()
    H.export_reviewer_packets([record], out)
    import json
    packets = json.loads((out / "reviewer_a_packets.json").read_text(encoding="utf-8"))
    assert packets[0].get("contract_review") is not None


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

    holdout = engine_benchmark.evaluate_holdout_engine(pairs_root=tmp_path / "nope")
    assert holdout["available"] is False


@pytest.mark.skipif(not os.path.isdir(r"C:\Repos\QuixBugs"), reason="QuixBugs absent")
def test_quixbugs_unchanged():
    report = engine_benchmark.evaluate_quixbugs_engine(r"C:\Repos\QuixBugs")
    assert report["true_positives"] == 12
    assert report["false_positives"] == 0


@pytest.mark.skipif(not engine_benchmark._PAIRS_ROOT.is_dir(), reason="holdout absent")
def test_holdout_unchanged():
    report = engine_benchmark.evaluate_holdout_engine()
    assert report["true_positives"] == 2
    assert report["false_positives"] == 0


def test_disable_enrichment_flag(monkeypatch):
    monkeypatch.setattr(contract_enrichment, "CONTRACT_ENRICHMENT_ENABLED", False)
    res = _analyze("""
        def helper(x) -> str:
            if x:
                return "a"
    """)
    assert _ir_findings(res)[0].contract_review is None
