"""Phase 136 — generalization benchmark runner.

For each target repository: scan once, then exercise the four benchmark
categories through the REAL Atlas APIs (the same entrypoints the product uses),
score them structurally, and record categorized failures. Writes machine-readable
JSON per repo + an aggregate. Atlas itself is never modified here.

Usage:
    py -3 benchmarks/generalization/runner.py                 # all available repos
    py -3 benchmarks/generalization/runner.py home_assistant django
"""

from __future__ import annotations

import json
import sys
import time
import traceback
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from benchmarks.generalization import registry, scenarios, scorer  # noqa: E402

RESULTS_DIR = Path(__file__).resolve().parent / "results"


def _reset_state() -> None:
    from jarvis_desktop import api
    api._STATE.update({"path": None, "scan": None, "graph": None, "index": None,
                       "risks": None, "evidence_store": None, "architecture": None,
                       "scan_cache": {}})


def run_repo(resolved: "registry.ResolvedRepo") -> Dict[str, Any]:
    from jarvis_desktop import api

    spec = resolved.spec
    base: Dict[str, Any] = {
        "id": spec.id, "display": spec.display, "language": spec.language,
        "framework": spec.framework, "category": spec.category,
        "available": resolved.available, "path": str(resolved.path) if resolved.path else None,
    }
    if not resolved.available:
        base.update({"status": "unavailable", "reason": "repository not checked out locally"})
        return base

    t0 = time.time()
    _reset_state()
    try:
        scan = api.scan_repository(str(resolved.path))
        # Massive-mode (very large, e.g. VS Code) import-graph builds are
        # occasionally degenerate (0 modules from thousands of files) due to a
        # cold-cache timing flake. A repo with many files but an empty module
        # graph cannot resolve anything; retry once with fresh state so the
        # measurement reflects Atlas, not a transient scan miss.
        if scan.get("ok") and not scan.get("module_count") and (scan.get("file_count") or 0) > 500:
            _reset_state()
            scan = api.scan_repository(str(resolved.path))
    except Exception as exc:  # scan crash is itself a finding
        base.update({"status": "scan_crash", "error": f"{type(exc).__name__}: {exc}",
                     "traceback": traceback.format_exc()[-1500:],
                     "scores": {"understanding": 0, "impact": 0, "investigation": 0, "build": 0, "overall": 0},
                     "failures": [scorer.Failure(spec.id, "scan", "successful scan",
                                                 f"{type(exc).__name__}", str(exc)[:120],
                                                 "scan pipeline", scorer.GRAPH_FAILURE).to_dict()]})
        return base
    if not scan.get("ok"):
        base.update({"status": "scan_failed", "error": scan.get("error"),
                     "scores": {"understanding": 0, "impact": 0, "investigation": 0, "build": 0, "overall": 0},
                     "failures": [scorer.Failure(spec.id, "scan", "successful scan", "scan not ok",
                                                 str(scan.get("error"))[:120], "scan pipeline",
                                                 scorer.GRAPH_FAILURE).to_dict()]})
        return base

    summary = api.current_summary()
    base["scan"] = {
        "module_count": scan.get("module_count"), "edges": scan.get("dependency_edges"),
        "subsystem_count": scan.get("subsystem_count"), "files": scan.get("file_count"),
        "massive_mode": scan.get("massive_mode"), "graph_detail": scan.get("graph_detail"),
        "scan_seconds": round(time.time() - t0, 1),
    }

    failures: List[Dict[str, Any]] = []

    # 1 — Repository Understanding
    u = scorer.score_understanding(spec.id, summary)
    failures += u.pop("failures")

    # 2 — Impact (user-facing Copilot route)
    concepts = scenarios.GENERIC_IMPACT_CONCEPTS + list(spec.impact_concepts)
    imp_results = []
    for c in concepts:
        prompt = scenarios.IMPACT_PROMPT_TEMPLATE.format(concept=c)
        try:
            resp = api.copilot_ask(prompt, "none", "compact")
        except Exception as exc:
            resp = {"answer": f"crash: {exc}", "error": str(exc)}
        imp_results.append({"prompt": prompt, "concept": c, "response": _slim_impact(resp)})
    i = scorer.score_impact(spec.id, imp_results)
    failures += i.pop("failures")

    # 3 — Investigation
    inv_results = []
    for sym in scenarios.INVESTIGATION_SYMPTOMS:
        try:
            resp = api.investigate_symptom(sym)
        except Exception as exc:
            resp = {"plan": {}, "error": str(exc)}
        inv_results.append({"symptom": sym, "response": _slim_inv(resp)})
    inv = scorer.score_investigation(spec.id, inv_results)
    failures += inv.pop("failures")

    # 4 — Build Plan
    build_results = []
    for req in scenarios.BUILD_REQUESTS:
        try:
            resp = api.plan_change(req)
        except Exception as exc:
            resp = {"plan": {}, "error": str(exc)}
        build_results.append({"request": req, "response": _slim_build(resp)})
    b = scorer.score_build(spec.id, build_results)
    failures += b.pop("failures")

    ov = scorer.overall(u["score"], i["score"], inv["score"], b["score"])
    base.update({
        "status": "ok",
        "scores": {"understanding": u["score"], "impact": i["score"],
                   "investigation": inv["score"], "build": b["score"], "overall": ov},
        "understanding": u, "impact": i, "investigation": inv, "build": b,
        "impact_samples": imp_results[:4],
        "investigation_samples": inv_results[:3],
        "build_samples": build_results[:2],
        "failures": failures,
        "elapsed_seconds": round(time.time() - t0, 1),
    })
    return base


def _slim_impact(resp: Dict[str, Any]) -> Dict[str, Any]:
    return {k: resp.get(k) for k in ("answer", "mode", "semantic_label", "resolved_modules",
            "direct_impact", "indirect_impact", "architectural_blast_radius", "confidence", "files")}


def _slim_inv(resp: Dict[str, Any]) -> Dict[str, Any]:
    plan = resp.get("plan", {}) or {}
    return {"plan": {k: plan.get(k) for k in ("likely_modules", "hypotheses", "most_likely_root_cause", "intent")}}


def _slim_build(resp: Dict[str, Any]) -> Dict[str, Any]:
    plan = resp.get("plan", {}) or {}
    return {"plan": {k: plan.get(k) for k in ("likely_affected_modules", "implementation_order",
            "tests_required", "rollback_plan", "intent")}}


def run_all(only: Optional[List[str]] = None) -> Dict[str, Any]:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    repos = registry.available_repos()
    if only:
        wanted = set(only)
        repos = [r for r in repos if r.spec.id in wanted]
    results = []
    for resolved in repos:
        print(f"[bench] {resolved.spec.id} available={resolved.available} ...", flush=True)
        rec = run_repo(resolved)
        results.append(rec)
        (RESULTS_DIR / f"{resolved.spec.id}.json").write_text(json.dumps(rec, indent=2), encoding="utf-8")
        s = rec.get("scores")
        print(f"[bench] {resolved.spec.id} status={rec.get('status')} scores={s}", flush=True)
    aggregate = {"generated": time.strftime("%Y-%m-%d %H:%M:%S"), "results": results}
    (RESULTS_DIR / "aggregate.json").write_text(json.dumps(aggregate, indent=2), encoding="utf-8")
    return aggregate


if __name__ == "__main__":
    only = sys.argv[1:] or None
    run_all(only)
