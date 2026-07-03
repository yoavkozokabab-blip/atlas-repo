#!/usr/bin/env python3
"""Collect Phase 121B graph payload metrics (no browser required)."""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from atlas_desktop import api  # noqa: E402


def bench_repo(label: str, path: Path) -> dict:
    api._STATE.update({"path": None, "scan": None, "graph": None, "index": None, "risks": None})
    t0 = time.perf_counter()
    scan = api.scan_repository(str(path), {"mode": "entire_repo"})
    scan_ms = round((time.perf_counter() - t0) * 1000)
    if not scan.get("ok"):
        return {"label": label, "ok": False, "error": scan.get("error")}
    t1 = time.perf_counter()
    module_graph = api.current_graph("module")
    module_ms = round((time.perf_counter() - t1) * 1000)
    t2 = time.perf_counter()
    overview = api.current_graph("subsystem")
    overview_ms = round((time.perf_counter() - t2) * 1000)
    return {
        "label": label,
        "ok": True,
        "scan_ms": scan_ms,
        "module_graph_ms": module_ms,
        "overview_graph_ms": overview_ms,
        "modules": scan.get("module_count"),
        "edges": scan.get("dependency_edges"),
        "recommended_view": module_graph.get("recommended_view"),
        "module_nodes_rendered": module_graph.get("node_count"),
        "overview_nodes": overview.get("node_count"),
        "clusters": module_graph.get("cluster_count"),
        "architecture_clusters": overview.get("architecture_clusters"),
    }


def main() -> int:
    targets = [
        ("ts_sample", ROOT / "atlas_desktop" / "demo" / "ts_sample_repo"),
    ]
    fastapi = Path(r"c:\J.A.R.V.I.S\local_atlas\demo_repos\fastapi")
    if fastapi.is_dir():
        targets.append(("fastapi", fastapi))
    out = [bench_repo(label, path) for label, path in targets]
    print(json.dumps(out, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
