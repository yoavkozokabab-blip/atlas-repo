"""Phase 95A tests for the read-only real-repository validation harness."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from builder_core.bug_intelligence.finding import Finding, LOGIC_BUG
from builder_core.real_repo_validation import cli
from builder_core.real_repo_validation import harness as H


def _git(root: Path, *args: str) -> str:
    proc = subprocess.run(
        ["git", *args],
        cwd=root,
        capture_output=True,
        text=True,
        check=True,
    )
    return proc.stdout.strip()


def _repo(tmp_path: Path, name: str = "repo") -> tuple[Path, str]:
    root = tmp_path / name
    root.mkdir()
    (root / "vuln.py").write_text(
        "import subprocess\n\n"
        "def run(cmd):\n"
        "    subprocess.call(cmd, shell=True)\n",
        encoding="utf-8",
    )
    (root / "clean.py").write_text(
        "def add(a, b):\n"
        "    return a + b\n",
        encoding="utf-8",
    )
    _git(root, "init")
    _git(root, "config", "user.email", "phase95a@example.invalid")
    _git(root, "config", "user.name", "Phase 95A Test")
    _git(root, "add", ".")
    _git(root, "commit", "-m", "fixture")
    return root, _git(root, "rev-parse", "HEAD")


def _manifest(root: Path, commit: str, repo_id: str = "fixture") -> dict:
    return {
        "schema_version": 1,
        "program_id": "phase95a-test",
        "candidate": H.candidate_record(),
        "historical_bugs": [],
        "repositories": [
            {
                "id": repo_id,
                "path": str(root),
                "commit": commit,
                "license": "test-only",
                "size_band": "small",
                "language_profile": "python_dominant",
                "project_shape": "library",
                "selection_rationale": "Synthetic local fixture for harness tests.",
                "python_loc": 6,
                "python_files": 2,
            }
        ],
    }


def _finding(file: str = "same.py") -> Finding:
    return Finding(
        category=LOGIC_BUG,
        kind="data_flow",
        severity="high",
        confidence="high",
        file=file,
        line=3,
        title="container consumption",
        explanation="queue may empty",
        why_might_be_wrong="external guard",
        next_verification_step="inspect guard",
        rule="unguarded_container_consumption",
    )


def test_manifest_format_requires_pinned_repository_metadata(tmp_path):
    manifest = {
        "schema_version": 1,
        "program_id": "x",
        "candidate": H.candidate_record(),
        "repositories": [{"id": "r"}],
    }
    issues = H.validate_manifest(manifest)
    assert "repository[0] missing required field 'path'" in issues
    assert "repository[0] missing required field 'commit'" in issues
    assert H.validate_manifest(_manifest(tmp_path, "abc")) == []


def test_manifest_supports_preregistered_historical_bug_cases(tmp_path):
    manifest = _manifest(tmp_path, "abc")
    manifest["historical_bugs"] = [
        {
            "id": "bug-1",
            "repo_id": "fixture",
            "parent_commit": "parent",
            "fix_commit": "fixed",
            "description": "Real bug fixed later.",
            "fixed_files": ["x.py"],
        }
    ]
    assert H.validate_manifest(manifest) == []


def test_scan_is_read_only_and_exports_grounded_security(tmp_path):
    root, commit = _repo(tmp_path)
    repo = _manifest(root, commit)["repositories"][0]
    before = H.snapshot_repo(str(root))
    scan = H.scan_repository(repo)
    after = H.snapshot_repo(str(root))

    assert scan["outcome"] == "success"
    assert H.compare_snapshots(before, after)["safe"] is True
    assert scan["safety"]["safe"] is True
    command_injection = next(r for r in scan["records"] if r["rule"] == "command_injection")
    assert command_injection["kind"] == "security"
    assert command_injection["verdict_eligible"] is True
    assert command_injection["source_window"]


def test_commit_mismatch_blocks_analysis(tmp_path, monkeypatch):
    root, _commit = _repo(tmp_path)
    repo = _manifest(root, "0" * 40)["repositories"][0]

    def fail_if_called(_root):
        raise AssertionError("engine must not run against an unpinned checkout")

    monkeypatch.setattr(H.engine, "analyze_repository", fail_if_called)
    scan = H.scan_repository(repo)
    assert scan["outcome"] == "failed"
    assert scan["errors"] == ["checkout commit does not match manifest commit"]


def test_record_ids_are_stable_and_unique_across_repositories(tmp_path):
    finding = _finding()
    first = H.finding_record(finding, {"id": "a", "path": str(tmp_path)})
    second = H.finding_record(finding, {"id": "b", "path": str(tmp_path)})
    repeated = H.finding_record(finding, {"id": "a", "path": str(tmp_path)})
    assert first["record_id"] != second["record_id"]
    assert first["record_id"] == repeated["record_id"]


def test_review_template_supports_two_reviewers_and_adjudication(tmp_path):
    record = H.finding_record(_finding(), {"id": "repo", "path": str(tmp_path)})
    path = tmp_path / "reviews.json"
    H.export_review_template([record], path)
    reviews = H.load_reviews(path)
    review = reviews["findings"][record["record_id"]]
    assert set(review) >= {"reviewer_a", "reviewer_b", "adjudication"}

    review["reviewer_a"].update(label="confirmed_actionable", usefulness=4)
    review["reviewer_b"].update(label="benign_or_intended", usefulness=0)
    pending = H.merge_reviews([record], reviews)[0]
    assert pending["label"] == "unreviewed"
    assert pending["needs_adjudication"] is True

    review["adjudication"].update(label="confirmed_actionable", usefulness=3)
    resolved = H.merge_reviews([record], reviews)
    precision = H.measure_precision(resolved)
    assert resolved[0]["review_resolution"] == "adjudicated"
    assert precision["strict_precision"] == 1.0
    assert precision["by_kind"]["data_flow"]["precision"] == 1.0


def test_precision_and_usefulness_report_strata(tmp_path):
    record = H.finding_record(
        _finding(),
        {
            "id": "repo",
            "path": str(tmp_path),
            "size_band": "small",
            "language_profile": "python_dominant",
            "project_shape": "library",
        },
    )
    labeled = [
        {
            **record,
            "label": "confirmed_actionable",
            "usefulness": 4,
            "needs_adjudication": False,
        }
    ]
    precision = H.measure_precision(labeled)
    usefulness = H.score_usefulness(
        labeled,
        {
            "repositories": {
                "repo": {"usefulness": 4, "would_use_again": True, "reason": "useful"}
            }
        },
    )
    assert precision["strict_precision"] == 1.0
    assert precision["weighted_strict_precision"] == 1.0
    assert precision["by_size_band"]["small"]["precision"] == 1.0
    assert precision["by_language_profile"]["python_dominant"]["precision"] == 1.0
    assert usefulness["per_repository"]["median_repo_usefulness"] == 4
    assert usefulness["per_repository"]["would_use_again_rate"] == 1.0


def test_finding_export_is_deterministic(tmp_path):
    first = H.finding_record(_finding("b.py"), {"id": "repo", "path": str(tmp_path)})
    second = H.finding_record(_finding("a.py"), {"id": "repo", "path": str(tmp_path)})
    a = tmp_path / "a.json"
    b = tmp_path / "b.json"
    H.export_findings([first, second], a)
    H.export_findings([second, first], b)
    assert a.read_bytes() == b.read_bytes()
    assert [r["file"] for r in json.loads(a.read_text(encoding="utf-8"))] == ["a.py", "b.py"]


def test_run_to_directory_writes_complete_artifact_set(tmp_path):
    root, commit = _repo(tmp_path)
    output = tmp_path / "artifacts"
    manifest = _manifest(root, commit)
    H.run_to_directory(manifest, output)
    expected = {
        "findings.json",
        "findings.reviewed.json",
        "manifest.normalized.json",
        "metrics.json",
        "program.json",
        "report.md",
        "repository_scores.json",
        "reviews.json",
    }
    assert {path.name for path in output.iterdir()} == expected
    assert "# Real Repository Validation Report" in (output / "report.md").read_text(encoding="utf-8")
    assert _git(root, "status", "--short") == ""


def test_output_directory_inside_target_is_rejected(tmp_path):
    root, commit = _repo(tmp_path)
    with pytest.raises(ValueError, match="outside target repository"):
        H.run_to_directory(_manifest(root, commit), root / "artifacts")


def test_cli_run_and_report(tmp_path, capsys):
    root, commit = _repo(tmp_path)
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(_manifest(root, commit)), encoding="utf-8")
    output = tmp_path / "artifacts"
    assert cli.main(["run", "--manifest", str(manifest_path), "--output", str(output)]) == 0
    assert cli.main(["report", "--run-dir", str(output)]) == 0
    out = capsys.readouterr().out
    assert "Validation artifacts written" in out
    assert "Validation report refreshed" in out
