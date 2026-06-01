"""Codex Alone vs JARVIS + Codex aggregate reporting."""

from __future__ import annotations

from statistics import mean
from typing import Any, Dict, Iterable, Optional

from .schema import MODES, ManualScore, RunLog
from .scoring import aggregate_bug_accuracy


def _avg(values: Iterable[float]) -> Optional[float]:
    materialized = list(values)
    return round(mean(materialized), 4) if materialized else None


def _percent_reduction(baseline: float, candidate: float) -> Optional[float]:
    return round(100.0 * (baseline - candidate) / baseline, 2) if baseline else None


def _ratio(baseline: float, candidate: float) -> Optional[float]:
    return round(baseline / candidate, 3) if candidate else None


def _display(value: Any, suffix: str = "") -> str:
    return "n/a" if value is None else f"{value}{suffix}"


def aggregate(run_logs: list[RunLog], manual_scores: list[ManualScore]) -> Dict[str, Any]:
    logs = {(item.task_id, item.mode): item for item in run_logs}
    scores = {(item.task_id, item.mode): item for item in manual_scores}
    task_ids = sorted({task_id for task_id, _mode in logs} | {task_id for task_id, _mode in scores})
    per_task: list[Dict[str, Any]] = []
    reductions: list[float] = []
    speedups: list[float] = []
    quality_deltas: list[float] = []
    wins = {"jarvis_plus_codex": 0, "codex_alone": 0, "tie": 0, "incomplete": 0}

    for task_id in task_ids:
        base_log = logs.get((task_id, "codex_alone"))
        jarvis_log = logs.get((task_id, "jarvis_plus_codex"))
        base_score = scores.get((task_id, "codex_alone"))
        jarvis_score = scores.get((task_id, "jarvis_plus_codex"))
        row: Dict[str, Any] = {"task_id": task_id}
        if base_log:
            row["codex_alone"] = {"run_log": base_log.to_dict()}
        if jarvis_log:
            row["jarvis_plus_codex"] = {"run_log": jarvis_log.to_dict()}
        if base_score:
            row.setdefault("codex_alone", {})["score"] = base_score.to_dict()
        if jarvis_score:
            row.setdefault("jarvis_plus_codex", {})["score"] = jarvis_score.to_dict()

        if not all((base_log, jarvis_log, base_score, jarvis_score)):
            row["winner"] = "incomplete"
            wins["incomplete"] += 1
            per_task.append(row)
            continue

        reduction = _percent_reduction(base_log.estimated_total_tokens, jarvis_log.estimated_total_tokens)
        speedup = _ratio(base_log.elapsed_seconds, jarvis_log.elapsed_seconds)
        delta = round(jarvis_score.total_score - base_score.total_score, 2)
        row["estimated_token_reduction_percent"] = reduction
        row["speedup"] = speedup
        row["quality_delta_points"] = delta
        if reduction is not None:
            reductions.append(reduction)
        if speedup is not None:
            speedups.append(speedup)
        quality_deltas.append(delta)
        if delta > 0:
            winner = "jarvis_plus_codex"
        elif delta < 0:
            winner = "codex_alone"
        elif jarvis_score.task_success and not base_score.task_success:
            winner = "jarvis_plus_codex"
        elif base_score.task_success and not jarvis_score.task_success:
            winner = "codex_alone"
        else:
            winner = "tie"
        row["winner"] = winner
        wins[winner] += 1
        per_task.append(row)

    arm_stats: Dict[str, Dict[str, Any]] = {}
    for mode in MODES:
        arm_logs = [item for item in run_logs if item.mode == mode]
        arm_scores = [item for item in manual_scores if item.mode == mode]
        arm_stats[mode] = {
            "runs_logged": len(arm_logs),
            "runs_scored": len(arm_scores),
            "average_estimated_input_tokens": _avg(item.estimated_input_tokens for item in arm_logs),
            "average_estimated_output_tokens": _avg(item.estimated_output_tokens for item in arm_logs),
            "average_estimated_total_tokens": _avg(item.estimated_total_tokens for item in arm_logs),
            "average_latency_seconds": _avg(item.elapsed_seconds for item in arm_logs),
            "task_success_rate": _avg(1.0 if item.task_success else 0.0 for item in arm_scores),
            "average_correctness": _avg(item.correctness for item in arm_scores),
            "average_evidence_quality": _avg(item.evidence_quality for item in arm_scores),
            "average_completeness": _avg(item.completeness for item in arm_scores),
            "average_hallucination_risk": _avg(item.hallucination_risk for item in arm_scores),
            "average_total_score": _avg(item.total_score for item in arm_scores),
            "bug_finding_accuracy": aggregate_bug_accuracy(arm_scores),
        }

    return {
        "comparison": "Codex Alone vs JARVIS + Codex",
        "token_numbers_are_estimates": True,
        "tasks_compared": sum(1 for row in per_task if row["winner"] != "incomplete"),
        "win_loss_tie": wins,
        "average_estimated_token_reduction_percent": _avg(reductions),
        "average_speedup": _avg(speedups),
        "average_quality_delta_points": _avg(quality_deltas),
        "modes": arm_stats,
        "per_task": per_task,
    }


def render_markdown(summary: Dict[str, Any], *, run_id: str) -> str:
    baseline = summary["modes"]["codex_alone"]
    jarvis = summary["modes"]["jarvis_plus_codex"]
    outcomes = summary["win_loss_tie"]
    lines = [
        f"# Benchmark Summary: Codex Alone vs JARVIS + Codex ({run_id})",
        "",
        "> All token numbers are estimates unless manually overridden.",
        "",
        "## Aggregate",
        "",
        "| Metric | Codex Alone | JARVIS + Codex |",
        "|---|---:|---:|",
        f"| Logged runs | {baseline['runs_logged']} | {jarvis['runs_logged']} |",
        f"| Scored runs | {baseline['runs_scored']} | {jarvis['runs_scored']} |",
        f"| Average estimated input tokens | {_display(baseline['average_estimated_input_tokens'])} | {_display(jarvis['average_estimated_input_tokens'])} |",
        f"| Average estimated output tokens | {_display(baseline['average_estimated_output_tokens'])} | {_display(jarvis['average_estimated_output_tokens'])} |",
        f"| Average estimated total tokens | {_display(baseline['average_estimated_total_tokens'])} | {_display(jarvis['average_estimated_total_tokens'])} |",
        f"| Average latency seconds | {_display(baseline['average_latency_seconds'])} | {_display(jarvis['average_latency_seconds'])} |",
        f"| Task success rate | {_display(baseline['task_success_rate'])} | {_display(jarvis['task_success_rate'])} |",
        f"| Correctness (0..5) | {_display(baseline['average_correctness'])} | {_display(jarvis['average_correctness'])} |",
        f"| Evidence quality (0..5) | {_display(baseline['average_evidence_quality'])} | {_display(jarvis['average_evidence_quality'])} |",
        f"| Answer completeness (0..5) | {_display(baseline['average_completeness'])} | {_display(jarvis['average_completeness'])} |",
        f"| Hallucination risk (0..5, lower is better) | {_display(baseline['average_hallucination_risk'])} | {_display(jarvis['average_hallucination_risk'])} |",
        f"| Average quality score | {_display(baseline['average_total_score'])} | {_display(jarvis['average_total_score'])} |",
        "",
        f"- Average estimated token reduction: {_display(summary['average_estimated_token_reduction_percent'], '%')}",
        f"- Average speedup: {_display(summary['average_speedup'], 'x')}",
        f"- Average quality delta: {_display(summary['average_quality_delta_points'], ' points')}",
        f"- Win/loss/tie/incomplete: {outcomes['jarvis_plus_codex']}/{outcomes['codex_alone']}/{outcomes['tie']}/{outcomes['incomplete']}",
        "",
        "## Bug-Finding Accuracy",
        "",
        "| Metric | Codex Alone | JARVIS + Codex |",
        "|---|---:|---:|",
        f"| True positives | {baseline['bug_finding_accuracy']['true_positives']} | {jarvis['bug_finding_accuracy']['true_positives']} |",
        f"| False positives | {baseline['bug_finding_accuracy']['false_positives']} | {jarvis['bug_finding_accuracy']['false_positives']} |",
        f"| False negatives | {baseline['bug_finding_accuracy']['false_negatives']} | {jarvis['bug_finding_accuracy']['false_negatives']} |",
        f"| Precision | {_display(baseline['bug_finding_accuracy']['precision'])} | {_display(jarvis['bug_finding_accuracy']['precision'])} |",
        f"| Recall | {_display(baseline['bug_finding_accuracy']['recall'])} | {_display(jarvis['bug_finding_accuracy']['recall'])} |",
        "",
        "## Per-task Breakdown",
        "",
        "| Task | Winner | Estimated token reduction | Speedup | Quality delta |",
        "|---|---|---:|---:|---:|",
    ]
    for row in summary["per_task"]:
        lines.append(
            f"| {row['task_id']} | {row['winner']} | "
            f"{row.get('estimated_token_reduction_percent', '-')} | "
            f"{row.get('speedup', '-')} | {row.get('quality_delta_points', '-')} |"
        )
    return "\n".join(lines) + "\n"
