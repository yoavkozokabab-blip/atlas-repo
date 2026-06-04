"""Atlas Knowledge Engine — local software engineering knowledge base (Phase 127)."""

from .engine import (
    ConceptClassification,
    KnowledgeEngine,
    RepoFileRoles,
    get_engine,
)
from .loader import knowledge_root, load_concepts_from_disk
from .schema import ConceptRecord, validate_concept

__all__ = [
    "ConceptClassification",
    "ConceptRecord",
    "KnowledgeEngine",
    "RepoFileRoles",
    "get_engine",
    "knowledge_root",
    "load_concepts_from_disk",
    "validate_concept",
]


def concept_count() -> int:
    return get_engine().concept_count
