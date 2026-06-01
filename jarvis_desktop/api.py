"""Framework-agnostic product API core for JARVIS Desktop.

Pure functions returning JSON-able dicts, wrapping the existing Builder Core
engine (indexer roles, production-scope dependency graph, architectural risk
ranking). No web framework, no network, no external APIs — so it is fully unit
testable and the desktop server is a thin adapter over this module.

Where a real Builder Core surface is wired it is used directly. Where a surface
is not yet wired (deep bug semantics), a clearly-marked heuristic/mock is used.
Search ``MOCK``/``TODO`` for those spots.
"""

from __future__ import annotations

import os
import re
import time
from typing import Any, Dict, List, Optional, Tuple

from builder_core import architectural_risk, repository_understanding
from builder_core.bug_intelligence import depgraph

PRODUCT_VERSION = "phase110-demo-ready"
CHARS_PER_TOKEN = 4.0
GRAPH_DISPLAY_CAP = 5000
RISK_RANK_TOP = 5000

_CODE_EXTENSIONS = {
    ".py", ".js", ".ts", ".tsx", ".jsx", ".go", ".rs", ".java", ".cs", ".rb",
    ".cpp", ".c", ".h", ".hpp", ".swift", ".kt", ".scala", ".php", ".vue",
}
_DEMO_REPO_PATH = os.path.join(os.path.dirname(__file__), "demo", "sample_repo")

# Directories pruned from the light index walk (keeps scans fast + excludes the
# vendored data corpus, mirroring the depgraph production scope).
_SKIP_DIRS = {
    ".git", "__pycache__", "node_modules", ".venv", "venv", "env", ".env",
    "dist", "build", ".pytest_cache", ".mypy_cache", ".idea", ".vscode",
    "site-packages", ".tox", "target", "vendor", ".next", ".cache", "coverage",
    "htmlcov", ".gradle", ".pytest_tmp", "tests_tmp", "backups", "data",
    ".jarvis_builder", ".jarvis",
}

# Single-repo product state (one repository open at a time).
_STATE: Dict[str, Any] = {
    "path": None,
    "scan": None,
    "graph": None,
    "index": None,
    "risks": None,
    "demo_mode": False,
}


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------
def estimate_tokens(text: str) -> int:
    return max(0, round(len(text or "") / CHARS_PER_TOKEN))


def _read(path: str) -> str:
    try:
        with open(path, "r", encoding="utf-8-sig", errors="ignore") as fh:
            return fh.read()
    except OSError:
        return ""


def _light_index(root: str) -> Dict[str, Any]:
    """Fast index: file roles + subsystem map, WITHOUT the slow per-file analysis.

    Sufficient for ``architectural_risk.rank_modules`` (which tolerates empty
    ``python_analysis``/``churn``) and the product summary.
    """
    root = os.path.abspath(root)
    files: List[Dict[str, Any]] = []
    py_docs: List[Dict[str, str]] = []
    role_counts: Dict[str, int] = {}
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d not in _SKIP_DIRS)
        for name in sorted(filenames):
            abs_path = os.path.join(dirpath, name)
            rel = os.path.relpath(abs_path, root).replace("\\", "/")
            ext = os.path.splitext(name)[1].lower()
            role = repository_understanding.classify_file_role(rel, ext, project_root=root)
            try:
                size = os.path.getsize(abs_path)
            except OSError:
                continue
            text = _read(abs_path) if ext == ".py" and size < 400_000 else ""
            files.append({
                "path": rel,
                "role": role,
                "category": repository_understanding.legacy_category(role, rel),
                "ext": ext,
                "size": size,
                "lines": (text.count("\n") + 1) if text else 0,
            })
            role_counts[role] = role_counts.get(role, 0) + 1
            if role == "production_code" and text:
                py_docs.append({"path": rel, "text": text})
    subsystems = repository_understanding.discover_subsystems(files, py_docs)
    return {
        "project_root": root,
        "files": files,
        "subsystems": subsystems,
        "python_analysis": [],   # skipped for speed; rank_modules tolerates this
        "churn": {},
        "chunks": [],
        "stats": {"files": len(files), "roles": role_counts},
    }


def _short(node_id: str) -> str:
    return node_id.split(":", 1)[1] if ":" in node_id else node_id


# --------------------------------------------------------------------------
# Endpoints
# --------------------------------------------------------------------------
def health() -> Dict[str, Any]:
    scan = _STATE.get("scan") or {}
    return {
        "status": "ok",
        "product": "JARVIS",
        "tagline": "Repository Intelligence Platform",
        "version": PRODUCT_VERSION,
        "repository_open": bool(scan),
        "demo_mode": bool(_STATE.get("demo_mode")),
        "repo_name": scan.get("repo_name"),
    }


def demo_repo_path() -> str:
    return os.path.abspath(_DEMO_REPO_PATH)


def _count_code_files(root: str) -> Tuple[int, int]:
    """Return (total_files, code_files) under root, skipping vendor dirs."""
    total = 0
    code = 0
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d not in _SKIP_DIRS)
        for name in filenames:
            total += 1
            ext = os.path.splitext(name)[1].lower()
            if ext in _CODE_EXTENSIONS:
                code += 1
    return total, code


def validate_repository_path(path: str) -> Dict[str, Any]:
    """Validate a repository path before scan (exists, readable, contains code)."""
    raw = (path or "").strip()
    if not raw:
        return {
            "ok": False,
            "code": "empty_path",
            "error": "Enter a folder path to scan.",
            "warnings": [],
        }
    abspath = os.path.abspath(os.path.expanduser(raw))
    if not os.path.exists(abspath):
        return {
            "ok": False,
            "code": "not_found",
            "error": f"Path does not exist: {abspath}",
            "path": abspath,
            "warnings": [],
        }
    if not os.path.isdir(abspath):
        return {
            "ok": False,
            "code": "not_directory",
            "error": f"Path is not a folder: {abspath}",
            "path": abspath,
            "warnings": [],
        }
    if not os.access(abspath, os.R_OK | os.X_OK):
        return {
            "ok": False,
            "code": "permission_denied",
            "error": f"Cannot read folder (check permissions): {abspath}",
            "path": abspath,
            "warnings": [],
        }
    total_files, code_files = _count_code_files(abspath)
    warnings: List[str] = []
    if code_files == 0:
        return {
            "ok": False,
            "code": "no_code_files",
            "error": "No source code files found in this folder (.py, .js, .ts, .go, …).",
            "path": abspath,
            "name": os.path.basename(abspath) or abspath,
            "total_files": total_files,
            "code_files": code_files,
            "warnings": ["Choose a project root that contains source files."],
        }
    if total_files < 3:
        warnings.append("Very small folder — scan results may be limited.")
    return {
        "ok": True,
        "path": abspath,
        "name": os.path.basename(abspath) or abspath,
        "total_files": total_files,
        "code_files": code_files,
        "warnings": warnings,
    }


def _scan_next_actions(scan: Dict[str, Any]) -> List[str]:
    actions = [
        "Explore the dependency graph in Command Center",
        "Ask Copilot: What does this repository do?",
        "Ask Copilot: What are the top architectural risks?",
    ]
    if scan.get("top_hubs"):
        hub = scan["top_hubs"][0].get("path") or scan["top_hubs"][0].get("module")
        if hub:
            actions.append(f"Ask Copilot: What breaks if I change {hub}?")
    if scan.get("import_cycle_count"):
        actions.append("Ask Copilot: Show import cycles")
    actions.append("Export a compact Claude/Codex/Cursor context packet")
    return actions


def select_repository(path: str) -> Dict[str, Any]:
    validation = validate_repository_path(path)
    if not validation.get("ok"):
        return {
            "ok": False,
            "error": validation.get("error", "Invalid path"),
            "code": validation.get("code", "invalid"),
            "warnings": validation.get("warnings", []),
        }
    abspath = validation["path"]
    _STATE["path"] = abspath
    _STATE["demo_mode"] = False
    return {
        "ok": True,
        "path": abspath,
        "name": validation["name"],
        "code_files": validation.get("code_files", 0),
        "warnings": validation.get("warnings", []),
    }


def load_demo_mode() -> Dict[str, Any]:
    """Load bundled sample repository into product state (clearly labeled demo)."""
    demo_path = demo_repo_path()
    if not os.path.isdir(demo_path):
        return {
            "ok": False,
            "error": "Bundled demo repository is missing.",
            "code": "demo_missing",
        }
    _STATE["demo_mode"] = False
    result = scan_repository(demo_path)
    if not result.get("ok"):
        return result
    _STATE["demo_mode"] = True
    result["demo_mode"] = True
    result["repo_name"] = "JARVIS Demo Sample"
    result["repo_path"] = demo_path
    _STATE["scan"]["demo_mode"] = True
    _STATE["scan"]["repo_name"] = "JARVIS Demo Sample"
    _STATE["scan"]["repo_path"] = demo_path
    return result


def scan_repository(path: Optional[str] = None) -> Dict[str, Any]:
    """Run the real Builder Core scan (graph + light index + risk ranking)."""
    repo = os.path.abspath(path or _STATE.get("path") or ".")
    validation = validate_repository_path(repo)
    if not validation.get("ok"):
        return {
            "ok": False,
            "error": validation.get("error", "Invalid repository path"),
            "code": validation.get("code", "invalid"),
            "warnings": validation.get("warnings", []),
        }
    repo = validation["path"]
    _STATE["demo_mode"] = repo == demo_repo_path()
    started = time.time()

    graph = depgraph.build_graph(repo)               # production scope (Phase 100G)
    index = _light_index(repo)
    module_nodes = [n for n in graph.get("nodes", []) if n.get("type") == "module"]
    module_count = len(module_nodes)
    try:
        risks = architectural_risk.rank_modules(
            index,
            graph,
            top=min(RISK_RANK_TOP, max(module_count, 12)),
        )
    except Exception as exc:  # never crash the product on a risk-engine edge case
        risks = {"ranked_modules": [], "error": f"{type(exc).__name__}: {exc}"}

    stats = graph.get("statistics", {})
    diag = graph.get("scope_diagnostics", {})
    import_edges = [e for e in graph.get("edges", []) if e.get("type") == "imports" and e.get("resolved")]
    unresolved = stats.get("unresolved_counts", {})

    top_hubs = [
        {"module": h.get("dotted") or h.get("path"), "fan_in": h.get("count", 0), "path": h.get("path")}
        for h in stats.get("top_imported_modules", [])[:8]
    ]
    ranked = risks.get("ranked_modules", [])
    top_risks = [
        {
            "module": r.get("label"),
            "path": r.get("path"),
            "score": r.get("total_score"),
            "reasons": r.get("signals", [])[:4],
            "subsystem": r.get("subsystem"),
        }
        for r in ranked[:6]
    ]

    duration = round(time.time() - started, 2)
    top_risk = top_risks[0] if top_risks else {}
    scan = {
        "ok": True,
        "repo_path": repo,
        "repo_name": os.path.basename(repo) or repo,
        "demo_mode": bool(_STATE.get("demo_mode")),
        "file_count": len(index["files"]),
        "files_discovered": diag.get("total_candidate_files", len(module_nodes)),
        "module_count": len(module_nodes),
        "subsystem_count": len(index["subsystems"]),
        "dependency_edges": len(import_edges),
        "unresolved_imports": unresolved.get("imports_external", 0),
        "unresolved_calls": unresolved.get("calls_unresolved", 0),
        "graph_scope": graph.get("graph_scope"),
        "degraded": bool(graph.get("degraded")),
        "import_cycle_count": stats.get("import_cycles") and len(stats["import_cycles"]) or 0,
        "top_hubs": top_hubs,
        "top_risks": top_risks,
        "top_risk_module": top_risk.get("module") or top_risk.get("path") or "",
        "top_risk_score": top_risk.get("score", 0),
        "role_counts": index["stats"]["roles"],
        "scan_duration_seconds": duration,
        "scanned_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "validation_warnings": validation.get("warnings", []),
        "suggested_next_actions": [],
    }
    scan["suggested_next_actions"] = _scan_next_actions(scan)
    # token estimate for the compact AI-context packet built from this scan
    _STATE.update({"path": repo, "scan": scan, "graph": graph, "index": index, "risks": risks})
    scan["compact_token_estimate"] = estimate_tokens(_render_context("claude", "compact"))
    scan["verbose_token_estimate"] = estimate_tokens(_render_context("claude", "verbose"))
    _STATE["scan"]["compact_token_estimate"] = scan["compact_token_estimate"]
    return scan


def current_summary() -> Dict[str, Any]:
    scan = _STATE.get("scan")
    if not scan:
        return {"ok": False, "error": "No repository scanned yet."}
    index = _STATE["index"]
    subsystems = sorted(
        index["subsystems"],
        key=lambda s: (-s.get("role_counts", {}).get("production_code", 0), s.get("name", "")),
    )
    prod = [s for s in subsystems if s.get("role_counts", {}).get("production_code", 0) > 0]
    entry_points: List[str] = []
    for s in prod[:8]:
        for ef in s.get("entry_files", [])[:2]:
            if ef not in entry_points:
                entry_points.append(ef)
    return {
        "ok": True,
        "repo_name": scan["repo_name"],
        "repo_path": scan["repo_path"],
        "demo_mode": bool(scan.get("demo_mode")),
        "file_count": scan["file_count"],
        "module_count": scan["module_count"],
        "subsystem_count": scan["subsystem_count"],
        "dependency_edges": scan["dependency_edges"],
        "graph_scope": scan["graph_scope"],
        "degraded": scan["degraded"],
        "risk_score": _repo_risk_score(),
        "graph_health": _graph_health(scan),
        "token_savings": _token_savings(scan),
        "subsystems": [
            {
                "name": s["name"],
                "production_files": s.get("role_counts", {}).get("production_code", 0),
                "entry_files": s.get("entry_files", [])[:3],
                "dependencies": s.get("dependencies", []),
            }
            for s in prod[:14]
        ],
        "entry_points": entry_points,
        "top_hubs": scan["top_hubs"],
        "top_risks": scan["top_risks"],
        "explanation": _plain_english(scan, prod, entry_points),
        "recommended_questions": _recommended_questions(scan),
    }


def _subsystem_for_path(path: str, index: Dict[str, Any]) -> str:
    """Map a module path to a discovered subsystem name (never fabricated)."""
    if not path:
        return "(root)"
    normalized = path.replace("\\", "/")
    best = ""
    for sub in index.get("subsystems", []):
        name = str(sub.get("name", "")).replace("\\", "/")
        if not name:
            continue
        if normalized == name or normalized.startswith(name + "/"):
            if len(name) > len(best):
                best = name
        for entry in sub.get("entry_files", []):
            entry_norm = str(entry).replace("\\", "/")
            if normalized == entry_norm or normalized.startswith(entry_norm.rsplit("/", 1)[0] + "/"):
                if len(name) > len(best):
                    best = name
    if best:
        return best
    return normalized.split("/")[0] if "/" in normalized else "(root)"


def _risk_lookup(risks: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    return {str(r.get("path", "")): r for r in (risks or {}).get("ranked_modules", []) if r.get("path")}


def _risk_tier(
    *,
    score: float,
    rank: Optional[int],
    max_score: float,
    in_cycle: bool,
) -> str:
    if in_cycle:
        return "cycle"
    if rank and rank <= 5:
        return "top"
    if max_score > 0 and score >= max_score * 0.55:
        return "top"
    if score >= 25 or (max_score > 0 and score >= max_score * 0.3):
        return "elevated"
    return "normal"


def _module_graph_payload(
    graph: Dict[str, Any],
    index: Dict[str, Any],
    risks: Dict[str, Any],
) -> Dict[str, Any]:
    """Build module-level force-graph payload from real depgraph + risk ranking."""
    risk_by_path = _risk_lookup(risks)
    max_score = max((float(r.get("total_score", 0)) for r in risk_by_path.values()), default=0.0)

    fan_in: Dict[str, int] = {}
    fan_out: Dict[str, int] = {}
    for edge in graph.get("edges", []):
        if edge.get("type") != "imports" or not edge.get("resolved"):
            continue
        fan_in[edge["to"]] = fan_in.get(edge["to"], 0) + 1
        fan_out[edge["from"]] = fan_out.get(edge["from"], 0) + 1

    cycle_nodes: set[str] = set()
    for cycle in graph.get("statistics", {}).get("import_cycles", []):
        cycle_nodes.update(cycle)

    nodes: List[Dict[str, Any]] = []
    for node in graph.get("nodes", []):
        if node.get("type") != "module":
            continue
        nid = node["id"]
        path = node.get("path", "")
        risk = risk_by_path.get(path, {})
        score = float(risk.get("total_score", 0))
        rank = risk.get("rank")
        fi = fan_in.get(nid, 0)
        fo = fan_out.get(nid, 0)
        in_cycle = nid in cycle_nodes
        tier = _risk_tier(score=score, rank=rank, max_score=max_score, in_cycle=in_cycle)
        nodes.append(
            {
                "id": nid,
                "label": node.get("dotted") or path,
                "path": path,
                "subsystem": _subsystem_for_path(path, index),
                "fan_in": fi,
                "fan_out": fo,
                "importers_count": fi,
                "imported_modules_count": fo,
                "loc": int(node.get("line_count") or 0),
                "risk_score": round(score, 2),
                "risk_rank": rank,
                "risk_tier": tier,
                "in_cycle": in_cycle,
                "size": round(2.5 + min(22.0, score * 0.22 + fi * 0.08), 2),
            }
        )

    node_ids = {n["id"] for n in nodes}
    links: List[Dict[str, Any]] = []
    for edge in graph.get("edges", []):
        if edge.get("type") != "imports" or not edge.get("resolved"):
            continue
        source, target = edge["from"], edge["to"]
        if source not in node_ids or target not in node_ids:
            continue
        target_fi = fan_in.get(target, 0)
        links.append(
            {
                "source": source,
                "target": target,
                "weight": round(1.0 + min(6.0, target_fi * 0.12), 2),
                "opacity": round(min(0.82, 0.1 + target_fi * 0.025), 3),
            }
        )

    total_modules = len(nodes)
    if total_modules > GRAPH_DISPLAY_CAP:
        nodes.sort(key=lambda item: (-item["risk_score"], -item["fan_in"], item["label"]))
        keep_ids = {n["id"] for n in nodes[:GRAPH_DISPLAY_CAP]}
        nodes = nodes[:GRAPH_DISPLAY_CAP]
        links = [link for link in links if link["source"] in keep_ids and link["target"] in keep_ids]

    return {
        "view": "module",
        "node_count": len(nodes),
        "link_count": len(links),
        "total_modules": total_modules,
        "total_edges": len(
            [e for e in graph.get("edges", []) if e.get("type") == "imports" and e.get("resolved")]
        ),
        "nodes": nodes,
        "links": links,
    }


def _subsystem_graph_payload(
    graph: Dict[str, Any],
    index: Dict[str, Any],
    risks: Dict[str, Any],
) -> Dict[str, Any]:
    """Collapse modules into subsystem hubs using real cross-subsystem import edges."""
    module_payload = _module_graph_payload(graph, index, risks)
    module_by_id = {n["id"]: n for n in module_payload["nodes"]}

    subsystem_nodes: Dict[str, Dict[str, Any]] = {}
    for node in module_payload["nodes"]:
        sub = node["subsystem"]
        bucket = subsystem_nodes.setdefault(
            sub,
            {
                "id": f"subsystem:{sub}",
                "label": sub,
                "path": sub,
                "subsystem": sub,
                "fan_in": 0,
                "fan_out": 0,
                "importers_count": 0,
                "imported_modules_count": 0,
                "loc": 0,
                "risk_score": 0.0,
                "risk_rank": None,
                "risk_tier": "normal",
                "in_cycle": False,
                "module_count": 0,
                "size": 4.0,
            },
        )
        bucket["module_count"] += 1
        bucket["loc"] += node["loc"]
        bucket["fan_in"] += node["fan_in"]
        bucket["fan_out"] += node["fan_out"]
        bucket["risk_score"] = max(bucket["risk_score"], node["risk_score"])
        bucket["in_cycle"] = bucket["in_cycle"] or node["in_cycle"]

    max_score = max((n["risk_score"] for n in subsystem_nodes.values()), default=0.0)
    ranked_subs = sorted(subsystem_nodes.values(), key=lambda s: (-s["risk_score"], s["label"]))
    for rank, sub in enumerate(ranked_subs, 1):
        sub["risk_rank"] = rank
        sub["risk_tier"] = _risk_tier(
            score=sub["risk_score"],
            rank=rank,
            max_score=max_score,
            in_cycle=sub["in_cycle"],
        )
        sub["size"] = round(4.0 + min(28.0, sub["risk_score"] * 0.25 + sub["module_count"] * 0.6), 2)
        sub["importers_count"] = sub["fan_in"]
        sub["imported_modules_count"] = sub["fan_out"]

    edge_weights: Dict[tuple[str, str], int] = {}
    for edge in graph.get("edges", []):
        if edge.get("type") != "imports" or not edge.get("resolved"):
            continue
        src = module_by_id.get(edge["from"])
        dst = module_by_id.get(edge["to"])
        if not src or not dst:
            continue
        src_sub, dst_sub = src["subsystem"], dst["subsystem"]
        if src_sub == dst_sub:
            continue
        key = (src_sub, dst_sub)
        edge_weights[key] = edge_weights.get(key, 0) + 1

    nodes = list(subsystem_nodes.values())
    links = [
        {
            "source": f"subsystem:{src}",
            "target": f"subsystem:{dst}",
            "weight": round(1.0 + min(8.0, count * 0.35), 2),
            "opacity": round(min(0.85, 0.14 + count * 0.04), 3),
            "edge_count": count,
        }
        for (src, dst), count in sorted(edge_weights.items(), key=lambda item: (-item[1], item[0]))
    ]
    return {
        "view": "subsystem",
        "node_count": len(nodes),
        "link_count": len(links),
        "total_modules": module_payload["total_modules"],
        "total_edges": module_payload["total_edges"],
        "nodes": nodes,
        "links": links,
    }


def current_graph(view: str = "module") -> Dict[str, Any]:
    """Graph payload shaped for a 3D force graph (nodes + links)."""
    graph = _STATE.get("graph")
    if not graph:
        return {"ok": False, "error": "No repository scanned yet.", "nodes": [], "links": []}
    index = _STATE.get("index") or {}
    risks = _STATE.get("risks") or {}
    mode = (view or "module").strip().lower()
    payload = (
        _subsystem_graph_payload(graph, index, risks)
        if mode == "subsystem"
        else _module_graph_payload(graph, index, risks)
    )
    return {
        "ok": True,
        "graph_scope": graph.get("graph_scope"),
        "degraded": bool(graph.get("degraded")),
        "view": payload["view"],
        "node_count": payload["node_count"],
        "link_count": payload["link_count"],
        "total_modules": payload["total_modules"],
        "total_edges": payload["total_edges"],
        "display_cap": GRAPH_DISPLAY_CAP,
        "nodes": payload["nodes"],
        "links": payload["links"],
    }


def current_risks() -> Dict[str, Any]:
    risks = _STATE.get("risks")
    if not risks:
        return {"ok": False, "error": "No repository scanned yet.", "ranked_modules": []}
    return {
        "ok": True,
        "graph_scope": _STATE["scan"]["graph_scope"],
        "import_cycles": _STATE["scan"].get("import_cycle_count", 0),
        "ranked_modules": risks.get("ranked_modules", []),
    }


def impact(target: str) -> Dict[str, Any]:
    """Reverse-dependency impact from the real graph (mock fallback if unresolved)."""
    graph = _STATE.get("graph")
    if not graph or not target:
        return _impact_mock(target, reason="No scan / no target")
    target = target.strip().replace("\\", "/")
    nodes = {n["id"]: n for n in graph.get("nodes", []) if n.get("type") == "module"}
    match = None
    for nid, n in nodes.items():
        p = n.get("path", "")
        if p == target or p.endswith("/" + target) or (n.get("dotted") == target):
            match = (nid, n)
            break
    if match is None:
        return _impact_mock(target, reason="Target not found in production graph")
    nid, node = match
    importers = [e["from"] for e in graph.get("edges", [])
                 if e.get("type") == "imports" and e.get("resolved") and e.get("to") == nid]
    affected_files = sorted({nodes[i]["path"] for i in importers if i in nodes})
    affected_subsystems = sorted({(p.split("/")[0] if "/" in p else "(root)") for p in affected_files})
    risk = next((r for r in (_STATE.get("risks") or {}).get("ranked_modules", []) if r.get("path") == node["path"]), {})
    fan_in = len(importers)
    level = "high" if fan_in >= 25 else "medium" if fan_in >= 6 else "low"
    return {
        "ok": True,
        "target": node.get("path"),
        "fan_in": fan_in,
        "risk_level": level,
        "risk_score": risk.get("total_score", 0),
        "affected_files": affected_files[:40],
        "affected_file_count": len(affected_files),
        "affected_subsystems": affected_subsystems,
        "recommended_tests": _recommended_tests(node.get("path", ""), affected_subsystems),
        "recommended_prompt": _impact_prompt(node.get("path", ""), fan_in, affected_subsystems),
        "note": "Static reverse-import impact (resolved edges only); dynamic dispatch not counted.",
    }


def _impact_mock(target: str, reason: str) -> Dict[str, Any]:
    # MOCK / TODO: wire Phase 94B transitive impact engine for full blast radius.
    return {
        "ok": True,
        "mock": True,
        "todo": "Wire Phase 94B impact engine for transitive closure.",
        "target": target,
        "reason": reason,
        "risk_level": "unknown",
        "affected_files": [],
        "affected_subsystems": [],
        "recommended_tests": ["Run the module's own tests and its direct importers' tests."],
        "recommended_prompt": f"Analyze the blast radius of changing `{target}` and list the tests to run.",
    }


def bug_investigation(text: str) -> Dict[str, Any]:
    """Heuristic bug localization from a stack trace / description.

    MOCK/TODO: real semantic localization + verification evidence wiring is future
    work. This v1 matches file/identifier tokens to indexed modules — honest and
    deterministic, with explicit confidence.
    """
    index = _STATE.get("index")
    if not index:
        return {"ok": False, "error": "No repository scanned yet."}
    blob = (text or "")
    paths = [f["path"] for f in index["files"] if f["path"] and f["path"] in blob.replace("\\", "/")]
    # token-level fallback: match basenames / dotted modules mentioned in the text
    lowered = blob.lower()
    if not paths:
        for f in index["files"]:
            base = os.path.basename(f["path"]).lower()
            if base and base.endswith(".py") and base[:-3] in lowered and len(base) > 6:
                paths.append(f["path"])
    paths = sorted(set(paths))[:8]
    confidence = "high" if any(p in blob.replace("\\", "/") for p in paths) else ("medium" if paths else "low")
    return {
        "ok": True,
        "mock": not bool(paths),
        "todo": "Wire semantic localization + verification evidence for confirmed-defect ranking.",
        "likely_modules": paths,
        "evidence": [f"`{p}` referenced in the provided text" for p in paths] or
                    ["No repository path or module name matched the input text."],
        "confidence": confidence,
        "recommended_files": paths,
        "suggested_prompt": _bug_prompt(text, paths),
    }


def context_export(target: str = "claude", packet: str = "compact") -> Dict[str, Any]:
    """Build a copyable, token-estimated AI-context packet for the open repo."""
    if not _STATE.get("scan"):
        return {"ok": False, "error": "No repository scanned yet."}
    target = (target or "claude").lower()
    packet = (packet or "compact").lower()
    if target not in ("claude", "codex", "cursor"):
        target = "claude"
    if packet not in ("compact", "verbose"):
        packet = "compact"
    text = _render_context(target, packet)
    return {
        "ok": True,
        "target": target,
        "packet": packet,
        "estimated_tokens": estimate_tokens(text),
        "text": text,
    }


# --------------------------------------------------------------------------
# Derived intelligence (deterministic, from the scan)
# --------------------------------------------------------------------------
def _repo_risk_score() -> int:
    risks = (_STATE.get("risks") or {}).get("ranked_modules", [])
    if not risks:
        return 0
    top = max((r.get("total_score", 0) for r in risks[:5]), default=0)
    return int(round(top))


def _graph_health(scan: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "scope": scan["graph_scope"],
        "degraded": scan["degraded"],
        "modules": scan["module_count"],
        "edges": scan["dependency_edges"],
        "import_cycles": scan.get("import_cycle_count", 0),
        "unresolved_imports": scan.get("unresolved_imports", 0),
        "label": "healthy" if (not scan["degraded"] and scan.get("import_cycle_count", 0) <= 4) else "watch",
    }


def _token_savings(scan: Dict[str, Any]) -> Dict[str, Any]:
    # Estimated tokens a coding agent would otherwise read to understand the repo
    # (rough: production modules x avg module tokens) vs the compact packet.
    avg_module_tokens = 600
    naive = scan["module_count"] * avg_module_tokens
    compact = scan.get("compact_token_estimate", 0) or 1
    return {
        "naive_read_estimate": naive,
        "compact_packet_tokens": compact,
        "reduction_percent": round(100 * (naive - compact) / naive, 1) if naive else 0,
        "note": "Estimate only (chars/4). The compact packet replaces broad repo reading.",
    }


def _recommended_tests(path: str, subsystems: List[str]) -> List[str]:
    base = os.path.basename(path)[:-3] if path.endswith(".py") else os.path.basename(path)
    tests = [f"tests for `{path}` (e.g. test_{base}.py)"]
    if subsystems:
        tests.append(f"tests in affected subsystems: {', '.join(subsystems[:5])}")
    tests.append("the project's full test suite before merge")
    return tests


def _impact_prompt(target: str, fan_in: int, subsystems: List[str]) -> str:
    subs = ", ".join(subsystems[:6]) or "(none resolved)"
    return (
        f"I am about to change `{target}` (imported by {fan_in} module(s), affecting "
        f"subsystems: {subs}). Review the change for breakage risk: check each direct "
        f"importer's usage, confirm the public interface stays compatible, and list the "
        f"specific tests to run before merge. Flag any dynamic/unresolved usage I should verify manually."
    )


def _bug_prompt(text: str, paths: List[str]) -> str:
    files = ", ".join(f"`{p}`" for p in paths) or "the most relevant modules"
    snippet = (text or "").strip().splitlines()
    head = snippet[0][:160] if snippet else ""
    return (
        f"Investigate this bug. Start with {files}. "
        f"Reported symptom: \"{head}\". For each candidate file, trace the failing path, "
        f"identify the root cause (not just the symptom line), and propose a minimal fix "
        f"with the test that would have caught it. State your confidence and any unknowns."
    )


def _recommended_questions(scan: Dict[str, Any]) -> List[str]:
    qs = [
        "What are the most important production subsystems?",
        "Rank the top architectural-risk modules and explain why.",
    ]
    if scan["top_hubs"]:
        qs.append(f"What is the blast radius of changing {scan['top_hubs'][0]['module']}?")
    if scan.get("import_cycle_count", 0):
        qs.append("Where are the import cycles and how do I break them?")
    qs.append("Prepare a compact context packet for Claude/Codex/Cursor.")
    return qs


def _plain_english(scan: Dict[str, Any], prod: List[Dict[str, Any]], entries: List[str]) -> str:
    names = ", ".join(s["name"] for s in prod[:6]) or "(none detected)"
    hub = scan["top_hubs"][0]["module"] if scan["top_hubs"] else "n/a"
    risk = scan["top_risks"][0]["module"] if scan["top_risks"] else "n/a"
    return (
        f"This repository has {scan['module_count']} production modules across "
        f"{scan['subsystem_count']} top-level subsystems. The largest production "
        f"subsystems are {names}. Its most depended-on module is {hub}, and the "
        f"highest architectural-risk module is {risk}. The dependency graph is "
        f"'{scan['graph_scope']}' with {scan['dependency_edges']} resolved import "
        f"edges and {scan.get('import_cycle_count', 0)} import cycle(s). Entry points "
        f"include {', '.join(entries[:4]) or 'n/a'}."
    )


# --------------------------------------------------------------------------
# Context packet rendering (the product's core value)
# --------------------------------------------------------------------------
_TARGET_PREAMBLE = {
    "claude": "You are assisting with the repository below. Use this precomputed JARVIS repository intelligence as ground truth; read cited files only when you need detail.",
    "codex": "Repository context for Codex. Treat the JARVIS facts below as verified structure; do not re-derive them by scanning the whole repo.",
    "cursor": "Cursor workspace context. JARVIS has pre-analyzed this repo; use these facts to navigate and answer with fewer reads.",
}


def _render_context(target: str, packet: str) -> str:
    scan = _STATE.get("scan")
    index = _STATE.get("index") or {}
    if not scan:
        return ""
    subs = sorted(
        (s for s in index.get("subsystems", []) if s.get("role_counts", {}).get("production_code", 0) > 0),
        key=lambda s: (-s.get("role_counts", {}).get("production_code", 0), s.get("name", "")),
    )
    sub_lines = []
    for s in subs[: (8 if packet == "compact" else 20)]:
        deps = ",".join(s.get("dependencies", [])[:6])
        entry = ",".join(s.get("entry_files", [])[:2])
        sub_lines.append(
            f"- {s['name']} ({s['role_counts'].get('production_code',0)} prod files)"
            + (f"; entry: {entry}" if entry else "")
            + (f"; deps: {deps}" if deps else "")
        )
    hub_lines = [f"- {h['module']} <- {h['fan_in']} importers" for h in scan["top_hubs"][: (5 if packet == "compact" else 8)]]
    risk_lines = [
        f"- {r['module']} (score {r['score']}): {', '.join(r['reasons'][:3])}"
        for r in scan["top_risks"][: (4 if packet == "compact" else 6)]
    ]
    lines = [
        _TARGET_PREAMBLE[target],
        "",
        f"# JARVIS REPOSITORY CONTEXT — {scan['repo_name']}  ({packet})",
        f"scope={scan['graph_scope']} degraded={scan['degraded']}",
        f"modules={scan['module_count']} subsystems={scan['subsystem_count']} "
        f"edges={scan['dependency_edges']} cycles={scan.get('import_cycle_count',0)}",
        "",
        "## PRODUCTION SUBSYSTEMS",
        *sub_lines,
        "",
        "## MOST DEPENDED-ON MODULES (import fan-in)",
        *hub_lines,
        "",
        "## TOP ARCHITECTURAL RISKS",
        *risk_lines,
        "",
        "## UNCERTAINTY",
        "- Fan-in is a static lower bound (dynamic imports/dispatch not counted).",
    ]
    if scan["degraded"]:
        lines.append("- Dependency graph is DEGRADED; treat structure facts as partial.")
    if packet == "verbose":
        lines += [
            "",
            "## ENTRY POINTS",
            *[f"- {e}" for e in (current_summary().get("entry_points", [])[:10])],
        ]
    lines += [
        "",
        "## HOW TO USE",
        "Answer the user's question using these facts first; open a cited file only "
        "if you need its body. Prefer these structured facts over re-scanning the repo.",
    ]
    return "\n".join(lines).strip() + "\n"


# --------------------------------------------------------------------------
# Interactive repository copilot (Phase 109)
# --------------------------------------------------------------------------
def _copilot_copy_targets(packet: str = "compact") -> Dict[str, str]:
    return {
        "claude": _render_context("claude", packet),
        "codex": _render_context("codex", packet),
        "cursor": _render_context("cursor", packet),
    }


def _copilot_envelope(
    mode: str,
    answer: str,
    *,
    evidence: Optional[List[str]] = None,
    files: Optional[List[str]] = None,
    risk_level: str = "unknown",
    suggested_prompt: str = "",
    suggested_action: str = "",
    confidence: str = "high",
    limitations: Optional[List[str]] = None,
    packet: str = "compact",
) -> Dict[str, Any]:
    return {
        "ok": True,
        "mode": mode,
        "answer": answer,
        "evidence": evidence or [],
        "files": files or [],
        "risk_level": risk_level,
        "suggested_prompt": suggested_prompt,
        "suggested_action": suggested_action,
        "copy_targets": _copilot_copy_targets(packet),
        "confidence": confidence,
        "limitations": limitations or [],
    }


def classify_copilot_question(question: str) -> str:
    """Deterministic intent routing for copilot questions."""
    q = (question or "").strip().lower()
    if not q:
        return "unknown"
    if any(token in q for token in ("claude", "codex", "cursor", "context packet", "generate a prompt", "generate prompt")):
        return "context_export"
    if "prompt" in q and any(token in q for token in ("generate", "copy", "prepare", "export")):
        return "context_export"
    if any(token in q for token in ("cycle", "circular", "import loop")):
        return "cycles"
    if any(token in q for token in ("who imports", "importers", "imported by", "imports this")):
        return "dependency"
    if any(token in q for token in ("what breaks", "blast radius", "impact of", "if i change", "what tests")):
        return "impact"
    if "change " in q or "changing " in q:
        return "impact"
    if any(token in q for token in ("risk", "dangerous", "bottleneck", "architectural risk")):
        return "risk"
    if any(token in q for token in ("what does this", "what does the repo", "repository do", "where should i start", "where to start", "entry point")):
        return "repository_understanding"
    if any(token in q for token in ("architecture", "subsystem", "subsystems", "explain module", "explain this module")):
        return "repository_understanding"
    if any(token in q for token in ("dependenc", "depend on")):
        return "dependency"
    return "unknown"


def _extract_path_from_question(question: str) -> Optional[str]:
    text = (question or "").replace("\\", "/")
    match = re.search(r"[\w./-]+\.py\b", text)
    if match:
        return match.group(0).strip("`'\"")
    match = re.search(r"change\s+([\w./-]+)", text, re.I)
    if match:
        candidate = match.group(1).strip("`'\"")
        if candidate.endswith(".py") or "/" in candidate:
            return candidate
    return None


def _extract_subsystem_from_question(question: str) -> Optional[str]:
    index = _STATE.get("index") or {}
    q = (question or "").lower()
    best = ""
    best_name = ""
    for sub in index.get("subsystems", []):
        name = str(sub.get("name", ""))
        if not name:
            continue
        if name.lower() in q and len(name) > len(best):
            best = name.lower()
            best_name = name
    return best_name or None


def _resolve_module_path(question: str, node_context: Optional[Dict[str, Any]] = None) -> Optional[str]:
    if node_context and node_context.get("path"):
        return str(node_context["path"])
    extracted = _extract_path_from_question(question)
    if extracted:
        return extracted
    graph = _STATE.get("graph") or {}
    q = (question or "").lower()
    for node in graph.get("nodes", []):
        if node.get("type") != "module":
            continue
        path = str(node.get("path", ""))
        label = str(node.get("dotted") or path)
        base = path.split("/")[-1].lower()
        if path and path.lower() in q:
            return path
        if base and base in q:
            return path
        if label.lower() in q:
            return path
    return None


def node_copilot_prompts(node: Dict[str, Any]) -> List[str]:
    path = str(node.get("path") or node.get("label") or "this module")
    return [
        f"Explain module {path}",
        f"What breaks if I change {path}?",
        f"Who imports {path}?",
        f"Generate a Claude prompt for {path}",
    ]


def _module_graph_neighbors(path: str) -> Tuple[Optional[Dict[str, Any]], List[str], List[str]]:
    graph = _STATE.get("graph") or {}
    nodes = {n["id"]: n for n in graph.get("nodes", []) if n.get("type") == "module"}
    match: Optional[Tuple[str, Dict[str, Any]]] = None
    for nid, node in nodes.items():
        node_path = str(node.get("path", ""))
        if node_path == path or node_path.endswith("/" + path) or path.endswith(node_path):
            match = (nid, node)
            break
    if match is None:
        return None, [], []
    nid, node = match
    importers: List[str] = []
    imports: List[str] = []
    for edge in graph.get("edges", []):
        if edge.get("type") != "imports" or not edge.get("resolved"):
            continue
        if edge.get("to") == nid and edge.get("from") in nodes:
            importers.append(nodes[edge["from"]]["path"])
        if edge.get("from") == nid and edge.get("to") in nodes:
            imports.append(nodes[edge["to"]]["path"])
    return node, sorted(set(importers)), sorted(set(imports))


def _answer_repository_understanding(question: str, packet: str) -> Dict[str, Any]:
    summary = current_summary()
    scan = _STATE.get("scan") or {}
    sub_name = _extract_subsystem_from_question(question)
    limitations: List[str] = []
    if sub_name:
        sub = next((s for s in summary.get("subsystems", []) if s.get("name") == sub_name), None)
        if sub:
            answer = (
                f"Subsystem `{sub_name}` contains {sub.get('production_files', 0)} production file(s). "
                f"Entry files: {', '.join(sub.get('entry_files') or []) or 'none listed'}. "
                f"Cross-subsystem dependencies: {', '.join(sub.get('dependencies') or []) or 'none detected'}."
            )
            evidence = [
                f"subsystem={sub_name}",
                f"production_files={sub.get('production_files', 0)}",
            ]
            files = list(sub.get("entry_files") or [])[:6]
            return _copilot_envelope(
                "repository_understanding",
                answer,
                evidence=evidence,
                files=files,
                risk_level="low",
                suggested_prompt=f"Explain the role of subsystem `{sub_name}` in this repository and how its entry files connect to the rest of the codebase.",
                suggested_action=f"Open entry files under `{sub_name}` and trace their imports.",
                confidence="high",
                limitations=limitations,
                packet=packet,
            )
        limitations.append(f"Subsystem `{sub_name}` was mentioned but not found in the scan index.")
    if "start" in question.lower():
        entries = summary.get("entry_points") or []
        answer = (
            "Start with the detected entry points, then follow import hubs. "
            f"Suggested entry files: {', '.join(entries[:6]) or 'none detected'}."
        )
        suggested_action = f"Inspect {entries[0]}" if entries else "Scan subsystems in Project Intelligence."
    else:
        answer = summary.get("explanation") or "No repository summary available."
        suggested_action = "Review subsystems and top hubs in Project Intelligence."
    return _copilot_envelope(
        "repository_understanding",
        answer,
        evidence=[
            f"modules={scan.get('module_count', 0)}",
            f"subsystems={scan.get('subsystem_count', 0)}",
            f"graph_scope={scan.get('graph_scope', '')}",
        ],
        files=(summary.get("entry_points") or [])[:8],
        risk_level="low",
        suggested_prompt=_render_context("claude", packet)[:800] + ("…" if len(_render_context("claude", packet)) > 800 else ""),
        suggested_action=suggested_action,
        confidence="high",
        limitations=limitations,
        packet=packet,
    )


def _answer_risk(packet: str) -> Dict[str, Any]:
    risks = current_risks()
    ranked = risks.get("ranked_modules") or []
    if not ranked:
        return _copilot_envelope(
            "risk",
            "No architectural risk ranking is available for this scan.",
            confidence="low",
            limitations=["Risk engine returned no ranked modules."],
            packet=packet,
        )
    lines = []
    evidence = []
    files = []
    for item in ranked[:8]:
        path = item.get("path", "")
        lines.append(
            f"{item.get('rank', '?')}. {item.get('label', path)} — score {item.get('total_score', 0)} "
            f"(fan-in={item.get('metrics', {}).get('fan_in', 0)})"
        )
        evidence.extend((item.get("signals") or [])[:2])
        if path:
            files.append(path)
    top_score = ranked[0].get("total_score", 0)
    risk_level = "high" if top_score >= 25 else "medium" if top_score >= 10 else "low"
    answer = "Top architectural-risk modules (production scope):\n" + "\n".join(lines)
    return _copilot_envelope(
        "risk",
        answer,
        evidence=evidence[:10],
        files=files[:10],
        risk_level=risk_level,
        suggested_prompt=(
            "Review the top architectural-risk modules below and explain which signals "
            "are structural vs. which could be challenged with better tests or refactors:\n"
            + answer
        ),
        suggested_action="Open the highest-ranked module and inspect its importers and test coverage.",
        confidence="high",
        limitations=["Ranking uses static import graph evidence; dynamic dispatch is not counted."],
        packet=packet,
    )


def _answer_impact(question: str, node_context: Optional[Dict[str, Any]], packet: str) -> Dict[str, Any]:
    target = _resolve_module_path(question, node_context)
    if not target:
        return _copilot_envelope(
            "impact",
            "Name a file or module to analyze (for example `config.py` or `core/logger.py`).",
            confidence="low",
            suggested_action="Ask: What breaks if I change config.py?",
            limitations=["No target path could be resolved from the question."],
            packet=packet,
        )
    payload = impact(target)
    if payload.get("mock"):
        return _copilot_envelope(
            "impact",
            f"Could not resolve `{target}` in the production graph ({payload.get('reason', 'unknown')}).",
            files=[target],
            risk_level="unknown",
            suggested_prompt=payload.get("recommended_prompt", ""),
            suggested_action="Verify the path exists in the scanned repository.",
            confidence="low",
            limitations=[payload.get("todo", ""), payload.get("reason", "")],
            packet=packet,
        )
    answer = (
        f"Changing `{payload['target']}` affects {payload['affected_file_count']} direct importer(s) "
        f"across subsystems: {', '.join(payload.get('affected_subsystems') or []) or 'none'}."
    )
    return _copilot_envelope(
        "impact",
        answer,
        evidence=[
            f"fan_in={payload.get('fan_in', 0)}",
            payload.get("note", ""),
        ],
        files=(payload.get("affected_files") or [])[:20],
        risk_level=str(payload.get("risk_level", "unknown")),
        suggested_prompt=str(payload.get("recommended_prompt", "")),
        suggested_action="Run the recommended tests before merging the change.",
        confidence="high" if payload.get("affected_file_count") else "medium",
        limitations=["Direct importers only; transitive impact engine (Phase 94B) not wired."],
        packet=packet,
    )


def _answer_cycles(packet: str) -> Dict[str, Any]:
    graph = _STATE.get("graph") or {}
    cycles = (graph.get("statistics") or {}).get("import_cycles") or []
    if not cycles:
        return _copilot_envelope(
            "cycles",
            "No import cycles were detected in the production dependency graph.",
            evidence=[f"graph_scope={graph.get('graph_scope', '')}"],
            risk_level="low",
            suggested_action="Review top fan-in modules instead.",
            confidence="high",
            packet=packet,
        )
    lines = []
    files: List[str] = []
    for index, cycle in enumerate(cycles[:8], 1):
        members = cycle if isinstance(cycle, list) else cycle.get("members", [])
        shown = [str(item).replace("module:", "") for item in members[:6]]
        lines.append(f"Cycle {index}: {' -> '.join(shown)}")
        for item in members:
            path = str(item).split(":", 1)[-1]
            if path.endswith(".py"):
                files.append(path)
    answer = f"Found {len(cycles)} import cycle(s):\n" + "\n".join(lines)
    return _copilot_envelope(
        "cycles",
        answer,
        evidence=[f"cycle_count={len(cycles)}"],
        files=sorted(set(files))[:12],
        risk_level="medium" if len(cycles) <= 3 else "high",
        suggested_prompt="Help me break these import cycles with the smallest safe refactor plan.",
        suggested_action="Pick one cycle and remove the weakest dependency edge first.",
        confidence="high",
        limitations=["Cycles are computed on resolved import edges only."],
        packet=packet,
    )


def _answer_dependency(question: str, node_context: Optional[Dict[str, Any]], packet: str) -> Dict[str, Any]:
    target = _resolve_module_path(question, node_context)
    if not target:
        return _copilot_envelope(
            "dependency",
            "Specify a module path to inspect importers and imports.",
            confidence="low",
            suggested_action="Ask: Who imports builder_core/ask.py?",
            packet=packet,
        )
    node, importers, imports = _module_graph_neighbors(target)
    if node is None:
        return _copilot_envelope(
            "dependency",
            f"`{target}` was not found in the production module graph.",
            files=[target],
            confidence="low",
            limitations=["Target not indexed as a production module."],
            packet=packet,
        )
    answer = (
        f"Module `{node.get('path')}` is imported by {len(importers)} module(s) and imports "
        f"{len(imports)} resolved module(s)."
    )
    if importers:
        answer += "\nImporters: " + ", ".join(importers[:12])
    if imports:
        answer += "\nImports: " + ", ".join(imports[:12])
    return _copilot_envelope(
        "dependency",
        answer,
        evidence=[
            f"fan_in={len(importers)}",
            f"fan_out={len(imports)}",
        ],
        files=([node.get("path", "")] + importers + imports)[:20],
        risk_level="high" if len(importers) >= 25 else "medium" if len(importers) >= 6 else "low",
        suggested_prompt=f"Explain how `{node.get('path')}` is used across the repository based on these importers and imports.",
        suggested_action="Inspect the top importer modules before changing this file.",
        confidence="high",
        limitations=["Unresolved/dynamic imports are not included."],
        packet=packet,
    )


def _answer_context_export(question: str, packet: str) -> Dict[str, Any]:
    targets = _copilot_copy_targets(packet)
    primary = "claude"
    q = question.lower()
    if "codex" in q:
        primary = "codex"
    elif "cursor" in q:
        primary = "cursor"
    tokens = estimate_tokens(targets[primary])
    answer = (
        f"Generated a {packet} JARVIS context packet (~{tokens} tokens) for {primary.title()}. "
        "Use the copy buttons to paste into your assistant."
    )
    return _copilot_envelope(
        "context_export",
        answer,
        evidence=[f"packet={packet}", f"estimated_tokens={tokens}"],
        risk_level="low",
        suggested_prompt=targets[primary],
        suggested_action=f"Copy the {primary.title()} prompt and attach your follow-up question.",
        confidence="high",
        limitations=["Context is deterministic from the scan; it is not a live LLM answer."],
        packet=packet,
    )


def _answer_unknown(question: str, packet: str) -> Dict[str, Any]:
    scan = _STATE.get("scan") or {}
    suggestions = _recommended_questions(scan)
    answer = (
        "I could not map that question to a grounded analysis mode. "
        "Try one of the suggested questions below."
    )
    return _copilot_envelope(
        "unknown",
        answer,
        evidence=[f"question={question[:120]}"],
        risk_level="unknown",
        suggested_prompt=suggestions[0] if suggestions else "What does this repository do?",
        suggested_action="Pick a suggested question or name a specific file path.",
        confidence="low",
        limitations=["Question did not match deterministic routing rules."],
        packet=packet,
    )


def copilot_ask(
    question: str,
    target: str = "none",
    packet: str = "compact",
    *,
    node_context: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Answer repository questions using deterministic Builder Core scan outputs."""
    if not _STATE.get("scan"):
        return {
            "ok": False,
            "error": "No repository scanned yet.",
            "mode": "unknown",
            "answer": "",
            "evidence": [],
            "files": [],
            "risk_level": "unknown",
            "suggested_prompt": "",
            "suggested_action": "",
            "copy_targets": {"claude": "", "codex": "", "cursor": ""},
            "confidence": "low",
            "limitations": ["Scan a repository first."],
        }
    packet = (packet or "compact").lower()
    if packet not in ("compact", "verbose"):
        packet = "compact"
    _ = (target or "none").lower()  # reserved for future primary copy target preference

    mode = classify_copilot_question(question)
    if node_context and mode == "unknown":
        q = question.lower()
        if "impact" in q or "break" in q or "change" in q:
            mode = "impact"
        elif "import" in q:
            mode = "dependency"
        elif "explain" in q or "module" in q:
            mode = "repository_understanding"
        elif "prompt" in q or "claude" in q:
            mode = "context_export"

    if mode == "repository_understanding":
        return _answer_repository_understanding(question, packet)
    if mode == "risk":
        return _answer_risk(packet)
    if mode == "impact":
        return _answer_impact(question, node_context, packet)
    if mode == "cycles":
        return _answer_cycles(packet)
    if mode == "dependency":
        return _answer_dependency(question, node_context, packet)
    if mode == "context_export":
        return _answer_context_export(question, packet)
    return _answer_unknown(question, packet)
