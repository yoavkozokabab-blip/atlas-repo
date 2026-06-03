"""Phase 136 — structural scoring + failure categorization.

There is no gold-standard ground truth for arbitrary external repositories, so
the scorer measures OUTPUT ROBUSTNESS / USEFULNESS (did Atlas produce grounded,
non-fallback, non-noisy output) rather than correctness against a fixed answer
key. This is intentionally honest: it detects where Atlas degrades, falls back,
returns empty, or routes to junk — exactly the generalization weaknesses Phase 136
is meant to expose. Scores are 0-100 per category.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

# Failure taxonomy (matches the phase spec).
GRAPH_FAILURE = "graph_failure"
RESOLVER_FAILURE = "resolver_failure"
SEMANTIC_ROUTING_FAILURE = "semantic_routing_failure"
INVESTIGATION_FAILURE = "investigation_failure"
BUILD_PLAN_FAILURE = "build_plan_failure"
ARCHITECTURE_FAILURE = "architecture_failure"
UX_FAILURE = "ux_failure"

_DOTFILE_MARKERS = (
    ".prettierrc", "package.json", "package-lock", "pyproject.toml", ".eslintrc",
    "eslint.config", ".lock", ".gitignore", ".editorconfig", "/docs/", ".md",
    "tsconfig", "/.github/", "dockerfile",
)

_CONF = {"high": 1.0, "medium-high": 0.85, "medium": 0.6, "low-medium": 0.45, "low": 0.3}


@dataclass
class Failure:
    repository: str
    scenario: str
    expected: str
    actual: str
    root_cause: str
    subsystem: str
    category: str

    def to_dict(self) -> Dict[str, Any]:
        return self.__dict__.copy()


def _has_dotfile(paths: List[str]) -> bool:
    blob = " ".join(str(p).lower() for p in paths)
    return any(m in blob for m in _DOTFILE_MARKERS)


# --------------------------------------------------------------------------
# 1 — Repository Understanding
# --------------------------------------------------------------------------
def score_understanding(repo: str, summary: Dict[str, Any]) -> Dict[str, Any]:
    failures: List[Failure] = []
    if not summary.get("ok"):
        failures.append(Failure(repo, "repository_understanding", "scan + summary",
                                "summary not ok", "scan/summary failed", "graph/scan", GRAPH_FAILURE))
        return {"score": 0.0, "components": {}, "failures": [f.to_dict() for f in failures]}

    arch = summary.get("architecture") or {}
    expl = summary.get("explanation") or ""
    subs = summary.get("subsystems") or []
    entries = summary.get("entry_points") or []
    risks = summary.get("top_risks") or []
    hubs = summary.get("top_hubs") or []
    modules = int(summary.get("module_count") or 0)
    hubs_identical = arch.get("hubs_risks_identical")

    comp = {
        "graph_built": 20.0 if modules >= 30 else (10.0 if modules >= 5 else 0.0),
        "explanation": 15.0 if len(expl) >= 80 else (8.0 if expl else 0.0),
        "subsystems": 15.0 if len(subs) >= 3 else (8.0 if subs else 0.0),
        "entry_points": 10.0 if entries else 0.0,
        "runtime_boundaries": 15.0 if (arch.get("top_boundaries")) else 0.0,
        "top_risks": 10.0 if risks else 0.0,
        "hubs_vs_risks_separated": 15.0 if (hubs and risks and hubs_identical is False) else (
            5.0 if (hubs and risks) else 0.0),
    }
    score = round(sum(comp.values()), 1)
    if modules < 30:
        failures.append(Failure(repo, "repository_understanding", ">=30 modules indexed",
                                f"{modules} modules", "graph sparse/degraded for this layout",
                                "graph build", GRAPH_FAILURE))
    if not arch.get("top_boundaries"):
        failures.append(Failure(repo, "runtime_boundaries", "boundary modules identified",
                                "none", "no cross-subsystem boundaries detected for this layout",
                                "architecture analyzer", ARCHITECTURE_FAILURE))
    return {"score": score, "components": comp, "failures": [f.to_dict() for f in failures],
            "module_count": modules, "edges": summary.get("dependency_edges")}


# --------------------------------------------------------------------------
# 2 — Impact (via the user-facing Copilot route)
# --------------------------------------------------------------------------
def score_impact(repo: str, results: List[Dict[str, Any]]) -> Dict[str, Any]:
    failures: List[Failure] = []
    if not results:
        return {"score": 0.0, "resolution_rate": 0.0, "fallback_rate": 1.0, "failures": []}
    resolved = 0
    conf_sum = 0.0
    useful = 0
    fallbacks = 0
    for item in results:
        prompt = item.get("prompt", "")
        r = item.get("response", {}) or {}
        answer = str(r.get("answer", ""))
        is_fallback = ("Name a file" in answer) or ("could not be resolved" in answer.lower()) \
            or ("not in the production graph" in answer.lower())
        has_modules = bool(r.get("resolved_modules")) or bool(r.get("direct_impact")) or bool(r.get("indirect_impact")) or bool(r.get("files"))
        if is_fallback or not has_modules:
            fallbacks += 1
            failures.append(Failure(repo, prompt, "concept resolves to modules",
                                    "fallback / no target" if is_fallback else "empty impact",
                                    "concept absent from repo or not in resolver map",
                                    "target_resolver / impact_engine",
                                    SEMANTIC_ROUTING_FAILURE if is_fallback else RESOLVER_FAILURE))
            continue
        resolved += 1
        conf_sum += _CONF.get(str(r.get("confidence", "medium")), 0.6)
        if (r.get("direct_impact") or r.get("indirect_impact") or r.get("files")):
            useful += 1
    n = len(results)
    resolution_rate = resolved / n
    score = round(60.0 * resolution_rate + 20.0 * (conf_sum / max(1, resolved)) * resolution_rate
                  + 20.0 * (useful / n), 1)
    return {"score": score, "resolution_rate": round(resolution_rate, 3),
            "fallback_rate": round(fallbacks / n, 3), "resolved": resolved, "total": n,
            "failures": [f.to_dict() for f in failures]}


# --------------------------------------------------------------------------
# 3 — Investigation
# --------------------------------------------------------------------------
def score_investigation(repo: str, results: List[Dict[str, Any]]) -> Dict[str, Any]:
    failures: List[Failure] = []
    if not results:
        return {"score": 0.0, "grounded_rate": 0.0, "failures": []}
    grounded = clean = with_hyp = 0
    noise_total = 0
    for item in results:
        sym = item.get("symptom", "")
        plan = (item.get("response", {}) or {}).get("plan", {}) or {}
        mods = plan.get("likely_modules") or []
        hyps = plan.get("hypotheses") or []
        noise_total += len(mods)
        if mods:
            grounded += 1
        else:
            failures.append(Failure(repo, sym, "grounded likely modules", "none",
                                    "no module matched the symptom in this repo",
                                    "investigation/planning_engine", INVESTIGATION_FAILURE))
        if mods and not _has_dotfile(mods):
            clean += 1
        elif _has_dotfile(mods):
            failures.append(Failure(repo, sym, "no config/dotfiles for runtime symptom",
                                    f"dotfile in {mods[:3]}", "runtime symptom routed to config file",
                                    "investigation routing", INVESTIGATION_FAILURE))
        if hyps:
            with_hyp += 1
    n = len(results)
    score = round(50.0 * (grounded / n) + 25.0 * (clean / n) + 25.0 * (with_hyp / n), 1)
    return {"score": score, "grounded_rate": round(grounded / n, 3),
            "clean_rate": round(clean / n, 3), "avg_modules": round(noise_total / n, 1),
            "failures": [f.to_dict() for f in failures]}


# --------------------------------------------------------------------------
# 4 — Build Plan
# --------------------------------------------------------------------------
def score_build(repo: str, results: List[Dict[str, Any]]) -> Dict[str, Any]:
    failures: List[Failure] = []
    if not results:
        return {"score": 0.0, "failures": []}
    mods = order = tests = rollback = 0
    for item in results:
        req = item.get("request", "")
        plan = (item.get("response", {}) or {}).get("plan", {}) or {}
        has_mods = bool(plan.get("likely_affected_modules"))
        if has_mods:
            mods += 1
        else:
            failures.append(Failure(repo, req, "affected modules", "none",
                                    "no module matched the build concept in this repo",
                                    "planning_engine", BUILD_PLAN_FAILURE))
        if plan.get("implementation_order"):
            order += 1
        if plan.get("tests_required") or plan.get("tests_likely_affected"):
            tests += 1
        if plan.get("rollback_plan"):
            rollback += 1
    n = len(results)
    score = round(25.0 * (mods / n) + 25.0 * (order / n) + 25.0 * (tests / n) + 25.0 * (rollback / n), 1)
    return {"score": score, "with_modules": mods, "total": n,
            "failures": [f.to_dict() for f in failures]}


def overall(u: float, i: float, inv: float, b: float) -> float:
    # Weighted: understanding .25, impact .30, investigation .25, build .20.
    return round(0.25 * u + 0.30 * i + 0.25 * inv + 0.20 * b, 1)
