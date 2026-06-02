"""Data models for repository evidence (Phase 129)."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class SymbolKind(str, Enum):
    FUNCTION = "function"
    CLASS = "class"
    METHOD = "method"
    IMPORT = "import"
    DECORATOR = "decorator"
    INTERFACE = "interface"
    PROTOCOL = "protocol"
    ABSTRACT = "abstract"
    REGISTRY = "registry"
    CONFIG = "config"
    MIDDLEWARE = "middleware"
    FACTORY = "factory"


class ImplementationStatus(str, Enum):
    IMPLEMENTED = "Implemented"
    PARTIAL = "Partially Implemented"
    NOT_FOUND = "Not Found"


@dataclass
class SymbolRecord:
    name: str
    kind: str
    file_path: str
    line: int = 0
    qualname: str = ""
    decorators: List[str] = field(default_factory=list)
    bases: List[str] = field(default_factory=list)
    usage_count: int = 0
    is_definition: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class SymbolReference:
    symbol_name: str
    file_path: str
    line: int
    context: str = "reference"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class FileEvidence:
    path: str
    evidence_score: float
    matching_symbols: List[str] = field(default_factory=list)
    matching_concepts: List[str] = field(default_factory=list)
    usage_patterns: List[str] = field(default_factory=list)
    reason_selected: str = ""
    symbol_details: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class RepositoryEvidenceBundle:
    concept_id: str
    concept_name: str = ""
    status: str = ImplementationStatus.NOT_FOUND.value
    found: List[str] = field(default_factory=list)
    missing: List[str] = field(default_factory=list)
    recommended_insertion: str = ""
    recommended_insertion_reason: str = ""
    confidence_score: float = 0.0
    file_evidences: List[FileEvidence] = field(default_factory=list)
    call_paths: List[str] = field(default_factory=list)
    evidence_summary: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "concept_id": self.concept_id,
            "concept_name": self.concept_name,
            "status": self.status,
            "found": list(self.found),
            "missing": list(self.missing),
            "recommended_insertion": self.recommended_insertion,
            "recommended_insertion_reason": self.recommended_insertion_reason,
            "confidence_score": round(self.confidence_score, 1),
            "file_evidences": [fe.to_dict() for fe in self.file_evidences],
            "call_paths": list(self.call_paths),
            "evidence_summary": self.evidence_summary,
        }

    @classmethod
    def from_dict(cls, raw: Dict[str, Any]) -> "RepositoryEvidenceBundle":
        fes = [FileEvidence(**fe) for fe in (raw.get("file_evidences") or [])]
        return cls(
            concept_id=raw.get("concept_id") or "",
            concept_name=raw.get("concept_name") or "",
            status=raw.get("status") or ImplementationStatus.NOT_FOUND.value,
            found=list(raw.get("found") or []),
            missing=list(raw.get("missing") or []),
            recommended_insertion=raw.get("recommended_insertion") or "",
            recommended_insertion_reason=raw.get("recommended_insertion_reason") or "",
            confidence_score=float(raw.get("confidence_score") or 0),
            file_evidences=fes,
            call_paths=list(raw.get("call_paths") or []),
            evidence_summary=raw.get("evidence_summary") or "",
        )
