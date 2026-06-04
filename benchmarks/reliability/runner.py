"""Phase 140 — reliability runner.

Exercises Atlas's scan pipeline across many repositories and REPEATEDLY on the
locally-available ones, classifying every outcome with the reliability taxonomy
(`jarvis_desktop/reliability.py`). It combines two evidence sources:

  * LIVE: fresh scans of locally-available repos (each scanned multiple times) —
    proves Atlas can process repositories repeatedly without manual intervention,
    and exercises the new degraded-scan detection + transient retry.
  * INGESTED: the 18-repo overnight validation campaign
    (`benchmarks/overnight_validation/raw/`) — breadth of real-world outcomes
    (timeouts, zero-edge graph failures) without re-running multi-hour scans.

Writes a machine-readable reliability dashboard to
``benchmarks/reliability/results/dashboard.json``.

Usage:
    py -3 benchmarks/reliability/runner.py                 # live fast repos + ingest
    py -3 benchmarks/reliability/runner.py --repeats 3 fastapi django quixbugs
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

from jarvis_desktop import reliability  # noqa: E402
from benchmarks.generalization import registry  # noqa: E402

RESULTS_DIR = Path(__file__).resolve().parent / "results"
OVERNIGHT_RAW = ROOT / "benchmarks" / "overnight_validation" / "raw"

# Fast, locally-available repos to scan live by default (skip the multi-minute
# giants — they are covered by the ingested campaign). Each scanned `repeats` times.
DEFAULT_LIVE = ["fastapi", "django", "quixbugs"]

try:
    import psutil  # type: ignore
    _PROC = psutil.Process()
except Exception:  # psutil optional
    _PROC = None


def _peak_rss_mb() -> Optional[float]:
    if _PROC is None:
        return None
    try:
        return _PROC.memory_info().rss / (1024 * 1024)
    except Exception:
        return None


def _reset_state() -> None:
    from jarvis_desktop import api
    api._STATE.update({"path": None, "scan": None, "graph": None, "index": None,
                       "risks": None, "evidence_store": None, "architecture": None,
                       "scan_cache": {}})


def _probe_capabilities() -> Dict[str, Any]:
    """Did impact + investigation produce grounded, non-crashing output?"""
    from jarvis_desktop import api
    out = {"impact_ok": False, "investigation_ok": False}
    try:
        r = api.copilot_ask("what breaks if I remove the api layer", "none", "compact")
        ans = str(r.get("answer", ""))
        out["impact_ok"] = bool(r) and "Name a file" not in ans and (
            bool(r.get("resolved_modules") or r.get("direct_impact") or r.get("files")))
    except Exception:
        out["impact_ok"] = False
    try:
        r = api.investigate_symptom("memory keeps growing over time")
        plan = (r or {}).get("plan", {}) or {}
        out["investigation_ok"] = bool(plan.get("likely_modules"))
    except Exception:
        out["investigation_ok"] = False
    return out


def scan_once(repo_id: str, path: str, attempt: int) -> Dict[str, Any]:
    from jarvis_desktop import api
    _reset_state()
    t0 = time.time()
    rss_before = _peak_rss_mb()
    rec: Dict[str, Any] = {"repo": repo_id, "source": "live", "attempt": attempt}
    try:
        scan = api.scan_repository(path)
    except Exception as exc:
        rec.update({
            "ok": False,
            "assessment": reliability.classify_scan({"ok": False, "error": str(exc),
                                                     "code": "scan_crash"}),
            "category": reliability.SCAN_CRASH,
            "error": f"{type(exc).__name__}: {exc}",
            "traceback": traceback.format_exc()[-800:],
            "seconds": round(time.time() - t0, 1),
        })
        rec["assessment"]["category"] = reliability.SCAN_CRASH
        return rec
    peak = _peak_rss_mb()
    rss = max(filter(None, [rss_before, peak]), default=None)
    assessment = reliability.classify_scan(scan, peak_rss_mb=rss)
    if scan.get("reliability", {}).get("retried"):
        assessment["retried"] = True
        assessment["retry_recovered"] = scan["reliability"].get("retry_recovered")
    caps = _probe_capabilities() if scan.get("ok") and scan.get("module_count") else \
        {"impact_ok": False, "investigation_ok": False}
    rec.update({
        "ok": bool(scan.get("ok")),
        "modules": scan.get("module_count"),
        "edges": scan.get("dependency_edges"),
        "files": scan.get("file_count"),
        "graph_detail": scan.get("graph_detail"),
        "seconds": round(time.time() - t0, 1),
        "peak_rss_mb": round(rss, 1) if rss else None,
        "category": assessment["category"],
        "healthy": assessment["healthy"],
        "warnings": assessment["warnings"],
        "assessment": assessment,
        **caps,
    })
    return rec


def run_live(repo_ids: List[str], repeats: int) -> List[Dict[str, Any]]:
    records: List[Dict[str, Any]] = []
    for rr in registry.available_repos():
        if rr.spec.id not in repo_ids or not rr.available:
            continue
        for attempt in range(1, repeats + 1):
            print(f"[reliability] live {rr.spec.id} attempt {attempt}/{repeats}", flush=True)
            rec = scan_once(rr.spec.id, str(rr.path), attempt)
            records.append(rec)
            print(f"[reliability]   -> category={rec.get('category')} "
                  f"modules={rec.get('modules')} edges={rec.get('edges')} "
                  f"impact_ok={rec.get('impact_ok')}", flush=True)
    return records


def _overnight_to_scan(raw: Dict[str, Any]) -> Dict[str, Any]:
    sm = raw.get("scan_metrics") or {}
    status = raw.get("status")
    failures = raw.get("failures") or []
    timed_out = status == "timeout" or any(
        f.get("category") == "performance_failure" for f in failures)
    return {
        # A timed-out scan still "ran"; classify it as a timeout (not a hard fail)
        # by keeping ok=True and flagging the build, so the taxonomy is precise.
        "ok": status in ("measured", "ok") or timed_out,
        "error": (failures[0].get("reason") if failures and status not in ("measured", "ok")
                  and not timed_out else None),
        "graph_build": {"timed_out": timed_out},
        "module_count": sm.get("modules") or 0,
        "dependency_edges": sm.get("edges") or 0,
        "file_count": sm.get("files") or 0,
        "graph_detail": sm.get("graph_detail") or "imports",
        "degraded": bool(sm.get("degraded")),
        "scan_duration_seconds": (raw.get("time_metrics") or {}).get("scan_sec")
        or raw.get("process_duration_sec") or 0,
        "timed_out": timed_out,
        "unresolved_imports": sm.get("unresolved_imports") or 0,
        "unresolved_ratio": sm.get("unresolved_ratio") or 0.0,
    }


def ingest_overnight() -> List[Dict[str, Any]]:
    records: List[Dict[str, Any]] = []
    if not OVERNIGHT_RAW.is_dir():
        return records
    for p in sorted(OVERNIGHT_RAW.glob("*.json")):
        raw = json.loads(p.read_text(encoding="utf-8"))
        scan = _overnight_to_scan(raw)
        assessment = reliability.classify_scan(scan)
        records.append({
            "repo": raw.get("repo_id") or p.stem,
            "source": "overnight",
            "attempt": 1,
            "ok": scan["ok"],
            "modules": scan["module_count"],
            "edges": scan["dependency_edges"],
            "files": scan["file_count"],
            "seconds": round(float(scan["scan_duration_seconds"] or 0), 1),
            "category": assessment["category"],
            "healthy": assessment["healthy"],
            "warnings": assessment["warnings"],
            "assessment": assessment,
            "raw_status": raw.get("status"),
        })
    return records


# A scan "failed" only if it did not complete usefully (crash/timeout/empty);
# a degraded-but-complete graph (zero-edge, unresolved-explosion, partial) still
# counts as a completed scan — its degradation shows in graph_build_success.
_SCAN_FAILURE = {reliability.SCAN_CRASH, reliability.SCAN_FAILED,
                 reliability.TIMEOUT, reliability.ZERO_MODULE_SCAN}


def _rates(records: List[Dict[str, Any]]) -> Dict[str, Any]:
    n = len(records) or 1
    scan_ok = sum(1 for r in records if r.get("category") not in _SCAN_FAILURE)
    graph_ok = sum(1 for r in records if (r.get("modules") or 0) > 0 and (r.get("edges") or 0) > 0)
    live = [r for r in records if r.get("source") == "live" and r.get("category") not in _SCAN_FAILURE]
    impact_ok = sum(1 for r in live if r.get("impact_ok"))
    inv_ok = sum(1 for r in live if r.get("investigation_ok"))
    live_n = len(live) or 1
    return {
        "total_runs": len(records),
        "distinct_repos": len({r["repo"] for r in records}),
        "scan_success_rate": round(100 * scan_ok / n, 1),
        "graph_build_success_rate": round(100 * graph_ok / n, 1),
        "impact_success_rate": round(100 * impact_ok / live_n, 1),
        "investigation_success_rate": round(100 * inv_ok / live_n, 1),
        "live_runs": len([r for r in records if r.get("source") == "live"]),
    }


def run(live_ids: Optional[List[str]] = None, repeats: int = 2) -> Dict[str, Any]:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    live = run_live(live_ids or DEFAULT_LIVE, repeats)
    ingested = ingest_overnight()
    records = live + ingested
    from collections import Counter
    taxonomy: Counter = Counter(r["category"] for r in records)
    faults = [r for r in records if r["category"] in reliability.FAULT_CATEGORIES]
    dashboard = {
        "generated": time.strftime("%Y-%m-%d %H:%M:%S"),
        "rates": _rates(records),
        "taxonomy": dict(taxonomy.most_common()),
        "faults": [{"repo": r["repo"], "source": r["source"], "category": r["category"],
                    "modules": r.get("modules"), "edges": r.get("edges"),
                    "warnings": r.get("warnings")} for r in faults],
        "records": records,
    }
    (RESULTS_DIR / "dashboard.json").write_text(json.dumps(dashboard, indent=2), encoding="utf-8")
    print(f"[reliability] {dashboard['rates']}")
    return dashboard


if __name__ == "__main__":
    args = sys.argv[1:]
    repeats = 2
    if "--repeats" in args:
        i = args.index("--repeats")
        repeats = int(args[i + 1])
        args = args[:i] + args[i + 2:]
    run(args or None, repeats)
