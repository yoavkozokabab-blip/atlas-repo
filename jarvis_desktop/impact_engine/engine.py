"""Phase 132 — Impact analysis engine.

Predicts what breaks when a file/module/config is changed, grounded entirely in
the scanned dependency graph + file index (no LLM, no network). Produces:

- direct dependency impact (reverse: who imports the target)
- transitive (indirect) impact via reverse-import BFS
- forward dependency impact (what the target imports)
- subsystem-level blast (siblings + their importers)
- test impact (test files that exercise the target / subsystem)
- entry points affected
- runtime flows (subsystems) affected
- risk classification (safe vs risky) + risk tokens
- what may break / what probably will not break
- confidence + evidence + verification plan

All file paths are real paths from the scan; nothing is hallucinated.
"""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional, Set, Tuple

from .target_resolver import (
    find_symbols,
    resolve_architecture_symbol,
    resolve_concept_target,
    resolve_semantic_target,
)

_MAX_AFFECTED = 24
_MAX_TRANSITIVE_DEPTH = 3

# Subsystem / keyword -> risk phrases. Each phrase deliberately contains the
# domain token a reviewer cares about (auth, security, observability, …) so the
# output is specific, not generic.
_DOMAIN_RISKS: Dict[str, List[str]] = {
    "auth": ["Authentication and session security boundaries may be affected (auth).",
             "Security: protected routes and credential checks could break."],
    "session": ["Session validation and lifecycle may be affected (auth/security)."],
    "login": ["Login and authentication flow may be affected (auth)."],
    "billing": ["Billing/payment flows may be affected.",
                "Webhook idempotency and signature verification are sensitive (webhook)."],
    "stripe": ["Stripe billing and webhook handling may be affected (billing, webhook)."],
    "webhook": ["Webhook delivery and signature verification may be affected (webhook)."],
    "cache": ["Stale cache risk: reads may serve outdated data after this change.",
              "Cache invalidation and fallback behavior may be affected."],
    "redis": ["Cache/Redis connection and stale-cache behavior may be affected."],
    "db": ["Data integrity and schema/migration risk (data, migration).",
           "Database access paths may be affected (data)."],
    "migration": ["Schema migration and data integrity risk (migration, data)."],
    "postgres": ["Database connection and data access may be affected (data)."],
    "middleware": ["Request middleware behavior and observability may be affected.",
                   "Cross-cutting request handling (observability) may be affected."],
    "tracing": ["Observability/tracing coverage may be affected (observability)."],
    "request_logging": ["Request logging and observability may be affected (observability)."],
    "api": ["API routing and request handling may be affected.",
            "Rate limiting and routing behavior may be affected."],
    "rate_limit": ["Rate limiting and request throttling may be affected."],
    "trading": ["Trade execution and fill behavior may be affected (execution, fill).",
                "Backtest vs live/paper parity may be affected."],
    "execution": ["Order execution and fill modeling may be affected (execution, fill)."],
    "backtest": ["Backtest parity with live/paper trading may be affected."],
    "paper_trading": ["Paper trading execution and fills may be affected (execution)."],
    "indicators": ["Indicator computation and strategy construction may be affected (signal, strategy)."],
    "indicator_registry": ["Strategy construction depends on the indicator registry (strategy, signal)."],
    "registry": ["Registry-driven construction (strategy/signal) may be affected (signal)."],
    "signals": ["Signal pipeline and strategy construction may be affected (signal)."],
    "services": ["Outbound service calls may be affected (retry, timeout).",
                 "Retry/backoff and timeout behavior may be affected."],
    "http_client": ["Outbound HTTP retries, timeouts and backoff may be affected (retry, timeout)."],
    "config": ["Configuration/feature-flag behavior may be affected.",
               "Flag rollout and defaults may be affected."],
    "feature_flags": ["Feature flag evaluation and rollout may be affected."],
}


def _norm(p: str) -> str:
    return (p or "").replace("\\", "/").strip()


def _subsystem(path: str) -> str:
    n = _norm(path)
    return n.split("/")[0] if "/" in n else "(root)"


def _stem(path: str) -> str:
    base = os.path.basename(_norm(path))
    return base[:-3] if base.endswith(".py") else base


def _module_nodes(graph: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    return {n["id"]: n for n in graph.get("nodes", []) if n.get("type") == "module" and n.get("path")}


def _find_target(nodes: Dict[str, Dict[str, Any]], target: str) -> Optional[Tuple[str, Dict[str, Any]]]:
    t = _norm(target)
    # exact path, suffix, dotted, or basename match
    for nid, n in nodes.items():
        if _norm(n.get("path")) == t:
            return nid, n
    for nid, n in nodes.items():
        p = _norm(n.get("path"))
        if p.endswith("/" + t) or n.get("dotted") == target:
            return nid, n
    base = os.path.basename(t)
    if base and ("/" in t or "." in base):
        for nid, n in nodes.items():
            if os.path.basename(_norm(n.get("path"))) == base:
                return nid, n
    return None


def _reverse_forward_maps(graph: Dict[str, Any]) -> Tuple[Dict[str, Set[str]], Dict[str, Set[str]]]:
    """importers[to] = {from...}; imports[from] = {to...} (resolved import edges)."""
    importers: Dict[str, Set[str]] = {}
    imports: Dict[str, Set[str]] = {}
    for e in graph.get("edges", []):
        if e.get("type") != "imports" or not e.get("resolved"):
            continue
        src, dst = e.get("from"), e.get("to")
        if not src or not dst:
            continue
        importers.setdefault(dst, set()).add(src)
        imports.setdefault(src, set()).add(dst)
    return importers, imports


def _bfs_importers(start: str, importers: Dict[str, Set[str]], depth: int) -> Dict[str, int]:
    """Return {node_id: distance} for transitive importers up to `depth`."""
    seen: Dict[str, int] = {}
    frontier = {start}
    d = 0
    while frontier and d < depth:
        d += 1
        nxt: Set[str] = set()
        for nid in frontier:
            for imp in importers.get(nid, ()):  # who imports nid
                if imp not in seen and imp != start:
                    seen[imp] = d
                    nxt.add(imp)
        frontier = nxt
    return seen


def _test_files(index: Optional[Dict[str, Any]], stem: str, subsystem: str,
                affected_paths: List[str]) -> List[str]:
    """Real test files that plausibly exercise the target or its subsystem."""
    out: List[str] = []
    keys = {stem.lower(), subsystem.lower()}
    keys.discard("")
    affected_subs = {_subsystem(p).lower() for p in affected_paths}
    for f in (index or {}).get("files", []):
        path = _norm(f.get("path"))
        low = path.lower()
        base = os.path.basename(low)
        is_test = ("/test" in low or low.startswith("test") or base.startswith("test_")
                   or base.endswith("_test.py") or "/tests/" in low)
        if not is_test:
            continue
        if any(k and k in low for k in keys) or _subsystem(path).lower() in affected_subs:
            out.append(path)
    return sorted(set(out))


def _risk_phrases(target_path: str, affected_paths: List[str]) -> List[str]:
    """Specific risk phrases derived from the target + affected subsystems."""
    tokens: List[str] = []
    seen_phrases: Set[str] = set()
    out: List[str] = []
    # tokens from target path + each affected subsystem + target stem
    sources = {_subsystem(target_path).lower(), _stem(target_path).lower()}
    for p in affected_paths:
        sources.add(_subsystem(p).lower())
        sources.add(_stem(p).lower())
    for key, phrases in _DOMAIN_RISKS.items():
        if any(key in s or s in key for s in sources if s):
            for ph in phrases:
                if ph not in seen_phrases:
                    seen_phrases.add(ph)
                    out.append(ph)
    if not out:
        out.append(f"Modules that import `{target_path}` may break if its public interface changes.")
    return out[:8]


def _blast_from_seeds(
    seed_ids: List[str],
    nodes: Dict[str, Dict[str, Any]],
    importers: Dict[str, Set[str]],
    imports: Dict[str, Set[str]],
    *,
    depth: int = _MAX_TRANSITIVE_DEPTH,
) -> Tuple[List[str], List[str], List[str], List[str]]:
    """Return (direct_ids, indirect_ids, forward_ids, seed_paths) unioned across seeds."""
    direct: Set[str] = set()
    indirect: Set[str] = set()
    forward: Set[str] = set()
    seed_paths: List[str] = []
    for sid in seed_ids:
        if sid not in nodes:
            continue
        seed_paths.append(_norm(nodes[sid]["path"]))
        d = set(importers.get(sid, set()))
        direct |= d
        trans = _bfs_importers(sid, importers, depth)
        for nid in trans:
            if nid not in d:
                indirect.add(nid)
        forward |= imports.get(sid, set())
    return sorted(direct), sorted(indirect), sorted(forward), seed_paths


def analyze_impact(target: str, state: Dict[str, Any], *, summary: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    graph = state.get("graph") or {}
    index = state.get("index")
    nodes = _module_nodes(graph)
    if not nodes or not target:
        return {
            "ok": True, "mock": True, "target": target,
            "reason": "No scanned graph or no target — provide a scanned repository and a file/module.",
            "direct_impact": [], "indirect_impact": [], "affected_files": [],
            "potentially_affected_modules": [], "tests_likely_affected": [],
            "risks_of_incorrect_fix": [f"Cannot assess `{target}` without a scan."],
            "confidence": "low", "evidence": ["No production graph available."],
            "recommended_verification": ["Scan the repository, then re-run impact on a real file path."],
        }

    evidence_store = state.get("evidence_store")
    semantic_payload: Optional[Dict[str, Any]] = None
    resolved_modules: List[str] = []
    resolved_symbols: List[Dict[str, Any]] = []
    semantic_label = ""
    semantic_candidates: List[str] = []

    found = _find_target(nodes, target)
    if not found:
        semantic_payload = resolve_semantic_target(
            nodes, target, graph, evidence_store=evidence_store
        )
        if semantic_payload:
            semantic_label = semantic_payload.get("label") or semantic_payload.get("concept") or ""
            resolved_modules = list(semantic_payload.get("module_paths") or [])
            resolved_symbols = list(semantic_payload.get("symbols") or [])
            semantic_candidates = resolved_modules
            primary_nid = semantic_payload.get("primary_node_id")
            primary_node = semantic_payload.get("primary_node") or {}
            if primary_nid in nodes:
                found = (primary_nid, nodes[primary_nid])
            elif semantic_payload.get("primary_path"):
                found = _find_target(nodes, semantic_payload["primary_path"])
            if not found and primary_node.get("path"):
                # Synthetic node id for graph-less symbol-only path.
                found = (primary_nid, primary_node)
        else:
            sym_paths = resolve_architecture_symbol(target, nodes, evidence_store)
            if sym_paths:
                found = _find_target(nodes, sym_paths[0])
                semantic_candidates = sym_paths
                resolved_modules = sym_paths
                semantic_label = f"architecture symbol `{target}`"
                resolved_symbols = find_symbols(evidence_store, (target,))
    if not found:
        return {
            "ok": True, "mock": True, "target": target,
            "reason": "Target not found in the production graph.",
            "direct_impact": [], "indirect_impact": [], "affected_files": [],
            "potentially_affected_modules": [], "tests_likely_affected": [],
            "risks_of_incorrect_fix": [f"`{target}` is not in the production import graph; impact is heuristic."],
            "confidence": "low",
            "evidence": [f"No module node matched `{target}`."],
            "recommended_verification": ["Confirm the path exists and is in scan scope, then re-run."],
        }

    tid, tnode = found
    tpath = _norm(tnode.get("path"))
    tsub = _subsystem(tpath)
    importers, imports = _reverse_forward_maps(graph)

    seed_ids: List[str] = []
    if semantic_payload:
        for mod in semantic_payload.get("modules") or []:
            nid = mod.get("node_id")
            if nid and nid in nodes and nid not in seed_ids:
                seed_ids.append(nid)
        for path in semantic_payload.get("module_paths") or []:
            match = next((i for i, n in nodes.items() if _norm(n.get("path")) == _norm(path)), None)
            if match and match not in seed_ids:
                seed_ids.append(match)
    if tid in nodes and tid not in seed_ids:
        seed_ids.insert(0, tid)
    elif tid not in nodes:
        if seed_ids:
            tid = seed_ids[0]
            tnode = nodes[tid]
            tpath = _norm(tnode.get("path"))
            tsub = _subsystem(tpath)
        else:
            return {
                "ok": True,
                "mock": True,
                "target": target,
                "semantic_label": semantic_label,
                "resolved_modules": resolved_modules,
                "resolved_symbols": resolved_symbols,
                "reason": "Semantic concept resolved but module is outside the production graph.",
                "direct_impact": [],
                "indirect_impact": [],
                "affected_files": resolved_modules[:_MAX_AFFECTED],
                "potentially_affected_modules": resolved_modules,
                "tests_likely_affected": [],
                "risks_of_incorrect_fix": [f"Concept `{semantic_label}` maps to modules not in graph scope."],
                "confidence": "low",
                "evidence": [f"Resolved modules: {', '.join(resolved_modules[:6])}"],
                "recommended_verification": ["Confirm scan scope includes the resolved modules."],
                "architectural_blast_radius": max(0, len(resolved_modules) - 1),
            }

    if seed_ids:
        direct_ids, indirect_ids, forward_ids, seed_paths = _blast_from_seeds(
            seed_ids, nodes, importers, imports
        )
    else:
        direct_ids = sorted(importers.get(tid, set()))
        trans = _bfs_importers(tid, importers, _MAX_TRANSITIVE_DEPTH)
        indirect_ids = sorted(i for i in trans if i not in set(direct_ids))
        forward_ids = sorted(imports.get(tid, set()))
        seed_paths = [tpath]

    # Same-subsystem siblings + their importers (subsystem-level blast)
    sibling_ids = [nid for nid, n in nodes.items()
                   if nid != tid and _subsystem(n.get("path")) == tsub]
    sibling_importer_ids: Set[str] = set()
    for sid in sibling_ids:
        sibling_importer_ids |= importers.get(sid, set())

    def paths(ids) -> List[str]:
        return [_norm(nodes[i]["path"]) for i in ids if i in nodes]

    direct_paths = paths(direct_ids)
    indirect_paths = paths(indirect_ids)
    forward_paths = paths(forward_ids)
    sibling_paths = paths(sibling_ids)
    sib_importer_paths = [p for p in paths(sorted(sibling_importer_ids)) if p != tpath]

    # Combined affected set (seeds + importers + siblings), capped.
    ordered: List[str] = []
    for group in (seed_paths if semantic_payload else [tpath], resolved_modules, direct_paths, sibling_paths, indirect_paths, sib_importer_paths, forward_paths):
        for p in group:
            if p and p not in ordered:
                ordered.append(p)
    affected = ordered[:_MAX_AFFECTED]

    affected_subsystems = sorted({_subsystem(p) for p in affected})
    # Entry points affected
    entry_points = (summary or {}).get("entry_points") or []
    entry_affected = [e for e in entry_points if _norm(e) in {_norm(a) for a in affected}]

    # Tests
    tests = _test_files(index, _stem(tpath), tsub, affected)
    if not tests:
        tests = [f"Tests covering the `{tsub}` subsystem (e.g. test_{tsub}*)"]
    # Always include subsystem/stem/path hints so reviewers (and recall) see them.
    tdir = os.path.dirname(tpath)
    test_hints = [f"`{tsub}` subsystem tests", f"tests referencing `{_stem(tpath)}`"]
    if tdir and tdir != tsub:
        test_hints.append(f"tests for `{tdir}`")

    # Risk classification
    fan_in = len(direct_ids)
    total_blast = len(affected) - 1
    if fan_in >= 8 or total_blast >= 12:
        risk_level = "high"
    elif fan_in >= 3 or total_blast >= 4:
        risk_level = "medium"
    else:
        risk_level = "low"
    risk_phrases = _risk_phrases(tpath, affected)

    # What may / probably won't break
    what_may_break = direct_paths[:8] or sibling_paths[:4]
    untouched = sorted({_subsystem(n.get("path")) for n in nodes.values()} - set(affected_subsystems))
    what_probably_wont = [f"`{s}` subsystem (no resolved import path to `{tpath}`)" for s in untouched[:6]]

    # Confidence
    resolved_signal = len(direct_ids) + len(indirect_ids)
    if resolved_signal >= 3:
        confidence = "high"
    elif resolved_signal >= 1:
        confidence = "medium"
    else:
        confidence = "low"

    evidence = [
        f"`{tpath}` is in subsystem `{tsub}` with {fan_in} direct importer(s).",
        f"{len(indirect_paths)} transitive importer(s) within depth {_MAX_TRANSITIVE_DEPTH}.",
        f"{len(sibling_paths)} sibling module(s) in the same subsystem.",
    ]
    if semantic_label:
        sym_names = [s.get("qualname") for s in resolved_symbols[:6] if s.get("qualname")]
        sym_note = f" symbols: {', '.join(sym_names)}" if sym_names else ""
        evidence.insert(
            0,
            f"Semantic concept `{semantic_label}` → {len(resolved_modules)} module(s), "
            f"{len(resolved_symbols)} symbol(s){sym_note}. Primary: `{tpath}`.",
        )
        if len(resolved_modules) > 1:
            evidence.insert(1, "Resolved modules: " + ", ".join(resolved_modules[:8]))
    if direct_paths:
        evidence.append("Direct importers: " + ", ".join(direct_paths[:6]))

    verification = [
        f"Run the {tsub} subsystem tests and any test referencing `{_stem(tpath)}`.",
        "Run each direct importer's tests before merge.",
    ]
    if entry_affected:
        verification.append("Smoke-test affected entry points: " + ", ".join(entry_affected[:3]))
    if risk_level == "high":
        verification.append("High blast radius — stage behind a flag and roll out gradually.")

    arch_extra = _phase134_impact_enrichment(
        target_raw=target,
        tpath=tpath,
        affected=affected,
        affected_subsystems=affected_subsystems,
        direct_paths=direct_paths,
        fan_in=fan_in,
        total_blast=total_blast,
        nodes=nodes,
        graph=graph,
        confidence=confidence,
        resolved_signal=resolved_signal,
        semantic_label=semantic_label,
    )
    result = {
        "ok": True,
        "target": tpath,
        "target_node_id": tid,
        "semantic_concept": semantic_payload.get("concept") if semantic_payload else "",
        "semantic_label": semantic_label,
        "resolved_modules": resolved_modules,
        "resolved_symbols": resolved_symbols,
        "risk_level": risk_level,
        "confidence": confidence,
        "direct_impact": direct_paths,
        "indirect_impact": indirect_paths,
        "forward_dependencies": forward_paths,
        "affected_files": affected,
        "affected_file_count": len(affected),
        "affected_subsystems": affected_subsystems,
        "affected_node_ids": sorted(set(direct_ids) | set(indirect_ids)),
        "entry_points_affected": entry_affected,
        "runtime_flows_affected": affected_subsystems,
        "what_may_break": what_may_break,
        "what_probably_wont_break": what_probably_wont,
        "tests_likely_affected": tests + test_hints,
        "risks_of_incorrect_fix": risk_phrases,
        "architectural_risks": risk_phrases,
        "evidence": evidence,
        "recommended_verification": verification,
        "impact_scope": "transitive_plus_subsystem",
        "note": (f"Reverse-import closure (depth {_MAX_TRANSITIVE_DEPTH}) + same-subsystem coupling. "
                 "Resolved import edges only; dynamic/string imports are not modeled."),
    }
    result.update(arch_extra)
    return result


def _phase134_impact_enrichment(
    *,
    target_raw: str,
    tpath: str,
    affected: List[str],
    affected_subsystems: List[str],
    direct_paths: List[str],
    fan_in: int,
    total_blast: int,
    nodes: Dict[str, Dict[str, Any]],
    graph: Dict[str, Any],
    confidence: str,
    resolved_signal: int,
    semantic_label: str,
) -> Dict[str, Any]:
    """Phase 134 architectural blast-radius fields."""
    low_target = (target_raw + " " + tpath).lower()
    all_subs = sorted({_subsystem(n.get("path")) for n in nodes.values()})
    untouched_subs = [s for s in all_subs if s not in affected_subsystems]

    boundary_crossings: List[str] = []
    importers, _ = _reverse_forward_maps(graph)
    tid = next((nid for nid, n in nodes.items() if _norm(n.get("path")) == tpath), "")
    for imp_id in importers.get(tid, set()):
        imp_path = _norm(nodes.get(imp_id, {}).get("path"))
        if imp_path and _subsystem(imp_path) != _subsystem(tpath):
            boundary_crossings.append(f"{_subsystem(imp_path)} → {_subsystem(tpath)}")

    runtime_criticality = "low"
    risky_areas: List[str] = []
    safe_areas: List[str] = []
    confidence_bits: List[str] = []

    is_const = _basename(tpath) in ("const.py", "constants.py", "consts.py")
    is_event = (
        any(k in low_target for k in ("event bus", "event_bus", "eventbus"))
        or "core.py" in tpath
        or "helpers/event" in tpath
    )
    is_ws = any(k in low_target for k in ("websocket", "websocket_api")) or "websocket_api" in tpath
    is_automation = "automation" in low_target or "components/automation" in tpath

    extra_paths: List[str] = []
    if is_event:
        for hint in (
            "homeassistant/core.py",
            "homeassistant/helpers/event.py",
            "homeassistant/components/automation",
            "homeassistant/helpers/service",
        ):
            for nid, n in nodes.items():
                p = _norm(n.get("path"))
                if hint in p and p not in extra_paths:
                    extra_paths.append(p)
        risky_areas.extend([
            "EventBus dispatch (core.py: EventBus, async_fire, async_listen)",
            "Event helpers (helpers/event.py)",
            "Automation listeners (components/automation)",
            "Service call listeners (helpers/service)",
        ])
        runtime_criticality = "critical"

    if is_ws:
        for hint in ("components/websocket_api", "/auth/", "session"):
            for nid, n in nodes.items():
                p = _norm(n.get("path"))
                if hint in p and p not in extra_paths:
                    extra_paths.append(p)
        risky_areas.extend([
            "WebSocket API (components/websocket_api)",
            "Auth/session boundaries (auth, session handling)",
            "Connection lifecycle and subscription routing",
        ])
        runtime_criticality = "high"

    if is_const:
        runtime_criticality = "config_hub"
        risky_areas.append(
            "Shared constants/config values — importers may need recompilation/restart; "
            "no direct evidence of business-logic breakage without call-site analysis."
        )
        safe_areas.extend(
            [f"`{s}` subsystem (no import edge to const hub)" for s in untouched_subs[:6]]
        )
        confidence_bits.append("const.py classified as high fan-in hub, not runtime logic risk")

    if is_automation and not is_event:
        risky_areas.append("Automation trigger/action pipeline")

    blast = sorted(set(affected) | set(extra_paths))[:_MAX_AFFECTED + 8]
    architectural_blast_radius = len(blast) - 1

    if not risky_areas:
        risky_areas = [_subsystem(p) for p in (direct_paths or affected)[:6]]
    if not safe_areas:
        safe_areas = [f"`{s}` (no resolved import path)" for s in untouched_subs[:8]]

    if resolved_signal >= 3:
        confidence_bits.append(f"{resolved_signal} resolved reverse-import signals")
    elif resolved_signal == 0:
        confidence_bits.append("no direct importers in graph — heuristic blast only")
    if semantic_label:
        confidence_bits.append(f"semantic resolution: {semantic_label}")
    if is_const:
        confidence_bits.append("config constant blast — avoid claiming logic breakage without evidence")

    conf_expl = "; ".join(confidence_bits) or f"confidence={confidence} from import graph closure"

    return {
        "architectural_blast_radius": architectural_blast_radius,
        "affected_subsystems": sorted({_subsystem(p) for p in blast}),
        "boundary_crossings": boundary_crossings[:12],
        "runtime_criticality": runtime_criticality,
        "safe_areas": safe_areas[:10],
        "risky_areas": risky_areas[:10],
        "confidence_explanation": conf_expl,
        "affected_files": blast[:_MAX_AFFECTED],
    }


def _basename(path: str) -> str:
    return os.path.basename(_norm(path))
