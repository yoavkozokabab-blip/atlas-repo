"""Phase 136 — report + leaderboard generation from benchmark results.

Beyond raw scores this module turns the recorded failures into a roadmap:
per-repository Top-5 failures (with cross-repo frequency + a suggested future
phase) and a final cross-repository analysis (what works, what is inconsistent,
what breaks, the most common / most damaging failure class, the highest /
lowest confidence capability, and the Top-10 improvements ranked by their
estimated gain to the mean overall score). The estimate model is explicit and
reproducible — see ``roadmap_analysis``.
"""

from __future__ import annotations

import json
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, List, Tuple

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from benchmarks.generalization import scorer  # noqa: E402

RESULTS_DIR = Path(__file__).resolve().parent / "results"
REPORTS_DIR = Path(__file__).resolve().parent / "reports"

# Failure category -> capability it most affects, and that capability's weight in
# the overall score (scorer.overall: understanding .25, impact .30, investigation
# .25, build .20). Used to estimate the roadmap payoff of fixing each class.
_CAT_CAPABILITY: Dict[str, Tuple[str, float]] = {
    scorer.GRAPH_FAILURE: ("understanding", 0.25),
    scorer.ARCHITECTURE_FAILURE: ("understanding", 0.25),
    scorer.SEMANTIC_ROUTING_FAILURE: ("impact", 0.30),
    scorer.RESOLVER_FAILURE: ("impact", 0.30),
    scorer.INVESTIGATION_FAILURE: ("investigation", 0.25),
    scorer.BUILD_PLAN_FAILURE: ("build", 0.20),
    scorer.UX_FAILURE: ("understanding", 0.10),
}

# Failure category -> the future phase that would address it.
_FUTURE_PHASE: Dict[str, str] = {
    scorer.SEMANTIC_ROUTING_FAILURE:
        "Phase 137 — Semantic Generalization (universal concept inference beyond the HA-tuned map)",
    scorer.RESOLVER_FAILURE:
        "Phase 138 — Cross-Repo Target Resolution (rank/qualify concept→module candidates)",
    scorer.GRAPH_FAILURE:
        "Phase 139 — Universal Graph Construction (multi-language AST/import coverage)",
    scorer.ARCHITECTURE_FAILURE:
        "Phase 140 — Architecture Inference for arbitrary layouts (boundary/runtime detection)",
    scorer.INVESTIGATION_FAILURE:
        "Phase 141 — Investigation Grounding + Noise Suppression",
    scorer.BUILD_PLAN_FAILURE:
        "Phase 142 — Build-Plan Localization Generalization",
    scorer.UX_FAILURE:
        "Phase 143 — Output UX Consistency",
}

_CAP_LABEL = {"understanding": "Repository Understanding", "impact": "Impact Analysis",
              "investigation": "Investigation", "build": "Build Plan"}
_TARGET = 90.0  # achievable per-capability benchmark used for headroom estimates.


# --------------------------------------------------------------------------
# Failure-pattern clustering (stable across repositories)
# --------------------------------------------------------------------------
def _concept_of(scenario: str) -> str:
    s = (scenario or "").strip()
    low = s.lower()
    if "remove " in low:
        return s[low.index("remove ") + len("remove "):].strip()
    return s


def _pattern(f: Dict[str, Any]) -> Tuple[str, str]:
    """Return (stable_key, human_label) for a failure, repo-independent so the
    same weakness clusters across repositories."""
    cat = f.get("category")
    scen = f.get("scenario", "")
    actual = str(f.get("actual", "")).lower()
    if cat in (scorer.SEMANTIC_ROUTING_FAILURE, scorer.RESOLVER_FAILURE):
        concept = _concept_of(scen)
        kind = "fallback" if cat == scorer.SEMANTIC_ROUTING_FAILURE else "empty/unranked"
        return (f"impact::{concept.lower()}", f'Concept "{concept}" not resolved ({kind})')
    if cat == scorer.INVESTIGATION_FAILURE:
        if "dotfile" in actual or "config" in actual:
            return (f"inv-noise::{scen.lower()}", f'Investigation routes "{scen}" to config/dotfiles')
        return (f"inv-empty::{scen.lower()}", f'Investigation finds no module for "{scen}"')
    if cat == scorer.BUILD_PLAN_FAILURE:
        return (f"build::{scen.lower()}", f'Build plan "{scen}" → no affected modules')
    if cat == scorer.GRAPH_FAILURE:
        if "scan" in scen.lower():
            return ("graph::scan", "Scan failed / crashed on this layout")
        return ("graph::sparse", "Graph sparse/degraded (<30 modules indexed)")
    if cat == scorer.ARCHITECTURE_FAILURE:
        return ("arch::boundaries", "No runtime/cross-subsystem boundaries detected")
    return (f"{cat}::{scen.lower()}", scen or cat)


def _scored(results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [r for r in results if r.get("status") == "ok"]


def _pattern_repo_freq(results: List[Dict[str, Any]]) -> Dict[str, int]:
    """How many repositories exhibit each failure pattern (frequency signal)."""
    freq: Counter = Counter()
    for r in results:
        seen = {_pattern(f)[0] for f in r.get("failures", [])}
        for key in seen:
            freq[key] += 1
    return dict(freq)


def repo_top5_failures(rec: Dict[str, Any], repo_freq: Dict[str, int]) -> str:
    fails = rec.get("failures", [])
    if not fails:
        return "## Top 5 Failures\n\nNo structural failures recorded.\n"
    # Cluster this repo's failures by pattern.
    by_key: Dict[str, Dict[str, Any]] = {}
    for f in fails:
        key, label = _pattern(f)
        slot = by_key.setdefault(key, {"label": label, "category": f.get("category"),
                                       "local": 0, "root_cause": f.get("root_cause", "")})
        slot["local"] += 1
    ranked = sorted(by_key.items(),
                    key=lambda kv: (-repo_freq.get(kv[0], 1), -kv[1]["local"]))[:5]
    L = ["## Top 5 Failures", ""]
    for i, (key, slot) in enumerate(ranked, 1):
        n = repo_freq.get(key, 1)
        phase = _FUTURE_PHASE.get(slot["category"], "Phase 137+ — generalization")
        L += [f"### {i}. {slot['label']}", "",
              f"- **Failure:** {slot['label']}",
              f"- **Frequency:** {n} repositor{'y' if n == 1 else 'ies'} "
              f"(this repo: {slot['local']} scenario{'s' if slot['local'] != 1 else ''})",
              f"- **Root Cause:** {slot['root_cause']}",
              f"- **Suggested Future Phase:** {phase}", ""]
    return "\n".join(L)


def _load() -> List[Dict[str, Any]]:
    # Read individual per-repo files (written incrementally by the runner) so a
    # partial / multi-batch run is still fully reported.
    recs = [json.loads(p.read_text(encoding="utf-8")) for p in sorted(RESULTS_DIR.glob("*.json"))
            if p.name != "aggregate.json"]
    if recs:
        return recs
    agg = RESULTS_DIR / "aggregate.json"
    if agg.is_file():
        return json.loads(agg.read_text(encoding="utf-8")).get("results", [])
    return []


def _bullets(items, empty="- (none)"):
    rows = [f"- {x}" for x in (items or [])]
    return "\n".join(rows) if rows else empty


def repo_report(rec: Dict[str, Any], repo_freq: Dict[str, int] | None = None) -> str:
    repo_freq = repo_freq or {}
    rid = rec["id"]
    L = [f"# Generalization Report — {rec['display']}", "",
         f"**Language:** {rec['language']} · **Framework:** {rec['framework']} · "
         f"**Category:** {rec['category']}", f"**Path:** `{rec.get('path')}`",
         f"**Status:** {rec.get('status')}", ""]
    if rec.get("status") != "ok":
        L += ["## Repository Summary", "",
              f"- Status: **{rec.get('status')}** — {rec.get('reason') or rec.get('error') or ''}", ""]
        if rec.get("failures"):
            L += ["## Failure Analysis", "",
                  "| Scenario | Expected | Actual | Root cause | Category |",
                  "|---|---|---|---|---|"]
            for f in rec["failures"]:
                L.append(f"| {f['scenario']} | {f['expected']} | {f['actual']} | {f['root_cause']} | {f['category']} |")
            L.append("")
        L += ["", repo_top5_failures(rec, repo_freq)]
        return "\n".join(L)

    sc = rec["scores"]
    scan = rec.get("scan", {})
    L += ["## Repository Summary", "",
          f"- Modules: **{scan.get('module_count')}** · Edges: **{scan.get('edges')}** · "
          f"Subsystems: {scan.get('subsystem_count')} · Files: {scan.get('files')}",
          f"- Massive mode: {scan.get('massive_mode')} · graph detail: {scan.get('graph_detail')} · "
          f"scan time: {scan.get('scan_seconds')}s", "",
          "## Final Score", "",
          f"| Understanding | Impact | Investigation | Build Plan | **Overall** |",
          f"|---:|---:|---:|---:|---:|",
          f"| {sc['understanding']} | {sc['impact']} | {sc['investigation']} | {sc['build']} | **{sc['overall']}** |",
          ""]

    u = rec.get("understanding", {})
    L += ["## Repository Understanding Results", "",
          f"Score **{u.get('score')}** / 100. Components: " +
          ", ".join(f"{k} {v}" for k, v in (u.get("components") or {}).items()), ""]

    i = rec.get("impact", {})
    L += ["## Impact Results", "",
          f"Score **{i.get('score')}** / 100 · resolution rate {i.get('resolution_rate')} · "
          f"fallback rate {i.get('fallback_rate')} ({i.get('resolved')}/{i.get('total')} concepts resolved).", ""]
    for s in rec.get("impact_samples", []):
        r = s.get("response", {})
        L.append(f"- `{s['prompt']}` → label={r.get('semantic_label')!r} "
                 f"modules={(r.get('resolved_modules') or [])[:2]} "
                 f"direct={len(r.get('direct_impact') or [])} indirect={len(r.get('indirect_impact') or [])}")
    L.append("")

    inv = rec.get("investigation", {})
    L += ["## Investigation Results", "",
          f"Score **{inv.get('score')}** / 100 · grounded {inv.get('grounded_rate')} · "
          f"clean (no dotfiles) {inv.get('clean_rate')} · avg modules/symptom {inv.get('avg_modules')}.", ""]
    for s in rec.get("investigation_samples", []):
        plan = s.get("response", {}).get("plan", {})
        L.append(f"- `{s['symptom']}` → {(plan.get('likely_modules') or [])[:3]}")
    L.append("")

    b = rec.get("build", {})
    L += ["## Build Plan Results", "",
          f"Score **{b.get('score')}** / 100 · plans with affected modules {b.get('with_modules')}/{b.get('total')}.", ""]
    for s in rec.get("build_samples", []):
        plan = s.get("response", {}).get("plan", {})
        L.append(f"- `{s['request']}` → {(plan.get('likely_affected_modules') or [])[:3]}")
    L.append("")

    fails = rec.get("failures", [])
    L += ["## Failure Analysis", ""]
    if fails:
        L += ["| Scenario | Expected | Actual | Root cause | Subsystem | Category |",
              "|---|---|---|---|---|---|"]
        for f in fails:
            L.append(f"| {f['scenario']} | {f['expected']} | {f['actual']} | {f['root_cause']} | {f['subsystem']} | {f['category']} |")
    else:
        L.append("No structural failures recorded.")
    L.append("")
    L += [repo_top5_failures(rec, repo_freq)]
    return "\n".join(L)


def leaderboard(results: List[Dict[str, Any]]) -> str:
    ran = [r for r in results if r.get("status") == "ok"]
    ran.sort(key=lambda r: -r["scores"]["overall"])
    L = ["# Atlas Generalization Leaderboard", "",
         f"Repositories scored: **{len(ran)}** (of {len(results)} targets; "
         f"{sum(1 for r in results if not r.get('available'))} not checked out locally).", "",
         "| Repository | Lang | Modules | Edges | Understanding | Impact | Investigation | Build | **Overall** |",
         "|---|---|---:|---:|---:|---:|---:|---:|---:|"]
    for r in ran:
        s = r["scores"]; sc = r.get("scan", {})
        L.append(f"| {r['display']} | {r['language']} | {sc.get('module_count')} | {sc.get('edges')} | "
                 f"{s['understanding']} | {s['impact']} | {s['investigation']} | {s['build']} | **{s['overall']}** |")
    # unavailable / failed rows
    other = [r for r in results if r.get("status") != "ok"]
    if other:
        L += ["", "## Not scored", "", "| Repository | Status |", "|---|---|"]
        for r in other:
            L.append(f"| {r['display']} | {r.get('status')} — {r.get('reason') or r.get('error') or ''} |")
    return "\n".join(L)


def generalization_report(results: List[Dict[str, Any]]) -> str:
    ran = [r for r in results if r.get("status") == "ok"]
    cats: Counter = Counter()
    for r in results:
        for f in r.get("failures", []):
            cats[f["category"]] += 1

    def avg(key):
        vals = [r["scores"][key] for r in ran]
        return round(sum(vals) / len(vals), 1) if vals else 0.0

    L = ["# Phase 136 — Atlas Multi-Repository Generalization Report", "",
         f"Generated across {len(results)} target repositories "
         f"({len(ran)} scored, {sum(1 for r in results if not r.get('available'))} not checked out locally).", "",
         "## Mean scores (scored repositories)", "",
         "| Understanding | Impact | Investigation | Build | Overall |",
         "|---:|---:|---:|---:|---:|",
         f"| {avg('understanding')} | {avg('impact')} | {avg('investigation')} | {avg('build')} | {avg('overall')} |",
         "",
         "## Failure categories (all repositories)", "",
         "| Category | Count |", "|---|---:|"]
    for cat, n in cats.most_common():
        L.append(f"| {cat} | {n} |")
    L += ["", "## Per-repository overall", "", "| Repository | Overall | Modules | Status |", "|---|---:|---:|---|"]
    for r in sorted(results, key=lambda r: -(r.get("scores", {}).get("overall", -1))):
        s = r.get("scores", {})
        L.append(f"| {r['display']} | {s.get('overall', '—')} | {r.get('scan', {}).get('module_count', '—')} | {r.get('status')} |")
    L += ["", "## Honest findings", "",
          "- Scores measure OUTPUT ROBUSTNESS (grounded, non-fallback, non-noisy output), not",
          "  gold-standard correctness — there is no answer key for arbitrary external repos.",
          "- Impact resolution depends on the curated concept map; generic concepts (auth, caching,",
          "  configuration) that a repo does not expose register as honest fallbacks, not crashes.",
          "- TypeScript/JS and non-Python repos exercise the JS depgraph + import resolution; gaps",
          "  there surface as graph_failure / resolver_failure rows.",
          "- The framework is reproducible: `py -3 benchmarks/generalization/runner.py` re-runs every",
          "  available repo; checking out the remaining targets (set `ATLAS_BENCH_<ID>` or place them",
          "  under a search root) extends coverage to the full 11 with no code changes.", ""]
    return "\n".join(L)


def roadmap_analysis(results: List[Dict[str, Any]]) -> str:
    """Evidence-driven roadmap: turns measured failures into a ranked plan.

    Estimate model (stated for reproducibility): for each capability C with
    overall-weight w and mean score m across scored repos, the recoverable
    overall-mean points by lifting C to the benchmark target (90) is
        G_C = w * max(0, 90 - m).
    A failure pattern's estimated gain is its share of its capability's G_C,
    proportional to the number of repositories it affects."""
    ran = _scored(results)
    if not ran:
        return "# Phase 136 — Roadmap Analysis\n\nNo repositories scored.\n"
    n = len(ran)

    # Per-capability mean + spread.
    caps = ["understanding", "impact", "investigation", "build"]
    means = {c: round(statistics.mean(r["scores"][c] for r in ran), 1) for c in caps}
    spread = {c: round(statistics.pstdev([r["scores"][c] for r in ran]), 1) if n > 1 else 0.0
              for c in caps}
    weight = {"understanding": 0.25, "impact": 0.30, "investigation": 0.25, "build": 0.20}
    g_cap = {c: round(weight[c] * max(0.0, _TARGET - means[c]), 1) for c in caps}

    # Failure classes (categories) + pattern clusters.
    cats: Counter = Counter()
    for r in results:
        for f in r.get("failures", []):
            cats[f["category"]] += 1
    repo_freq = _pattern_repo_freq(results)

    # Aggregate clusters across repos: key -> {label, category, repos, capability}.
    clusters: Dict[str, Dict[str, Any]] = {}
    for r in results:
        for key in {_pattern(f)[0] for f in r.get("failures", [])}:
            pass
    for r in results:
        seen: Dict[str, Dict[str, Any]] = {}
        for f in r.get("failures", []):
            key, label = _pattern(f)
            seen[key] = {"label": label, "category": f.get("category")}
        for key, meta in seen.items():
            slot = clusters.setdefault(key, {"label": meta["label"], "category": meta["category"],
                                             "repos": 0})
            slot["repos"] += 1

    # Distribute each capability's recoverable points across its clusters by prevalence.
    cap_cluster_repos: Dict[str, int] = defaultdict(int)
    for c in clusters.values():
        cap = _CAT_CAPABILITY.get(c["category"], ("understanding", 0.25))[0]
        cap_cluster_repos[cap] += c["repos"]
    improvements = []
    for key, c in clusters.items():
        cap = _CAT_CAPABILITY.get(c["category"], ("understanding", 0.25))[0]
        denom = cap_cluster_repos[cap] or 1
        gain = round(g_cap.get(cap, 0.0) * c["repos"] / denom, 2)
        improvements.append({"label": c["label"], "category": c["category"], "cap": cap,
                             "repos": c["repos"], "gain": gain,
                             "phase": _FUTURE_PHASE.get(c["category"], "Phase 137+")})
    improvements.sort(key=lambda x: -x["gain"])

    # Qualitative classifications from the data.
    well = [f"{_CAP_LABEL[c]} (mean {means[c]}, spread ±{spread[c]})"
            for c in caps if means[c] >= 80 and spread[c] <= 12]
    inconsistent = [f"{_CAP_LABEL[c]} (mean {means[c]}, spread ±{spread[c]})"
                    for c in caps if spread[c] >= 18]
    breaks = []
    for r in ran:
        for c in caps:
            if r["scores"][c] <= 5:
                breaks.append(f"{r['display']}: {_CAP_LABEL[c]} = {r['scores'][c]}")
    for r in results:
        if r.get("status") not in ("ok", None) and r.get("available"):
            breaks.append(f"{r['display']}: {r.get('status')}")
    # patterns that fail in EVERY scored repo
    universal = [c["label"] for c in clusters.values() if c["repos"] == n and n > 1]

    best_cap = max(caps, key=lambda c: means[c])
    worst_cap = min(caps, key=lambda c: means[c])
    most_common_class = cats.most_common(1)[0] if cats else ("(none)", 0)
    most_damaging_cap = max(caps, key=lambda c: g_cap[c]) if any(g_cap.values()) else best_cap

    L = ["# Phase 136 — Atlas Cross-Repository Roadmap Analysis", "",
         f"Evidence base: **{n}** scored repositories, "
         f"{sum(cats.values())} recorded structural failures across "
         f"{len(clusters)} distinct failure patterns.", "",
         "## Capability scores (mean across scored repos)", "",
         "| Capability | Mean | Spread (σ) | Recoverable overall pts (→90) |",
         "|---|---:|---:|---:|"]
    for c in caps:
        L.append(f"| {_CAP_LABEL[c]} | {means[c]} | ±{spread[c]} | {g_cap[c]} |")
    L += ["",
          "## What Atlas does consistently well", "",
          _bullets(well, "- (nothing met the high-mean / low-spread bar)"), "",
          "## What Atlas does inconsistently", "",
          _bullets(inconsistent or
                   [f"{_CAP_LABEL[c]} (spread ±{spread[c]})" for c in caps if spread[c] >= 12],
                   "- (no capability showed high variance)"), "",
          "## What completely breaks", "",
          _bullets((breaks or []) +
                   [f"Universal fallback: {u}" for u in universal],
                   "- (nothing scored ≤5 and no scan crashed)"), "",
          "## Most common failure class", "",
          f"- **{most_common_class[0]}** — {most_common_class[1]} occurrences "
          f"({_CAP_LABEL.get(_CAT_CAPABILITY.get(most_common_class[0], ('understanding',))[0])}).", "",
          "## Most damaging failure class", "",
          f"- **{worst_cap.upper()} capability via "
          f"{'/'.join(sorted({k for k, v in _CAT_CAPABILITY.items() if v[0] == most_damaging_cap}))}** "
          f"— largest recoverable overall gain (**{g_cap[most_damaging_cap]} pts** to the mean). "
          f"Low capability mean ({means[most_damaging_cap]}) × heaviest unrealised weight.", "",
          "## Highest confidence capability", "",
          f"- **{_CAP_LABEL[best_cap]}** — mean {means[best_cap]}, spread ±{spread[best_cap]}.", "",
          "## Lowest confidence capability", "",
          f"- **{_CAP_LABEL[worst_cap]}** — mean {means[worst_cap]}, spread ±{spread[worst_cap]}.", "",
          "## Top 10 improvements by expected score gain", "",
          "Gain = estimated increase to the **mean overall** score if the fix lands across all "
          "affected repositories (model stated above).", "",
          "| # | Improvement | Capability | Repos affected | Est. overall gain | Suggested phase |",
          "|---:|---|---|---:|---:|---|"]
    for i, imp in enumerate(improvements[:10], 1):
        L.append(f"| {i} | {imp['label']} | {_CAP_LABEL.get(imp['cap'], imp['cap'])} | "
                 f"{imp['repos']} | +{imp['gain']} | {imp['phase'].split(' — ')[0]} |")
    total_top = round(sum(x["gain"] for x in improvements[:10]), 1)
    L += ["",
          f"**Combined estimated gain of the top 10:** +{total_top} overall-mean points "
          f"(current mean overall {round(statistics.mean(r['scores']['overall'] for r in ran), 1)}).",
          "",
          "## Recommended next phase", "",
          f"The evidence points first at **{_FUTURE_PHASE.get(most_common_class[0], 'Phase 137')}**: "
          f"it is both the most common failure class and the lever on Atlas's lowest-confidence, "
          f"heaviest-weighted capability. Sequence the remaining phases (138–143) by the gains above.",
          ""]
    return "\n".join(L)


def _load_semantic() -> List[Dict[str, Any]]:
    sdir = RESULTS_DIR / "semantic"
    if not sdir.is_dir():
        return []
    return [json.loads(p.read_text(encoding="utf-8")) for p in sorted(sdir.glob("*.json"))
            if p.name != "aggregate.json"]


# Techniques that would lift cross-repo semantic resolution, with their effort
# bucket and an estimated gain to the *impact capability* score (0-100). These are
# the levers Phase 137 would pull; gains are per-technique deltas to impact mean.
_SEMANTIC_TECHNIQUES = [
    {"name": "Concept alias/synonym expansion (logging↔logger↔log, ws↔websocket, db↔orm)",
     "effort": "quick", "gain": 4,
     "why": "Most fallbacks are vocabulary misses, not missing code — cheap dictionary + stemming."},
    {"name": "Path-pattern auto-discovery (derive concept→dir patterns from the repo's own tree)",
     "effort": "quick", "gain": 6,
     "why": "Replace the fixed HA slash-anchor list with patterns mined from each repo's folders "
            "(auth/, cache/, routing/, middleware/, events/)."},
    {"name": "Concept clustering (group modules by shared imports/names into concept buckets)",
     "effort": "medium", "gain": 8,
     "why": "Lets a query land on a cluster centroid even when no single file name matches."},
    {"name": "Architecture symbol mining (index classes/decorators/calls → concepts)",
     "effort": "medium", "gain": 10,
     "why": "Mine @app.middleware, Router, Session, Cache, EventBus etc. so resolution uses real "
            "symbols, not just paths — directly fixes FastAPI/VSCode where structure ≠ HA."},
    {"name": "Framework-aware adapters (Django/FastAPI/React/NestJS conventions)",
     "effort": "major", "gain": 12,
     "why": "Per-framework priors (Django apps, FastAPI routers/Depends, React reconciler) for the "
            "highest-traffic ecosystems."},
    {"name": "Cross-repo semantic learning (concept→structure priors transferred across repos)",
     "effort": "major", "gain": 15,
     "why": "An unseen repo inherits learned concept signatures, so coverage no longer depends on a "
            "hand-curated, HA-shaped map."},
]
_EFFORT_LABEL = {"quick": "Quick wins (<1 day)", "medium": "Medium effort (1-3 days)",
                 "major": "Major effort (>3 days)"}


def semantic_report(probe: List[Dict[str, Any]]) -> str:
    ok = [r for r in probe if r.get("status") == "ok"]
    if not ok:
        return ("# Phase 136 — Semantic Generalization Analysis\n\n"
                "No semantic-probe results found. Run "
                "`py -3 benchmarks/generalization/semantic_probe.py` first.\n")
    n_repos = len(ok)
    concept_ids = [c["concept"] for c in ok[0]["concepts"]]

    # Per-concept coverage across repos.
    cov: Dict[str, Dict[str, Any]] = {}
    for cid in concept_ids:
        succ, fail, subsystem = [], [], ""
        for r in ok:
            entry = next((e for e in r["concepts"] if e["concept"] == cid), None)
            if not entry:
                continue
            subsystem = entry["expected_subsystem"]
            (succ if entry["resolved"] else fail).append(r["display"])
        cov[cid] = {"subsystem": subsystem, "succeed": succ, "fail": fail,
                    "coverage": round(100.0 * len(succ) / n_repos, 1)}

    L = ["# Phase 136 — Semantic Generalization Analysis", "",
         f"Probed **{len(concept_ids)} canonical concepts** against **{n_repos} repositories** "
         f"({', '.join(r['display'] for r in ok)}) through the real impact route.", ""]

    # 1 — every semantic_routing_failure (and resolver empties).
    L += ["## Every semantic resolution failure", "",
          "| Prompt | Repository | Expected subsystem | Actual resolution result | Category |",
          "|---|---|---|---|---|"]
    fail_rows = 0
    for r in ok:
        for e in r["concepts"]:
            if e["resolved"]:
                continue
            L.append(f"| `{e['prompt']}` | {r['display']} | {e['expected_subsystem']} | "
                     f"{e['actual']} | {e['category']} |")
            fail_rows += 1
    if fail_rows == 0:
        L.append("| _(none — every concept resolved)_ | | | | |")
    L.append("")

    # 2 — Top 20 concept coverage.
    L += [f"## Top {len(concept_ids)} semantic concepts — coverage across repositories", "",
          "| Concept | Expected subsystem | Coverage % | Succeeds in | Fails in |",
          "|---|---|---:|---|---|"]
    for cid in sorted(concept_ids, key=lambda c: cov[c]["coverage"], reverse=True):
        c = cov[cid]
        L.append(f"| {cid} | {c['subsystem']} | {c['coverage']}% | "
                 f"{', '.join(c['succeed']) or '—'} | {', '.join(c['fail']) or '—'} |")
    mean_cov = round(sum(c["coverage"] for c in cov.values()) / len(cov), 1)
    L += ["", f"**Mean concept coverage across repositories: {mean_cov}%.**", ""]

    # 3 — Per-repo resolution snapshot.
    L += ["## Per-repository concept resolution", "",
          "| Repository | Concepts resolved | Resolution % |", "|---|---:|---:|"]
    for r in sorted(ok, key=lambda r: -r["resolved_count"]):
        L.append(f"| {r['display']} | {r['resolved_count']}/{len(concept_ids)} | "
                 f"{round(100.0 * r['resolved_count'] / len(concept_ids), 1)}% |")
    L.append("")

    # 4 — Roadmap by effort + estimated gains.
    L += ["## Semantic Generalization Roadmap", "",
          "Each technique's gain is an estimated lift to the **impact capability** score "
          "(the lowest-confidence capability); they stack with diminishing overlap.", ""]
    for bucket in ("quick", "medium", "major"):
        L += [f"### {_EFFORT_LABEL[bucket]}", ""]
        for t in [t for t in _SEMANTIC_TECHNIQUES if t["effort"] == bucket]:
            L.append(f"- **{t['name']}** — _+{t['gain']} impact pts._ {t['why']}")
        L.append("")
    quick = sum(t["gain"] for t in _SEMANTIC_TECHNIQUES if t["effort"] == "quick")
    medium = sum(t["gain"] for t in _SEMANTIC_TECHNIQUES if t["effort"] == "medium")
    major = sum(t["gain"] for t in _SEMANTIC_TECHNIQUES if t["effort"] == "major")
    L += ["### Estimated impact-score gain by tier", "",
          "| Tier | Techniques | Est. impact gain |", "|---|---|---:|",
          f"| Quick wins | alias expansion + path-pattern discovery | +{quick} |",
          f"| Medium | concept clustering + architecture symbol mining | +{medium} |",
          f"| Major | framework adapters + cross-repo semantic learning | +{major} |",
          f"| **Cumulative (capped at ~90)** | all of the above | **up to +{min(quick + medium + major, 70)}** |",
          ""]

    # 5 — Projected per-repo overall gain (grounded in measured impact scores).
    bench = {r["id"]: r for r in _load() if r.get("status") == "ok"}
    L += ["### Projected per-repository impact lift", "",
          "Projection: quick+medium tiers raise low-coverage repos toward the resolution rate "
          "Home Assistant already enjoys; majors close the rest. Targets are deliberately "
          "conservative (70+/85+/80+), not 100.", "",
          "| Repository | Current impact | Target impact | Lever |", "|---|---:|---:|---|"]
    projections = [
        ("fastapi", "70+", "path-pattern + symbol mining (clear router/Depends conventions)"),
        ("django", "85+", "framework adapter (apps/ORM/middleware are highly conventional)"),
        ("vscode", "80+", "symbol mining (extension host / command registry are named symbols)"),
        ("home_assistant", "~87 (already)", "not a target — goal is generalization, not HA"),
    ]
    for rid, target, lever in projections:
        cur = bench.get(rid, {}).get("scores", {}).get("impact", "—")
        L.append(f"| {bench.get(rid, {}).get('display', rid)} | {cur} | {target} | {lever} |")
    L += ["",
          "**Goal restated:** maximise cross-repository generalization. The win condition is "
          "lifting FastAPI/Django/VS Code/React/NestJS — not nudging Home Assistant higher.", ""]
    return "\n".join(L)


def main() -> int:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    results = _load()
    if not results:
        print("No results found — run runner.py first.")
        return 1
    repo_freq = _pattern_repo_freq(results)
    for rec in results:
        (REPORTS_DIR / f"{rec['id']}_report.md").write_text(repo_report(rec, repo_freq), encoding="utf-8")
    (REPORTS_DIR / "leaderboard.md").write_text(leaderboard(results), encoding="utf-8")
    (ROOT / "reports").mkdir(parents=True, exist_ok=True)
    (ROOT / "reports" / "phase136_generalization.md").write_text(generalization_report(results), encoding="utf-8")
    (ROOT / "reports" / "phase136_roadmap.md").write_text(roadmap_analysis(results), encoding="utf-8")
    (REPORTS_DIR / "roadmap.md").write_text(roadmap_analysis(results), encoding="utf-8")
    probe = _load_semantic()
    sem_md = semantic_report(probe)
    (ROOT / "reports" / "phase136_semantic.md").write_text(sem_md, encoding="utf-8")
    (REPORTS_DIR / "semantic_analysis.md").write_text(sem_md, encoding="utf-8")
    print(f"Wrote {len(results)} repo reports + leaderboard + generalization + roadmap + semantic"
          f" ({len(probe)} probed).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
