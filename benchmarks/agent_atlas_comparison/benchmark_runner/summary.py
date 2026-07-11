"""Summarize completed benchmark runs."""

from __future__ import annotations

import csv
import json
from collections import defaultdict
from pathlib import Path
from statistics import mean, median
from typing import Any

from .io import read_json
from .models import CONDITIONS
from .paths import REPORTS_DIR, RUNS_DIR, SCORES_DIR


def iter_run_paths(root: Path = RUNS_DIR) -> list[Path]:
    return sorted(path for path in root.glob("*/*.json") if path.is_file())


def score_for(record: dict[str, Any]) -> dict[str, Any] | None:
    scores = record.get("scores") or {}
    return scores.get("manual") or scores.get("heuristic_v1")


def metric_value(record: dict[str, Any], key: str) -> Any:
    observations = record.get("observations") or {}
    if key == "latency_ms":
        return observations.get("latency_ms")
    if key == "tool_calls":
        return len(observations.get("tool_calls") or [])
    if key == "atlas_calls":
        return len(observations.get("atlas_calls") or [])
    if key == "files_opened":
        return len(observations.get("files_opened") or [])
    if key == "total_tokens":
        return ((observations.get("token_usage") or {}).get("total_tokens") or {}).get("value")
    if key == "output_tokens":
        return ((observations.get("token_usage") or {}).get("output_tokens") or {}).get("value")
    return None


def avg(values: list[float]) -> float | None:
    return round(mean(values), 3) if values else None


def med(values: list[float]) -> float | None:
    return round(median(values), 3) if values else None


def summarize_records(records: list[dict[str, Any]]) -> dict[str, Any]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    by_repo: dict[str, list[dict[str, Any]]] = defaultdict(list)
    by_cat: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        groups[record.get("condition", "")].append(record)
        by_repo[record.get("repository_id", "")].append(record)
        by_cat[record.get("category", "")].append(record)

    def summarize_group(items: list[dict[str, Any]]) -> dict[str, Any]:
        completed = [r for r in items if r.get("status") == "completed"]
        scored = [(r, score_for(r)) for r in completed if score_for(r)]
        scores = [float(s["accuracy_percent"]) for _, s in scored]
        pass_count = sum(1 for _, s in scored if s.get("strict_success"))
        latencies = [float(v) for r in completed if (v := metric_value(r, "latency_ms")) is not None]
        tokens = [float(v) for r in completed if (v := metric_value(r, "total_tokens")) is not None]
        tool_calls = [float(metric_value(r, "tool_calls") or 0) for r in completed]
        files_opened = [float(metric_value(r, "files_opened") or 0) for r in completed]
        failures = [r for r in items if r.get("status") == "technical_failure"]
        return {
            "runs": len(items),
            "completed_runs": len(completed),
            "scored_runs": len(scored),
            "technical_failures": len(failures),
            "mean_accuracy_percent": avg(scores),
            "median_accuracy_percent": med(scores),
            "pass_rate_percent": round((pass_count / len(scored)) * 100.0, 3) if scored else None,
            "mean_latency_ms": avg(latencies),
            "median_latency_ms": med(latencies),
            "mean_total_tokens": avg(tokens),
            "median_total_tokens": med(tokens),
            "mean_tool_calls": avg(tool_calls),
            "mean_files_opened": avg(files_opened),
        }

    by_condition = {condition: summarize_group(groups.get(condition, [])) for condition in CONDITIONS}
    return {
        "overall": summarize_group(records),
        "by_condition": by_condition,
        "by_repository": {key: summarize_group(value) for key, value in sorted(by_repo.items())},
        "by_category": {key: summarize_group(value) for key, value in sorted(by_cat.items())},
        "atlas_impact": classify_atlas_impact(records),
    }


def paired(records: list[dict[str, Any]]) -> dict[tuple[str, str, str], dict[str, dict[str, Any]]]:
    out: dict[tuple[str, str, str], dict[str, dict[str, Any]]] = defaultdict(dict)
    for record in records:
        if record.get("status") != "completed":
            continue
        key = (record.get("runner", {}).get("agent", ""), record.get("task_id", ""), str(record.get("run_set_id") or ""))
        out[key][record.get("condition", "")] = record
    return out


def classify_atlas_impact(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    impacts: list[dict[str, Any]] = []
    for (agent, task_id, run_set_id), item in paired(records).items():
        no_key = f"{agent}_no_atlas"
        with_key = f"{agent}_with_atlas"
        if no_key not in item or with_key not in item:
            continue
        base = score_for(item[no_key])
        atlas = score_for(item[with_key])
        if not base or not atlas:
            continue
        accuracy_delta = float(atlas["accuracy_percent"]) - float(base["accuracy_percent"])
        base_latency = metric_value(item[no_key], "latency_ms")
        atlas_latency = metric_value(item[with_key], "latency_ms")
        latency_delta_percent = None
        if base_latency and atlas_latency:
            latency_delta_percent = ((float(atlas_latency) - float(base_latency)) / float(base_latency)) * 100.0
        label = "No meaningful difference"
        if accuracy_delta >= 15:
            label = "Strong win"
        elif accuracy_delta >= 5:
            label = "Moderate win"
        elif accuracy_delta <= -15:
            label = "Strong regression"
        elif accuracy_delta <= -5:
            label = "Moderate regression"
        elif abs(accuracy_delta) < 5 and latency_delta_percent is not None:
            if latency_delta_percent <= -30:
                label = "Moderate win"
            elif latency_delta_percent >= 30:
                label = "Moderate regression"
        impacts.append(
            {
                "agent": agent,
                "task_id": task_id,
                "run_set_id": run_set_id,
                "atlas_result": label,
                "accuracy_delta_points": round(accuracy_delta, 3),
                "latency_delta_percent": round(latency_delta_percent, 3) if latency_delta_percent is not None else None,
            }
        )
    return impacts


def write_csv_summary(summary: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = []
    for condition, stats in summary["by_condition"].items():
        rows.append({"condition": condition, **stats})
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()) if rows else ["condition"])
        writer.writeheader()
        writer.writerows(rows)


def render_markdown(summary: dict[str, Any]) -> str:
    def show(value: Any) -> str:
        return "n/a" if value is None else str(value)

    lines = [
        "# Agent/Atlas Benchmark Summary",
        "",
        "## Executive Summary",
        "",
    ]
    overall = summary["overall"]
    if overall["completed_runs"] < 24:
        lines.append(
            f"Only {overall['completed_runs']} completed runs are available. "
            "Do not make a performance conclusion before 24 valid completed pilot runs."
        )
    else:
        lines.append(f"Completed runs: {overall['completed_runs']}; scored runs: {overall['scored_runs']}.")
    lines.extend(
        [
            "",
            "## Accuracy Comparison",
            "",
            "| Condition | Completed | Scored | Mean accuracy % | Median accuracy % | Pass rate % |",
            "|-----------|-----------|--------|-----------------|-------------------|-------------|",
        ]
    )
    for condition, stats in summary["by_condition"].items():
        lines.append(
            f"| {condition} | {stats['completed_runs']} | {stats['scored_runs']} | "
            f"{show(stats['mean_accuracy_percent'])} | {show(stats['median_accuracy_percent'])} | {show(stats['pass_rate_percent'])} |"
        )
    lines.extend(
        [
            "",
            "## Token, Latency, And Tool Calls",
            "",
            "| Condition | Mean tokens | Mean latency ms | Mean tool calls | Mean files opened |",
            "|-----------|-------------|-----------------|-----------------|-------------------|",
        ]
    )
    for condition, stats in summary["by_condition"].items():
        lines.append(
            f"| {condition} | {show(stats['mean_total_tokens'])} | {show(stats['mean_latency_ms'])} | "
            f"{show(stats['mean_tool_calls'])} | {show(stats['mean_files_opened'])} |"
        )
    lines.extend(
        [
            "",
            "## Per-Repository Results",
            "",
            "| Repository | Completed | Mean accuracy % | Mean tokens | Mean latency ms |",
            "|------------|-----------|-----------------|-------------|-----------------|",
        ]
    )
    for repo, stats in summary["by_repository"].items():
        lines.append(
            f"| {repo} | {stats['completed_runs']} | {show(stats['mean_accuracy_percent'])} | "
            f"{show(stats['mean_total_tokens'])} | {show(stats['mean_latency_ms'])} |"
        )
    lines.extend(
        [
            "",
            "## Per-Category Results",
            "",
            "| Category | Completed | Mean accuracy % | Mean tokens | Mean latency ms |",
            "|----------|-----------|-----------------|-------------|-----------------|",
        ]
    )
    for category, stats in summary["by_category"].items():
        lines.append(
            f"| {category} | {stats['completed_runs']} | {show(stats['mean_accuracy_percent'])} | "
            f"{show(stats['mean_total_tokens'])} | {show(stats['mean_latency_ms'])} |"
        )
    lines.extend(
        [
            "",
            "## Atlas Wins And Regressions",
            "",
            "| Agent | Task | Atlas result | Accuracy delta | Latency delta % |",
            "|-------|------|--------------|----------------|-----------------|",
        ]
    )
    if summary["atlas_impact"]:
        for item in summary["atlas_impact"]:
            lines.append(
                f"| {item['agent']} | {item['task_id']} | {item['atlas_result']} | "
                f"{item['accuracy_delta_points']} | {item['latency_delta_percent']} |"
            )
    else:
        lines.append("| n/a | n/a | Not enough paired completed scored runs | n/a | n/a |")
    lines.extend(
        [
            "",
            "## Threats To Validity",
            "",
            "- Manual agent execution can introduce operator timing and session-reset variance.",
            "- Heuristic scores are useful for triage but need human review before publication.",
            "- Token counts may be estimated unless the provider exposes exact usage.",
            "- Atlas cold-start indexing and warm-run retrieval must be reported separately when captured.",
            "- Cursor and Codex results must not be merged.",
            "",
        ]
    )
    return "\n".join(lines)


def summarize_to_files(root: Path = RUNS_DIR) -> dict[str, Any]:
    records = [read_json(path) for path in iter_run_paths(root)]
    summary = summarize_records(records)
    SCORES_DIR.mkdir(parents=True, exist_ok=True)
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    write_csv_summary(summary, SCORES_DIR / "summary.csv")
    (REPORTS_DIR / "benchmark_report.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    (REPORTS_DIR / "benchmark_report.md").write_text(render_markdown(summary), encoding="utf-8")
    return summary
