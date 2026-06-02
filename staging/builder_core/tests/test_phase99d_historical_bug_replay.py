"""Phase 99D tests: historical bug replay harness."""

from __future__ import annotations

import json
import os
import textwrap

import pytest

from builder_core.bug_intelligence import confirmed_defect_gate as CDG
from builder_core.bug_intelligence import verification_evidence as VE
from builder_core.bug_intelligence import engine_benchmark
from builder_core.historical_bug_replay import harness as HBR

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

FIXED = textwrap.dedent("""
    def helper(x) -> str:
        if x:
            return "a"
        return ""
    def caller():
        return helper(1).upper()
""")


def _inline_case(case_id: str, buggy: str, fixed: str, **extra):
    return {
        "id": case_id,
        "description": extra.get("description", ""),
        "buggy_revision": {"kind": "inline", "source": buggy, "rel_path": "m.py"},
        "fixed_revision": {"kind": "inline", "source": fixed, "rel_path": "m.py"},
        **{k: v for k, v in extra.items() if k != "description"},
    }


def test_replay_disabled_by_default(tmp_path):
    assert HBR.HISTORICAL_BUG_REPLAY_ENABLED is False
    manifest = {
        "schema_version": 1,
        "cases": [_inline_case("one", PROVEN, FIXED)],
    }
    with pytest.raises(ValueError, match="disabled"):
        HBR.run_replay(manifest, tmp_path / "out", enabled=False)


def test_replay_produces_json_and_metrics(tmp_path):
    manifest = {
        "schema_version": 1,
        "program_id": "phase99d-test",
        "cases": [
            _inline_case(
                "inconsistent_return_proven",
                PROVEN,
                FIXED,
                test_documents=[{"path": "tests/test_m.py", "content": PROVEN_TEST}],
                target_rules=["inconsistent_return"],
            )
        ],
    }
    HBR.run_replay(manifest, tmp_path / "run", enabled=True)
    results = json.loads((tmp_path / "run" / "results.json").read_text(encoding="utf-8"))
    metrics = json.loads((tmp_path / "run" / "metrics.json").read_text(encoding="utf-8"))
    assert results["cases"][0]["case_id"] == "inconsistent_return_proven"
    assert "buggy" in results["cases"][0]
    assert "fixed" in results["cases"][0]
    assert metrics["metrics"]["cases_evaluated"] == 1
    assert (tmp_path / "run" / "report.md").is_file()


def test_detected_on_buggy_with_gate_enabled(tmp_path):
    result = HBR.replay_case(
        _inline_case(
            "proven",
            PROVEN,
            FIXED,
            test_documents=[{"path": "tests/test_m.py", "content": PROVEN_TEST}],
            target_rules=["inconsistent_return"],
        )
    )
    assert result["buggy"]["by_classification"]["detected"] >= 1
    assert result["summary"]["detected_on_buggy"] is True
    assert result["buggy"]["pipeline"]["confirmed_defect_gate"] is True


def test_fixed_revision_outputs_classification_buckets():
    result = HBR.replay_case(_inline_case("pair", PROVEN, FIXED, target_rules=["inconsistent_return"]))
    for side in ("buggy", "fixed"):
        buckets = result[side]["by_classification"]
        for bucket in HBR.OUTPUT_BUCKETS:
            assert bucket in buckets


def test_aggregate_metrics_counts_cases():
    cases = [
        {
            "buggy": {"by_classification": {"detected": 1, "strong_suspect": 0, "review_lead": 0, "refuted": 0, "unknown": 0}},
            "fixed": {"by_classification": {"detected": 0, "strong_suspect": 0, "review_lead": 0, "refuted": 0, "unknown": 0}},
            "summary": {"detected_on_buggy": True, "detected_on_fixed": False, "detected_buggy_only": True},
        }
    ]
    metrics = HBR.aggregate_metrics(cases)
    assert metrics["cases_evaluated"] == 1
    assert metrics["cases_with_detected_on_buggy"] == 1
    assert metrics["cases_with_detected_on_fixed"] == 0
    assert metrics["buggy"]["detected"] == 1


def test_manifest_validation_requires_revisions():
    issues = HBR.validate_manifest({"schema_version": 1, "cases": [{"id": "x"}]})
    assert any("buggy_revision" in issue for issue in issues)


def test_analyze_revision_restores_gate_default():
    assert CDG.CONFIRMED_DEFECT_GATE_ENABLED is False
    assert VE.EVIDENCE_PROMOTION_ENABLED is False
    HBR.analyze_revision(
        {"kind": "inline", "source": PROVEN, "rel_path": "m.py"},
        test_documents=[{"path": "tests/test_m.py", "content": PROVEN_TEST}],
        target_rules=["inconsistent_return"],
    )
    assert CDG.CONFIRMED_DEFECT_GATE_ENABLED is False
    assert VE.EVIDENCE_PROMOTION_ENABLED is False


@pytest.mark.skipif(not engine_benchmark._PAIRS_ROOT.is_dir(), reason="holdout absent")
def test_holdout_pair_replay(tmp_path):
    pair_dir = engine_benchmark._PAIRS_ROOT / "transfer_bfs_empty_queue"
    manifest = {
        "schema_version": 1,
        "program_id": "holdout-smoke",
        "cases": [
            {
                "id": "transfer_bfs_empty_queue",
                "description": "Holdout pair replay smoke",
                "pair_dir": str(pair_dir),
            }
        ],
    }
    HBR.run_replay(manifest, tmp_path / "holdout", enabled=True)
    results = json.loads((tmp_path / "holdout" / "results.json").read_text(encoding="utf-8"))
    assert results["cases"][0]["buggy"]["findings"] is not None


def test_quixbugs_benchmark_unchanged(tmp_path):
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
def test_holdout_benchmark_unchanged():
    report = engine_benchmark.evaluate_holdout_engine()
    assert report["false_positives"] == 0
    assert report["true_positives"] >= 2
