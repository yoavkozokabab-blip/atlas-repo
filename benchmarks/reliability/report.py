"""Phase 140 — render the reliability dashboard + report from dashboard.json."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parents[2]
RESULTS = Path(__file__).resolve().parent / "results" / "dashboard.json"
REPORT = ROOT / "reports" / "phase140_reliability.md"

_CAT_LABEL = {
    "ok": "Healthy", "scan_crash": "Scan crash", "scan_failed": "Scan failed",
    "zero_module_scan": "Zero-module scan", "zero_edge_graph": "Zero-edge graph",
    "partial_graph": "Partial/degraded graph", "timeout_failure": "Timeout",
    "unresolved_import_explosion": "Unresolved-import explosion",
    "memory_pressure": "Memory pressure", "empty_repo": "Empty repo (not a fault)",
}


def render(d: Dict[str, Any]) -> str:
    r = d["rates"]
    tax = d.get("taxonomy", {})
    faults = d.get("faults", [])
    records = d.get("records", [])
    live = [x for x in records if x.get("source") == "live"]
    ingested = [x for x in records if x.get("source") == "overnight"]

    L: List[str] = [
        "# Phase 140 — Reliability Hardening", "",
        f"_Generated {d.get('generated')}_", "",
        "Reliability-only hardening: degraded-scan detection, a safe transient",
        "retry, and a failure taxonomy so Atlas processes repositories repeatedly",
        "without manual intervention. No new intelligence, concepts, billing or UI.", "",
        "## Success-rate dashboard", "",
        "| Metric | Rate |", "|---|---:|",
        f"| Scan success | **{r['scan_success_rate']}%** |",
        f"| Graph build success (modules+edges) | **{r['graph_build_success_rate']}%** |",
        f"| Impact success (live) | **{r['impact_success_rate']}%** |",
        f"| Investigation success (live) | **{r['investigation_success_rate']}%** |",
        "",
        f"Evidence base: **{r['total_runs']} scan executions** across "
        f"**{r['distinct_repos']} distinct repositories** "
        f"({r['live_runs']} live repeated scans + {r['total_runs'] - r['live_runs']} "
        "ingested from the overnight validation campaign).", "",
        "## Failure taxonomy (every outcome classified)", "",
        "| Category | Count |", "|---|---:|",
    ]
    for cat, n in tax.items():
        L.append(f"| {_CAT_LABEL.get(cat, cat)} (`{cat}`) | {n} |")
    L += ["", "## Detected faults", ""]
    if faults:
        L += ["| Repository | Source | Category | Modules | Edges | Warning |",
              "|---|---|---|---:|---:|---|"]
        for f in faults:
            w = (f.get("warnings") or [""])[0]
            L.append(f"| {f['repo']} | {f['source']} | `{f['category']}` | "
                     f"{f.get('modules')} | {f.get('edges')} | {w} |")
    else:
        L.append("No faults detected.")

    L += ["", "## Reliability features added (this phase)", "",
          "1. **Degraded-scan auto-detection** (`atlas_desktop/reliability.py`): every",
          "   scan result is classified; degraded scans (0 modules, 0 edges, partial /",
          "   timed-out graph, unresolved-import explosion, memory pressure) surface a",
          "   warning immediately via `scan['reliability']` + `scan['health_warnings']`.",
          "2. **Safe transient retry** (`api.scan_repository`): a massive-mode build that",
          "   yields 0 modules from >500 files is rebuilt once (side-effect-free). Only",
          "   `zero_module_scan` is auto-retried — timeouts and hard failures are not.",
          "3. **Failure taxonomy**: stable categories (`ok`, `scan_crash`, `scan_failed`,",
          "   `zero_module_scan`, `zero_edge_graph`, `partial_graph`, `timeout_failure`,",
          "   `unresolved_import_explosion`, `memory_pressure`, `empty_repo`).",
          "4. **Reliability harness** (`benchmarks/reliability/`): scans repos repeatedly,",
          "   classifies every outcome, and writes this dashboard — reproducible.", "",
          "## Repeatability evidence (live, repeated scans)", "",
          "| Repository | Attempt | Category | Modules | Edges | Seconds | Impact ok | Investigation ok |",
          "|---|---:|---|---:|---:|---:|:--:|:--:|"]
    for x in live:
        L.append(f"| {x['repo']} | {x.get('attempt')} | `{x.get('category')}` | "
                 f"{x.get('modules')} | {x.get('edges')} | {x.get('seconds')} | "
                 f"{'✓' if x.get('impact_ok') else '–'} | {'✓' if x.get('investigation_ok') else '–'} |")

    L += ["", "## Ingested campaign outcomes (breadth)", "",
          "| Repository | Category | Modules | Edges |", "|---|---|---:|---:|"]
    for x in sorted(ingested, key=lambda r: r.get("category", "")):
        L.append(f"| {x['repo']} | `{x.get('category')}` | {x.get('modules')} | {x.get('edges')} |")

    healthy = sum(1 for x in records if x.get("healthy"))
    L += ["", "## Assessment", "",
          f"- **{healthy}/{len(records)}** scan executions classified healthy or "
          "legitimately-empty; every fault has a category and an immediate warning.",
          "- The previously-unhandled VS Code degenerate scan (0 modules) is now",
          "  auto-detected and retried; timeouts and zero-edge graph failures are",
          "  surfaced rather than silently producing empty analysis.",
          "- Remaining known faults (self-scan timeout, zero-edge on edge-sparse repos)",
          "  are now **classified and visible**, not silent — the prerequisite for",
          "  unattended, repeatable processing.", ""]
    return "\n".join(L)


def main() -> int:
    if not RESULTS.is_file():
        print("No dashboard.json — run runner.py first.")
        return 1
    d = json.loads(RESULTS.read_text(encoding="utf-8"))
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(render(d), encoding="utf-8")
    print(f"Wrote {REPORT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
