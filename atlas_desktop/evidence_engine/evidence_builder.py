"""Build repository evidence bundles and merge into Build/Investigate plans."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from .call_graph import CallGraph, build_call_graph
from .evidence_models import FileEvidence, RepositoryEvidenceBundle
from .implementation_detector import (
    DetectionResult,
    file_evidences_from_detection,
    pick_insertion_point,
    resolve_detector,
)
from .precision_engine import (
    PrecisionResult,
    apply_precision_to_impact,
    apply_precision_to_plan,
    rank_files,
)
from .symbol_evidence import build_evidence_panel
from .symbol_index import SymbolIndex, build_symbol_index

IMPLEMENTATION_FILES_MAX = 5


@dataclass
class EvidenceStore:
    project_root: str
    symbol_index: SymbolIndex
    call_graph: CallGraph = field(default_factory=CallGraph)
    built_at: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "project_root": self.project_root,
            "built_at": self.built_at,
            "symbol_index": self.symbol_index.to_dict(),
            "call_graph": self.call_graph.to_dict(),
        }

    @classmethod
    def from_dict(cls, raw: Dict[str, Any]) -> "EvidenceStore":
        return cls(
            project_root=raw.get("project_root") or "",
            built_at=raw.get("built_at") or "",
            symbol_index=SymbolIndex.from_dict(raw.get("symbol_index") or {}),
            call_graph=CallGraph.from_dict(raw.get("call_graph") or {}),
        )


def _production_module_paths(graph: Optional[Dict[str, Any]]) -> List[str]:
    if not graph:
        return []
    paths: List[str] = []
    for node in graph.get("nodes") or []:
        if node.get("type") == "module" and node.get("path"):
            lang = node.get("language") or "python"
            if lang in ("python", None, ""):
                paths.append(node["path"])
    return paths


def build_evidence_store(
    project_root: str,
    graph: Optional[Dict[str, Any]] = None,
    index: Optional[Dict[str, Any]] = None,
) -> EvidenceStore:
    import time

    paths = _production_module_paths(graph)
    if not paths and index:
        paths = [
            f["path"]
            for f in (index.get("files") or [])
            if (f.get("path") or "").endswith(".py")
        ]
    sym_index = build_symbol_index(project_root, paths)
    cg = build_call_graph(sym_index, graph)
    return EvidenceStore(
        project_root=project_root,
        symbol_index=sym_index,
        call_graph=cg,
        built_at=time.strftime("%Y-%m-%dT%H:%M:%S"),
    )


def analyze_concept(
    store: EvidenceStore,
    *,
    concept_id: str,
    concept_name: str = "",
    category: str = "",
    domain: str = "",
    path_keywords: Optional[List[str]] = None,
    heuristic_paths: Optional[List[str]] = None,
    graph: Optional[Dict[str, Any]] = None,
) -> Tuple[RepositoryEvidenceBundle, PrecisionResult]:
    detector = resolve_detector(concept_id, category=category, domain=domain)
    keywords = list(path_keywords or [])
    if detector:
        detection = detector(store.symbol_index, store.call_graph, keywords)
    else:
        patterns = keywords or [concept_id.replace("_", " "), concept_name.lower()]
        syms = store.symbol_index.find_in_source(patterns)
        detection = DetectionResult(
            concept_id=concept_id,
            found_labels=[f"{s.qualname or s.name} in `{s.file_path}`" for s in syms[:6]],
            missing_labels=[concept_name or concept_id] if not syms else [],
            matched_symbols=syms,
            search_patterns=patterns,
            status="Partially Implemented" if syms else "Not Found",
        )

    file_evidences = file_evidences_from_detection(detection, store.symbol_index)
    insertion, insertion_reason = pick_insertion_point(
        detection, file_evidences, store.symbol_index, concept_id=concept_id
    )

    precision = rank_files(
        store.symbol_index,
        store.call_graph,
        detection,
        concept_keywords=keywords,
        heuristic_paths=(heuristic_paths or [])[:8],
        graph=graph,
        insertion_path=insertion,
    )

    if precision.insertion_path:
        insertion = precision.insertion_path
    elif precision.tier1:
        insertion = precision.tier1[0]

    confidence = precision.insertion_confidence
    if detection.status == "Implemented":
        confidence = max(confidence, 75.0)
    elif detection.status == "Partially Implemented" and insertion:
        confidence = max(confidence, 55.0)

    call_paths: List[str] = []
    if insertion:
        deps = store.call_graph.who_depends_on_file(insertion)
        call_paths.extend(deps[:5])
        entries = store.call_graph.data_entry_files(store.symbol_index)
        if entries:
            call_paths.append(f"Request entry: {entries[0]}")

    search_patterns = list(detection.search_patterns or keywords)
    panel_paths = precision.tier1 or ([insertion] if insertion else [])
    evidence_panel = build_evidence_panel(
        store,
        panel_paths,
        keywords,
        patterns=search_patterns,
        anchor_path=insertion,
    ).to_dict()

    summary_parts = [
        f"Status: {detection.status}",
        f"Insertion confidence: {precision.insertion_confidence:.0f}/100",
        f"Tier-1 files: {len(precision.tier1)}",
        f"Symbols matched: {len(evidence_panel.get('matched_symbols') or [])}",
    ]
    if detection.missing_labels:
        summary_parts.append(f"Missing: {', '.join(detection.missing_labels[:3])}")

    bundle = RepositoryEvidenceBundle(
        concept_id=concept_id,
        concept_name=concept_name or concept_id,
        status=detection.status,
        found=detection.found_labels[:12],
        missing=detection.missing_labels[:8],
        recommended_insertion=insertion,
        recommended_insertion_reason=insertion_reason,
        confidence_score=confidence,
        insertion_confidence=precision.insertion_confidence,
        file_evidences=precision.file_evidences[:10],
        call_paths=call_paths[:6],
        evidence_summary=" · ".join(summary_parts),
        recommendation_tiers=precision.to_dict(),
        evidence_panel=evidence_panel,
    )
    return bundle, precision


def analyze_investigation(
    store: EvidenceStore,
    *,
    concept_id: str = "backtest_live_divergence",
    symptom: str = "",
    heuristic_paths: Optional[List[str]] = None,
    graph: Optional[Dict[str, Any]] = None,
) -> Tuple[RepositoryEvidenceBundle, PrecisionResult]:
    lower = (symptom or "").lower()
    if concept_id == "indicator_backtest_live" or (
        "indicator" in lower and any(k in lower for k in ("backtest", "paper", "live"))
    ):
        concept_id = "indicator_backtest_live"
    elif any(k in lower for k in ("backtest", "paper", "live", "slippage", "fill", "timing", "sim")):
        concept_id = "backtest_live_divergence"
    bundle, precision = analyze_concept(
        store,
        concept_id=concept_id,
        concept_name="Backtest vs live divergence",
        category="symptom",
        domain="trading",
        heuristic_paths=heuristic_paths,
        graph=graph,
    )
    if symptom:
        bundle.evidence_panel = build_evidence_panel(
            store,
            precision.tier1 or [bundle.recommended_insertion],
            [symptom],
            symptom=symptom,
            anchor_path=bundle.recommended_insertion,
        ).to_dict()
    return bundle, precision


def merge_file_roles_with_evidence(
    roles: Any,
    bundle: RepositoryEvidenceBundle,
    precision: Optional[PrecisionResult] = None,
) -> Any:
    """Apply evidence-tier file roles (precision-first, no heuristic merge)."""
    from ..atlas_knowledge.engine import RepoFileRoles

    if not isinstance(roles, RepoFileRoles):
        return roles

    tiers = precision or None
    if tiers is None and bundle.recommendation_tiers:
        t = bundle.recommendation_tiers
        tier1 = list(t.get("tier1_strong_evidence") or [])
        tier2 = list(t.get("tier2_supporting") or [])
        tier3 = list(t.get("tier3_verify_only") or [])
    elif tiers:
        tier1, tier2, tier3 = tiers.tier1, tiers.tier2, tiers.tier3
    else:
        tier1 = [fe.path for fe in bundle.file_evidences[:5]]
        tier2 = []
        tier3 = list(roles.verify_only)

    note = roles.integration_note
    if bundle.recommended_insertion:
        ins_conf = bundle.insertion_confidence or bundle.confidence_score
        note = (
            f"Insertion confidence {ins_conf:.0f}/100 — `{bundle.recommended_insertion}`. "
            f"{bundle.recommended_insertion_reason}"
        )

    return RepoFileRoles(
        must_inspect=tier1[:5],
        likely_modify=tier2[:8],
        verify_only=[],
        do_not_touch=list(roles.do_not_touch),
        dedicated_module_found=roles.dedicated_module_found or bool(bundle.found),
        integration_note=note,
    )


def apply_to_build_plan(
    plan: Dict[str, Any],
    bundle: RepositoryEvidenceBundle,
    precision: Optional[PrecisionResult] = None,
) -> None:
    plan["repository_evidence"] = bundle.to_dict()
    plan["evidence_panel"] = bundle.evidence_panel or {}
    plan["evidence_confidence"] = bundle.confidence_score
    plan["insertion_confidence"] = bundle.insertion_confidence

    if precision:
        apply_precision_to_plan(plan, precision)
        tier1 = precision.tier1[:IMPLEMENTATION_FILES_MAX]
        plan["implementation_files"] = tier1
        plan["files_to_inspect_first"] = tier1
        plan["implementation_files_with_why"] = [
            {
                "path": fe.path,
                "why": fe.selected_because or fe.reason_selected,
                "tier": "implementation",
            }
            for fe in (precision.file_evidences or [])[:IMPLEMENTATION_FILES_MAX]
        ]
        review = precision.tier2[:6]
        plan["review_files"] = review
        plan["files_review_only"] = review
        plan["implementation_files_with_why"].extend(
            {"path": p, "why": "Supporting evidence (review before editing)", "tier": "review"}
            for p in review
        )
    else:
        if bundle.recommended_insertion:
            plan["files_to_inspect_first"] = [bundle.recommended_insertion]
            plan["files_likely_to_change"] = [bundle.recommended_insertion]

    evidence_lines = [
        f"Implementation status: {bundle.status}",
        f"Insertion confidence: {bundle.insertion_confidence:.0f}/100",
        f"Tier-1 (strong evidence): {', '.join((precision.tier1 if precision else [])[:3]) or 'n/a'}",
    ]
    if bundle.found:
        evidence_lines.append("Found: " + "; ".join(bundle.found[:4]))
    if bundle.missing:
        evidence_lines.append("Missing: " + "; ".join(bundle.missing[:4]))
    if bundle.recommended_insertion:
        evidence_lines.append(f"Recommended insertion: `{bundle.recommended_insertion}`")
    plan["evidence"] = evidence_lines + list(plan.get("evidence") or [])[:4]

    if bundle.file_evidences and precision:
        order = [fe.path for fe in precision.file_evidences]
        plan["implementation_order"] = order[:10]

    dk = plan.get("domain_knowledge") or {}
    if dk.get("applied"):
        dk["repository_evidence"] = plan["repository_evidence"]
        dk["insertion_confidence"] = bundle.insertion_confidence
        if bundle.concept_id:
            dk["concept_id"] = bundle.concept_id
        plan["domain_knowledge"] = dk
        plan["knowledge_engine"] = dk


def apply_to_investigation_plan(
    plan: Dict[str, Any],
    bundle: RepositoryEvidenceBundle,
    precision: Optional[PrecisionResult] = None,
) -> None:
    plan["repository_evidence"] = bundle.to_dict()
    plan["evidence_panel"] = bundle.evidence_panel or {}
    plan["evidence_confidence"] = bundle.confidence_score
    plan["insertion_confidence"] = bundle.insertion_confidence

    if bundle.found:
        plan["evidence"] = [f"Evidence: {x}" for x in bundle.found[:6]] + list(plan.get("evidence") or [])[:3]
        plan["most_likely_root_cause"] = bundle.found[0]
        if bundle.insertion_confidence >= 60:
            plan["confidence"] = "high"
        elif bundle.insertion_confidence >= 35:
            plan["confidence"] = "medium"

    if precision:
        apply_precision_to_plan(plan, precision, investigate=True)

    for hyp in plan.get("hypotheses") or []:
        if bundle.found and "slippage" in (hyp.get("title") or "").lower():
            hyp["evidence"] = [f"Repository evidence: {bundle.found[0]}"] + list(hyp.get("evidence") or [])
            hyp["confidence"] = "high" if bundle.insertion_confidence >= 55 else hyp.get("confidence")

    dk = plan.get("domain_knowledge") or {}
    if dk.get("applied"):
        dk["repository_evidence"] = plan["repository_evidence"]
        plan["domain_knowledge"] = dk


def apply_impact_precision(
    plan: Dict[str, Any],
    target: str,
    graph: Optional[Dict[str, Any]] = None,
    *,
    evidence_store: Optional[Dict[str, Any]] = None,
) -> None:
    apply_precision_to_impact(plan, target, graph)
    if evidence_store and evidence_store.get("symbol_index"):
        from .symbol_evidence import impact_symbol_blast

        store = EvidenceStore.from_dict(evidence_store)
        extra_files, extra_reasons, panel = impact_symbol_blast(store, target)
        if extra_files:
            merged = list(dict.fromkeys(list(plan.get("affected_files") or []) + extra_files))[:24]
            plan["affected_files"] = merged
            plan["potentially_affected_modules"] = merged
            plan["direct_impact"] = list(dict.fromkeys(list(plan.get("direct_impact") or []) + extra_files[:8]))
        plan["impact_evidence_panel"] = panel.to_dict()
        plan["evidence_panel"] = panel.to_dict()
        if extra_reasons:
            plan["evidence"] = extra_reasons[:4] + list(plan.get("evidence") or [])
