"""Phase 97A tests: verification evidence infrastructure (no promotion)."""

from __future__ import annotations

import json
import os
import textwrap

import pytest

from builder_core.bug_intelligence import (
    engine,
    engine_benchmark,
    fact_detectors,
    verification_evidence as VE,
)
from builder_core.real_repo_validation import harness as H
from builder_core.real_repo_validation import review_tool


PROD = textwrap.dedent("""
    def helper(x) -> str:
        if x:
            return "a"
    def caller():
        return helper(1).upper()
""")

TEST_DOC = textwrap.dedent("""
    from m import helper

    def test_helper_non_none():
        assert helper(1) is not None
""")


def _analyze(src: str, file: str = "m.py", **kwargs):
    return engine.analyze_source(textwrap.dedent(src), file, **kwargs)


def _ir(result):
    return [f for f in result.findings if f.rule == "inconsistent_return"]


def test_inconsistent_return_gets_verification_overlay():
    res = _analyze(PROD)
    f = _ir(res)[0]
    ve = f.verification_evidence
    assert ve is not None
    assert ve["schema_version"] == VE.SCHEMA_VERSION
    assert ve["status"] in {
        VE.STATUS_ENRICHED_LEAD,
        VE.STATUS_BLOCKED,
        VE.STATUS_REFUTED,
        VE.STATUS_UNKNOWN,
    }
    assert ve["review_packet_status"] == "review_lead_only"
    assert "review_lead_only" in f.tags
    assert "confirmed_bug" not in f.tags
    assert "confirmed_defect" not in f.tags


def test_all_evidence_types_exist_in_schema():
    assert set(VE.EVIDENCE_TYPES) == {
        VE.EVIDENCE_TEST,
        VE.EVIDENCE_ASSERTION,
        VE.EVIDENCE_CONTRACT_VIOLATION,
        VE.EVIDENCE_PATH_FEASIBILITY,
        VE.EVIDENCE_RUNTIME,
    }
    assert set(VE.STRENGTH_LEVELS) == {VE.E0, VE.E1, VE.E2, VE.E3, VE.E4}


def test_mapped_test_evidence_binds():
    res = _analyze(
        PROD,
        test_documents=[{"path": "tests/test_m.py", "content": TEST_DOC}],
    )
    f = _ir(res)[0]
    atoms = f.verification_evidence["atoms"]
    test_atoms = [a for a in atoms if a["evidence_type"] == VE.EVIDENCE_TEST]
    assert test_atoms
    assert test_atoms[0]["strength"] == VE.E2
    assert test_atoms[0]["polarity"] == VE.POLARITY_SUPPORTS


def test_star_import_test_stays_weak():
    weak_test = textwrap.dedent("""
        from m import *

        def test_helper():
            assert helper(1) is not None
    """)
    res = _analyze(PROD, test_documents=[{"path": "tests/test_m.py", "content": weak_test}])
    test_atoms = [
        a for a in _ir(res)[0].verification_evidence["atoms"]
        if a["evidence_type"] == VE.EVIDENCE_TEST
    ]
    assert test_atoms
    assert test_atoms[0]["strength"] == VE.E1
    assert "star_import" in test_atoms[0]["binding"]["unresolved_reasons"]


def test_contract_violation_atom_for_explicit_hint_and_fallthrough():
    res = _analyze("""
        def helper(x) -> str:
            if x:
                return "a"
    """)
    violations = [
        a for a in _ir(res)[0].verification_evidence["atoms"]
        if a["evidence_type"] == VE.EVIDENCE_CONTRACT_VIOLATION
    ]
    assert violations
    assert violations[0]["strength"] == VE.E2


def test_optional_return_blocks_violation():
    res = _analyze("""
        def helper(x) -> str | None:
            if x:
                return "a"
    """)
    ve = _ir(res)[0].verification_evidence
    violations = [a for a in ve["atoms"] if a["evidence_type"] == VE.EVIDENCE_CONTRACT_VIOLATION]
    assert not violations
    assert "conflicting_optional_return_contract" in ve["blockers"]


def test_promoted_finding_gets_e3_path_witness():
    res = _analyze(PROD)
    f = _ir(res)[0]
    assert f.kind == "value_flow"
    paths = [
        a for a in f.verification_evidence["atoms"]
        if a["evidence_type"] == VE.EVIDENCE_PATH_FEASIBILITY
    ]
    assert paths
    assert any(a["strength"] == VE.E3 for a in paths)


def test_null_checking_caller_refutes_path():
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
    refuting = _ir(res)[0].verification_evidence["refuting_evidence"]
    assert refuting
    assert any(a["evidence_type"] == VE.EVIDENCE_PATH_FEASIBILITY for a in refuting)


def test_runtime_artifact_parser_redacts_and_caps_strength():
    atom = VE.parse_runtime_artifact({
        "revision": "abc123",
        "command": "pytest tests/test_m.py --token=secret123",
        "exit_code": 1,
        "determinism_result": "deterministic",
        "failure_class": "AssertionError",
        "subject": {"file": "m.py", "qualname": "helper", "line": 1},
        "artifact_ref": "ci/run-42.json",
    })
    assert atom is not None
    assert atom["evidence_type"] == VE.EVIDENCE_RUNTIME
    assert atom["strength"] == VE.E2
    assert "<redacted>" in atom["provenance"]["command_fingerprint"]


def test_no_promotion_candidate_when_gate_disabled():
    res = _analyze(PROD)
    assert VE.EVIDENCE_PROMOTION_ENABLED is False
    for f in _ir(res):
        assert f.verification_evidence["status"] != VE.STATUS_PROMOTION_CANDIDATE


def test_flag_off_omits_overlay():
    old = VE.VERIFICATION_EVIDENCE_ENABLED
    try:
        VE.VERIFICATION_EVIDENCE_ENABLED = False
        f = _ir(_analyze(PROD))[0]
        assert f.verification_evidence is None
    finally:
        VE.VERIFICATION_EVIDENCE_ENABLED = old


def test_promotion_and_kind_unchanged():
    assert fact_detectors.INTERPROC_PROMOTION_ENABLED is True
    res = _analyze(PROD)
    f = _ir(res)[0]
    assert f.kind == "value_flow"
    assert f.confidence == "high"


def test_evidence_ids_stable():
    res_a = _analyze(PROD, test_documents=[{"path": "tests/test_m.py", "content": TEST_DOC}])
    res_b = _analyze(PROD, test_documents=[{"path": "tests/test_m.py", "content": TEST_DOC}])
    ids_a = [a["evidence_id"] for a in _ir(res_a)[0].verification_evidence["atoms"]]
    ids_b = [a["evidence_id"] for a in _ir(res_b)[0].verification_evidence["atoms"]]
    assert ids_a == ids_b


def test_finding_record_and_reviewer_packet_export():
    res = _analyze(PROD)
    record = H.finding_record(_ir(res)[0], {"id": "repo", "path": ".", "commit": "x"})
    assert record.get("verification_evidence") is not None
    assert record["verification_evidence"]["status"]


def test_review_tool_shows_verification_section(tmp_path):
    res = _analyze(PROD)
    record = H.finding_record(_ir(res)[0], {"id": "repo", "path": str(tmp_path), "commit": "x"})
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    H.export_reviewer_packets([record], run_dir)
    H.write_json(run_dir / "review_sample.json", [record])
    H.write_json(run_dir / "reviews.json", {"findings": {record["record_id"]: {"reviewer_a": {}, "reviewer_b": {}}}})
    ctx = review_tool.load_run_context(run_dir)
    text = review_tool.format_candidate(ctx, record["record_id"])
    assert "VERIFICATION EVIDENCE" in text
    assert "MISSING PROOF OBLIGATIONS" in text


def test_grounded_verdict_unchanged():
    res = _analyze("""
        def find(xs, t):
            for i, x in enumerate(xs):
                if x == t:
                    return i
    """)
    grounded = engine_benchmark.grounded_findings(res)
    assert all(f.rule != "inconsistent_return" for f in grounded)


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
            assert f.verification_evidence is None


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
