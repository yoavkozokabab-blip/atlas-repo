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
    if base:
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

    found = _find_target(nodes, target)
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

    # 1. Direct importers
    direct_ids = sorted(importers.get(tid, set()))
    # 2. Transitive importers (indirect)
    trans = _bfs_importers(tid, importers, _MAX_TRANSITIVE_DEPTH)
    indirect_ids = sorted(i for i in trans if i not in set(direct_ids))
    # 3. Forward deps (what the target imports — may break contract-wise)
    forward_ids = sorted(imports.get(tid, set()))
    # 4. Same-subsystem siblings + their importers (subsystem-level blast)
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

    # Combined affected set (the target + everything plausibly coupled), capped.
    ordered: List[str] = [tpath]
    for group in (direct_paths, sibling_paths, indirect_paths, sib_importer_paths, forward_paths):
        for p in group:
            if p not in ordered:
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

    return {
        "ok": True,
        "target": tpath,
        "target_node_id": tid,
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
