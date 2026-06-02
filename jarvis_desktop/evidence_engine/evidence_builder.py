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
from .symbol_index import SymbolIndex, build_symbol_index


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
) -> RepositoryEvidenceBundle:
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
    insertion, insertion_reason = pick_insertion_point(detection, file_evidences, store.symbol_index)

    if file_evidences:
        confidence = min(100.0, file_evidences[0].evidence_score)
    elif detection.found_labels:
        confidence = 45.0
    else:
        confidence = 10.0

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

    summary_parts = [
        f"Status: {detection.status}",
        f"Found {len(detection.found_labels)} implementation signal(s)",
    ]
    if detection.missing_labels:
        summary_parts.append(f"Missing: {', '.join(detection.missing_labels[:3])}")

    return RepositoryEvidenceBundle(
        concept_id=concept_id,
        concept_name=concept_name or concept_id,
        status=detection.status,
        found=detection.found_labels[:12],
        missing=detection.missing_labels[:8],
        recommended_insertion=insertion,
        recommended_insertion_reason=insertion_reason,
        confidence_score=confidence,
        file_evidences=file_evidences[:10],
        call_paths=call_paths[:6],
        evidence_summary=" · ".join(summary_parts),
    )


def analyze_investigation(
    store: EvidenceStore,
    *,
    concept_id: str = "backtest_live_divergence",
    symptom: str = "",
) -> RepositoryEvidenceBundle:
    lower = (symptom or "").lower()
    if any(k in lower for k in ("backtest", "paper", "live", "slippage", "fill")):
        concept_id = "backtest_live_divergence"
    return analyze_concept(
        store,
        concept_id=concept_id,
        concept_name="Backtest vs live divergence",
        category="symptom",
        domain="trading",
    )


def merge_file_roles_with_evidence(
    roles: Any,
    bundle: RepositoryEvidenceBundle,
) -> Any:
    """Reorder RepoFileRoles using evidence scores (evidence-first, not path-name-first)."""
    from ..atlas_knowledge.engine import RepoFileRoles

    if not isinstance(roles, RepoFileRoles):
        return roles

    ranked_paths = [fe.path for fe in bundle.file_evidences]
    if bundle.recommended_insertion and bundle.recommended_insertion not in ranked_paths:
        ranked_paths.insert(0, bundle.recommended_insertion)

    must = list(dict.fromkeys(ranked_paths + roles.must_inspect))[:8]
    likely = list(dict.fromkeys(ranked_paths + roles.likely_modify))[:8]
    verify = list(roles.verify_only)

    note = roles.integration_note
    if bundle.recommended_insertion:
        note = (
            f"Insertion supported by AST evidence ({bundle.confidence_score:.0f}/100): "
            f"`{bundle.recommended_insertion}`. {bundle.recommended_insertion_reason}"
        )

    return RepoFileRoles(
        must_inspect=must[:6],
        likely_modify=likely[:6],
        verify_only=verify[:6],
        do_not_touch=list(roles.do_not_touch),
        dedicated_module_found=roles.dedicated_module_found or bool(bundle.found),
        integration_note=note,
    )


def apply_to_build_plan(plan: Dict[str, Any], bundle: RepositoryEvidenceBundle) -> None:
    plan["repository_evidence"] = bundle.to_dict()
    plan["evidence_confidence"] = bundle.confidence_score

    if bundle.recommended_insertion:
        inspect = list(dict.fromkeys([bundle.recommended_insertion] + (plan.get("files_to_inspect_first") or [])))
        plan["files_to_inspect_first"] = inspect[:8]
        change = list(dict.fromkeys([bundle.recommended_insertion] + (plan.get("files_likely_to_change") or [])))
        plan["files_likely_to_change"] = change[:8]

    if bundle.file_evidences:
        order = [fe.path for fe in sorted(bundle.file_evidences, key=lambda x: -x.evidence_score)]
        existing = plan.get("implementation_order") or []
        plan["implementation_order"] = list(dict.fromkeys(order + existing))[:12]

    evidence_lines = [
        f"Implementation status: {bundle.status}",
        f"Evidence score: {bundle.confidence_score:.0f}/100",
    ]
    if bundle.found:
        evidence_lines.append("Found: " + "; ".join(bundle.found[:4]))
    if bundle.missing:
        evidence_lines.append("Missing: " + "; ".join(bundle.missing[:4]))
    if bundle.recommended_insertion:
        evidence_lines.append(f"Recommended insertion: `{bundle.recommended_insertion}`")
    plan["evidence"] = evidence_lines + list(plan.get("evidence") or [])[:6]

    dk = plan.get("domain_knowledge") or {}
    if dk.get("applied"):
        dk["repository_evidence"] = bundle.to_dict()
        dk["file_evidence_summary"] = [
            {
                "path": fe.path,
                "score": fe.evidence_score,
                "symbols": fe.matching_symbols[:4],
                "reason": fe.reason_selected,
            }
            for fe in bundle.file_evidences[:6]
        ]
        plan["domain_knowledge"] = dk
        plan["knowledge_engine"] = dk


def apply_to_investigation_plan(plan: Dict[str, Any], bundle: RepositoryEvidenceBundle) -> None:
    plan["repository_evidence"] = bundle.to_dict()
    plan["evidence_confidence"] = bundle.confidence_score

    if bundle.found:
        plan["evidence"] = [f"Evidence: {x}" for x in bundle.found[:6]] + list(plan.get("evidence") or [])[:4]
        plan["most_likely_root_cause"] = bundle.found[0]
        if bundle.confidence_score >= 60:
            plan["confidence"] = "high"
        elif bundle.confidence_score >= 35:
            plan["confidence"] = "medium"

    for hyp in plan.get("hypotheses") or []:
        if bundle.found and "slippage" in (hyp.get("title") or "").lower():
            hyp["evidence"] = [f"Repository evidence: {bundle.found[0]}"] + list(hyp.get("evidence") or [])
            hyp["confidence"] = "high" if bundle.confidence_score >= 55 else hyp.get("confidence")

    dk = plan.get("domain_knowledge") or {}
    if dk.get("applied"):
        dk["repository_evidence"] = bundle.to_dict()
        plan["domain_knowledge"] = dk
