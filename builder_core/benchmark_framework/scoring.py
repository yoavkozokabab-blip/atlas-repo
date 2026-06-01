"""Manual score support for Phase 103 benchmark runs."""

from __future__ import annotations

from typing import Any, Dict

from .schema import ManualScore, validate_manual_score


def build_manual_score(
    *,
    task_id: str,
    mode: str,
    correctness: float,
    evidence_quality: float,
    completeness: float,
    hallucination_risk: float,
    task_success: bool,
    true_positives: int = 0,
    false_positives: int = 0,
    false_negatives: int = 0,
    notes: str = "",
) -> ManualScore:
    score = ManualScore(
        task_id=task_id,
        mode=mode,
        correctness=correctness,
        evidence_quality=evidence_quality,
        completeness=completeness,
        hallucination_risk=hallucination_risk,
        task_success=task_success,
        true_positives=true_positives,
        false_positives=false_positives,
        false_negatives=false_negatives,
        notes=notes,
    )
    errors = validate_manual_score(score.to_dict())
    if errors:
        raise ValueError("; ".join(errors))
    return score


def aggregate_bug_accuracy(scores: list[ManualScore]) -> Dict[str, Any]:
    true_positives = sum(score.true_positives for score in scores)
    false_positives = sum(score.false_positives for score in scores)
    false_negatives = sum(score.false_negatives for score in scores)
    precision_denominator = true_positives + false_positives
    recall_denominator = true_positives + false_negatives
    return {
        "true_positives": true_positives,
        "false_positives": false_positives,
        "false_negatives": false_negatives,
        "precision": round(true_positives / precision_denominator, 4) if precision_denominator else None,
        "recall": round(true_positives / recall_denominator, 4) if recall_denominator else None,
    }
