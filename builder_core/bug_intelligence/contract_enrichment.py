"""Contract-enriched review packets (Phase 96C).

Attaches supporting contract evidence to ``inconsistent_return`` findings for
human review. Does NOT promote findings, confirm defects, or change detector
logic.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from . import contract_facts
from .finding import Finding

CONTRACT_ENRICHMENT_ENABLED = True
REVIEW_LEAD_TAG = "review_lead_only"

# Sources allowed in each packet section (Phase 96B audit + 96C scope).
_RETURN_EVIDENCE_SOURCES = {contract_facts.SOURCE_TYPE_HINT}
_CALLER_EVIDENCE_SOURCES = {contract_facts.SOURCE_CALLER_BEHAVIOR}
# Shown only under conflicting_evidence — never used for promotion.
_CONFLICT_DISPLAY_SOURCES = {
    contract_facts.SOURCE_DOCSTRING,
    contract_facts.SOURCE_TYPE_HINT,
    contract_facts.SOURCE_CALLER_BEHAVIOR,
}


def _qualname_for_finding(module_facts: Dict[str, Any], finding: Finding) -> str:
    interproc = module_facts.get("interproc") or {}
    cg = interproc.get("call_graph") or {}
    line_to_qual = {
        meta.get("line"): qual
        for qual, meta in (cg.get("functions") or {}).items()
    }
    qual = line_to_qual.get(finding.line)
    if qual:
        return qual
    for q, meta in (cg.get("functions") or {}).items():
        if meta.get("line") == finding.line:
            return q
    return finding.function or ""


def _summarize_contract(rec: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "obligation": rec.get("obligation"),
        "confidence": rec.get("confidence"),
        "sources": list(rec.get("sources") or []),
        "subject": dict(rec.get("subject") or {}),
    }


def _matches_qual(rec: Dict[str, Any], qual: str) -> bool:
    subj = rec.get("subject") or {}
    return subj.get("qualname") == qual


def _has_source(rec: Dict[str, Any], source: str) -> bool:
    return source in (rec.get("sources") or [])


def _build_packet(
    finding: Finding,
    module_facts: Dict[str, Any],
    qual: str,
) -> Dict[str, Any]:
    contracts = module_facts.get("contracts") or {}
    if not contracts.get("enabled"):
        return {
            "review_packet_status": REVIEW_LEAD_TAG,
            "return_contract_evidence": [],
            "caller_behavior_evidence": [],
            "conflicting_evidence": [],
            "why_not_confirmed": [
                "Contract facts unavailable for this module.",
                "This finding remains a review lead only — not a confirmed defect.",
            ],
        }

    return_records = list(contracts.get("return_contracts") or [])
    subject_records = [r for r in return_records if _matches_qual(r, qual)]

    return_evidence: List[Dict[str, Any]] = []
    for rec in subject_records:
        if not _has_source(rec, contract_facts.SOURCE_TYPE_HINT):
            continue
        if rec.get("confidence") != contract_facts.CONFIDENCE_EXPLICIT:
            continue
        if rec.get("obligation") not in (
            "return.non_none",
            "return.shape_uniform",
            "return.never_implicit_none",
        ):
            continue
        return_evidence.append(_summarize_contract(rec))

    caller_evidence: List[Dict[str, Any]] = []
    for rec in subject_records:
        if not _has_source(rec, contract_facts.SOURCE_CALLER_BEHAVIOR):
            continue
        if rec.get("confidence") != contract_facts.CONFIDENCE_INFERRED_STRONG:
            continue
        caller_evidence.append(_summarize_contract(rec))

    conflicting: List[Dict[str, Any]] = []
    for rec in subject_records:
        srcs = set(rec.get("sources") or [])
        if not srcs & _CONFLICT_DISPLAY_SOURCES:
            continue
        obligation = rec.get("obligation")
        confidence = rec.get("confidence")
        if obligation == "return.optional":
            conflicting.append({
                **_summarize_contract(rec),
                "conflict_reason": "optional_return_signal",
            })
        elif (
            _has_source(rec, contract_facts.SOURCE_CALLER_BEHAVIOR)
            and confidence == contract_facts.CONFIDENCE_INFERRED_WEAK
        ):
            conflicting.append({
                **_summarize_contract(rec),
                "conflict_reason": "mixed_or_null_checking_callers",
            })
        elif (
            _has_source(rec, contract_facts.SOURCE_TYPE_HINT)
            and obligation == "return.optional"
        ):
            conflicting.append({
                **_summarize_contract(rec),
                "conflict_reason": "explicit_optional_annotation",
            })

    if finding.kind == "pattern":
        conflicting.append({
            "conflict_reason": "interprocedural_gate_not_met",
            "detail": (
                "No unambiguous same-file caller dereferences the return without "
                "null-checking it (Phase 93B promotion gate)."
            ),
        })

    why_not: List[str] = [
        "Contract enrichment is supporting evidence only; no confirmation "
        "evaluators are enabled.",
        "This finding is labeled review_lead_only — not a confirmed defect.",
        "callee_behavior, guard, and docstring-return facts are excluded from "
        "promotion and confirmation.",
    ]
    if finding.kind == "pattern":
        why_not.append(
            "Finding remains quarantined (kind=pattern); contract facts do not "
            "change promotion."
        )
    if conflicting:
        why_not.append(
            "Conflicting contract or interprocedural signals prevent confirmation."
        )
    if not return_evidence and not caller_evidence:
        why_not.append(
            "No explicit return type-hint contract or strong caller-behavior "
            "contract attached for this function."
        )

    return {
        "review_packet_status": REVIEW_LEAD_TAG,
        "function_qualname": qual,
        "return_contract_evidence": return_evidence,
        "caller_behavior_evidence": caller_evidence,
        "conflicting_evidence": conflicting,
        "why_not_confirmed": why_not,
    }


def enrich_inconsistent_return_finding(
    finding: Finding,
    module_facts: Dict[str, Any],
) -> Finding:
    """Return a copy of ``finding`` with contract review packet attached."""
    if finding.rule != "inconsistent_return":
        return finding
    qual = _qualname_for_finding(module_facts, finding)
    packet = _build_packet(finding, module_facts, qual)
    tags = list(finding.tags)
    if REVIEW_LEAD_TAG not in tags:
        tags.append(REVIEW_LEAD_TAG)
    tags = [t for t in tags if t not in ("confirmed_bug", "confirmed_defect")]
    return Finding(
        category=finding.category,
        kind=finding.kind,
        severity=finding.severity,
        confidence=finding.confidence,
        file=finding.file,
        line=finding.line,
        title=finding.title,
        explanation=finding.explanation,
        why_might_be_wrong=finding.why_might_be_wrong,
        next_verification_step=finding.next_verification_step,
        function=finding.function,
        evidence=finding.evidence,
        rule=finding.rule,
        source_facts=list(finding.source_facts),
        tags=tags,
        id=finding.id,
        contract_review=packet,
        verification_evidence=finding.verification_evidence,
    )


def enrich_findings(
    findings: List[Finding],
    module_facts: Dict[str, Any],
) -> List[Finding]:
    if not CONTRACT_ENRICHMENT_ENABLED:
        return findings
    return [
        enrich_inconsistent_return_finding(f, module_facts)
        if f.rule == "inconsistent_return"
        else f
        for f in findings
    ]
