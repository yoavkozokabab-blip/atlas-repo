"""Build curated concept dicts for Phase 128 export."""

from __future__ import annotations

from typing import Any, Dict, List, Optional


def build_concept(
    concept_id: str,
    name: str,
    domain: str,
    category: str,
    *,
    concept_quality_score: str = "curated_deep",
    aliases: Optional[List[str]] = None,
    description: str = "",
    when_to_use: str = "",
    requirements: Optional[List[str]] = None,
    implementation_strategies: Optional[List[str]] = None,
    common_implementations: Optional[List[str]] = None,
    risks: Optional[List[str]] = None,
    security_risks: Optional[List[str]] = None,
    performance_risks: Optional[List[str]] = None,
    failure_modes: Optional[List[str]] = None,
    verification: Optional[List[str]] = None,
    testing: Optional[List[str]] = None,
    related_concepts: Optional[List[str]] = None,
    references: Optional[List[str]] = None,
    path_keywords: Optional[List[str]] = None,
    implementation_steps: Optional[List[str]] = None,
    investigate_only: bool = False,
    feature_type: Optional[str] = None,
) -> Dict[str, Any]:
    kw = path_keywords or [
        w.lower() for w in (concept_id.replace("_", " ") + " " + name).split() if len(w) > 2
    ][:8]
    all_risks = list(risks or [])
    if security_risks:
        all_risks.extend(security_risks)
    if performance_risks:
        all_risks.extend(performance_risks)

    return {
        "concept_id": concept_id,
        "name": name,
        "title": name,
        "domain": domain,
        "category": category,
        "feature_type": feature_type or category,
        "concept_quality_score": concept_quality_score,
        "confidence": "high" if concept_quality_score == "source_backed" else "medium",
        "aliases": list(dict.fromkeys(aliases or [concept_id.replace("_", " "), name.lower()])),
        "description": description.strip(),
        "when_to_use": when_to_use.strip(),
        "requirements": requirements or [],
        "implementation_strategies": implementation_strategies or implementation_steps or [],
        "implementation_steps": implementation_steps or implementation_strategies or [],
        "common_implementations": common_implementations or [],
        "risks": all_risks,
        "security_risks": security_risks or [],
        "performance_risks": performance_risks or [],
        "failure_modes": failure_modes or [],
        "verification": verification or [],
        "testing": testing or [],
        "related_concepts": related_concepts or [],
        "references": references or [],
        "path_keywords": kw,
        "investigate_only": investigate_only,
    }
