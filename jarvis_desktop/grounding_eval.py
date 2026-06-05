"""Phase 161 — grounding measurement harness.

A self-contained, dependency-free evaluation of Atlas's grounding behavior. It
runs a fixed battery of labeled scenarios over synthetic repository contexts and
measures the metrics the Phase 161 sprint cares about:

  * misleading %  — Atlas presented a confident/specialized result that was not
                    justified (concept leakage, "healthy" on an unsupported repo,
                    fake impact success, over-confident result).
  * wrong %       — Atlas named a concretely wrong artifact (e.g. a stdlib module
                    as the root cause).
  * confidence calibration — distribution of confidence labels and how often
                    "high" is claimed.
  * evidence count — average grounded evidence signals per result.
  * target resolution quality — fraction of impact targets correctly classified
                    as resolved / unresolved.

Run:  py -3 -m jarvis_desktop.grounding_eval
"""

from __future__ import annotations

from typing import Any, Dict, List

from . import planning_engine as pe
from . import reliability as rel
from .impact_engine.engine import analyze_impact


# --------------------------------------------------------------------------- #
# Synthetic contexts
# --------------------------------------------------------------------------- #
def _ctx(paths: List[str], scan: Dict[str, Any] | None = None) -> Dict[str, Any]:
    nodes = [
        {"id": f"n{i}", "type": "module", "path": p, "fan_in": 2,
         "dotted": p.replace("/", ".").rstrip(".py")}
        for i, p in enumerate(paths)
    ]
    edges = [{"type": "imports", "from": "n0", "to": "n1", "resolved": True}] if len(nodes) > 1 else []
    return {
        "graph": {"nodes": nodes, "edges": edges},
        "index": {"files": [{"path": p} for p in paths]},
        "risks": {"ranked_modules": []},
        "evidence_store": {},
        "repo_name": "eval_repo",
        "entry_points": [],
        "scan": scan or {"file_count": len(paths), "module_count": len(paths),
                         "dependency_edges": max(0, len(paths) - 1)},
    }


_WEB_PATHS = ["api/routes.py", "services/auth.py", "core/hub.py",
              "dispatch/event.py", "listeners/handler.py", "db/models.py"]
_TRADING_PATHS = ["trading/strategy.py", "indicators/ema.py", "backtest/engine.py",
                  "broker/adapter.py"]
_K8S_SCAN = {"file_count": 24860, "module_count": 3, "dependency_edges": 0, "graph_scope": "entire_repo"}
_HEALTHY_SCAN = {"file_count": 300, "module_count": 73, "dependency_edges": 159, "graph_scope": "entire_repo"}


def _conf_rank(label: str) -> int:
    return rel._confidence_rank(label)


# --------------------------------------------------------------------------- #
# Evaluation
# --------------------------------------------------------------------------- #
def evaluate_grounding() -> Dict[str, Any]:
    results: List[Dict[str, Any]] = []
    misleading = 0
    wrong = 0
    confidences: List[str] = []
    evidence_counts: List[int] = []
    resolution_correct = 0
    resolution_total = 0

    def record(name: str, *, mislead: bool, is_wrong: bool, note: str = "") -> None:
        nonlocal misleading, wrong
        if mislead:
            misleading += 1
        if is_wrong:
            wrong += 1
        results.append({"scenario": name, "misleading": mislead, "wrong": is_wrong, "note": note})

    # --- Concept leakage (must NOT inject trading/EMA into non-trading repos) ---
    leak_prompts = [
        ("build", "add structured logging to API handlers"),
        ("build", "add rate limiting to the API"),
        ("build", "add an indicator signal pipeline"),  # tempting EMA bait
        ("investigate", "why are duplicate events being fired"),
        ("investigate", "authentication is broken"),
        ("investigate", "memory leak in the worker"),
        ("investigate", "the dashboard shows wrong metrics"),
        ("investigate", "schema validation is failing"),  # 'schema' contains 'ema'
    ]
    for kind, prompt in leak_prompts:
        ctx = _ctx(_WEB_PATHS)
        res = pe.plan_change(prompt, ctx) if kind == "build" else pe.investigate_symptom(prompt, ctx)
        plan = res.get("plan") or {}
        dkb = plan.get("domain_knowledge") or {}
        leaked = dkb.get("domain") == "trading" or dkb.get("concept_id") == "ema"
        conf = plan.get("confidence") or res.get("confidence") or "low"
        confidences.append(conf)
        if kind == "build":
            evidence_counts.append(len(plan.get("implementation_files") or plan.get("files_to_inspect_first") or []))
        else:
            evidence_counts.append(len(plan.get("likely_modules") or []))
        record(f"no_leak::{prompt}", mislead=leaked, is_wrong=leaked,
               note=f"domain={dkb.get('domain')} concept={dkb.get('concept_id')}")

    # --- Trading allowed WITH trading evidence (not misleading) ---
    res = pe.investigate_symptom("ema calculation giving wrong values", _ctx(_TRADING_PATHS))
    record("trading_allowed_on_trading_repo", mislead=False, is_wrong=not res.get("ok", False))

    # --- Graph health truth (k8s must NOT be healthy) ---
    k8s_label = rel.graph_health_label(_K8S_SCAN)
    record("k8s_not_healthy", mislead=(k8s_label == "healthy"), is_wrong=(k8s_label == "healthy"),
           note=f"label={k8s_label}")
    healthy_label = rel.graph_health_label(_HEALTHY_SCAN)
    record("python_is_healthy", mislead=(healthy_label != "healthy"), is_wrong=False,
           note=f"label={healthy_label}")

    # --- Impact target resolution (no fake success) ---
    resolved_state = {"graph": _ctx(_WEB_PATHS)["graph"], "index": {"files": []}, "scan": _HEALTHY_SCAN}
    imp_ok = analyze_impact("api/routes.py", resolved_state)
    resolution_total += 1
    if imp_ok.get("ok") and imp_ok.get("status") == "resolved":
        resolution_correct += 1
    confidences.append(imp_ok.get("confidence", "low"))
    record("impact_resolved", mislead=not imp_ok.get("ok", False), is_wrong=False)

    imp_miss = analyze_impact("does/not/exist.py", resolved_state)
    resolution_total += 1
    correct_miss = (imp_miss.get("ok") is False)
    if correct_miss:
        resolution_correct += 1
    # Misleading if it faked success / blast radius on an unresolved target.
    record("impact_unresolved_no_fake", mislead=(imp_miss.get("ok") is True or imp_miss.get("mock") is True),
           is_wrong=(imp_miss.get("ok") is True), note=f"status={imp_miss.get('status')}")

    # --- Confidence not over-claimed on degraded scan ---
    degraded_ctx = _ctx(_WEB_PATHS, scan=_K8S_SCAN)
    res = pe.plan_change("add caching layer", degraded_ctx)
    plan = res.get("plan") or {}
    conf = plan.get("confidence") or res.get("confidence") or "low"
    confidences.append(conf)
    over_confident = _conf_rank(conf) >= _conf_rank("high")
    record("degraded_scan_not_high_confidence", mislead=over_confident, is_wrong=False,
           note=f"confidence={conf}")

    # --- Root cause: no stdlib/noise as root cause ---
    noisy_ctx = _ctx(["__future__.py", "re.py", "api/routes.py", "services/event.py"])
    res = pe.investigate_symptom("why are events fired twice", noisy_ctx)
    plan = res.get("plan") or {}
    root = (plan.get("most_likely_root_cause") or "").lower()
    bad_root = "__future__" in root or root.strip() == "defect originates in `re.py`"
    record("root_cause_not_stdlib", mislead=bad_root, is_wrong=bad_root, note=f"root={root[:60]}")

    total = len(results)
    high = sum(1 for c in confidences if _conf_rank(c) >= _conf_rank("high"))
    medium = sum(1 for c in confidences if c and _conf_rank(c) == 1)
    low = sum(1 for c in confidences if _conf_rank(c) == 0)
    conf_total = len(confidences) or 1

    return {
        "ok": True,
        "total_scenarios": total,
        "misleading": misleading,
        "wrong": wrong,
        "misleading_pct": round(100.0 * misleading / total, 2),
        "wrong_pct": round(100.0 * wrong / total, 2),
        "confidence_distribution": {
            "high": high, "medium": medium, "low": low,
            "high_pct": round(100.0 * high / conf_total, 2),
        },
        "avg_evidence_count": round(sum(evidence_counts) / (len(evidence_counts) or 1), 2),
        "target_resolution_quality": round(100.0 * resolution_correct / (resolution_total or 1), 2),
        "results": results,
    }


def format_report(metrics: Dict[str, Any]) -> str:
    lines = [
        "Atlas grounding evaluation (Phase 161)",
        "=" * 40,
        f"Scenarios:            {metrics['total_scenarios']}",
        f"Misleading:           {metrics['misleading']} ({metrics['misleading_pct']}%)",
        f"Wrong:                {metrics['wrong']} ({metrics['wrong_pct']}%)",
        f"Confidence (H/M/L):   {metrics['confidence_distribution']['high']}/"
        f"{metrics['confidence_distribution']['medium']}/{metrics['confidence_distribution']['low']} "
        f"(high {metrics['confidence_distribution']['high_pct']}%)",
        f"Avg evidence count:   {metrics['avg_evidence_count']}",
        f"Target resolution:    {metrics['target_resolution_quality']}% correct",
        "",
        "Per-scenario:",
    ]
    for r in metrics["results"]:
        flag = "MISLEADING" if r["misleading"] else ("WRONG" if r["wrong"] else "ok")
        lines.append(f"  [{flag:^10}] {r['scenario']}  {('— ' + r['note']) if r['note'] else ''}")
    return "\n".join(lines)


if __name__ == "__main__":  # pragma: no cover
    print(format_report(evaluate_grounding()))
