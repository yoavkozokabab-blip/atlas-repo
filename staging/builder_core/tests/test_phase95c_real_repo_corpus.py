"""Phase 95C tests for corpus execution and aggregate reporting."""

from __future__ import annotations

from copy import deepcopy

from builder_core.bug_intelligence.finding import Finding, LOGIC_BUG
from builder_core.real_repo_validation import harness as H


def _finding(record_id: str, *, repo: str = "repo", severity: str = "medium") -> dict:
    finding = Finding(
        category=LOGIC_BUG,
        kind="data_flow",
        severity=severity,
        confidence="high",
        file=f"{record_id}.py",
        line=1,
        title="test",
        explanation="test",
        why_might_be_wrong="test",
        next_verification_step="test",
        rule="unguarded_container_consumption",
    )
    record = finding.to_dict()
    record.update({
        "record_id": record_id,
        "repo_id": repo,
        "sampling_probability": 1.0,
        "size_band": "small",
        "language_profile": "python_dominant",
        "verdict_eligible": True,
    })
    return record


def _manifest() -> dict:
    return {
        "schema_version": 1,
        "program_id": "phase95c-test",
        "sampling_seed": "stable",
        "candidate": H.candidate_record(),
        "historical_bugs": [],
        "repositories": [
            {
                "id": "repo",
                "path": ".",
                "commit": "abc",
                "license": "test",
                "size_band": "small",
                "language_profile": "python_dominant",
                "project_shape": "library",
                "selection_rationale": "test",
                "track": "pilot",
                "primary_eligible": False,
            }
        ],
    }


def test_manifest_accepts_pilot_track_and_rejects_unknown_track():
    manifest = _manifest()
    assert H.validate_manifest(manifest) == []
    manifest["repositories"][0]["track"] = "mystery"
    assert "repository[0] has invalid track 'mystery'" in H.validate_manifest(manifest)


def test_review_sample_is_deterministic_and_keeps_high_severity():
    records = [_finding(f"r{i:03}", severity="high" if i == 0 else "medium") for i in range(350)]
    first = H.select_review_sample(records, seed="fixed", max_findings=40)
    second = H.select_review_sample(list(reversed(records)), seed="fixed", max_findings=40)
    assert [r["record_id"] for r in first] == [r["record_id"] for r in second]
    assert "r000" in {r["record_id"] for r in first}
    assert all(r["sampling_probability"] > 0 for r in first)


def test_corpus_summary_counts_primary_separately_from_pilot():
    manifest = _manifest()
    manifest["repositories"].append({
        **deepcopy(manifest["repositories"][0]),
        "id": "primary",
        "track": "primary",
        "primary_eligible": True,
    })
    program = {
        "scans": [
            {"repo_id": "repo", "outcome": "success"},
            {"repo_id": "primary", "outcome": "degraded"},
        ]
    }
    summary = H.corpus_summary(manifest, program)
    assert summary["repositories_scanned"] == 2
    assert summary["primary_eligible_repositories"] == 1
    assert summary["tracks"] == {"pilot": 1, "primary": 1}


def test_finding_inventory_keeps_advisory_separate():
    grounded = _finding("grounded")
    advisory = {**_finding("advisory"), "kind": "pattern", "verdict_eligible": False}
    inventory = H.finding_inventory([advisory, grounded])
    assert inventory["total_findings"] == 2
    assert inventory["verdict_eligible_findings"] == 1
    assert inventory["advisory_findings"] == 1
    assert inventory["advisory_by_kind"] == {"pattern": 1}


def test_readiness_holds_for_incomplete_pilot_corpus():
    manifest = _manifest()
    program = {"scans": [{"repo_id": "repo", "outcome": "success"}]}
    precision = H.measure_precision([])
    usefulness = H.score_usefulness([])
    readiness = H.evaluate_readiness(manifest, program, precision, usefulness)
    assert readiness["verdict"] == "HOLD"
    failed = {g["name"] for g in readiness["gates"] if not g["passed"]}
    assert "primary_repository_count" in failed
    assert "strict_precision" in failed


def test_reviewer_packets_are_blinded_and_deterministic(tmp_path):
    records = [_finding("b"), _finding("a")]
    H.export_reviewer_packets(records, tmp_path)
    first = (tmp_path / "reviewer_a_packets.json").read_text(encoding="utf-8")
    second = (tmp_path / "reviewer_b_packets.json").read_text(encoding="utf-8")
    assert first == second
    assert '"label"' not in first
    assert first.index('"record_id": "a"') < first.index('"record_id": "b"')


def test_report_includes_hold_verdict_and_corpus_composition():
    manifest = _manifest()
    program = {
        "candidate": H.candidate_record(),
        "scans": [{"repo_id": "repo", "outcome": "success", "duration_seconds": 0.1}],
    }
    precision = H.measure_precision([])
    usefulness = H.score_usefulness([])
    readiness = H.evaluate_readiness(manifest, program, precision, usefulness)
    report = H.generate_report(program, precision, usefulness, readiness)
    assert "## External Alpha Verdict" in report
    assert "**HOLD**" in report
    assert "primary eligible repositories: 0/24" in report
