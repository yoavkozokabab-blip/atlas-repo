"""Phase 116G — fresh repository scan metrics (no cache)."""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from atlas_desktop import api  # noqa: E402

REPOS = {
    "fastapi": r"C:\J.A.R.V.I.S\fastapi",
    "django": r"C:\J.A.R.V.I.S\django",
    "vscode": r"C:\J.A.R.V.I.S\vscode",
}
OUT_DIR = ROOT / "reports"


def _fresh_scan(repo_path: str) -> dict:
    api._STATE.update(
        {
            "path": None,
            "scan": None,
            "graph": None,
            "index": None,
            "risks": None,
            "scan_cache": {},
            "demo_mode": False,
        }
    )
    t0 = time.perf_counter()
    result = api.scan_repository(repo_path)
    elapsed = round(time.perf_counter() - t0, 3)
    summary = api.current_summary() if result.get("ok") else {}
    risks = api.current_risks() if result.get("ok") else {}
    top_risks = []
    if risks.get("ok"):
        for row in (risks.get("ranked_modules") or [])[:8]:
            top_risks.append(
                {
                    "module": row.get("module_id") or row.get("path"),
                    "score": row.get("total_score"),
                    "tier": row.get("tier"),
                    "fan_in": row.get("fan_in"),
                }
            )
    cache = result.get("cache") or {}
    return {
        "repo_path": repo_path,
        "scan_time_sec": elapsed,
        "cache_hit": bool(cache.get("hit")),
        "ok": result.get("ok"),
        "error": result.get("error"),
        "files_discovered": result.get("files_discovered") or result.get("file_count"),
        "file_count": result.get("file_count"),
        "code_files": result.get("code_files"),
        "module_count": result.get("module_count"),
        "dependency_edges": result.get("dependency_edges"),
        "subsystem_count": result.get("subsystem_count"),
        "graph_health": summary.get("graph_health") or result.get("graph_health"),
        "unresolved_imports": result.get("unresolved_imports"),
        "resolved_imports": result.get("resolved_imports"),
        "unresolved_ratio": result.get("unresolved_ratio"),
        "external_package_imports": result.get("external_package_imports"),
        "import_cycle_count": result.get("import_cycle_count"),
        "graph_scope": result.get("graph_scope"),
        "degraded": result.get("degraded"),
        "language_breakdown": result.get("language_breakdown"),
        "analytics_status": result.get("analytics_status"),
        "top_risks": top_risks,
        "nonproduction_sample_check": _fastapi_scope_check(repo_path, result),
    }


def _fastapi_scope_check(repo_path: str, result: dict) -> dict | None:
    if "fastapi" not in repo_path.lower():
        return None
    graph = api._STATE.get("graph") or {}
    paths = sorted(
        n.get("path", "")
        for n in graph.get("nodes", [])
        if n.get("type") == "module"
    )
    doc_like = [p for p in paths if p.startswith("docs") or "/docs" in p or p.startswith("examples")]
    return {
        "module_paths_in_graph": len(paths),
        "doc_or_example_paths_in_graph": doc_like[:20],
        "doc_or_example_count": len(doc_like),
    }


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for name, path in REPOS.items():
        if not Path(path).is_dir():
            print(f"SKIP {name}: missing {path}")
            continue
        print(f"Scanning {name} …")
        payload = _fresh_scan(path)
        out = OUT_DIR / f"phase116g_{name}_metrics.json"
        out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        print(f"  -> {out} ({payload.get('scan_time_sec')}s, ok={payload.get('ok')})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
