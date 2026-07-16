from __future__ import annotations

import json
from pathlib import Path

from score import score


def test_contract_scores_expected_observations_without_inventing_runs():
    root = Path(__file__).resolve().parent
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    observations = {"scenarios": {
        name: {"relevant_files": value["relevant_files"], "dependencies": value["dependencies"], "citations": value["citation_files"],
               "impact": value["impact"], "stale_context_rejected": value["stale_context_rejected"],
               **({"cross_repository_isolated": True} if value.get("cross_repository_isolated") else {})}
        for name, value in manifest["scenarios"].items()
    }}
    result = score(manifest, observations)
    assert result["observation_contract_scored"] is True
    assert result["metrics"]["file_relevance_precision"] == 1.0
    assert result["metrics"]["dependency_recall"] == 1.0
    assert result["metrics"]["impact_false_negative_rate"] == 0.0


def test_contract_penalizes_cross_repository_leakage_and_invalid_citations():
    manifest = {"scenarios": {"isolation": {"files": ["repo_a/a.py", "repo_b/a.py"], "relevant_files": ["repo_a/a.py"],
                                             "dependencies": [], "impact": [], "citation_files": ["repo_a/a.py"],
                                             "stale_context_rejected": True, "cross_repository_isolated": True}}}
    result = score(manifest, {"scenarios": {"isolation": {"relevant_files": ["repo_b/a.py"], "dependencies": [], "citations": ["missing.py"],
                                                             "impact": [], "stale_context_rejected": False, "cross_repository_isolated": False}}})
    assert result["metrics"]["file_relevance_recall"] == 0.0
    assert result["metrics"]["citation_validity"] == 0.0
    assert result["metrics"]["cross_repository_isolation"] == 0.0


def test_every_manifest_file_exists_in_its_fixture():
    root = Path(__file__).resolve().parent
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    for scenario, expected in manifest["scenarios"].items():
        fixture = root / "fixtures" / scenario
        for relative in expected["files"]:
            assert (fixture / relative).is_file(), f"missing fixture file: {scenario}/{relative}"
