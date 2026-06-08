"""Structured analysis reports for Atlas workflow results (presentation only).

Reformats engine output into executive summaries, evidence, ranked files,
confidence, verification steps, and copy-ready prompts. Does not alter
planning or impact engine logic.
"""

from __future__ import annotations

import re
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

_CONF_ORDER = ("low", "medium", "high")
_STRENGTH_ORDER = ("weak", "moderate", "strong")


def _norm_confidence(value: Any) -> str:
    raw = str(value or "low").strip().lower()
    if "high" in raw or raw in ("medium-high", "strong"):
        return "High"
    if "medium" in raw or raw in ("low-medium", "moderate"):
        return "Medium"
    return "Low"


def _evidence_strength(
    *,
    file_count: int,
    evidence_count: int,
    has_symbols: bool,
    confidence: str,
) -> str:
    conf = _norm_confidence(confidence)
    score = file_count + evidence_count + (2 if has_symbols else 0)
    if conf == "High" and score >= 4:
        return "Strong"
    if conf == "Low" and score <= 1:
        return "Weak"
    return "Moderate"


def _risk_label(value: Any) -> str:
    raw = str(value or "unknown").strip().lower()
    if raw in ("high", "critical"):
        return "High"
    if raw in ("medium", "moderate", "watch"):
        return "Medium"
    if raw in ("low", "minimal"):
        return "Low"
    return "Unknown"


def _clean_goal(text: str) -> str:
    """Avoid echoing typo-heavy user input verbatim in summaries."""
    t = re.sub(r"\s+", " ", (text or "").strip())
    if len(t) > 120:
        t = t[:117].rstrip() + "…"
    return t


def _paraphrase_request(text: str, *, fallback: str) -> str:
    cleaned = _clean_goal(text)
    if not cleaned or len(cleaned) < 4:
        return fallback
    lower = cleaned.lower()
    if any(k in lower for k in ("bug", "error", "fail", "broken", "wrong", "crash")):
        return "the reported symptom"
    if any(k in lower for k in ("add", "implement", "create", "introduce", "build")):
        return "the requested change"
    if any(k in lower for k in ("remove", "delete", "change", "refactor")):
        return "the proposed modification"
    return "your request"


def _md_bullets(items: Iterable[str], empty: str = "- (none)") -> List[str]:
    rows = [f"- {x}" for x in items if x]
    return rows or [empty]


def _md_ranked_files(files: Sequence[Dict[str, Any]]) -> List[str]:
    if not files:
        return ["- (none matched — add a file path, error message, or more specific context)"]
    lines: List[str] = []
    for row in files:
        rank = row.get("rank", len(lines) + 1)
        path = row.get("path") or "(unknown)"
        why = row.get("why") or row.get("reason") or "Selected from repository scan signals."
        risk = row.get("risk") or row.get("impact") or "Unknown"
        action = row.get("action") or row.get("recommended_action") or "Inspect and confirm relevance."
        lines.append(f"{rank}. `{path}`")
        lines.append(f"   Why: {why}")
        lines.append(f"   Risk: {risk}")
        lines.append(f"   Action: {action}")
    return lines


def _md_evidence(items: Sequence[Dict[str, Any]]) -> List[str]:
    if not items:
        return ["- Atlas had limited grounded signals for this result — treat paths as starting points, not proof."]
    out: List[str] = []
    for item in items:
        signal = item.get("signal") or item.get("text") or ""
        why = item.get("why_it_matters") or item.get("why") or ""
        if why:
            out.append(f"- **{signal}** — {why}")
        else:
            out.append(f"- {signal}")
    return out


def _md_verification(steps: Sequence[Dict[str, Any]]) -> List[str]:
    if not steps:
        return ["- (none — gather a stack trace, failing test, or exact file path first)"]
    lines: List[str] = []
    for i, step in enumerate(steps, 1):
        what = step.get("what") or step.get("text") or ""
        where = step.get("where") or ""
        confirms = step.get("confirms") or step.get("confirms_if") or ""
        rules_out = step.get("rules_out") or step.get("rules_out_if") or ""
        lines.append(f"{i}. **What to check:** {what}")
        if where:
            lines.append(f"   **Where:** {where}")
        if confirms:
            lines.append(f"   **Confirms hypothesis if:** {confirms}")
        if rules_out:
            lines.append(f"   **Rules out if:** {rules_out}")
    return lines


def _verification_from_strings(steps: Sequence[str]) -> List[Dict[str, str]]:
    out: List[Dict[str, str]] = []
    for raw in steps:
        text = str(raw or "").strip()
        if not text:
            continue
        where = ""
        m = re.search(r"\b(?:in|at|from|under|inside)\s+(`[^`]+`|[\w./-]+\.(?:py|js|ts|tsx|go|rs|java))\b", text, re.I)
        if m:
            where = m.group(1).strip("`")
        confirms = ""
        rules_out = ""
        if " if " in text.lower():
            parts = re.split(r"\s+if\s+", text, maxsplit=1, flags=re.I)
            if len(parts) == 2:
                confirms = parts[1].strip()
        if " unless " in text.lower():
            parts = re.split(r"\s+unless\s+", text, maxsplit=1, flags=re.I)
            if len(parts) == 2:
                rules_out = parts[1].strip()
        out.append({"what": text, "where": where, "confirms": confirms, "rules_out": rules_out})
    return out


def _merge_ranked_files(*sources: Sequence[Dict[str, Any]], limit: int = 12) -> List[Dict[str, Any]]:
    seen: set[str] = set()
    merged: List[Dict[str, Any]] = []
    for source in sources:
        for row in source:
            path = str(row.get("path") or "").strip()
            if not path or path in seen:
                continue
            seen.add(path)
            merged.append(dict(row))
            if len(merged) >= limit:
                return merged
    for i, row in enumerate(merged, 1):
        row.setdefault("rank", i)
    return merged


def _file_evidences_to_ranked(
    file_evidences: Sequence[Dict[str, Any]],
    *,
    default_risk: str = "Medium",
) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for fe in file_evidences:
        path = fe.get("path") or ""
        if not path:
            continue
        syms = ", ".join((fe.get("matching_symbols") or [])[:4])
        reason = fe.get("selected_because") or fe.get("reason_selected") or ""
        if not reason:
            reason = f"Matched symbols: {syms}" if syms else "Repository evidence matched this path."
        score = fe.get("evidence_score")
        risk = default_risk
        if isinstance(score, (int, float)):
            if score >= 70:
                risk = "High"
            elif score <= 30:
                risk = "Low"
        out.append({
            "path": path,
            "why": reason,
            "risk": risk,
            "action": "Open this file and confirm the matched symbols or imports support the plan.",
        })
    return out


def _paths_to_ranked(
    paths: Sequence[str],
    *,
    why_default: str,
    risk: str = "Medium",
    action: str = "Inspect this file against the request and note importers/tests.",
) -> List[Dict[str, Any]]:
    return [
        {"path": p, "why": why_default, "risk": risk, "action": action}
        for p in paths if p
    ]


def _implementation_why_ranked(rows: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for row in rows:
        path = row.get("path") or ""
        if not path:
            continue
        tier = str(row.get("tier") or "").lower()
        risk = "High" if tier == "break" else "Medium" if tier == "implementation" else "Low"
        out.append({
            "path": path,
            "why": row.get("why") or "Selected from dependency and keyword signals.",
            "risk": risk,
            "action": "Compare current behavior here with the planned change.",
        })
    return out


def _collect_change_ranked_files(plan: Dict[str, Any]) -> List[Dict[str, Any]]:
    rev = plan.get("repository_evidence") or {}
    impl = _implementation_why_ranked(plan.get("implementation_files_with_why") or [])
    evidence = _file_evidences_to_ranked(rev.get("file_evidences") or [])
    inspect = _paths_to_ranked(
        plan.get("files_to_inspect_first") or [],
        why_default="High-priority starting point from graph and keyword overlap.",
        risk="Medium",
    )
    modify = _paths_to_ranked(
        (plan.get("files_likely_to_change") or plan.get("likely_affected_modules") or [])[:8],
        why_default="Likely touched during implementation based on coupling.",
        risk="High",
        action="Plan edits here carefully; check direct importers after changes.",
    )
    breakers = _paths_to_ranked(
        (plan.get("files_likely_to_break") or plan.get("what_may_break") or [])[:6],
        why_default="Direct importers or high-coupling neighbors that may regress.",
        risk="High",
        action="Run focused tests on these modules after any interface change.",
    )
    return _merge_ranked_files(evidence, impl, inspect, modify, breakers)


def _collect_investigate_ranked_files(plan: Dict[str, Any]) -> List[Dict[str, Any]]:
    ranked: List[Dict[str, Any]] = []
    for hyp in (plan.get("hypotheses") or [])[:3]:
        conf = _norm_confidence(hyp.get("confidence"))
        risk = "High" if conf == "High" else "Medium"
        for path in (hyp.get("files_involved") or [])[:4]:
            ranked.append({
                "path": path,
                "why": hyp.get("why_it_fits") or f"Linked to hypothesis: {hyp.get('title') or 'primary lead'}.",
                "risk": risk,
                "action": hyp.get("what_to_inspect") or "Inspect call paths and data flow here.",
            })
    rev = plan.get("repository_evidence") or {}
    ranked.extend(_file_evidences_to_ranked(rev.get("file_evidences") or [], default_risk="Medium"))
    ranked.extend(_paths_to_ranked(
        plan.get("inspect_first") or [],
        why_default="Symptom keywords or graph signals point here first.",
    ))
    return _merge_ranked_files(ranked)


def _collect_impact_ranked_files(result: Dict[str, Any]) -> List[Dict[str, Any]]:
    direct = _paths_to_ranked(
        result.get("direct_impact") or [],
        why_default="Imports the target module directly — most likely to break on signature or behavior changes.",
        risk="High",
        action="Review imports and run tests covering this module.",
    )
    indirect = _paths_to_ranked(
        result.get("indirect_impact") or [],
        why_default="Transitive dependency — may break if direct importers change behavior.",
        risk="Medium",
        action="Smoke-test after direct importers are updated.",
    )
    return _merge_ranked_files(direct, indirect)


def _collect_evidence_change(plan: Dict[str, Any]) -> List[Dict[str, str]]:
    items: List[Dict[str, str]] = []
    rev = plan.get("repository_evidence") or {}
    for found in (rev.get("found") or [])[:6]:
        items.append({"signal": found, "why_it_matters": "Existing repository pattern Atlas matched to your request."})
    for fe in (rev.get("file_evidences") or [])[:5]:
        syms = ", ".join((fe.get("matching_symbols") or [])[:4])
        if syms:
            items.append({
                "signal": f"`{fe.get('path')}` — symbols: {syms}",
                "why_it_matters": "Symbol index ties this file to the requested concept or change area.",
            })
    deps = plan.get("dependencies_involved") or {}
    inbound = deps.get("inbound_importers") or []
    if inbound:
        items.append({
            "signal": f"Inbound importers: {', '.join(inbound[:5])}",
            "why_it_matters": "Changes may ripple outward through these dependent modules.",
        })
    outbound = deps.get("outbound_imports") or []
    if outbound:
        items.append({
            "signal": f"Outbound imports: {', '.join(outbound[:5])}",
            "why_it_matters": "Implementation may need to align with dependencies this area already uses.",
        })
    dk = plan.get("domain_knowledge") or {}
    if dk.get("applied") and dk.get("concept_name"):
        items.append({
            "signal": f"Concept match: {dk.get('concept_name')}",
            "why_it_matters": str(dk.get("why_this_matters") or "Domain knowledge shaped file roles and risks."),
        })
    for risk in (plan.get("architectural_risks") or [])[:3]:
        items.append({"signal": str(risk), "why_it_matters": "Architectural coupling or boundary risk to respect during the change."})
    return items[:10]


def _collect_evidence_investigate(plan: Dict[str, Any]) -> List[Dict[str, str]]:
    items: List[Dict[str, str]] = []
    for hyp in (plan.get("hypotheses") or [])[:3]:
        for ev in (hyp.get("evidence") or [])[:3]:
            items.append({
                "signal": str(ev),
                "why_it_matters": f"Supports hypothesis: {hyp.get('title') or 'ranked lead'}.",
            })
    for ev in (plan.get("evidence") or [])[:4]:
        items.append({"signal": str(ev), "why_it_matters": "Grounding signal from scan metadata or symptom parsing."})
    rev = plan.get("repository_evidence") or {}
    for found in (rev.get("found") or [])[:4]:
        items.append({"signal": found, "why_it_matters": "Repository pattern relevant to the symptom area."})
    return items[:10]


def _collect_evidence_impact(result: Dict[str, Any]) -> List[Dict[str, str]]:
    items: List[Dict[str, str]] = []
    for ev in (result.get("evidence") or [])[:6]:
        items.append({"signal": str(ev), "why_it_matters": "Import-graph or symbol evidence for blast-radius estimate."})
    if result.get("semantic_label"):
        items.append({
            "signal": f"Semantic target: {result.get('semantic_label')}",
            "why_it_matters": "Atlas resolved your target to concrete modules beyond exact path match.",
        })
    panel = result.get("evidence_panel") or result.get("impact_evidence_panel") or {}
    for row in (panel.get("items") or panel.get("evidence_items") or [])[:4]:
        if isinstance(row, dict):
            items.append({
                "signal": row.get("label") or row.get("path") or str(row),
                "why_it_matters": row.get("why") or row.get("detail") or "Symbol or import evidence.",
            })
    arch = result.get("architecture") or {}
    for crossing in (arch.get("boundary_crossings") or result.get("boundary_crossings") or [])[:3]:
        items.append({"signal": str(crossing), "why_it_matters": "Cross-subsystem coupling increases regression risk."})
    return items[:10]


def _confidence_reason_change(plan: Dict[str, Any], *, strength: str) -> str:
    bits: List[str] = []
    files = _collect_change_ranked_files(plan)
    if files:
        bits.append(f"{len(files)} ranked file(s) with grounded signals")
    else:
        bits.append("few file matches from the current scan")
    rev = plan.get("repository_evidence") or {}
    if rev.get("found"):
        bits.append("repository evidence matched existing patterns")
    if rev.get("missing"):
        bits.append("some expected patterns were not found")
    if plan.get("limitations"):
        bits.append(str(plan["limitations"][0]))
    if strength == "Weak":
        bits.append("treat this as a starting hypothesis until you confirm in code")
    return "; ".join(bits[:4]).capitalize() + "."


def _confidence_reason_investigate(plan: Dict[str, Any], *, strength: str) -> str:
    hyps = plan.get("hypotheses") or []
    bits: List[str] = []
    if hyps:
        bits.append(f"{len(hyps)} ranked hypothesis/hypotheses from symptom anchors")
    else:
        bits.append("symptom alone did not anchor a specific module")
    if plan.get("most_likely_root_cause") or plan.get("most_likely_source"):
        bits.append("a primary lead module was identified")
    if strength == "Weak":
        bits.append("add a stack trace, failing test, or exact file path to strengthen grounding")
    return "; ".join(bits[:4]).capitalize() + "."


def _confidence_reason_impact(result: Dict[str, Any], *, strength: str) -> str:
    bits: List[str] = []
    if result.get("confidence_explanation"):
        bits.append(str(result["confidence_explanation"]))
    direct = len(result.get("direct_impact") or [])
    indirect = len(result.get("indirect_impact") or [])
    bits.append(f"{direct} direct and {indirect} transitive importer(s) in graph")
    if result.get("confidence_cap_reason"):
        bits.append(str(result["confidence_cap_reason"]))
    if strength == "Weak":
        bits.append("dynamic imports and runtime dispatch are not modeled")
    return "; ".join(bits[:4]).capitalize() + "."


def build_change_plan_report(plan: Dict[str, Any], *, user_request: str = "") -> Dict[str, Any]:
    goal = str(plan.get("goal") or plan.get("change_goal") or "")
    request_label = _paraphrase_request(user_request or goal, fallback="the requested change")
    ranked = _collect_change_ranked_files(plan)
    evidence_items = _collect_evidence_change(plan)
    confidence = _norm_confidence(plan.get("confidence"))
    strength = _evidence_strength(
        file_count=len(ranked),
        evidence_count=len(evidence_items),
        has_symbols=any("symbols:" in (e.get("signal") or "") for e in evidence_items),
        confidence=confidence,
    )
    order = list(plan.get("implementation_order") or [])
    strategy = (
        order[0] if order else
        "Start with the highest-ranked file, confirm current behavior, then expand outward through importers."
    )
    if len(order) > 1:
        strategy_text = " → ".join(order[:4])
        if len(order) > 4:
            strategy_text += f" → … ({len(order)} steps total)"
    else:
        strategy_text = strategy
    safest = ranked[0]["path"] if ranked else (order[0] if order else "No single safe anchor — inspect entry points first.")
    subs = plan.get("likely_affected_subsystems") or plan.get("affected_systems") or []
    sub_text = f" in {', '.join(subs[:3])}" if subs else ""
    if ranked:
        executive_summary = (
            f"Atlas mapped {request_label} to {len(ranked)} primary file(s){sub_text}, "
            f"starting at `{ranked[0]['path']}`. "
            f"Confidence is {confidence.lower()} ({strength.lower()} evidence)."
        )
    else:
        executive_summary = (
            f"Atlas mapped {request_label}{sub_text} but found limited file matches. "
            f"Confidence is {confidence.lower()} ({strength.lower()} evidence) — add a file path or narrower scope."
        )
    verification = _verification_from_strings(
        (plan.get("verification_plan") or plan.get("verification_steps") or [])[:8]
    )
    copy_prompt = build_change_copy_prompt(plan, ranked_files=ranked, verification=verification, user_request=user_request or goal)
    return {
        "workflow": "change_plan",
        "executive_summary": executive_summary,
        "direction": {
            "title": "Recommended implementation direction",
            "items": [
                {"label": "Strategy", "value": strategy_text},
                {"label": "Safest first change", "value": f"Begin with `{safest}` — confirm current behavior before broad edits."},
                {"label": "Expected risk", "value": f"{_risk_label(plan.get('risk_level'))} — estimated size {plan.get('estimated_change_size') or 'Unknown'}."},
            ],
        },
        "confidence": {
            "level": confidence,
            "evidence_strength": strength,
            "reason": _confidence_reason_change(plan, strength=strength),
        },
        "evidence": evidence_items,
        "ranked_files": ranked,
        "verification_steps": verification,
        "copy_prompt": copy_prompt,
    }


def build_investigation_report(plan: Dict[str, Any], *, user_request: str = "") -> Dict[str, Any]:
    symptom = str(plan.get("symptom_summary") or plan.get("symptom") or "")
    request_label = _paraphrase_request(user_request or symptom, fallback="the reported symptom")
    ranked = _collect_investigate_ranked_files(plan)
    evidence_items = _collect_evidence_investigate(plan)
    confidence = _norm_confidence(plan.get("confidence"))
    strength = _evidence_strength(
        file_count=len(ranked),
        evidence_count=len(evidence_items),
        has_symbols=bool(evidence_items),
        confidence=confidence,
    )
    root = plan.get("most_likely_root_cause") or plan.get("most_likely_source") or "(not localizable yet — add a file path or error text)"
    top_hyp = (plan.get("hypotheses") or [{}])[0]
    hyp_files = list(top_hyp.get("files_involved") or [])
    if not hyp_files and ranked:
        hyp_files = [ranked[0]["path"]]
    likely_area = ", ".join(hyp_files[:3]) or "unknown module"
    why_likely = top_hyp.get("why_it_fits") or "Symptom keywords and graph proximity suggest this area first."
    executive_summary = (
        f"Atlas analyzed {request_label} and identified {len(plan.get('hypotheses') or [])} grounded hypothesis/hypotheses. "
        f"The strongest lead points to `{likely_area}` with {confidence.lower()} confidence ({strength.lower()} evidence). "
        f"Verify before changing code."
    )
    verification = _verification_from_strings(
        (plan.get("verification_checklist") or plan.get("verification_steps") or [])[:8]
    )
    copy_prompt = build_investigation_copy_prompt(plan, ranked_files=ranked, verification=verification, user_request=user_request or symptom)
    return {
        "workflow": "debug",
        "executive_summary": executive_summary,
        "direction": {
            "title": "Most likely cause",
            "items": [
                {"label": "Likely cause", "value": str(root)},
                {"label": "Likely area", "value": likely_area},
                {"label": "Why this is likely", "value": why_likely},
            ],
        },
        "confidence": {
            "level": confidence,
            "evidence_strength": strength,
            "reason": _confidence_reason_investigate(plan, strength=strength),
        },
        "evidence": evidence_items,
        "ranked_files": ranked,
        "verification_steps": verification,
        "copy_prompt": copy_prompt,
    }


def build_impact_report(result: Dict[str, Any], *, user_request: str = "") -> Dict[str, Any]:
    target = str(result.get("target") or user_request or "this module")
    ranked = _collect_impact_ranked_files(result)
    evidence_items = _collect_evidence_impact(result)
    confidence = _norm_confidence(result.get("confidence"))
    strength = _evidence_strength(
        file_count=len(ranked),
        evidence_count=len(evidence_items),
        has_symbols=bool(result.get("resolved_symbols")),
        confidence=confidence,
    )
    subs = result.get("affected_subsystems") or []
    direct_n = len(result.get("direct_impact") or [])
    executive_summary = (
        f"Atlas assessed the blast radius of changing `{target}`. "
        f"{direct_n} module(s) import it directly"
        f"{f', affecting subsystems: {", ".join(subs[:4])}' if subs else ''}. "
        f"Confidence is {confidence.lower()} ({strength.lower()} evidence)."
    )
    why_break = (
        "Direct importers compile against this module's interface; behavior or signature changes propagate immediately. "
        "Transitive modules may fail if their dependencies change error handling or return values."
    )
    verification = _verification_from_strings(
        (result.get("recommended_verification") or [])[:8]
    )
    copy_prompt = build_impact_copy_prompt(result, ranked_files=ranked, verification=verification)
    return {
        "workflow": "what_breaks",
        "executive_summary": executive_summary,
        "direction": {
            "title": "Impact summary",
            "items": [
                {"label": "Most affected systems", "value": ", ".join(subs[:6]) or "none resolved from graph"},
                {"label": "Why they may break", "value": why_break},
                {"label": "Confidence", "value": f"{confidence} ({strength} evidence)"},
            ],
        },
        "confidence": {
            "level": confidence,
            "evidence_strength": strength,
            "reason": _confidence_reason_impact(result, strength=strength),
        },
        "evidence": evidence_items,
        "ranked_files": ranked,
        "verification_steps": verification,
        "copy_prompt": copy_prompt,
    }


def build_repository_understanding_report(
    *,
    answer: str,
    evidence: Sequence[str],
    files: Sequence[str],
    confidence: str = "High",
    limitations: Optional[Sequence[str]] = None,
    suggested_action: str = "",
    subsystem: str = "",
) -> Dict[str, Any]:
    evidence_items = [
        {"signal": str(ev), "why_it_matters": "Scan metadata or subsystem index supporting this overview."}
        for ev in evidence if ev
    ]
    ranked = _paths_to_ranked(
        list(files)[:8],
        why_default="Entry or hub file for understanding this area of the repository.",
        risk="Low",
        action="Open and trace imports outward to map responsibilities.",
    )
    strength = _evidence_strength(
        file_count=len(ranked),
        evidence_count=len(evidence_items),
        has_symbols=False,
        confidence=confidence,
    )
    focus = subsystem or "this repository"
    executive_summary = (
        f"Atlas summarized how {focus} is organized based on the latest scan. "
        f"{answer[:200].rstrip()}{'…' if len(answer) > 200 else ''} "
        f"Confidence is {confidence.lower()} ({strength.lower()} evidence)."
    )
    verification = _verification_from_strings([
        suggested_action or "Open the listed entry files and confirm they match your mental model of the repo.",
    ])
    copy_prompt = (
        "Use the following Atlas repository overview to orient yourself.\n\n"
        f"## Goal\nUnderstand the structure and entry points for {focus}.\n\n"
        f"## Summary\n{answer}\n\n"
        f"## Key files\n" + "\n".join(f"- `{f}`" for f in files[:8]) + "\n\n"
        "## Verification\n- Confirm entry files match the active application path.\n"
        "- Trace one import chain from an entry file to a core module.\n\n"
        "## Constraints\n- Do not refactor unrelated systems while exploring.\n"
        "- Ask before making structural changes.\n"
    )
    return {
        "workflow": "repository_understanding",
        "executive_summary": executive_summary,
        "direction": {
            "title": "Where to start",
            "items": [
                {"label": "Recommended starting point", "value": suggested_action or "Review entry files and subsystem map."},
                {"label": "Focus area", "value": focus},
            ],
        },
        "confidence": {
            "level": _norm_confidence(confidence),
            "evidence_strength": strength,
            "reason": "; ".join(limitations or ["Based on static scan index and subsystem grouping."]).capitalize() + ".",
        },
        "evidence": evidence_items,
        "ranked_files": ranked,
        "verification_steps": verification,
        "copy_prompt": copy_prompt,
    }


def format_report_markdown(report: Dict[str, Any], *, title: str) -> str:
    direction = report.get("direction") or {}
    conf = report.get("confidence") or {}
    lines = [
        title,
        "=" * len(title),
        "",
        "## Executive Summary",
        report.get("executive_summary") or "",
        "",
        f"## {direction.get('title') or 'Analysis'}",
    ]
    for item in direction.get("items") or []:
        lines.append(f"- **{item.get('label')}:** {item.get('value')}")
    lines.extend([
        "",
        "## Confidence",
        f"- **Confidence:** {conf.get('level', 'Low')}",
        f"- **Evidence strength:** {conf.get('evidence_strength', 'Weak')}",
        f"- **Reason:** {conf.get('reason', '')}",
        "",
        "## Evidence",
        *_md_evidence(report.get("evidence") or []),
        "",
        "## Ranked files",
        *_md_ranked_files(report.get("ranked_files") or []),
        "",
        "## Verification steps",
        *_md_verification(report.get("verification_steps") or []),
        "",
        "## Next prompt for Claude / Cursor / Codex",
        report.get("copy_prompt") or "",
    ])
    lim = report.get("limitations") or []
    if lim:
        lines.extend(["", "## Limitations", *_md_bullets(lim)])
    return "\n".join(lines).strip() + "\n"


def format_change_plan_markdown(plan: Dict[str, Any], *, user_request: str = "") -> str:
    report = build_change_plan_report(plan, user_request=user_request)
    return format_report_markdown(report, title="CHANGE PLAN")


def format_investigation_plan_markdown(plan: Dict[str, Any], *, user_request: str = "") -> str:
    report = build_investigation_report(plan, user_request=user_request)
    return format_report_markdown(report, title="DEBUG ANALYSIS")


def format_impact_markdown(result: Dict[str, Any], *, user_request: str = "") -> str:
    report = build_impact_report(result, user_request=user_request)
    return format_report_markdown(report, title="WHAT BREAKS")


def format_repository_understanding_markdown(report: Dict[str, Any]) -> str:
    return format_report_markdown(report, title="REPOSITORY UNDERSTANDING")


def build_change_copy_prompt(
    plan: Dict[str, Any],
    *,
    ranked_files: Sequence[Dict[str, Any]],
    verification: Sequence[Dict[str, Any]],
    user_request: str,
) -> str:
    goal = _clean_goal(user_request or plan.get("goal") or "")
    files = [r.get("path") for r in ranked_files[:6] if r.get("path")]
    ver_lines = [v.get("what") or "" for v in verification[:5] if v.get("what")]
    return (
        "Use the following Atlas findings to implement the change safely.\n\n"
        f"## Goal\n{goal or 'Implement the planned change grounded in the scanned repository.'}\n\n"
        f"## Likely files\n" + "\n".join(f"- `{f}`" for f in files) + "\n\n"
        "## Evidence\n"
        + "\n".join(f"- {e.get('signal')}: {e.get('why_it_matters')}" for e in _collect_evidence_change(plan)[:5])
        + "\n\n## Verification steps\n"
        + "\n".join(f"- {v}" for v in ver_lines)
        + "\n\n## Constraints\n"
        "- Do not change unrelated systems.\n"
        "- Make one focused change at a time.\n"
        "- Add or update tests for new behavior.\n"
        "- If the plan disagrees with the code, trust the code and report the mismatch.\n"
    )


def build_investigation_copy_prompt(
    plan: Dict[str, Any],
    *,
    ranked_files: Sequence[Dict[str, Any]],
    verification: Sequence[Dict[str, Any]],
    user_request: str,
) -> str:
    symptom = _clean_goal(user_request or plan.get("symptom_summary") or plan.get("symptom") or "")
    files = [r.get("path") for r in ranked_files[:6] if r.get("path")]
    ver_lines = [v.get("what") or "" for v in verification[:5] if v.get("what")]
    root = plan.get("most_likely_root_cause") or plan.get("most_likely_source") or ""
    return (
        "Use the following Atlas findings to investigate the issue.\n\n"
        f"## Goal\nDiagnose and fix: {symptom or 'the reported symptom'}.\n\n"
        f"## Most likely cause\n{root}\n\n"
        f"## Likely files\n" + "\n".join(f"- `{f}`" for f in files) + "\n\n"
        "## Evidence\n"
        + "\n".join(f"- {e.get('signal')}: {e.get('why_it_matters')}" for e in _collect_evidence_investigate(plan)[:5])
        + "\n\n## Verification steps\n"
        + "\n".join(f"- {v}" for v in ver_lines)
        + "\n\n## Constraints\n"
        "- Prove the root cause before editing.\n"
        "- Do not refactor unrelated systems.\n"
        "- Add a regression test once the fix is confirmed.\n"
    )


def build_impact_copy_prompt(
    result: Dict[str, Any],
    *,
    ranked_files: Sequence[Dict[str, Any]],
    verification: Sequence[Dict[str, Any]],
) -> str:
    target = result.get("target") or "this module"
    files = [r.get("path") for r in ranked_files[:8] if r.get("path")]
    ver_lines = [v.get("what") or "" for v in verification[:5] if v.get("what")]
    return (
        f"Use the following Atlas findings before changing `{target}`.\n\n"
        f"## Goal\nAssess and safely apply changes to `{target}` without breaking dependents.\n\n"
        f"## Likely affected files\n" + "\n".join(f"- `{f}`" for f in files) + "\n\n"
        "## Evidence\n"
        + "\n".join(f"- {e.get('signal')}: {e.get('why_it_matters')}" for e in _collect_evidence_impact(result)[:5])
        + "\n\n## Verification steps\n"
        + "\n".join(f"- {v}" for v in ver_lines)
        + "\n\n## Constraints\n"
        "- Do not change unrelated systems.\n"
        "- Run listed tests after each change.\n"
        "- Preserve public interfaces unless all importers are updated.\n"
    )
