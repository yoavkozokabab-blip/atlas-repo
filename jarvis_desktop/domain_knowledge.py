"""Domain knowledge facade — delegates to Syron Knowledge Engine (Phase 127).

Backward-compatible API for planning_engine and tests.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Set

from .atlas_knowledge.engine import (
    ConceptClassification,
    KnowledgeEngine,
    RepoFileRoles,
    get_engine,
)

def concepts_dict() -> Dict[str, Any]:
    return {cid: rec.to_dict() for cid, rec in get_engine().concepts.items()}


def _domains() -> Dict[str, str]:
    tax = get_engine()._taxonomy or {}
    domains = tax.get("domains") or {}
    return {k: v.get("label", k) for k, v in domains.items() if isinstance(v, dict)}


def classify_request(text: str, *, mode: str = "build") -> ConceptClassification:
    return get_engine().classify_request(text, mode=mode)


def search_terms_for_classification(classification: ConceptClassification) -> Set[str]:
    return get_engine().search_terms(classification)


def map_concept_to_repository(
    classification: ConceptClassification,
    modules: List[Dict[str, Any]],
    risks_map: Dict[str, Dict[str, Any]],
    *,
    scored_paths: Optional[List[str]] = None,
) -> RepoFileRoles:
    return get_engine().map_to_repository(
        classification, modules, risks_map, scored_paths=scored_paths
    )


def concept_understanding_text(classification: ConceptClassification) -> str:
    if classification.record:
        return classification.record.description
    return ""


def why_this_matters_text(classification: ConceptClassification) -> str:
    if not classification.record:
        return ""
    return get_engine()._why_matters(classification.record)


def knowledge_risks(classification: ConceptClassification) -> List[str]:
    if classification.record:
        return list(classification.record.risks)[:10]
    return []


def knowledge_verification(classification: ConceptClassification) -> List[str]:
    if classification.record:
        return list(classification.record.verification)[:10]
    return []


def knowledge_implementation_steps(classification: ConceptClassification) -> List[str]:
    if classification.record:
        return list(classification.record.implementation_steps)[:12]
    return []


def domain_investigation_notes(classification: ConceptClassification) -> List[str]:
    if not classification.record:
        return []
    rec = classification.record
    notes = list(rec.failure_modes)
    notes.extend(rec.verification[:4])
    return notes[:10]


def enrich_build_plan(
    plan: Dict[str, Any],
    classification: ConceptClassification,
    roles: RepoFileRoles,
) -> None:
    get_engine().enrich_build_plan(plan, classification, roles)


def enrich_investigation_plan(
    plan: Dict[str, Any],
    classification: ConceptClassification,
    roles: RepoFileRoles,
) -> None:
    get_engine().enrich_investigation_plan(plan, classification, roles)


def format_domain_prompt_section(classification: ConceptClassification) -> str:
    return get_engine().format_domain_prompt_section(classification)


def __getattr__(name: str) -> Any:
    if name == "CONCEPTS":
        return concepts_dict()
    if name == "DOMAINS":
        return _domains()
    raise AttributeError(name)
