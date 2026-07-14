#!/usr/bin/env python3
"""Phase 121C — trace module graph counts at each pipeline stage (no UI changes)."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List

from verification_isolation import activate_isolated_atlas_data

activate_isolated_atlas_data("phase121c-trace-graph")

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from atlas_desktop import api  # noqa: E402

DEFAULT_REPO = os.environ.get("ATLAS_TRACE_REPO", r"C:\FINAL_ALGO_TRADER")
SAMPLE_DIR = ROOT / "reports" / "phase121c_samples"


def _count_graph_modules(graph: Dict[str, Any]) -> int:
    return sum(1 for n in graph.get("nodes", []) if n.get("type") == "module")


def _count_import_edges(graph: Dict[str, Any], *, resolved_only: bool = True) -> int:
    total = 0
    for edge in graph.get("edges", []):
        if edge.get("type") != "imports":
            continue
        if resolved_only and not edge.get("resolved"):
            continue
        total += 1
    return total


def _subsystem_like(nodes: List[Dict[str, Any]]) -> int:
    return sum(
        1
        for n in nodes
        if n.get("graph_view") == "subsystem" or str(n.get("id", "")).startswith("subsystem:")
    )


def trace_repo(repo_path: str) -> Dict[str, Any]:
    api._STATE.update(
        {
            "path": None,
            "scan": None,
            "graph": None,
            "index": None,
            "risks": None,
            "demo_mode": False,
            "scan_cache": {},
        }
    )
    rows: List[Dict[str, Any]] = []

    def row(stage: str, nodes: int, edges: int, **extra: Any) -> None:
        rows.append({"stage": stage, "nodes": nodes, "edges": edges, **extra})

    if not Path(repo_path).is_dir():
        return {"ok": False, "error": f"Repository not found: {repo_path}", "rows": rows}

    est = api.pre_scan_estimate(repo_path, {"mode": "entire_repo"})
    row(
        "pre_scan_estimate",
        est.get("estimated_modules", 0),
        0,
        massive_mode_auto=est.get("massive_mode_auto"),
        code_files=est.get("code_files"),
    )

    scan = api.scan_repository(repo_path, {"mode": "entire_repo"})
    if not scan.get("ok"):
        return {"ok": False, "error": scan.get("error"), "rows": rows}

    row(
        "scan_result",
        scan.get("module_count", 0),
        scan.get("dependency_edges", 0),
        massive_mode=scan.get("massive_mode"),
        graph_scope=scan.get("graph_scope"),
        full_graph_pending=scan.get("full_graph_pending"),
    )

    graph = api._STATE.get("graph") or {}
    row(
        "builder_core_graph_stored",
        _count_graph_modules(graph),
        _count_import_edges(graph),
        all_import_edges=_count_import_edges(graph, resolved_only=False),
        graph_detail=graph.get("graph_detail"),
        degraded=graph.get("degraded"),
        atlas_partial=graph.get("atlas_partial"),
    )

    for view in ("module", "subsystem", "hierarchy"):
        if view == "hierarchy":
            payload = api.current_hierarchy_graph("subsystem")
        else:
            payload = api.current_graph(view)
        nodes = payload.get("nodes") or []
        row(
            f"api_payload_{view}",
            payload.get("node_count", len(nodes)),
            payload.get("link_count", len(payload.get("links") or [])),
            view=payload.get("view"),
            total_modules=payload.get("total_modules"),
            total_edges=payload.get("total_edges"),
            architecture_clusters=payload.get("architecture_clusters"),
            subsystem_like_nodes=_subsystem_like(nodes),
            cluster_count=payload.get("cluster_count"),
        )

    diag = api.current_graph("module", force_module=True)
    row(
        "api_payload_module_force_full",
        diag.get("node_count", 0),
        diag.get("link_count", 0),
        total_modules=diag.get("total_modules"),
    )

    # Simulate frontend chunk merge (universe.js loadChunk link filter)
    module_payload = api.current_graph("module")
    all_nodes = module_payload.get("nodes") or []
    all_links = module_payload.get("links") or []
    chunk_size = len(all_nodes) if len(all_nodes) <= 1000 else 160
    loaded = 0
    merged_nodes: List[Dict[str, Any]] = []
    while loaded < len(all_nodes):
        slice_nodes = all_nodes[loaded : loaded + chunk_size]
        loaded += len(slice_nodes)
        merged_nodes = merged_nodes + slice_nodes
        ids = {n["id"] for n in merged_nodes}
        merged_links = [
            l
            for l in all_links
            if l.get("source") in ids and l.get("target") in ids
        ]
    row(
        "frontend_chunk_simulation_final",
        len(merged_nodes),
        len(merged_links),
        chunk_size=chunk_size,
    )

    sample = {
        "scan": {
            "module_count": scan.get("module_count"),
            "dependency_edges": scan.get("dependency_edges"),
            "massive_mode": scan.get("massive_mode"),
        },
        "module_payload_meta": {
            k: module_payload.get(k)
            for k in (
                "view",
                "node_count",
                "link_count",
                "total_modules",
                "total_edges",
                "recommended_view",
                "architecture_clusters",
                "massive_mode",
                "render_warning",
            )
        },
        "first_5_nodes": (module_payload.get("nodes") or [])[:5],
        "subsystem_payload_node_labels": [
            n.get("label") for n in (api.current_graph("subsystem").get("nodes") or [])
        ],
    }

    SAMPLE_DIR.mkdir(parents=True, exist_ok=True)
    sample_path = SAMPLE_DIR / "final_algo_trader_graph_sample.json"
    sample_path.write_text(json.dumps(sample, indent=2), encoding="utf-8")

    return {
        "ok": True,
        "repo": repo_path,
        "rows": rows,
        "sample_path": str(sample_path),
    }


def main() -> int:
    repo = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_REPO
    result = trace_repo(repo)
    print(json.dumps(result, indent=2))
    if result.get("ok"):
        print("\n| Stage | Nodes | Edges |")
        print("|-------|------:|------:|")
        for r in result["rows"]:
            extra = " ".join(
                f"{k}={v}"
                for k, v in r.items()
                if k not in ("stage", "nodes", "edges")
            )
            note = f" ({extra})" if extra else ""
            print(f"| {r['stage']} | {r['nodes']} | {r['edges']} |{note}")
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
