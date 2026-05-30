"""Phase 84 external holdout benchmark tests."""

from __future__ import annotations

from builder_core.external_benchmark import evaluate_holdout


def test_holdout_corpus_available() -> None:
    report = evaluate_holdout()
    assert report["available"] is True
    assert report["cases_analyzed"] == 12


def test_holdout_reports_confusion_matrix_fields() -> None:
    report = evaluate_holdout()
    for key in (
        "true_positives",
        "false_positives",
        "false_negatives",
        "true_negatives",
        "precision",
        "recall",
    ):
        assert key in report
