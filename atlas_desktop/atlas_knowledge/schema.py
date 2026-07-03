"""Atlas Knowledge Engine — concept schema and validation (Phase 127)."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple


@dataclass
class ConceptRecord:
    concept_id: str
    name: str
    aliases: List[str]
    domain: str
    category: str
    description: str
    requirements: List[str] = field(default_factory=list)
    common_implementations: List[str] = field(default_factory=list)
    risks: List[str] = field(default_factory=list)
    failure_modes: List[str] = field(default_factory=list)
    verification: List[str] = field(default_factory=list)
    testing: List[str] = field(default_factory=list)
    related_concepts: List[str] = field(default_factory=list)
    references: List[str] = field(default_factory=list)
    confidence: str = "high"  # catalog confidence: high = stable local knowledge
    # Repo mapping hints (optional)
    path_keywords: List[str] = field(default_factory=list)
    typical_locations: List[str] = field(default_factory=list)
    implementation_steps: List[str] = field(default_factory=list)
    investigate_only: bool = False
    feature_type: str = "feature"
    # Legacy title field
    title: str = ""
    when_to_use: str = ""
    implementation_strategies: List[str] = field(default_factory=list)
    security_risks: List[str] = field(default_factory=list)
    performance_risks: List[str] = field(default_factory=list)
    concept_quality_score: str = "generated_template"

    @property
    def computed_quality_score(self) -> str:
        from .quality import normalize_quality

        return normalize_quality(self.concept_quality_score)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["title"] = d["title"] or self.name
        d["meaning"] = self.description  # backward compat
        d["implementation_risks"] = self.risks
        d["common_bugs"] = self.failure_modes
        d["tests_to_run"] = self.testing
        d["required_inputs"] = self.requirements[:5]
        d["required_outputs"] = self.requirements[5:10] if len(self.requirements) > 5 else []
        return d

    @classmethod
    def from_dict(cls, raw: Dict[str, Any]) -> "ConceptRecord":
        cid = (raw.get("concept_id") or raw.get("id") or "").strip()
        if not cid:
            raise ValueError("concept_id required")

        def _list(key: str, *alts: str) -> List[str]:
            for k in (key,) + alts:
                v = raw.get(k)
                if v is None:
                    continue
                if isinstance(v, str):
                    return [v] if v else []
                return [str(x) for x in v if x]
            return []

        desc = (
            raw.get("description")
            or raw.get("meaning")
            or raw.get("definition")
            or ""
        ).strip()

        aliases_raw = _list("aliases")
        seen: set[str] = set()
        aliases: List[str] = []
        for a in aliases_raw:
            key = a.lower().strip()
            if key and key not in seen:
                seen.add(key)
                aliases.append(a)
        if cid and cid.replace("_", " ") not in seen:
            aliases.insert(0, cid.replace("_", " "))

        return cls(
            concept_id=cid,
            name=(raw.get("name") or cid).strip(),
            aliases=aliases,
            domain=(raw.get("domain") or "general").strip(),
            category=(raw.get("category") or raw.get("feature_type") or "feature").strip(),
            description=desc,
            requirements=_list("requirements", "required_inputs"),
            common_implementations=_list("common_implementations", "typical_locations"),
            risks=_list("risks", "implementation_risks"),
            failure_modes=_list("failure_modes", "common_bugs"),
            verification=_list("verification"),
            testing=_list("testing", "tests_to_run"),
            related_concepts=_list("related_concepts"),
            references=_list("references"),
            confidence=(raw.get("confidence") or "high").strip(),
            path_keywords=_list("path_keywords"),
            typical_locations=_list("typical_locations"),
            implementation_steps=_list("implementation_steps"),
            investigate_only=bool(raw.get("investigate_only")),
            feature_type=(raw.get("feature_type") or raw.get("category") or "feature").strip(),
            title=(raw.get("title") or raw.get("name") or cid).strip(),
            when_to_use=(raw.get("when_to_use") or "").strip(),
            implementation_strategies=_list("implementation_strategies", "implementation_steps"),
            security_risks=_list("security_risks"),
            performance_risks=_list("performance_risks"),
            concept_quality_score=(raw.get("concept_quality_score") or "generated_template").strip(),
        )


def validate_concept(record: ConceptRecord, *, strict: bool = True) -> Tuple[bool, List[str]]:
    """Reject weak concepts (Phase 127 quality gates)."""
    errors: List[str] = []
    if len(record.description) < 20:
        errors.append("description too short (< 20 chars)")
    if not record.risks:
        errors.append("missing risks")
    if not record.failure_modes:
        errors.append("missing failure_modes")
    if not record.testing:
        errors.append("missing testing")
    if not record.verification:
        errors.append("missing verification")
    if not record.aliases:
        errors.append("missing aliases")
    if len(record.aliases) != len(set(a.lower() for a in record.aliases)):
        errors.append("duplicate aliases (case-insensitive)")
    if strict and not record.references and record.confidence == "high":
        # high-confidence catalog entries should cite authority when possible
        pass  # warn only in lint mode
    return (len(errors) == 0, errors)
