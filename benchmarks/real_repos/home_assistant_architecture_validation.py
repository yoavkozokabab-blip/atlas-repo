"""Phase 134 — Home Assistant architectural intelligence validation.

Run:
    py -3 benchmarks/real_repos/home_assistant_architecture_validation.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

HA_REPO = Path(os.environ.get("ATLAS_HA_REPO", str(ROOT / "external_repos" / "home_assistant")))


def validate(verbose: bool = True) -> int:
    from jarvis_desktop import api

    results = []

    def check(name: str, ok: bool, detail: str = "") -> None:
        results.append((name, ok, detail))
        if verbose:
            print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))

    if not HA_REPO.is_dir():
        print(f"SKIP: HA repo not at {HA_REPO}")
        return 1

    api._STATE.update(
        {"path": None, "scan": None, "graph": None, "index": None,
         "risks": None, "evidence_store": None, "architecture": None, "scan_cache": {}}
    )
    scan = api.scan_repository(str(HA_REPO))
    g = api._STATE.get("graph") or {}

    modules = int(scan.get("module_count") or 0)
    edges = int(scan.get("dependency_edges") or 0)
    check("graph.modules>9000", modules > 9000, str(modules))
    check("graph.edges>30000", edges > 30000, str(edges))

    hub_paths = [h.get("path") for h in scan.get("top_hubs", [])[:6]]
    risk_paths = [r.get("path") for r in scan.get("top_risks", [])[:6]]
    check("top_hubs!=top_risks", hub_paths != risk_paths, f"hubs={hub_paths[:3]} risks={risk_paths[:3]}")

    breakdown = scan.get("unresolved_breakdown") or {}
    check("unresolved.categorized", bool(breakdown), str(list(breakdown.keys())[:5]))
    internal = breakdown.get("internal_missing", 0) + breakdown.get("relative_resolution_issue", 0)
    external = breakdown.get("external_dependency", 0)
    check("unresolved.internal_separate", internal >= 0 and external >= internal, f"int={internal} ext={external}")

    const_hubs = [h for h in scan.get("top_hubs", []) if (h.get("path") or "").endswith("const.py")]
    top_risk_path = (scan.get("top_risks") or [{}])[0].get("path", "")
    check(
        "const.hub_not_top_risk",
        bool(const_hubs) and not top_risk_path.endswith("const.py"),
        f"const_hub={bool(const_hubs)} top_risk={top_risk_path}",
    )

    arch_sum = scan.get("architecture_summary") or {}
    areas = arch_sum.get("areas") or {}
    for area in ("components", "helpers", "core", "auth", "config_entries"):
        check(f"architecture_summary.{area}", areas.get(area, 0) > 0 or arch_sum.get(f"has_{area}"))

    api._STATE["path"] = str(HA_REPO)
    ev = api.change_impact_simulation("impact of changing the event bus")
    ev_blob = " ".join((ev.get("risky_areas") or []) + [ev.get("target") or ""]).lower()
    check("impact.event_bus", ev.get("ok") and any(k in ev_blob for k in ("event", "core", "automation", "service")), ev_blob[:120])

    ws = api.change_impact_simulation("remove websocket support")
    ws_blob = " ".join((ws.get("risky_areas") or []) + (ws.get("affected_files") or [])).lower()
    check("impact.websocket", ws.get("ok") and any(k in ws_blob for k in ("websocket", "auth", "session")), ws_blob[:120])

    failed = [n for n, ok, _ in results if not ok]
    if verbose:
        print(f"\n{len(results) - len(failed)}/{len(results)} passed")
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(validate())
