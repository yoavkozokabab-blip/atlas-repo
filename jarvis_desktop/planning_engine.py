"""Phase 120 — Change planner and symptom investigation (local, evidence-grounded).

Planning only — no code generation, no autonomous edits. All file paths must exist
in the scanned repository index or production graph.
"""

from __future__ import annotations

import re
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple

# Feature intents → search terms for path/module matching (deterministic heuristics).
_FEATURE_SPECS: Dict[str, Dict[str, Any]] = {
    "authentication": {
        "triggers": ("auth", "authentication", "login", "sign in", "signup", "jwt", "oauth", "session"),
        "search": ("auth", "login", "session", "user", "identity", "oauth", "jwt", "password"),
        "risks": ("Security boundaries for sessions and credentials must stay consistent across entry points.",),
    },
    "billing": {
        "triggers": ("stripe", "billing", "payment", "subscription", "checkout"),
        "search": ("stripe", "billing", "payment", "subscription", "checkout", "invoice"),
        "risks": ("Payment webhooks and idempotency are common failure points.",),
    },
    "caching": {
        "triggers": ("cache", "caching", "redis", "memcached"),
        "search": ("cache", "redis", "memcached", "lru"),
        "risks": ("Cache invalidation and stale reads affect correctness.",),
    },
    "audit_logging": {
        "triggers": ("audit", "audit log", "logging", "telemetry"),
        "search": ("audit", "log", "logger", "telemetry", "trace"),
        "risks": ("Logging volume and PII redaction need review.",),
    },
    "dark_mode": {
        "triggers": ("dark mode", "theme", "theming"),
        "search": ("theme", "dark", "css", "style", "ui"),
        "risks": ("UI tokens and component libraries may need coordinated updates.",),
    },
    "websocket": {
        "triggers": ("websocket", "websockets", "real-time", "realtime"),
        "search": ("websocket", "ws", "socket", "realtime", "stream"),
        "risks": ("Connection lifecycle and backpressure affect reliability.",),
    },
    "redis": {
        "triggers": ("redis",),
        "search": ("redis", "queue", "broker", "celery"),
        "risks": ("Connection pooling and key naming conventions matter at scale.",),
    },
}

_SYMPTOM_SPECS: Dict[str, Dict[str, Any]] = {
    "paper_trading": {
        "triggers": (
            "backtest",
            "paper trad",
            "live trad",
            "better than",
            "worse than",
            "simulation",
            "paper vs",
        ),
        "search": ("backtest", "paper", "live", "trade", "broker", "execution", "sim"),
        "why": "Symptoms comparing backtest vs live/paper often involve execution, slippage, or data-feed paths.",
    },
    "delayed_alerts": {
        "triggers": ("telegram", "alert", "delayed", "delay", "notification", "notify"),
        "search": ("telegram", "alert", "notify", "message", "webhook", "queue", "scheduler"),
        "why": "Alert delays usually trace through messaging integrations, queues, or schedulers.",
    },
    "memory_growth": {
        "triggers": ("memory", "leak", "increasing", "oom", "out of memory"),
        "search": ("cache", "pool", "worker", "stream", "buffer", "session", "loop"),
        "why": "Growing memory often ties to caches, long-lived workers, or unreleased handles.",
    },
    "dashboard_mismatch": {
        "triggers": ("dashboard", "numbers wrong", "metric", "display", "report wrong"),
        "search": ("dashboard", "metric", "report", "aggregate", "stats", "ui", "view"),
        "why": "Wrong dashboard values often come from aggregation, caching, or UI binding layers.",
    },
    "position_close": {
        "triggers": ("position close", "closes fail", "close order", "exit position"),
        "search": ("position", "close", "order", "execution", "trade", "risk"),
        "why": "Intermittent close failures often involve order routing, state machines, or broker adapters.",
        "hypothesis": "Order state, venue rules, or partial-fill handling may reject or delay close requests.",
        "verify": (
            "Reproduce with a single symbol and capture order lifecycle logs.",
            "Compare close path vs open path (same adapter, different state transitions).",
        ),
        "risk_if_fixed": "Overly aggressive retries could duplicate closes or violate risk limits.",
    },
    "dashboard_pnl": {
        "triggers": ("pnl", "profit and loss", "dashboard pnl", "wrong pnl", "pnl is wrong"),
        "search": ("pnl", "profit", "loss", "equity", "balance", "dashboard", "metric", "portfolio"),
        "why": "PnL mismatches often come from position accounting, mark-to-market sources, or UI aggregation.",
        "hypothesis": "Stale marks, double-counted fills, or inconsistent fee/slippage treatment between layers.",
        "verify": (
            "Trace PnL from raw fills → position ledger → API → dashboard widget.",
            "Compare paper/live vs backtest PnL components on the same date range.",
        ),
        "risk_if_fixed": "Fixing display-only bugs can hide real accounting errors; verify ledger first.",
    },
    "graph_module_count": {
        "triggers": (
            "module count",
            "wrong module",
            "scan graph",
            "graph shows wrong",
            "atlas graph",
            "repository map",
        ),
        "search": ("graph", "scan", "module", "index", "universe", "import", "dependency"),
        "why": "Graph/module count issues usually involve scan scope, production filters, or overview vs module view.",
        "hypothesis": "UI may show architecture overview or partial graph while totals reflect full scan.",
        "verify": (
            "Confirm scan scope (entire repo vs folder) and production filter settings.",
            "Switch to Module Graph and compare visible count to summary module_count.",
        ),
        "risk_if_fixed": "Forcing full module graph on huge repos may degrade performance — use hierarchy when appropriate.",
    },
}


def _path_symbols(path: str) -> List[str]:
    """Best-effort symbols from a file path (no AST — avoids hallucinated class names)."""
    base = (path or "").replace("\\", "/").split("/")[-1]
    if "." in base:
        stem = base.rsplit(".", 1)[0]
    else:
        stem = base
    out: List[str] = []
    if stem and stem not in {"__init__", "index", "main"}:
        out.append(stem)
    return out


def _risk_level_from_fan_in(fan_in: int, risk_score: float) -> str:
    if fan_in >= 25 or risk_score >= 60:
        return "high"
    if fan_in >= 6 or risk_score >= 35:
        return "medium"
    return "low"


def _implementation_order(paths: List[str], graph: Optional[Dict[str, Any]]) -> List[str]:
    """Leaf-ish modules first (lower fan-in), then hubs — static heuristic only."""
    if not paths or not graph:
        return list(paths)
    nodes = {n.get("path"): n for n in _production_modules(graph)}
    ordered = sorted(
        paths,
        key=lambda p: (int((nodes.get(p) or {}).get("fan_in", 0) or 0), p),
    )
    return ordered


def _files_likely_to_break(inbound_paths: List[str], risks_map: Dict[str, Dict[str, Any]]) -> List[str]:
    scored: List[Tuple[int, str]] = []
    for path in inbound_paths:
        row = risks_map.get(path) or {}
        fan = int(row.get("fan_in", 0) or 0)
        scored.append((fan + int(row.get("total_score", 0) or 0), path))
    scored.sort(key=lambda x: (-x[0], x[1]))
    return [p for _, p in scored[:10]]


def _subsystem_of(path: str) -> str:
    normalized = (path or "").replace("\\", "/")
    return normalized.split("/")[0] if "/" in normalized else "(root)"


def _tokenize(text: str) -> Set[str]:
    return {t for t in re.findall(r"[a-z][a-z0-9_]{2,}", (text or "").lower())}


def _detect_intent(text: str, specs: Dict[str, Dict[str, Any]]) -> Tuple[str, Set[str]]:
    lower = (text or "").lower()
    for name, spec in specs.items():
        if any(trigger in lower for trigger in spec["triggers"]):
            return name, set(spec["search"])
    return "general", _tokenize(text)


def _production_modules(graph: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
    if not graph:
        return []
    return [n for n in graph.get("nodes", []) if n.get("type") == "module" and n.get("path")]


def _score_modules(
    modules: List[Dict[str, Any]],
    terms: Set[str],
    risks_by_path: Dict[str, Dict[str, Any]],
) -> List[Tuple[float, Dict[str, Any]]]:
    scored: List[Tuple[float, Dict[str, Any]]] = []
    for node in modules:
        path = node.get("path") or ""
        p = path.lower().replace("\\", "/")
        score = 0.0
        for term in terms:
            if term in p:
                score += 3.0
        risk = risks_by_path.get(path) or {}
        score += min(5.0, float(risk.get("total_score", 0) or 0) / 20.0)
        score += min(3.0, float(node.get("fan_in", 0) or 0) / 10.0)
        if score > 0:
            scored.append((score, node))
    scored.sort(key=lambda item: (-item[0], item[1].get("path", "")))
    return scored


def _risks_map(risks: Optional[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    out: Dict[str, Dict[str, Any]] = {}
    for row in (risks or {}).get("ranked_modules", []) or []:
        path = row.get("path")
        if path:
            out[path] = row
    return out


def _graph_neighbors(graph: Dict[str, Any], module_ids: Set[str]) -> Tuple[List[str], List[str]]:
    """Return (outbound deps, inbound importers) as dotted/path labels from real edges."""
    nodes = {n["id"]: n for n in _production_modules(graph)}
    outbound: Set[str] = set()
    inbound: Set[str] = set()
    for edge in graph.get("edges", []):
        if edge.get("type") != "imports" or not edge.get("resolved"):
            continue
        src, dst = edge.get("from"), edge.get("to")
        if src in module_ids:
            dst_node = nodes.get(dst)
            if dst_node:
                outbound.add(dst_node.get("path") or dst)
        if dst in module_ids:
            src_node = nodes.get(src)
            if src_node:
                inbound.add(src_node.get("path") or src)
    return sorted(outbound)[:12], sorted(inbound)[:12]


def _estimate_size(module_count: int) -> str:
    if module_count <= 5:
        return "Small"
    if module_count <= 20:
        return "Medium"
    return "Large"


def _confidence_label(score_count: int, top_score: float, intent: str) -> str:
    if intent != "general" and score_count >= 2 and top_score >= 4:
        return "medium-high"
    if score_count >= 1 and top_score >= 3:
        return "medium"
    if score_count >= 1:
        return "low-medium"
    return "low"


def repository_context_from_state(state: Dict[str, Any]) -> Dict[str, Any]:
    scan = state.get("scan") or {}
    summary = state.get("summary") or {}
    return {
        "scan": scan,
        "graph": state.get("graph"),
        "index": state.get("index"),
        "risks": state.get("risks"),
        "repo_name": scan.get("repo_name") or summary.get("repo_name") or "repository",
        "entry_points": summary.get("entry_points") or scan.get("entry_points") or [],
        "subsystems": summary.get("subsystems") or [],
        "top_hubs": scan.get("top_hubs") or summary.get("top_hubs") or [],
        "explanation": summary.get("explanation") or "",
    }


def plan_change(request: str, ctx: Dict[str, Any]) -> Dict[str, Any]:
    """Build a grounded change plan from scanned repository state."""
    goal = (request or "").strip()
    if not goal:
        return {"ok": False, "error": "Describe what you want to add or change."}
    graph = ctx.get("graph")
    if not graph:
        return {"ok": False, "error": "No repository scanned yet."}

    intent, terms = _detect_intent(goal, _FEATURE_SPECS)
    spec = _FEATURE_SPECS.get(intent, {})
    extra_terms = set(spec.get("search", ())) | terms
    modules = _production_modules(graph)
    risks_map = _risks_map(ctx.get("risks"))
    scored = _score_modules(modules, extra_terms, risks_map)

    matched_paths = [node["path"] for _, node in scored[:12]]
    matched_ids = {node["id"] for _, node in scored[:12]}
    subsystems = sorted({_subsystem_of(p) for p in matched_paths})
    outbound, inbound = _graph_neighbors(graph, matched_ids)

    entry_points = [ep for ep in (ctx.get("entry_points") or []) if any(ep.startswith(s) for s in subsystems)]
    if not entry_points:
        entry_points = list(ctx.get("entry_points") or [])[:5]

    arch_risks: List[str] = []
    for path in matched_paths[:6]:
        row = risks_map.get(path)
        if row:
            reasons = row.get("reasons") or []
            arch_risks.append(f"`{path}` (score {row.get('total_score', 0)}): {', '.join(reasons[:2]) or 'high fan-in / coupling'}")
    for note in spec.get("risks", ()):
        if note not in arch_risks:
            arch_risks.append(note)

    tests = _tests_for_change(matched_paths, subsystems)
    top_score = scored[0][0] if scored else 0.0
    confidence = _confidence_label(len(matched_paths), top_score, intent)
    limitations: List[str] = []
    if not matched_paths:
        limitations.append("No production modules matched this request by path keyword — inspect entry points and hubs manually.")
        limitations.append("Provide subsystem names, file paths, or a narrower feature description and re-run.")
    if intent == "general":
        limitations.append("Request did not match a known feature pattern; results are keyword-based only.")
    limitations.append("Static import graph only — runtime plugins and dynamic imports may be missing.")

    top_node = scored[0][1] if scored else {}
    risk_level = _risk_level_from_fan_in(
        int(top_node.get("fan_in", 0) or 0),
        float((risks_map.get(top_node.get("path", "")) or {}).get("total_score", 0) or 0),
    )
    likely_break = _files_likely_to_break(inbound, risks_map)
    verification_plan = [
        "Read files_to_inspect_first and confirm the change boundary matches the goal.",
        "Run tests_likely_affected before and after the change.",
        "Re-scan or refresh impact on the highest fan-in file you touch.",
    ]
    if likely_break:
        verification_plan.append(f"Smoke-test direct importers: {', '.join(likely_break[:3])}")

    plan = {
        "goal": goal,
        "intent": intent,
        "likely_affected_modules": matched_paths,
        "likely_affected_subsystems": subsystems,
        "entry_points": entry_points,
        "files_to_inspect_first": matched_paths[:8],
        "files_likely_to_change": matched_paths[:8],
        "files_likely_to_break": likely_break,
        "dependencies_involved": {
            "outbound_imports": outbound,
            "inbound_importers": inbound,
        },
        "architectural_risks": arch_risks[:10],
        "tests_likely_affected": tests,
        "estimated_change_size": _estimate_size(len(matched_paths) or 1),
        "risk_level": risk_level,
        "implementation_order": _implementation_order(matched_paths[:12], graph),
        "verification_plan": verification_plan,
        "confidence": confidence,
        "evidence": _change_evidence(scored[:8], intent),
        "limitations": limitations,
    }
    prompts = build_implementation_prompts(plan, ctx)
    return {
        "ok": True,
        "plan": plan,
        "prompts": prompts,
        "limitations": limitations,
    }


def _change_evidence(scored: List[Tuple[float, Dict[str, Any]]], intent: str) -> List[str]:
    lines = [f"Matched feature intent: {intent}"]
    for score, node in scored[:5]:
        lines.append(
            f"Module `{node.get('path')}` — fan-in {node.get('fan_in', 0)}, risk {node.get('risk_score', 0)}, match score {score:.1f}"
        )
    if len(scored) > 5:
        lines.append(f"… and {len(scored) - 5} more scored modules (not listed).")
    return lines


def _tests_for_change(paths: List[str], subsystems: List[str]) -> List[str]:
    tests: List[str] = []
    for path in paths[:4]:
        base = path.split("/")[-1]
        stem = base.rsplit(".", 1)[0] if "." in base else base
        tests.append(f"Unit/integration tests covering `{path}` (e.g. test_{stem}*)")
    if subsystems:
        tests.append(f"Subsystem regression: {', '.join(subsystems[:4])}")
    tests.append("Project CI / full test suite before merge")
    return tests


def investigate_symptom(symptom: str, ctx: Dict[str, Any]) -> Dict[str, Any]:
    """Symptom-based investigation plan (not stack-trace literal matching)."""
    text = (symptom or "").strip()
    if not text:
        return {"ok": False, "error": "Describe the symptom or behavior."}
    graph = ctx.get("graph")
    index = ctx.get("index")
    if not graph and not index:
        return {"ok": False, "error": "No repository scanned yet."}

    intent, terms = _detect_intent(text, _SYMPTOM_SPECS)
    spec = _SYMPTOM_SPECS.get(intent, {})
    search_terms = set(spec.get("search", ())) | terms

    blob = text.replace("\\", "/")
    explicit_paths: List[str] = []
    if index:
        for f in index.get("files", []):
            p = f.get("path")
            if p and p in blob:
                explicit_paths.append(p)

    modules = _production_modules(graph)
    risks_map = _risks_map(ctx.get("risks"))
    scored = _score_modules(modules, search_terms, risks_map)
    for path in explicit_paths:
        if path not in [n.get("path") for _, n in scored]:
            node = next((n for n in modules if n.get("path") == path), None)
            if node:
                scored.insert(0, (10.0, node))

    likely_modules = [node["path"] for _, node in scored[:10]]
    matched_ids = {node["id"] for _, node in scored[:10]}
    outbound, inbound = _graph_neighbors(graph, matched_ids) if graph else ([], [])

    why = spec.get("why", "Keyword overlap between the symptom and indexed module paths.")
    logical_hypothesis = spec.get(
        "hypothesis",
        "Behavior may diverge between code paths that share names but differ in timing, I/O, or configuration.",
    )
    evidence: List[str] = [f"Symptom intent: {intent}", why]
    for score, node in scored[:5]:
        path = node.get("path") or ""
        fan = node.get("fan_in", 0)
        evidence.append(f"`{path}` matched (score {score:.1f}, fan-in {fan})")
    if outbound:
        evidence.append(f"Outbound imports (sample): {', '.join(outbound[:6])}")
    if inbound:
        evidence.append(f"Inbound importers (sample): {', '.join(inbound[:6])}")
        if len(inbound) >= 5:
            evidence.append("High blast radius: many direct importers on matched modules.")
    if explicit_paths:
        evidence.append(f"Explicit path mention in symptom: {', '.join(explicit_paths)}")
    if not likely_modules:
        evidence.append("No production module paths matched — investigation stays hypothesis-level.")

    likely_symbols: List[str] = []
    for path in likely_modules[:6]:
        likely_symbols.extend(_path_symbols(path))

    confidence = "high" if explicit_paths else _confidence_label(len(likely_modules), scored[0][0] if scored else 0, intent)
    limitations = [
        "Heuristic symptom routing — not runtime profiling or log analysis.",
        "Only indexed production-scope modules are considered.",
    ]
    if not likely_modules:
        limitations.append("Atlas cannot localize this symptom without stronger anchors (file paths, error types, or subsystem names).")

    verify_steps = list(spec.get("verify", ()))
    verify_steps.extend(_suggested_questions(intent, likely_modules)[:3])
    inspect_first = likely_modules[:5] or explicit_paths[:5]
    risk_if_fixed = spec.get(
        "risk_if_fixed",
        "A narrow fix may mask upstream data or configuration issues — validate with tests before shipping.",
    )

    questions = _suggested_questions(intent, likely_modules)
    plan = {
        "symptom": text,
        "intent": intent,
        "likely_modules": likely_modules,
        "likely_files": likely_modules,
        "likely_symbols": sorted(set(likely_symbols))[:12],
        "most_likely_source": likely_modules[0] if likely_modules else None,
        "why": why,
        "logical_hypothesis": logical_hypothesis,
        "relevant_dependencies": {"outbound": outbound, "inbound": inbound},
        "evidence": evidence,
        "confidence": confidence,
        "inspect_first": inspect_first,
        "verification_steps": verify_steps[:8],
        "risk_if_fixed": risk_if_fixed,
        "suggested_files_to_inspect": likely_modules[:8],
        "suggested_questions": questions,
        "limitations": limitations,
    }
    prompts = build_investigation_prompts(plan, ctx)
    return {"ok": True, "plan": plan, "prompts": prompts, "limitations": limitations}


def _suggested_questions(intent: str, modules: List[str]) -> List[str]:
    base = [
        "When did the symptom start (deploy, config change, data change)?",
        "Is the issue reproducible in a single environment?",
    ]
    if intent == "paper_trading":
        base.append("Do backtest and live/paper use the same data feed and bar timing rules?")
    elif intent == "delayed_alerts":
        base.append("Are alerts queued — check worker lag vs send latency?")
    elif intent == "memory_growth":
        base.append("Does memory grow under steady load or only after specific actions?")
    elif intent == "dashboard_mismatch":
        base.append("Is the wrong value in the API/DB or only in the UI layer?")
    elif intent == "position_close":
        base.append("Are failures correlated with specific symbols, venues, or order types?")
    if modules:
        base.append(f"Trace the code path starting at `{modules[0]}` — what calls it?")
    return base[:6]


def simulate_change_impact(target: str, impact_payload: Dict[str, Any], ctx: Dict[str, Any]) -> Dict[str, Any]:
    """Enrich reverse-import impact with verification guidance (Part D)."""
    if not impact_payload.get("ok"):
        return impact_payload
    affected_files = impact_payload.get("affected_files") or []
    subsystems = impact_payload.get("affected_subsystems") or []
    fan_in = int(impact_payload.get("fan_in") or 0)
    risk_level = impact_payload.get("risk_level") or "unknown"
    if fan_in >= 25 or risk_level == "high":
        risk = "high"
    elif fan_in >= 6 or risk_level == "medium":
        risk = "medium"
    else:
        risk = "low"
    verification = [
        "Run targeted tests for the changed module and each direct importer listed.",
        "Smoke-test entry points in affected subsystems.",
        "Review unresolved imports in the graph health panel before large refactors.",
    ]
    if impact_payload.get("mock"):
        verification.append("Impact data is heuristic — confirm targets exist in the production graph.")
    return {
        **impact_payload,
        "simulation": {
            "potentially_affected_modules": affected_files,
            "potentially_affected_subsystems": subsystems,
            "risk_level": risk,
            "recommended_verification": verification,
            "tests_likely_affected": impact_payload.get("recommended_tests") or _tests_for_change(
                [impact_payload.get("target") or target], subsystems
            ),
        },
        "limitations": [
            impact_payload.get("note") or "Static reverse-import impact (resolved edges only).",
            "Dynamic dispatch and string-based imports are not modeled.",
        ],
    }


def build_implementation_prompts(plan: Dict[str, Any], ctx: Dict[str, Any]) -> Dict[str, str]:
    repo = ctx.get("repo_name") or "this repository"
    goal = plan.get("goal") or ""
    modules = plan.get("likely_affected_modules") or []
    files = plan.get("files_to_inspect_first") or modules[:8]
    risks = plan.get("architectural_risks") or []
    deps = plan.get("dependencies_involved") or {}
    size = plan.get("estimated_change_size") or "Unknown"
    confidence = plan.get("confidence") or "low"
    context_blurb = (ctx.get("explanation") or "")[:400]

    shared = {
        "goal": goal,
        "repo": repo,
        "files": files,
        "modules": modules,
        "subsystems": plan.get("likely_affected_subsystems") or [],
        "risks": risks,
        "deps_out": deps.get("outbound_imports") or [],
        "deps_in": deps.get("inbound_importers") or [],
        "tests": plan.get("tests_likely_affected") or [],
        "size": size,
        "confidence": confidence,
        "context": context_blurb,
        "limitations": plan.get("limitations") or [],
    }
    return {
        "claude": _prompt_claude_change(shared),
        "codex": _prompt_codex_change(shared),
        "cursor": _prompt_cursor_change(shared),
    }


def build_investigation_prompts(plan: Dict[str, Any], ctx: Dict[str, Any]) -> Dict[str, str]:
    shared = {
        "repo": ctx.get("repo_name") or "this repository",
        "symptom": plan.get("symptom") or "",
        "modules": plan.get("likely_modules") or [],
        "why": plan.get("why") or "",
        "evidence": plan.get("evidence") or [],
        "questions": plan.get("suggested_questions") or [],
        "confidence": plan.get("confidence") or "low",
        "limitations": plan.get("limitations") or [],
    }
    return {
        "claude": _prompt_claude_investigate(shared),
        "codex": _prompt_codex_investigate(shared),
        "cursor": _prompt_cursor_investigate(shared),
    }


def _prompt_claude_change(s: Dict[str, Any]) -> str:
    files = "\n".join(f"- {p}" for p in s["files"]) or "- (none matched — start from entry points)"
    risks = "\n".join(f"- {r}" for r in s["risks"][:6]) or "- Review coupling on listed modules"
    return (
        f"You are planning a change in `{s['repo']}` — do not implement yet.\n\n"
        f"## Goal\n{s['goal']}\n\n"
        f"## Repository context\n{s['context']}\n\n"
        f"## Files to inspect first\n{files}\n\n"
        f"## Likely subsystems\n{', '.join(s['subsystems']) or 'unknown'}\n\n"
        f"## Architectural risks\n{risks}\n\n"
        f"## Dependencies\nOutbound: {', '.join(s['deps_out'][:8]) or 'none listed'}\n"
        f"Inbound importers: {', '.join(s['deps_in'][:8]) or 'none listed'}\n\n"
        f"## Expected behavior\nProduce an implementation plan only: steps, interfaces to extend, tests to add. "
        f"Estimated size: {s['size']}. Atlas confidence: {s['confidence']}.\n\n"
        f"## Limitations\n" + "\n".join(f"- {x}" for x in s["limitations"])
    )


def _prompt_codex_change(s: Dict[str, Any]) -> str:
    return (
        f"# Change plan — {s['repo']}\n"
        f"Goal: {s['goal']}\n"
        f"Inspect first: {', '.join(s['files'][:6]) or 'entry points'}\n"
        f"Subsystems: {', '.join(s['subsystems'][:6])}\n"
        f"Risks: {'; '.join(str(r) for r in s['risks'][:4])}\n"
        f"Tests: {'; '.join(s['tests'][:3])}\n"
        f"Size: {s['size']} | Confidence: {s['confidence']}\n"
        f"Plan implementation steps only — no code until reviewed."
    )


def _prompt_cursor_change(s: Dict[str, Any]) -> str:
    return (
        f"@workspace Plan change: {s['goal']}\n"
        f"Start in: {', '.join(s['files'][:5]) or 'repository entry points'}\n"
        f"Watch risks: {', '.join(str(r) for r in s['risks'][:3])}\n"
        f"Subsystems: {', '.join(s['subsystems'][:4])}\n"
        f"Before coding: list steps, affected tests, and open questions. "
        f"Confidence {s['confidence']} — {s['limitations'][0] if s['limitations'] else 'static graph only'}."
    )


def _prompt_claude_investigate(s: Dict[str, Any]) -> str:
    mods = "\n".join(f"- {m}" for m in s["modules"][:8]) or "- No grounded module match — widen search using entry points"
    ev = "\n".join(f"- {e}" for e in s["evidence"][:6])
    qs = "\n".join(f"- {q}" for q in s["questions"])
    return (
        f"Investigate a symptom in `{s['repo']}` — hypothesis-first, cite evidence.\n\n"
        f"## Symptom\n{s['symptom']}\n\n"
        f"## Why these areas\n{s['why']}\n\n"
        f"## Likely modules (from static index)\n{mods}\n\n"
        f"## Evidence from Atlas\n{ev}\n\n"
        f"## Questions to answer\n{qs}\n\n"
        f"Confidence: {s['confidence']}. Do not claim certainty without runtime proof.\n"
        f"Limitations: {'; '.join(s['limitations'])}"
    )


def _prompt_codex_investigate(s: Dict[str, Any]) -> str:
    return (
        f"Bug investigation — {s['repo']}\n"
        f"Symptom: {s['symptom']}\n"
        f"Start modules: {', '.join(s['modules'][:6]) or 'TBD'}\n"
        f"Rationale: {s['why']}\n"
        f"Answer the diagnostic questions, trace call paths, propose minimal fix + test. "
        f"Confidence {s['confidence']}."
    )


def _prompt_cursor_investigate(s: Dict[str, Any]) -> str:
    return (
        f"@workspace Investigate: {s['symptom']}\n"
        f"Inspect: {', '.join(s['modules'][:5]) or 'search repo for symptom keywords'}\n"
        f"Atlas rationale: {s['why']}\n"
        f"Work through: {s['questions'][0] if s['questions'] else 'repro steps?'}\n"
        f"State confidence and unknowns — no fake file paths."
    )


def _md_bullets(items: Iterable[str], empty_line: str = "- (none)") -> List[str]:
    rows = [f"- {x}" for x in items if x]
    return rows or [empty_line]


def format_change_plan_markdown(plan: Dict[str, Any]) -> str:
    deps = plan.get("dependencies_involved") or {}
    lines = [
        "CHANGE PLAN",
        "===========",
        "",
        f"Goal: {plan.get('goal', '')}",
        "",
        "Files to inspect first:",
        *_md_bullets(plan.get("files_to_inspect_first") or [], "- (none matched — provide more context)"),
        "",
        "Files likely to change:",
        *_md_bullets((plan.get("files_likely_to_change") or plan.get("likely_affected_modules") or [])[:12]),
        "",
        "Files likely to break (direct importers / high coupling):",
        *_md_bullets(plan.get("files_likely_to_break") or [], "- (none identified from graph)"),
        "",
        "Likely affected subsystems:",
        *_md_bullets(plan.get("likely_affected_subsystems") or [], "- (unknown)"),
        "",
        "Entry points:",
        *_md_bullets(plan.get("entry_points") or [], "- (none detected)"),
        "",
        "Dependencies involved:",
        f"- Outbound: {', '.join(deps.get('outbound_imports') or []) or 'none'}",
        f"- Inbound: {', '.join(deps.get('inbound_importers') or []) or 'none'}",
        "",
        "Implementation order (static heuristic):",
        *_md_bullets(plan.get("implementation_order") or []),
        "",
        "Tests to add/update:",
        *_md_bullets(plan.get("tests_likely_affected") or []),
        "",
        "Verification plan:",
        *_md_bullets(plan.get("verification_plan") or []),
        "",
        "Architectural risks:",
        *_md_bullets(plan.get("architectural_risks") or [], "- Review coupling on listed modules"),
        "",
        f"Risk level: {plan.get('risk_level', 'unknown')}",
        f"Estimated change size: {plan.get('estimated_change_size', 'Unknown')}",
        f"Confidence: {plan.get('confidence', 'low')}",
    ]
    lim = plan.get("limitations") or []
    if lim:
        lines.extend(["", "Limitations:", *(f"- {x}" for x in lim)])
    return "\n".join(lines)


def format_investigation_plan_markdown(plan: Dict[str, Any]) -> str:
    deps = plan.get("relevant_dependencies") or {}
    symbols = plan.get("likely_symbols") or []
    lines = [
        "BUG INVESTIGATION PLAN",
        "======================",
        "",
        f"Symptom: {plan.get('symptom', '')}",
        "",
        f"Most likely source: {plan.get('most_likely_source') or '(no grounded module — see limitations)'}",
        "",
        "Likely files:",
        *_md_bullets(plan.get("likely_modules") or [], "- (none matched)"),
        "",
    ]
    if symbols:
        lines.extend(["Likely symbols (from filenames only):", *(f"- {s}" for s in symbols), ""])
    lines.extend([
        f"Why: {plan.get('why', '')}",
        "",
        f"Possible logical cause: {plan.get('logical_hypothesis', '')}",
        "",
        "Evidence:",
        *(f"- {e}" for e in (plan.get("evidence") or [])),
        "",
        "What to inspect first:",
        *_md_bullets(
            plan.get("inspect_first") or plan.get("suggested_files_to_inspect") or [],
            "- Entry points and top import hubs",
        ),
        "",
        "Verification:",
        *_md_bullets(plan.get("verification_steps") or []),
        "",
        "Relevant dependencies:",
        f"- Outbound: {', '.join(deps.get('outbound') or []) or 'none'}",
        f"- Inbound: {', '.join(deps.get('inbound') or []) or 'none'}",
        "",
        f"Risk if fixed incorrectly: {plan.get('risk_if_fixed', '')}",
        "",
        f"Confidence: {plan.get('confidence', 'low')}",
    ])
    lim = plan.get("limitations") or []
    if lim:
        lines.extend(["", "Limitations:", *(f"- {x}" for x in lim)])
    return "\n".join(lines)
