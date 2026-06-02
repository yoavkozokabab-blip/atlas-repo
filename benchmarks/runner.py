"""Phase 130 — Run Atlas benchmark suite and produce validation report."""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

BENCHMARK_ROOT = Path(__file__).resolve().parent
REPORT_PATH = BENCHMARK_ROOT.parent / "reports" / "phase130_repository_understanding_validation.md"
RESULTS_PATH = BENCHMARK_ROOT / "results" / "latest_run.json"

# Allow importing jarvis_desktop from repo root
sys.path.insert(0, str(BENCHMARK_ROOT.parent))

from benchmarks.evaluator import evaluate_scenario  # noqa: E402
from benchmarks.schema import BenchmarkScenario, ScenarioResult, load_suite  # noqa: E402


def _reset_api_state() -> None:
    from jarvis_desktop import api

    api._STATE.update(
        {
            "path": None,
            "scan": None,
            "graph": None,
            "index": None,
            "risks": None,
            "evidence_store": None,
            "scan_cache": {},
        }
    )


def _run_scenario(scenario: BenchmarkScenario) -> Dict[str, Any]:
    from jarvis_desktop import api

    repo_path = scenario.repo_path()
    if not repo_path.is_dir():
        return {"ok": False, "error": f"Repository not found: {repo_path}"}

    _reset_api_state()
    scan = api.scan_repository(str(repo_path))
    if not scan.get("ok"):
        return {"ok": False, "error": scan.get("error", "scan failed")}

    if scenario.task_type == "build":
        res = api.plan_change(scenario.prompt)
        if not res.get("ok"):
            return {"ok": False, "error": res.get("error", "plan failed")}
        return {"ok": True, "plan": res["plan"]}

    if scenario.task_type == "investigate":
        res = api.investigate_symptom(scenario.prompt)
        if not res.get("ok"):
            return {"ok": False, "error": res.get("error", "investigate failed")}
        return {"ok": True, "plan": res["plan"]}

    if scenario.task_type == "impact":
        target = scenario.impact_target or scenario.prompt
        res = api.change_impact_simulation(target)
        if not res.get("ok"):
            return {"ok": False, "error": res.get("error", "impact failed")}
        plan = dict(res)
        plan.update(res.get("simulation") or {})
        plan["target"] = res.get("target") or target
        return {"ok": True, "plan": plan}

    return {"ok": False, "error": f"Unknown task_type {scenario.task_type}"}


def run_suite(
    *,
    suite_path: Optional[Path] = None,
    scenario_ids: Optional[List[str]] = None,
    include_optional: bool = True,
) -> List[ScenarioResult]:
    scenarios = load_suite(suite_path)
    if scenario_ids:
        wanted = set(scenario_ids)
        scenarios = [s for s in scenarios if s.scenario_id in wanted]

    results: List[ScenarioResult] = []
    for scenario in scenarios:
        if not include_optional and scenario.repository.startswith("FINAL_ALGO"):
            continue
        if scenario.repository.startswith("FINAL_ALGO") and not scenario.repo_path().is_dir():
            if not include_optional:
                continue
            results.append(
                evaluate_scenario(
                    scenario,
                    {},
                    ok=False,
                    error=f"Optional repo missing: {scenario.repository}",
                )
            )
            continue

        started = time.time()
        out = _run_scenario(scenario)
        elapsed = time.time() - started
        if not out.get("ok"):
            results.append(
                evaluate_scenario(scenario, {}, ok=False, error=out.get("error", "failed"))
            )
            continue
        result = evaluate_scenario(scenario, out["plan"])
        result.error = result.error or ""
        results.append(result)
        _ = elapsed
    return results


def _aggregate(results: List[ScenarioResult]) -> Dict[str, Any]:
    ok_results = [r for r in results if r.ok and not r.error]
    by_cat: Dict[str, List[ScenarioResult]] = {}
    for r in results:
        by_cat.setdefault(r.scenario.category, []).append(r)

    def avg_score(items: List[ScenarioResult]) -> float:
        if not items:
            return 0.0
        return round(sum(x.metrics.atlas_score for x in items) / len(items), 1)

    return {
        "total": len(results),
        "executed_ok": len(ok_results),
        "atlas_score_mean": avg_score(ok_results),
        "by_category": {
            cat: {
                "count": len(items),
                "atlas_score_mean": avg_score([x for x in items if x.ok and not x.error]),
                "file_precision_mean": round(
                    sum(x.metrics.file_precision for x in items if x.ok) / max(1, len([x for x in items if x.ok])),
                    3,
                ),
                "file_recall_mean": round(
                    sum(x.metrics.file_recall for x in items if x.ok) / max(1, len([x for x in items if x.ok])),
                    3,
                ),
            }
            for cat, items in by_cat.items()
        },
        "failures": [f.to_dict() for r in results for f in r.failures],
        "evidence_audits": [a.to_dict() for r in results for a in r.evidence_audits],
    }


def render_report(results: List[ScenarioResult], aggregate: Dict[str, Any]) -> str:
    lines = [
        "# Phase 130 — Repository Understanding Validation",
        "",
        f"Generated: {time.strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        "## Executive summary",
        "",
        f"- **Scenarios run:** {aggregate['total']} (reference repo `atlas_reference`, optional external repos excluded)",
        f"- **Executed successfully:** {aggregate['executed_ok']}",
        f"- **Mean Atlas score:** {aggregate['atlas_score_mean']}/100",
        "",
        "## Category breakdown",
        "",
        "| Category | Count | Mean Atlas score | File precision | File recall |",
        "|----------|-------|------------------|----------------|-------------|",
    ]
    for cat, stats in aggregate.get("by_category", {}).items():
        lines.append(
            f"| {cat} | {stats['count']} | {stats['atlas_score_mean']} | "
            f"{stats['file_precision_mean']} | {stats['file_recall_mean']} |"
        )

    lines.extend(
        [
            "",
            "## Score dimensions (averages over successful runs)",
            "",
        ]
    )
    ok = [r for r in results if r.ok and not r.error]
    if ok:
        dims = [
            ("Repository Understanding", "repository_understanding"),
            ("Knowledge Understanding", "knowledge_understanding"),
            ("Evidence Quality", "evidence_quality"),
            ("Investigation Quality", "investigation_quality"),
            ("Impact Analysis Quality", "impact_analysis_quality"),
        ]
        for label, attr in dims:
            val = round(sum(getattr(r.metrics, attr) for r in ok) / len(ok), 1)
            lines.append(f"- **{label}:** {val}/100")

    lines.extend(["", "## Sample scenario results", ""])
    for r in ok[:8]:
        s = r.scenario
        lines.extend(
            [
                f"### {s.scenario_id} — `{s.repository}`",
                "",
                f"**Prompt:** {s.prompt}",
                "",
                f"**Atlas score:** {r.metrics.atlas_score}/100",
                f"**File precision / recall:** {r.metrics.file_precision:.2f} / {r.metrics.file_recall:.2f}",
                f"**Insertion correct:** {'Yes' if r.metrics.insertion_point_correct else 'No'}",
                f"**Concept:** {r.actual_concept_id} (expected `{s.expected_concept_id or 'any'}`)",
                "",
            ]
        )

    audits = aggregate.get("evidence_audits") or []
    if audits:
        lines.extend(["## Repository evidence audit", ""])
        for a in audits[:15]:
            lines.append(f"- `{a['scenario_id']}` — **{a['audit_type']}**: {a['detail']}")
        lines.append("")

    failures = aggregate.get("failures") or []
    if failures:
        lines.extend(["## Failure analysis (sample)", ""])
        for f in failures[:12]:
            lines.extend(
                [
                    f"### {f['scenario_id']}",
                    f"- **Why:** {f['reason']}",
                    f"- **Evidence used:** {', '.join(f.get('evidence_used') or [])[:4] or 'n/a'}",
                    f"- **Expected:** {', '.join(f.get('expected_evidence') or [])[:4] or 'n/a'}",
                    f"- **Missing:** {', '.join(f.get('missing_evidence') or [])[:4] or 'n/a'}",
                    "",
                ]
            )

    lines.extend(
        [
            "## Competitive evaluation (manual)",
            "",
            "Use `benchmarks/competitive/manual_comparison_template.md` to score Atlas vs Claude Code vs Cursor.",
            "No API integration — paste assistant outputs and score file recall, insertion, and evidence quality manually.",
            "",
            "## Driving future phases",
            "",
            "Prioritize fixes for categories with lowest mean Atlas score and repeated failure reasons above.",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    results = run_suite(include_optional=False)
    aggregate = _aggregate(results)
    RESULTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    RESULTS_PATH.write_text(
        json.dumps(
            {"aggregate": aggregate, "results": [r.to_dict() for r in results]},
            indent=2,
        ),
        encoding="utf-8",
    )
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(render_report(results, aggregate), encoding="utf-8")
    print(f"Ran {len(results)} scenarios — mean Atlas score {aggregate['atlas_score_mean']}/100")
    print(f"Report: {REPORT_PATH}")
    print(f"JSON: {RESULTS_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
