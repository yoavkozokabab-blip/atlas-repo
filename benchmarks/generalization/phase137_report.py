"""Phase 137 — semantic generalization completion report generator."""

from __future__ import annotations

import json
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

RESULTS = Path(__file__).resolve().parent / "results"
SEMANTIC = RESULTS / "semantic"
OUT = ROOT / "reports" / "phase137_semantic_generalization.md"

PRIORITY_REPOS = [
    "home_assistant",
    "django",
    "fastapi",
    "vscode",
    "atlas_self",
    "quixbugs",
]

# Baseline impact scores before Phase 137 (from phase notes / prior aggregate).
BASELINE_IMPACT = {
    "fastapi": 23.2,
    "django": 65.1,
    "vscode": 0.0,
    "home_assistant": 100.0,
    "atlas_self": 62.5,
    "quixbugs": 24.6,
}


def _load_bench() -> Dict[str, Dict[str, Any]]:
    out: Dict[str, Dict[str, Any]] = {}
    for p in RESULTS.glob("*.json"):
        if p.name == "aggregate.json":
            continue
        rec = json.loads(p.read_text(encoding="utf-8"))
        out[rec["id"]] = rec
    return out


def _load_semantic() -> List[Dict[str, Any]]:
    if not SEMANTIC.is_dir():
        return []
    return [
        json.loads(p.read_text(encoding="utf-8"))
        for p in sorted(SEMANTIC.glob("*.json"))
        if p.name != "aggregate.json"
    ]


def _concept_matrix(probe: List[Dict[str, Any]], *, only: List[str] | None = None) -> Dict[str, Dict[str, Any]]:
    ok = [r for r in probe if r.get("status") == "ok"]
    if only:
        wanted = set(only)
        ok = [r for r in ok if r.get("id") in wanted]
    if not ok:
        return {}
    concept_ids = [c["concept"] for c in ok[0]["concepts"]]
    n = len(ok)
    matrix: Dict[str, Dict[str, Any]] = {}
    for cid in concept_ids:
        succ, fail = [], []
        categories: Counter = Counter()
        for r in ok:
            entry = next(e for e in r["concepts"] if e["concept"] == cid)
            if entry["resolved"]:
                succ.append(r["display"])
            else:
                fail.append(r["display"])
                categories[entry.get("category") or "unknown"] += 1
        matrix[cid] = {
            "coverage_pct": round(100.0 * len(succ) / n, 1),
            "success_pct": round(100.0 * len(succ) / n, 1),
            "failure_pct": round(100.0 * len(fail) / n, 1),
            "success_repos": succ,
            "failed_repos": fail,
            "resolution_category": dict(categories),
            "why_failed": _failure_reason(cid, fail, categories),
            "improvement": _improvement_opportunity(cid, len(succ), n, categories),
        }
    return matrix


def _failure_reason(concept: str, failed: List[str], categories: Counter) -> str:
    if not failed:
        return "—"
    if categories.get("semantic_routing_failure"):
        return (
            f"Fallback on {categories['semantic_routing_failure']} repo(s) — concept vocabulary or "
            f"path signals did not match `{concept}` in those layouts."
        )
    if categories.get("resolver_failure"):
        return f"Resolver returned empty modules for `{concept}` on {len(failed)} repo(s)."
    return f"No structural anchor for `{concept}` in: {', '.join(failed[:4])}"


def _improvement_opportunity(concept: str, succ: int, total: int, categories: Counter) -> str:
    cov = succ / total if total else 0
    if cov >= 0.9:
        return "Low — already generalizes well."
    if categories.get("semantic_routing_failure"):
        return f"Expand lexicon aliases / platform path priors for `{concept}` (+5–10% coverage)."
    if concept in ("background_jobs", "messaging", "scheduling"):
        return "Medium — add framework-specific worker/queue signatures (+8–12% coverage)."
    return f"Medium — symbol mining + directory clustering for `{concept}` (+6–10% coverage)."


def _leaderboard(bench: Dict[str, Dict[str, Any]]) -> str:
    rows = [bench[r] for r in bench if bench[r].get("status") == "ok"]
    rows.sort(key=lambda r: -r["scores"]["overall"])
    lines = [
        "| Rank | Repository | Understanding | Impact | Investigation | Build | **Overall** |",
        "|---:|---|---:|---:|---:|---:|---:|",
    ]
    for i, r in enumerate(rows, 1):
        s = r["scores"]
        lines.append(
            f"| {i} | {r['display']} | {s['understanding']} | {s['impact']} | "
            f"{s['investigation']} | {s['build']} | **{s['overall']}** |"
        )
    return "\n".join(lines)


def _roadmap(matrix: Dict[str, Dict[str, Any]], bench: Dict[str, Dict[str, Any]]) -> str:
    low = sorted(matrix.items(), key=lambda kv: kv[1]["coverage_pct"])[:8]
    lines = [
        "| Priority | Improvement | Est. impact gain | ROI |",
        "|---:|---|---:|---|",
    ]
    for i, (cid, row) in enumerate(low, 1):
        gain = "High" if row["coverage_pct"] < 50 else "Medium"
        lines.append(f"| {i} | {row['improvement']} | {gain} | Quick lexicon / path priors |")
    lines.append("")
    lines.append("**Cross-repo targets:** lift mean concept coverage toward 85%; keep Home Assistant at 100% impact.")
    return "\n".join(lines)


def generate() -> str:
    bench = _load_bench()
    probe = [r for r in _load_semantic() if r.get("id") in PRIORITY_REPOS]
    matrix = _concept_matrix(probe, only=PRIORITY_REPOS)

    lines = [
        "# Phase 137 — Semantic Generalization Completion",
        "",
        "## Executive summary",
        "",
        "Phase 137 adds a framework-agnostic concept lexicon and generic resolver fallback "
        "(`impact_engine/concept_lexicon.py`, `resolve_generic_concept`) so cross-cutting "
        "concepts resolve from each repository's own structure. Home Assistant curated "
        "mappings are preserved; copilot impact accepts semantic hits outside the import graph.",
        "",
        "## Current scores (priority repositories)",
        "",
        "| Repository | Impact (before → after) | Overall | Status |",
        "|---|---:|---:|---|",
    ]
    for rid in PRIORITY_REPOS:
        rec = bench.get(rid, {})
        s = rec.get("scores", {})
        before = BASELINE_IMPACT.get(rid, "—")
        after = s.get("impact", "—")
        overall = s.get("overall", "—")
        status = rec.get("status", "missing")
        delta = ""
        if isinstance(before, (int, float)) and isinstance(after, (int, float)):
            delta = f" ({'+' if after >= before else ''}{round(after - before, 1)})"
        lines.append(f"| {rec.get('display', rid)} | {before} → **{after}**{delta} | **{overall}** | {status} |")

    lines += [
        "",
        "### Success criteria",
        "",
        "| Criterion | Result |",
        "|---|---|",
    ]
    ha = bench.get("home_assistant", {}).get("scores", {}).get("impact", 0)
    vscode_imp = bench.get("vscode", {}).get("scores", {}).get("impact", 0)
    fastapi_imp = bench.get("fastapi", {}).get("scores", {}).get("impact", 0)
    django_imp = bench.get("django", {}).get("scores", {}).get("impact", 0)
    lines += [
        f"| VS Code impact > 80 | **{'PASS' if vscode_imp > 80 else 'FAIL'}** ({vscode_imp}) |",
        f"| FastAPI impact > 80 | **{'PASS' if fastapi_imp > 80 else 'FAIL'}** ({fastapi_imp}) |",
        f"| Django impact > 90 | **{'PASS' if django_imp > 90 else 'FAIL'}** ({django_imp}) |",
        f"| Home Assistant no regression | **{'PASS' if ha >= 100 else 'FAIL'}** ({ha}) |",
        "",
        "## Leaderboard (all scored repositories)",
        "",
        _leaderboard(bench),
        "",
        "## Semantic probe — 20 concept coverage matrix",
        "",
        "| Concept | Coverage % | Success % | Failure % | Resolution failures |",
        "|---|---:|---:|---:|---|",
    ]
    for cid, row in sorted(matrix.items(), key=lambda kv: -kv[1]["coverage_pct"]):
        cats = ", ".join(f"{k}:{v}" for k, v in row["resolution_category"].items()) or "—"
        lines.append(
            f"| {cid} | {row['coverage_pct']} | {row['success_pct']} | {row['failure_pct']} | {cats} |"
        )

    if matrix:
        mean_cov = round(statistics.mean(r["coverage_pct"] for r in matrix.values()), 1)
        lines.append("")
        lines.append(f"**Mean concept coverage:** {mean_cov}% across probed repositories.")

    lines += [
        "",
        "## Per-concept detail",
        "",
    ]
    for cid, row in sorted(matrix.items(), key=lambda kv: kv[1]["coverage_pct"]):
        lines += [
            f"### {cid}",
            "",
            f"- **Success repos:** {', '.join(row['success_repos']) or '—'}",
            f"- **Failed repos:** {', '.join(row['failed_repos']) or '—'}",
            f"- **Why it failed:** {row['why_failed']}",
            f"- **Improvement opportunity:** {row['improvement']}",
            "",
        ]

    lines += [
        "## Failure taxonomy",
        "",
        "- **semantic_routing_failure** — copilot fallback; concept not matched or no modules returned.",
        "- **resolver_failure** — matched concept but empty module list.",
        "- **Honest miss** — repository genuinely lacks the concept (expected on QuixBugs).",
        "",
        "## Improvement roadmap (ROI-ranked)",
        "",
        _roadmap(matrix, bench),
        "",
        "## Expected gains (next phases)",
        "",
        "| Lever | Expected impact lift |",
        "|---|---:|",
        "| Lexicon alias expansion (authorization, messaging) | +4–8 pts mean impact |",
        "| Platform path priors (prefer `src/vs/platform` over extensions) | +5–10 pts on TS repos |",
        "| Framework adapters (Django/FastAPI/NestJS) | +8–12 pts |",
        "| Cross-repo semantic learning | +10–15 pts long-term |",
        "",
        "## Tests",
        "",
        "```text",
        "py -3 -m pytest jarvis_desktop/tests/test_phase137_semantic_generalization.py -q",
        "py -3 -m pytest jarvis_desktop/tests/test_semantic_target_resolution.py -q",
        "```",
        "",
        "## Confirmation",
        "",
        "- No billing / usage / pricing / admin changes in this phase.",
        "- No Stripe or payment infrastructure touched.",
        "- Semantic generalization only — resolver + copilot impact wiring + benchmarks.",
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(generate(), encoding="utf-8")
    print(f"Wrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
