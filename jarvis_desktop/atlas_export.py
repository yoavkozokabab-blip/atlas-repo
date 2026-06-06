"""Phase 169 — Minimal Atlas export modes (FULL_EXPORT vs MINIMAL_EXPORT).

Formatting layer only; does not change planning/impact intelligence.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple

FULL_EXPORT = "FULL_EXPORT"
MINIMAL_EXPORT = "MINIMAL_EXPORT"
MEMORY_EXPORT = "MEMORY_EXPORT"
EXPORT_MODES = (FULL_EXPORT, MINIMAL_EXPORT, MEMORY_EXPORT)


def _bullets(items: List[str], limit: int = 5, empty: str = "- (none)") -> str:
    rows = [f"- {x}" for x in (items or [])[:limit] if x]
    return "\n".join(rows) if rows else empty


def _dedupe_paths(paths: List[str], limit: int = 5) -> List[str]:
    seen: set = set()
    out: List[str] = []
    for p in paths or []:
        norm = (p or "").replace("\\", "/").strip()
        if not norm or norm in seen:
            continue
        seen.add(norm)
        out.append(norm)
        if len(out) >= limit:
            break
    return out


def _concept_label(plan: Dict[str, Any]) -> str:
    dk = plan.get("domain_knowledge") or {}
    if not dk.get("applied") and not dk.get("concept_id"):
        return ""
    name = dk.get("concept_id") or dk.get("concept_name") or ""
    quality = dk.get("knowledge_quality_label") or dk.get("concept_quality_score") or ""
    if name and quality:
        return f"{name} ({quality})"
    return name or ""


def _evidence_lines(plan_or_result: Dict[str, Any], limit: int = 2) -> List[str]:
    ep = plan_or_result.get("evidence_panel") or (plan_or_result.get("plan") or {}).get("evidence_panel")
    if isinstance(ep, dict):
        if ep.get("summary"):
            return [str(ep["summary"])]
        items = ep.get("items") or []
        return [str(i.get("reason") or i.get("path") or i) for i in items[:limit] if i]
    ev = plan_or_result.get("evidence") or (plan_or_result.get("plan") or {}).get("evidence") or []
    return [str(x) for x in ev[:limit] if x]


def session_context(state: Dict[str, Any]) -> Dict[str, Any]:
    """Build once-per-scan session envelope (ATLAS_SESSION v1)."""
    scan = state.get("scan") or {}
    summary = state.get("summary") or {}
    gh = summary.get("graph_health") or scan.get("graph_health") or {}
    gh_label = gh.get("label") if isinstance(gh, dict) else str(gh or "unknown")
    index = state.get("index") or {}
    subs = sorted(
        (s for s in index.get("subsystems", []) if s.get("role_counts", {}).get("production_code", 0) > 0),
        key=lambda s: (-s.get("role_counts", {}).get("production_code", 0), s.get("name", "")),
    )
    sub_names = [s.get("name", "") for s in subs[:5] if s.get("name")]
    hubs = [f"{h.get('module')} ({h.get('fan_in', 0)} importers)" for h in (scan.get("top_hubs") or [])[:3]]
    risks = [r.get("module", "") for r in (scan.get("top_risks") or [])[:3] if r.get("module")]
    lines = [
        "ATLAS_SESSION v1",
        f"repo: {scan.get('repo_name') or summary.get('repo_name') or 'repository'}",
        f"graph_health: {gh_label}",
        f"modules: {scan.get('module_count', 0)}  edges: {scan.get('dependency_edges', 0)}  "
        f"files: {scan.get('file_count', 0)}",
        f"top_subsystems: {', '.join(sub_names) or 'n/a'}",
        f"top_hubs: {', '.join(hubs) or 'n/a'}",
        f"top_risks: {', '.join(risks) or 'n/a'}",
    ]
    text = "\n".join(lines)
    return {"text": text, "mode": "SESSION", "tokens": _estimate_tokens(text)}


def minimal_build_export(plan: Dict[str, Any], *, goal: str = "") -> str:
    files = _dedupe_paths(
        list(plan.get("files_to_inspect_first") or [])
        + list(plan.get("likely_affected_modules") or []),
        5,
    )
    may_break = _dedupe_paths(list(plan.get("what_may_break") or plan.get("files_likely_to_break") or []), 5)
    impl = _dedupe_paths(list(plan.get("implementation_order") or files), 4)
    concept = _concept_label(plan)
    evidence = _evidence_lines(plan, 2)
    lines = [
        "# Atlas Build (minimal)",
        f"Goal: {goal or plan.get('goal') or plan.get('intent') or ''}",
    ]
    if concept:
        lines.append(f"Concept: {concept}")
    lines.append(f"Confidence: {plan.get('confidence', 'low')} · Risk: {plan.get('risk_level', 'unknown')}")
    lines.append("")
    lines.append("## Files (top 5)")
    lines.append(_bullets(files, 5))
    if impl and impl != files:
        lines.append("")
        lines.append("## Implementation order")
        lines.append(_bullets(impl, 4))
    if may_break:
        lines.append("")
        lines.append("## May break (importers)")
        lines.append(_bullets(may_break, 5))
    if evidence:
        lines.append("")
        lines.append("## Evidence")
        lines.append(_bullets(evidence, 2))
    lim = (plan.get("limitations") or [])[:1]
    if lim:
        lines.append("")
        lines.append(f"Caveat: {lim[0]}")
    return "\n".join(lines).strip() + "\n"


def minimal_investigate_export(plan: Dict[str, Any]) -> str:
    symptom = plan.get("symptom_summary") or plan.get("symptom") or ""
    root = plan.get("most_likely_root_cause") or plan.get("most_likely_source") or ""
    hyps = plan.get("hypotheses") or []
    h1 = hyps[0] if hyps else {}
    h1_files = _dedupe_paths(list(h1.get("files_involved") or plan.get("likely_modules") or []), 5)
    verify = list(plan.get("verification_checklist") or plan.get("verification_steps") or [])[:4]
    fix = list(plan.get("minimal_fix_strategy") or [])[:3]
    evidence = _evidence_lines(plan, 2)
    lines = [
        "# Atlas Investigation (minimal)",
        f"Symptom: {symptom}",
        f"Confidence: {plan.get('confidence', 'low')}",
        "",
        "## Most likely root cause",
        root or "(not localizable yet)",
    ]
    if h1:
        lines.extend([
            "",
            "## Top hypothesis",
            f"- {h1.get('title', 'hypothesis')}: {h1.get('why_it_fits', '')}",
            "## Files",
            _bullets(h1_files, 5),
        ])
    elif h1_files:
        lines.extend(["", "## Files", _bullets(h1_files, 5)])
    if evidence:
        lines.append("")
        lines.append("## Evidence")
        lines.append(_bullets(evidence, 2))
    if verify:
        lines.append("")
        lines.append("## Verify")
        lines.append(_bullets(verify, 4))
    if fix:
        lines.append("")
        lines.append("## Minimal fix")
        lines.append(_bullets(fix, 3))
    return "\n".join(lines).strip() + "\n"


def minimal_impact_export(result: Dict[str, Any]) -> str:
    target = result.get("target") or ""
    direct = _dedupe_paths(list(result.get("direct_impact") or []), 8)
    indirect = _dedupe_paths(list(result.get("indirect_impact") or []), 5)
    evidence = _evidence_lines(result, 2)
    sem = result.get("semantic_label") or ""
    lines = [
        "# Atlas Impact (minimal)",
        f"Target: {target}",
    ]
    if sem:
        lines.append(f"Semantic: {sem}")
    lines.append(f"Confidence: {result.get('confidence', 'low')} · Risk: {result.get('risk_level', 'unknown')}")
    lines.append("")
    lines.append("## Direct impact")
    lines.append(_bullets(direct, 8))
    if indirect:
        lines.append("")
        lines.append("## Indirect (top 5)")
        lines.append(_bullets(indirect, 5))
    if evidence:
        lines.append("")
        lines.append("## Evidence")
        lines.append(_bullets(evidence, 2))
    return "\n".join(lines).strip() + "\n"


def full_build_export(plan: Dict[str, Any], formatted: str, prompts: Optional[Dict[str, str]] = None) -> str:
    """FULL_EXPORT: formatted markdown + Claude prompt (legacy rich export)."""
    parts = [formatted or ""]
    if prompts and prompts.get("claude"):
        parts.append("\n---\n## AI prompt\n" + prompts["claude"])
    return "\n".join(p for p in parts if p).strip() + "\n"


def full_investigate_export(plan: Dict[str, Any], formatted: str, prompts: Optional[Dict[str, str]] = None) -> str:
    parts = [formatted or ""]
    if prompts and prompts.get("claude"):
        parts.append("\n---\n## AI prompt\n" + prompts["claude"])
    return "\n".join(p for p in parts if p).strip() + "\n"


def full_impact_export(result: Dict[str, Any]) -> str:
    target = result.get("target") or ""
    direct = result.get("direct_impact") or []
    subs = result.get("affected_subsystems") or []
    subs_s = ", ".join(subs[:6]) or "(none resolved)"
    prompt = result.get("recommended_prompt") or (
        f"I am about to change `{target}` (imported by {len(direct)} module(s), "
        f"affecting subsystems: {subs_s}). Review breakage risk and list tests to run."
    )
    parts = [
        prompt,
        "",
        "## Impact detail",
        f"Target: {target}",
        f"Risk: {result.get('risk_level')} · Confidence: {result.get('confidence')}",
        "## Direct",
        _bullets(direct, 12),
        "## Indirect",
        _bullets(result.get("indirect_impact") or [], 12),
        "## Tests",
        _bullets(result.get("tests_likely_affected") or [], 8),
        "## Verification",
        _bullets(result.get("recommended_verification") or [], 6),
    ]
    if result.get("what_probably_wont_break"):
        parts.extend(["## Probably safe", _bullets(result.get("what_probably_wont_break") or [], 6)])
    arch = result.get("confidence_explanation") or ""
    if arch:
        parts.extend(["## Architecture note", arch])
    return "\n".join(parts).strip() + "\n"


def _estimate_tokens(text: str) -> int:
    return max(0, round(len(text or "") / 4))


def export_metrics(
    workflow: str,
    *,
    full_text: str,
    minimal_text: str,
    delta_text: str = "",
    mode: str = MINIMAL_EXPORT,
) -> Dict[str, Any]:
    full_tokens = _estimate_tokens(full_text)
    minimal_tokens = _estimate_tokens(minimal_text)
    delta_tokens = _estimate_tokens(delta_text) if delta_text else 0
    reduction = round(100 * (1 - minimal_tokens / full_tokens), 1) if full_tokens else 0.0
    delta_reduction = (
        round(100 * (1 - delta_tokens / minimal_tokens), 1)
        if minimal_tokens and delta_tokens
        else 0.0
    )
    if mode == MEMORY_EXPORT and delta_text:
        active = delta_text
    elif mode == MINIMAL_EXPORT:
        active = minimal_text
    else:
        active = full_text
    return {
        "mode": mode,
        "workflow": workflow,
        "tokens": _estimate_tokens(active),
        "full_export_tokens": full_tokens,
        "minimal_export_tokens": minimal_tokens,
        "delta_export_tokens": delta_tokens,
        "reduction_vs_full_pct": reduction,
        "delta_reduction_vs_minimal_pct": delta_reduction,
        "text": active,
        "full_text": full_text,
        "minimal_text": minimal_text,
        "delta_text": delta_text,
    }


def attach_workflow_exports(
    result: Dict[str, Any],
    workflow: str,
    *,
    plan: Optional[Dict[str, Any]] = None,
    formatted: str = "",
    prompts: Optional[Dict[str, str]] = None,
    goal: str = "",
    default_mode: str = MINIMAL_EXPORT,
    memory_ref: str = "",
) -> None:
    """Add export blocks to API result; default active export is MINIMAL.

    Phase 172: also computes MEMORY_EXPORT (delta-only) when memory_ref is supplied.
    The delta text is the compact per-question payload; the ATLAS_REPOSITORY_MEMORY v1
    header is sent separately via session_export_packet() and is NOT repeated here.
    """
    plan = plan or result.get("plan") or {}
    if workflow == "build":
        full = full_build_export(plan, formatted, prompts)
        minimal = minimal_build_export(plan, goal=goal)
    elif workflow == "investigate":
        full = full_investigate_export(plan, formatted, prompts)
        minimal = minimal_investigate_export(plan)
    elif workflow == "impact":
        full = full_impact_export(result)
        minimal = minimal_impact_export(result)
    else:
        return

    # Phase 172 — delta export (ATLAS_DELTA v1)
    delta = ""
    try:
        from . import repository_memory as _rm
        delta = _rm.delta_text(
            workflow,
            plan_or_result=result if workflow == "impact" else {"plan": plan},
            memory_ref=memory_ref,
            goal=goal,
        )
    except Exception:
        delta = ""

    metrics = export_metrics(
        workflow, full_text=full, minimal_text=minimal, delta_text=delta, mode=default_mode
    )
    result["export"] = metrics
    result["export_full"] = export_metrics(
        workflow, full_text=full, minimal_text=minimal, delta_text=delta, mode=FULL_EXPORT
    )
    result["export_minimal"] = export_metrics(
        workflow, full_text=full, minimal_text=minimal, delta_text=delta, mode=MINIMAL_EXPORT
    )
    if delta:
        result["export_memory"] = export_metrics(
            workflow, full_text=full, minimal_text=minimal, delta_text=delta, mode=MEMORY_EXPORT
        )


def quality_fidelity_score(workflow: str, full_text: str, minimal_text: str, plan_or_result: Dict[str, Any]) -> Dict[str, Any]:
    """Structural fidelity proxy for regression (paths + key fields preserved)."""
    plan = plan_or_result.get("plan") or plan_or_result

    def _paths_from_plan() -> List[str]:
        if workflow == "build":
            return _dedupe_paths(
                list(plan.get("files_to_inspect_first") or []) + list(plan.get("what_may_break") or []),
                12,
            )
        if workflow == "investigate":
            hyps = plan.get("hypotheses") or []
            files = list(hyps[0].get("files_involved") if hyps else []) or list(plan.get("likely_modules") or [])
            return _dedupe_paths(files, 12)
        if workflow == "impact":
            return _dedupe_paths(list(plan_or_result.get("direct_impact") or []), 12)
        return []

    canonical = _paths_from_plan()
    conf = plan.get("confidence") or plan_or_result.get("confidence") or ""

    def _path_hits(text: str) -> int:
        low = text.lower()
        return sum(1 for p in canonical[:5] if p and p.lower() in low)

    full_hits = _path_hits(full_text)
    min_hits = _path_hits(minimal_text)
    top5 = len(canonical[:5]) or 1
    path_score = min_hits / top5
    conf_ok = bool(conf) and conf.lower() in minimal_text.lower()
    checks = {
        "top_paths_in_minimal": min_hits,
        "top_paths_in_full": full_hits,
        "confidence_preserved": conf_ok,
        "minimal_smaller": _estimate_tokens(minimal_text) < _estimate_tokens(full_text),
    }
    fidelity = round((path_score * 0.7 + (0.2 if conf_ok else 0) + (0.1 if checks["minimal_smaller"] else 0)) * 100, 1)
    quality_loss_pct = round(max(0.0, 100 - fidelity), 1)
    return {
        "fidelity_pct": fidelity,
        "quality_loss_pct": quality_loss_pct,
        "checks": checks,
        "canonical_paths": canonical[:5],
    }
