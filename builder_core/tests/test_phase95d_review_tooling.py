"""Phase 95D tests for the human review helper tooling."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from builder_core.bug_intelligence.finding import Finding, SECURITY_RISK
from builder_core.real_repo_validation import harness as H
from builder_core.real_repo_validation import review_cli
from builder_core.real_repo_validation import review_tool as RT


def _packet(record_id: str, *, rule: str = "command_injection", kind: str = "security") -> dict:
    return {
        "record_id": record_id,
        "finding_id": f"BI-{record_id[-8:]}",
        "repo_id": "fixture",
        "file": f"{record_id}.py",
        "line": 10,
        "rule": rule,
        "kind": kind,
        "severity": "high",
        "confidence": "high",
        "title": rule.replace("_", " "),
        "explanation": "test explanation",
        "evidence": "subprocess.run(",
        "why_might_be_wrong": "may be constant",
        "next_verification_step": "inspect args",
        "source_window": [
            "8: def run():",
            "9:     cmd = ['git']",
            "10:     subprocess.run(",
            "11:         cmd,",
            "12:     )",
        ],
    }


def _sample_record(record_id: str) -> dict:
    finding = Finding(
        category=SECURITY_RISK,
        kind="security",
        severity="high",
        confidence="high",
        file=f"{record_id}.py",
        line=10,
        title="command injection",
        explanation="test",
        why_might_be_wrong="test",
        next_verification_step="test",
        rule="command_injection",
    )
    record = finding.to_dict()
    record.update({
        "record_id": record_id,
        "repo_id": "fixture",
        "sampling_probability": 1.0,
        "verdict_eligible": True,
        "source_window": _packet(record_id)["source_window"],
    })
    return record


def _write_run_dir(tmp_path: Path, record_ids: list[str]) -> Path:
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    records = [_sample_record(record_id) for record_id in record_ids]
    packets = [_packet(record_id) for record_id in record_ids]
    H.write_json(run_dir / "reviewer_a_packets.json", packets)
    H.write_json(run_dir / "reviewer_b_packets.json", packets)
    H.write_json(run_dir / "adjudication_packets.json", packets)
    H.write_json(run_dir / "review_sample.json", records)
    H.export_review_template(records, run_dir / "reviews.json")
    return run_dir


def test_validate_rejects_incomplete_packets(tmp_path):
    run_dir = _write_run_dir(tmp_path, ["RR-aaa", "RR-bbb"])
    packets = json.loads((run_dir / "reviewer_a_packets.json").read_text(encoding="utf-8"))
    packets.pop()
    H.write_json(run_dir / "reviewer_a_packets.json", packets)
    context = RT.load_run_context(run_dir)
    issues = RT.validate_packets(context)
    assert any("packet count" in issue for issue in issues)


def test_apply_decision_is_deterministic_and_resumes(tmp_path):
    run_dir = _write_run_dir(tmp_path, ["RR-bbb", "RR-aaa"])
    context = RT.load_run_context(run_dir)
    assert RT.next_pending_record_id(context, "reviewer_a") == "RR-bbb"

    RT.apply_decision(
        context,
        "RR-bbb",
        "true_positive",
        reviewer="alice",
        slot="reviewer_a",
        notes="confirmed",
    )
    assert RT.next_pending_record_id(context, "reviewer_a") == "RR-aaa"
    assert RT.pending_record_ids(context, "reviewer_a") == ["RR-aaa"]
    assert RT.reviewed_record_ids(context, "reviewer_a") == ["RR-bbb"]

    reviews = H.load_reviews(run_dir / "reviews.json")
    slot = reviews["findings"]["RR-bbb"]["reviewer_a"]
    assert slot["label"] == "confirmed_actionable"
    assert slot["usefulness"] == 4

    audit = json.loads((run_dir / "review_decisions.reviewer_a.json").read_text(encoding="utf-8"))
    assert audit["reviewer"] == "alice"
    assert audit["decisions"]["RR-bbb"]["label"] == "true_positive"


def test_apply_decision_rejects_overwrite_without_edit(tmp_path):
    run_dir = _write_run_dir(tmp_path, ["RR-one"])
    context = RT.load_run_context(run_dir)
    RT.apply_decision(context, "RR-one", "false_positive", reviewer="bob", fp_reason="constant")
    with pytest.raises(ValueError, match="already reviewed"):
        RT.apply_decision(context, "RR-one", "true_positive", reviewer="bob")
    RT.apply_decision(
        context,
        "RR-one",
        "true_positive",
        reviewer="bob",
        edit=True,
    )


def test_apply_decision_rejects_invalid_label_and_missing_reviewer(tmp_path):
    run_dir = _write_run_dir(tmp_path, ["RR-one"])
    context = RT.load_run_context(run_dir)
    with pytest.raises(ValueError, match="invalid label"):
        RT.apply_decision(context, "RR-one", "maybe", reviewer="alice")
    with pytest.raises(ValueError, match="reviewer name is required"):
        RT.apply_decision(context, "RR-one", "unclear", reviewer="  ")


def test_format_candidate_includes_source_window(tmp_path):
    run_dir = _write_run_dir(tmp_path, ["RR-one"])
    context = RT.load_run_context(run_dir)
    text = RT.format_candidate(context, "RR-one")
    assert "SOURCE WINDOW" in text
    assert "subprocess.run(" in text
    assert "record_id=RR-one" in text


def test_export_csv_is_stable(tmp_path):
    run_dir = _write_run_dir(tmp_path, ["RR-b", "RR-a"])
    context = RT.load_run_context(run_dir)
    RT.apply_decision(context, "RR-b", "useful_advisory", reviewer="alice")
    csv_text = RT.export_decisions_csv(context, "reviewer_a")
    lines = csv_text.strip().splitlines()
    assert lines[0].startswith("record_id,repo_id")
    assert lines[1].startswith("RR-b,")
    assert lines[2].startswith("RR-a,")
    assert lines[1].count(",") == lines[2].count(",")
    RT.write_decisions_csv(context, "reviewer_a", run_dir / "out.csv")
    assert (run_dir / "out.csv").read_text(encoding="utf-8") == csv_text


def test_estimate_progress_counts_precision_and_fp_reasons(tmp_path):
    run_dir = _write_run_dir(tmp_path, ["RR-a", "RR-b", "RR-c"])
    context = RT.load_run_context(run_dir)
    RT.apply_decision(context, "RR-a", "true_positive", reviewer="alice")
    RT.apply_decision(
        context,
        "RR-b",
        "false_positive",
        reviewer="alice",
        fp_reason="constant argv",
    )
    RT.apply_decision(context, "RR-c", "unclear", reviewer="alice")
    progress = RT.estimate_progress(context, "reviewer_a")
    assert progress["reviewed"] == 3
    assert progress["pending"] == 0
    assert progress["precision_estimate"] == 0.5
    assert progress["usefulness_estimate"] == 2.0
    assert progress["top_fp_reasons"][0]["reason"] == "constant argv"


def test_cli_validate_list_show_decide_report(tmp_path, capsys):
    run_dir = _write_run_dir(tmp_path, ["RR-one", "RR-two"])
    assert review_cli.main([
        "validate",
        "--run-dir",
        str(run_dir),
        "--slot",
        "reviewer_a",
    ]) == 0

    assert review_cli.main([
        "list",
        "--run-dir",
        str(run_dir),
        "--slot",
        "reviewer_a",
    ]) == 0
    out = capsys.readouterr().out
    assert "PENDING (2)" in out
    assert "RR-one" in out

    assert review_cli.main([
        "resume",
        "--run-dir",
        str(run_dir),
        "--slot",
        "reviewer_a",
    ]) == 0
    assert "ITEM 1/2" in capsys.readouterr().out

    assert review_cli.main([
        "decide",
        "--run-dir",
        str(run_dir),
        "--record-id",
        "RR-one",
        "--label",
        "not_useful",
        "--reviewer",
        "alice",
        "--slot",
        "reviewer_a",
    ]) == 0
    decide_out = capsys.readouterr().out
    assert "Saved RR-one -> not_useful" in decide_out
    assert "NEXT: RR-two" in decide_out

    assert review_cli.main([
        "report",
        "--run-dir",
        str(run_dir),
        "--slot",
        "reviewer_a",
    ]) == 0
    report_out = capsys.readouterr().out
    assert "reviewed: 1/2" in report_out
    assert "not_useful: 1" in report_out


def test_cli_export_csv_default_path(tmp_path, capsys):
    run_dir = _write_run_dir(tmp_path, ["RR-one"])
    context = RT.load_run_context(run_dir)
    RT.apply_decision(context, "RR-one", "true_positive", reviewer="alice")
    assert review_cli.main([
        "export-csv",
        "--run-dir",
        str(run_dir),
        "--slot",
        "reviewer_a",
    ]) == 0
    csv_path = run_dir / "review_decisions.reviewer_a.csv"
    assert csv_path.is_file()
    assert "true_positive" in csv_path.read_text(encoding="utf-8")
    assert "Wrote" in capsys.readouterr().out
