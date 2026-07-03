"""Phase 134 — Architectural intelligence analyzer.

Turns the raw dependency graph into architectural understanding: a multi-component
risk model (NOT raw centrality), hubs vs. risks separation, architectural pattern
detection, and unresolved-import classification. Pure functions over the scanned
graph — no LLM, no network, no new catalogs.
"""

from __future__ import annotations

import os
import re
from typing import Any, Dict, List, Optional, Set, Tuple

# Standard library roots (used to classify unresolved imports as stdlib/external).
_STDLIB = {
    "os", "sys", "re", "json", "typing", "collections", "itertools", "functools",
    "datetime", "time", "math", "abc", "enum", "io", "pathlib", "asyncio", "inspect",
    "logging", "warnings", "contextlib", "dataclasses", "types", "copy", "uuid",
    "hashlib", "base64", "http", "urllib", "decimal", "string", "traceback", "secrets",
    "importlib", "threading", "subprocess", "tempfile", "shutil", "glob", "random",
    "socket", "struct", "weakref", "operator", "email", "html", "ssl", "queue",
    "concurrent", "multiprocessing", "signal", "select", "array", "bisect", "heapq",
    "gzip", "zipfile", "tarfile", "csv", "sqlite3", "unittest", "argparse", "configparser",
    "textwrap", "difflib", "pprint", "numbers", "fractions", "statistics", "platform",
    "ctypes", "gc", "atexit", "builtins", "binascii", "codecs", "locale", "calendar",
}

# Runtime-boundary path markers — modules on the request/event/state critical path.
_RUNTIME_BOUNDARY = (
    "/core.py", "core.py", "eventbus", "/helpers/event.py", "/helpers/dispatcher.py",
    "statemachine", "state_machine", "websocket_api", "/http/", "/auth/", "/recorder/",
    "service", "bootstrap.py", "config_entries.py", "/loader.py", "/setup.py",
)

# Modules whose blast radius is mostly config/constants — high fan-in but NOT runtime
# logic. They should be flagged as hubs, not automatically as the top architectural risk.
_CONFIG_BASENAMES = {"const.py", "constants.py", "config.py", "manifest.json", "consts.py"}
_CONFIG_MARKERS = ("/const", "/constants", "/config", "/manifest")


def _norm(p: str) -> str:
    return (p or "").replace("\\", "/")


def _layer(path: str) -> str:
    """Architectural subsystem at a useful granularity (top-2 path segments;
    top-3 under a `components`/`integrations` dir so each integration is its own)."""
    n = _norm(path)
    parts = n.split("/")
    if len(parts) >= 3 and parts[1] in ("components", "integrations", "plugins"):
        return "/".join(parts[:3])
    if len(parts) >= 2:
        return "/".join(parts[:2])
    return parts[0] if parts else ""


def _basename(path: str) -> str:
    return os.path.basename(_norm(path))


def _is_config_module(path: str) -> bool:
    p = _norm(path).lower()
    return _basename(p) in _CONFIG_BASENAMES or any(m in p for m in _CONFIG_MARKERS)


def _is_runtime_boundary(path: str) -> bool:
    p = _norm(path).lower()
    return any(m in p for m in _RUNTIME_BOUNDARY)


def _percentile_ranks(values: Dict[str, float]) -> Dict[str, float]:
    """Map id -> percentile rank in [0,1] (ties share the lower rank)."""
    if not values:
        return {}
    ordered = sorted(values.items(), key=lambda kv: kv[1])
    n = len(ordered)
    out: Dict[str, float] = {}
    for i, (k, _) in enumerate(ordered):
        out[k] = i / (n - 1) if n > 1 else 0.0
    return out


def _module_nodes(graph: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    return {n["id"]: n for n in graph.get("nodes", [])
            if n.get("type") == "module" and n.get("path")}


def _internal_roots(nodes: Dict[str, Dict[str, Any]]) -> Set[str]:
    roots: Set[str] = set()
    for n in nodes.values():
        p = _norm(n.get("path"))
        seg = p.split("/")[0]
        if seg and not seg.endswith(".py"):
            roots.add(seg)
        dotted = (n.get("dotted") or "")
        if dotted:
            roots.add(dotted.split(".")[0])
    return roots


# --------------------------------------------------------------------------
# Unresolved import classification (Phase 134 — builder_core)
# --------------------------------------------------------------------------
def classify_unresolved(
    graph: Dict[str, Any],
    nodes: Optional[Dict[str, Dict[str, Any]]] = None,
    *,
    index: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    from builder_core import unresolved_imports as ui

    payload = ui.classify_graph_unresolved(graph, index)
    breakdown = payload.get("breakdown") or {}
    buckets = {
        "external_dependency": breakdown.get("external_dependency", 0),
        "optional_dependency": breakdown.get("optional_dependency", 0),
        "dynamic_import": breakdown.get("dynamic_import", 0),
        "internal_missing": breakdown.get("internal_missing", 0),
        "relative_resolution_issue": breakdown.get("relative_resolution_issue", 0),
        "namespace_package": breakdown.get("namespace_package", 0),
        "test_or_dev_only": breakdown.get("test_or_dev_only", 0),
    }
    per_module_internal: Dict[str, int] = {}
    for entry in payload.get("entries") or []:
        label = entry.get("classification")
        if label not in ("internal_missing", "relative_resolution_issue"):
            continue
        path = _norm(entry.get("from_module") or "")
        if path:
            per_module_internal[path] = per_module_internal.get(path, 0) + 1
    samples: Dict[str, List[str]] = {k: [] for k in buckets}
    for entry in (payload.get("entries") or [])[:200]:
        label = entry.get("classification") or "external_dependency"
        if label in samples and len(samples[label]) < 6:
            samples[label].append(str(entry.get("target") or "?"))

    internal_unresolved = int(payload.get("internal_unresolved_count", 0))
    external_unresolved = int(payload.get("external_dependency_count", 0))
    return {
        "total": int(payload.get("total", 0)),
        "buckets": buckets,
        "samples": samples,
        "internal_unresolved": internal_unresolved,
        "external_unresolved": external_unresolved,
        "dynamic_import_count": breakdown.get("dynamic_import", 0),
        "per_module_internal": per_module_internal,
        "note": (
            "Graph health weights internal_missing and relative_resolution_issue; "
            "external_dependency and dynamic_import are expected in large apps."
        ),
    }


def _cycle_membership(graph: Dict[str, Any], nodes: Dict[str, Dict[str, Any]]) -> Tuple[Set[str], Dict[str, int]]:
    """Return (set of node ids in any cycle, node_id -> largest cycle size it is in)."""
    in_cycle: Set[str] = set()
    cluster_size: Dict[str, int] = {}
    by_path = {_norm(n.get("path")): nid for nid, n in nodes.items()}
    for cyc in graph.get("statistics", {}).get("import_cycles", []) or []:
        members = cyc if isinstance(cyc, list) else (cyc.get("modules") or cyc.get("cycle") or [])
        ids = []
        for m in members:
            mid = m if m in nodes else by_path.get(_norm(m))
            if mid:
                ids.append(mid)
        for mid in ids:
            in_cycle.add(mid)
            cluster_size[mid] = max(cluster_size.get(mid, 0), len(ids))
    return in_cycle, cluster_size


def analyze(graph: Dict[str, Any], *, index: Optional[Dict[str, Any]] = None,
            risks: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    nodes = _module_nodes(graph)
    if not nodes:
        return {"ok": False, "reason": "no module nodes"}

    # 1. fan-in / fan-out + cross-subsystem (boundary) counts from resolved edges.
    fan_in: Dict[str, int] = {nid: 0 for nid in nodes}
    fan_out: Dict[str, int] = {nid: 0 for nid in nodes}
    boundary: Dict[str, int] = {nid: 0 for nid in nodes}
    subsystems_touched: Dict[str, Set[str]] = {nid: set() for nid in nodes}
    for e in graph.get("edges", []):
        if e.get("type") != "imports" or not e.get("resolved"):
            continue
        src, dst = e.get("from"), e.get("to")
        if src not in nodes or dst not in nodes:
            continue
        fan_out[src] += 1
        fan_in[dst] += 1
        ls, ld = _layer(nodes[src]["path"]), _layer(nodes[dst]["path"])
        if ls != ld:
            boundary[src] += 1
            boundary[dst] += 1
            subsystems_touched[src].add(ld)
            subsystems_touched[dst].add(ls)

    in_cycle, cluster_size = _cycle_membership(graph, nodes)
    unresolved = classify_unresolved(graph, nodes, index=index)
    unres_internal_by_path = unresolved["per_module_internal"]

    # 2. percentile-normalize the raw signals.
    pin = _percentile_ranks(fan_in)
    pout = _percentile_ranks(fan_out)
    pbound = _percentile_ranks(boundary)
    locs = {nid: float(n.get("line_count") or 0) for nid, n in nodes.items()}
    ploc = _percentile_ranks(locs)

    modules: List[Dict[str, Any]] = []
    for nid, n in nodes.items():
        path = _norm(n.get("path"))
        fi, fo = fan_in[nid], fan_out[nid]
        instability = fo / (fi + fo) if (fi + fo) else 0.0
        config_mod = _is_config_module(path)
        runtime = _is_runtime_boundary(path) and not config_mod
        god = pin.get(nid, 0) > 0.9 and pout.get(nid, 0) > 0.82 and ploc.get(nid, 0) > 0.6
        n_subs = len(subsystems_touched[nid])
        uint = unres_internal_by_path.get(path, 0)

        # Risk components (each ~0..1).
        centrality_risk = pin.get(nid, 0.0)
        coupling_risk = min(1.0, 0.6 * pout.get(nid, 0.0) + 0.4 * instability + (0.25 if god else 0.0))
        boundary_risk = min(1.0, 0.7 * pbound.get(nid, 0.0) + 0.3 * min(1.0, n_subs / 8.0)
                            + (0.3 if runtime else 0.0))
        cyc_sz = cluster_size.get(nid, 0)
        cycle_risk = min(1.0, (0.6 + min(0.4, cyc_sz / 10.0)) if nid in in_cycle else 0.0)
        unresolved_risk = min(1.0, uint / 8.0)
        runtime_criticality = 0.0
        if runtime:
            runtime_criticality = min(1.0, 0.5 + 0.5 * pin.get(nid, 0.0))

        # Weighted architectural risk — centrality is deliberately NOT dominant, so a
        # pure config/const hub does not become the top risk on fan-in alone.
        arch_risk = (
            0.16 * centrality_risk
            + 0.22 * coupling_risk
            + 0.22 * boundary_risk
            + 0.15 * cycle_risk
            + 0.07 * unresolved_risk
            + 0.18 * runtime_criticality
        )
        if config_mod:
            arch_risk *= 0.6  # config/const blast is mostly recompiles, not logic breakage
        if god:
            arch_risk = min(1.0, arch_risk + 0.1)

        # Confidence: how complete is this module's local graph view.
        local_unres = uint
        local_total = fo + local_unres
        confidence = "high" if local_total == 0 or local_unres / max(1, local_total) < 0.2 else (
            "medium" if local_unres / max(1, local_total) < 0.5 else "low")

        modules.append({
            "id": nid, "path": path, "dotted": n.get("dotted"),
            "layer": _layer(path), "fan_in": fi, "fan_out": fo,
            "instability": round(instability, 3), "loc": int(locs[nid]),
            "in_cycle": nid in in_cycle, "cycle_size": cyc_sz,
            "subsystems_touched": n_subs, "boundary_edges": boundary[nid],
            "is_config": config_mod, "is_runtime_boundary": runtime, "is_god_module": god,
            "unresolved_internal": uint,
            "risk_score": round(arch_risk * 100, 1),
            "risk_components": {
                "centrality": round(centrality_risk, 3),
                "coupling": round(coupling_risk, 3),
                "boundary": round(boundary_risk, 3),
                "cycle": round(cycle_risk, 3),
                "unresolved": round(unresolved_risk, 3),
                "runtime_criticality": round(runtime_criticality, 3),
            },
            "risk_confidence": confidence,
            "patterns": _detect_patterns(
                path, index, fi, fo, int(locs[nid]), n_subs, nid in in_cycle
            ),
        })

    # 3. Rankings — hubs (depended-on) vs risks (dangerous to change) are computed
    #    from DIFFERENT orderings and are not identical by construction.
    by_fan_in = sorted(modules, key=lambda m: (-m["fan_in"], m["path"]))
    by_risk = sorted(modules, key=lambda m: (-m["risk_score"], -m["boundary_edges"], m["path"]))
    by_boundary = sorted(modules, key=lambda m: (-m["boundary_edges"], -m["subsystems_touched"], m["path"]))

    top_hubs = [_hub_view(m) for m in by_fan_in[:10]]
    top_risks = [_risk_view(m) for m in by_risk[:10]]
    top_boundaries = [_boundary_view(m) for m in by_boundary[:8] if m["boundary_edges"] > 0]

    cycles = _cycle_clusters(graph, nodes)
    patterns_index = _aggregate_patterns(modules)
    dynamic_zones = _dynamic_zones(modules)
    module_paths = [m["path"] for m in modules]
    try:
        from atlas_desktop import architecture_patterns as ap

        arch_summary = ap.architecture_summary_for_repo(
            module_paths,
            patterns_by_path={m["path"]: m["patterns"] for m in modules},
        )
    except Exception:
        arch_summary = {}
    hubs_set = {h["path"] for h in top_hubs[:6]}
    risks_set = {r["path"] for r in top_risks[:6]}
    overlap = len(hubs_set & risks_set)

    return {
        "ok": True,
        "module_count": len(modules),
        "top_hubs": top_hubs,
        "top_risks": top_risks,
        "top_boundaries": top_boundaries,
        "cycles": cycles,
        "patterns": patterns_index,
        "dynamic_zones": dynamic_zones,
        "unresolved": unresolved,
        "hubs_risks_overlap": overlap,
        "hubs_risks_identical": [h["path"] for h in top_hubs[:6]] == [r["path"] for r in top_risks[:6]],
        "modules_by_path": {m["path"]: m for m in modules},
        "architecture_summary": arch_summary,
        "top_cycles": cycles[:8],
        "graph_health_reason": unresolved.get("note", ""),
    }


def _read_source(index: Optional[Dict[str, Any]], path: str) -> str:
    if not index:
        return ""
    root = index.get("project_root") or ""
    if not root:
        return ""
    full = os.path.join(root, path)
    try:
        with open(full, "r", encoding="utf-8-sig", errors="ignore") as fh:
            return fh.read(12000)
    except OSError:
        return ""


def _detect_patterns(
    path: str,
    index: Optional[Dict[str, Any]],
    fi: int,
    fo: int,
    line_count: int,
    n_subs: int,
    in_cycle: bool,
) -> List[str]:
    from atlas_desktop import architecture_patterns as ap

    return ap.detect_patterns(
        path,
        source=_read_source(index, path),
        fan_in=fi,
        fan_out=fo,
        line_count=line_count,
        subsystems_touched=n_subs,
        in_cycle=in_cycle,
    )


def _aggregate_patterns(modules: List[Dict[str, Any]]) -> Dict[str, List[str]]:
    idx: Dict[str, List[str]] = {}
    for m in modules:
        for pat in m["patterns"]:
            idx.setdefault(pat, [])
            if len(idx[pat]) < 12:
                idx[pat].append(m["path"])
    return dict(sorted(idx.items(), key=lambda kv: -len(kv[1])))


def _dynamic_zones(modules: List[Dict[str, Any]]) -> List[str]:
    # Integration/plugin packages are dynamically loaded by string in HA-style apps.
    zones = sorted({m["layer"] for m in modules
                    if "integration_module" in m["patterns"] or "plugin_loader" in m["patterns"]})
    return zones[:20]


def _cycle_clusters(graph: Dict[str, Any], nodes: Dict[str, Dict[str, Any]]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for cyc in (graph.get("statistics", {}).get("import_cycles") or [])[:10]:
        members = cyc if isinstance(cyc, list) else (cyc.get("modules") or cyc.get("cycle") or [])
        paths = []
        for m in members:
            if m in nodes:
                paths.append(_norm(nodes[m]["path"]))
            else:
                paths.append(_norm(m))
        if paths:
            out.append({"size": len(paths), "members": paths[:8]})
    return out


def _hub_view(m: Dict[str, Any]) -> Dict[str, Any]:
    return {"module": m["dotted"] or m["path"], "path": m["path"], "fan_in": m["fan_in"],
            "fan_out": m["fan_out"], "reason": f"depended on by {m['fan_in']} module(s)"}


def _risk_view(m: Dict[str, Any]) -> Dict[str, Any]:
    rc = m["risk_components"]
    drivers = sorted(rc.items(), key=lambda kv: -kv[1])[:3]
    why = ", ".join(f"{k.replace('_', ' ')} {v:.2f}" for k, v in drivers if v > 0.05) or "low overall"
    try:
        from atlas_desktop import architecture_patterns as ap

        cls = ap.hub_vs_risk_classification(m["path"], m["patterns"], fan_in=m["fan_in"])
    except Exception:
        cls = {}
    return {
        "module": m["dotted"] or m["path"], "path": m["path"], "score": m["risk_score"],
        "components": rc,
        "risk_components": rc,
        "confidence": m["risk_confidence"],
        "risk_confidence": m["risk_confidence"],
        "patterns": m["patterns"],
        "fan_in": m["fan_in"], "fan_out": m["fan_out"], "in_cycle": m["in_cycle"],
        "reasons": [why] + ([cls["note"]] if cls.get("note") else []),
        "is_config": m["is_config"],
        "hub_role": cls.get("hub_role"),
        "risk_role": cls.get("risk_role"),
    }


def _boundary_view(m: Dict[str, Any]) -> Dict[str, Any]:
    return {"module": m["dotted"] or m["path"], "path": m["path"],
            "boundary_edges": m["boundary_edges"], "subsystems_touched": m["subsystems_touched"]}
