"""Summarize scored benchmark results."""

from __future__ import annotations

import argparse
import csv
import statistics
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from lib.schema import BENCHMARK_ROOT, CONDITIONS, load_json  # noqa: E402


def _mean(vals: List[float]) -> float | None:
    return round(statistics.mean(vals), 2) if vals else None


def _median(vals: List[float]) -> float | None:
    return round(statistics.median(vals), 2) if vals else None


def cmd_summarize(pilot: bool) -> int:
    revealed = load_json(BENCHMARK_ROOT / "scores" / "revealed_scores.json")
    manifest = load_json(BENCHMARK_ROOT / "runs" / "pilot_manifest.json")

    by_condition: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    by_category: Dict[str, Dict[str, List[float]]] = defaultdict(lambda: defaultdict(list))

    tasks = {item["task_id"]: item for item in load_json(BENCHMARK_ROOT / "runs" / "pilot_manifest.json")["runs"]}

    task_categories = {}
    for task_path in (BENCHMARK_ROOT / "tasks").glob("pilot_*.json"):
        raw = load_json(task_path)
        task_categories[raw["task_id"]] = raw["category"]

    for row in revealed:
        by_condition[row["condition"]].append(row)
        cat = task_categories.get(row["task_id"], "unknown")
        by_category[cat][row["condition"]].append(float(row["total_score"]))

    summary_rows = []
    for condition in CONDITIONS:
        rows = by_condition.get(condition, [])
        totals = [float(r["total_score"]) for r in rows]
        summary_rows.append(
            {
                "condition": condition,
                "run_count": len(rows),
                "mean_total_score": _mean(totals),
                "median_total_score": _median(totals),
                "task_success_rate": _mean([1.0 if r["task_success"] else 0.0 for r in rows]),
                "mean_correctness": _mean([float(r["correctness"]) for r in rows]),
                "mean_citation_accuracy": _mean([float(r["citation_accuracy"]) for r in rows]),
                "mean_hallucination_avoidance": _mean([float(r["hallucination_avoidance"]) for r in rows]),
            }
        )

    # Atlas lift: average with_atlas - no_atlas per agent
    lifts = {}
    for agent in ("codex", "cursor"):
        with_rows = by_condition.get(f"{agent}_with_atlas", [])
        no_rows = by_condition.get(f"{agent}_no_atlas", [])
        with_mean = _mean([float(r["total_score"]) for r in with_rows]) or 0
        no_mean = _mean([float(r["total_score"]) for r in no_rows]) or 0
        lifts[agent] = {
            "with_atlas_mean": with_mean,
            "no_atlas_mean": no_mean,
            "absolute_delta": round(with_mean - no_mean, 2),
            "percent_delta": round(100 * (with_mean - no_mean) / no_mean, 1) if no_mean else None,
        }

    report = {
        "phase": "pilot_v1",
        "execution_backend": manifest.get("execution_backend"),
        "model_tool_version": manifest.get("model_tool_version"),
        "run_count": manifest.get("run_count"),
        "failures": manifest.get("failures", []),
        "by_condition": summary_rows,
        "atlas_lift_by_agent": lifts,
        "by_category": {
            cat: {cond: _mean(scores) for cond, scores in cond_map.items()}
            for cat, cond_map in by_category.items()
        },
        "publishable": False,
        "publishable_blockers": [
            "Live Codex/Cursor agent runs not executed (automated stand-in only)",
            "Sample size n=6 tasks, 1 repeat",
            "Deterministic scorer only; no blind human review",
            "codex_with_atlas and cursor_with_atlas are identical under automated MCP path",
        ],
    }

    dump_path_json = BENCHMARK_ROOT / "reports" / "benchmark_report.json"
    dump_path_json.parent.mkdir(parents=True, exist_ok=True)
    dump_path_json.write_text(
        __import__("json").dumps(report, indent=2) + "\n",
        encoding="utf-8",
    )

    summary_csv = BENCHMARK_ROOT / "scores" / "summary.csv"
    with summary_csv.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(summary_rows[0].keys()))
        writer.writeheader()
        writer.writerows(summary_rows)

    md = _render_pilot_md(report, revealed)
    md_path = BENCHMARK_ROOT / "reports" / "pilot_report.md"
    md_path.write_text(md, encoding="utf-8")

    print(f"Summary -> {summary_csv}")
    print(f"Report -> {md_path}")
    return 0


def _render_pilot_md(report: Dict[str, Any], revealed: List[Dict[str, Any]]) -> str:
    lines = [
        "# Pilot Report — Agent Comparison Benchmark",
        "",
        "## Executive summary",
        "",
        "Pilot harness executed with **automated stand-ins**, not live Codex/Cursor agents.",
        "",
    ]
    for agent, lift in report["atlas_lift_by_agent"].items():
        lines.append(
            f"- **{agent.title()}** (automated): with-Atlas mean {lift['with_atlas_mean']}/30 vs "
            f"no-Atlas {lift['no_atlas_mean']}/30 → delta **{lift['absolute_delta']:+.2f}** "
            f"({lift['percent_delta']}% vs baseline)"
        )
    lines.extend(
        [
            "",
            "## Conditions (pilot)",
            "",
            "| Condition | Runs | Mean score | Median | Success rate |",
            "|---|---:|---:|---:|---:|",
        ]
    )
    for row in report["by_condition"]:
        lines.append(
            f"| {row['condition']} | {row['run_count']} | {row['mean_total_score']} | "
            f"{row['median_total_score']} | {row['task_success_rate']} |"
        )

    lines.extend(["", "## Per-category means", ""])
    for cat, conds in report["by_category"].items():
        parts = ", ".join(f"{c}={v}" for c, v in sorted(conds.items()))
        lines.append(f"- **{cat}**: {parts}")

    # Wins and regressions
    paired = []
    for row in revealed:
        paired.append(row)
    by_task_cond = {}
    for row in revealed:
        by_task_cond[(row["task_id"], row["condition"])] = row

    deltas = []
    for task_id in sorted({r["task_id"] for r in revealed}):
        for agent in ("codex", "cursor"):
            no = by_task_cond.get((task_id, f"{agent}_no_atlas"))
            with_ = by_task_cond.get((task_id, f"{agent}_with_atlas"))
            if no and with_:
                delta = float(with_["total_score"]) - float(no["total_score"])
                deltas.append((delta, task_id, agent, float(no["total_score"]), float(with_["total_score"])))

    deltas.sort(key=lambda x: x[0], reverse=True)
    lines.extend(["", "## Largest Atlas gains (automated pilot)", ""])
    for delta, task_id, agent, no_s, with_s in deltas[:5]:
        lines.append(f"- {task_id} / {agent}: {no_s} → {with_s} (**{delta:+.1f}**)")

    regressions = [d for d in deltas if d[0] < 0]
    regressions.sort(key=lambda x: x[0])
    lines.extend(["", "## Atlas regressions (automated pilot)", ""])
    if regressions:
        for delta, task_id, agent, no_s, with_s in regressions[:5]:
            lines.append(f"- {task_id} / {agent}: {no_s} → {with_s} (**{delta:+.1f}**)")
    else:
        lines.append("- None in pilot automated runs")

    lines.extend(
        [
            "",
            "## Threats to validity",
            "",
            *[f"- {b}" for b in report["publishable_blockers"]],
            "",
            "## Publishable?",
            "",
            f"**No** — pilot only. Blockers listed above.",
            "",
            "## Tool versions",
            "",
            f"`{report.get('model_tool_version')}`",
            "",
            "## Failures",
            "",
        ]
    )
    if report["failures"]:
        for fail in report["failures"]:
            lines.append(f"- {fail['run_id']}: {fail.get('error')}")
    else:
        lines.append("- No technical run failures")

    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pilot", action="store_true")
    args = parser.parse_args()
    return cmd_summarize(args.pilot)


if __name__ == "__main__":
    raise SystemExit(main())
