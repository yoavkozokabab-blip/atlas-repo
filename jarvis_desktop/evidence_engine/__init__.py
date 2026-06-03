"""Repository evidence engine — AST-backed proof for Build Plan and Investigate (Phase 129)."""

from .evidence_builder import (
    EvidenceStore,
    analyze_concept,
    analyze_investigation,
    apply_to_build_plan,
    apply_to_investigation_plan,
    apply_impact_precision,
    build_evidence_store,
    merge_file_roles_with_evidence,
)
from .precision_engine import PrecisionResult, rank_files
from .evidence_models import FileEvidence, RepositoryEvidenceBundle

__all__ = [
    "EvidenceStore",
    "FileEvidence",
    "RepositoryEvidenceBundle",
    "analyze_concept",
    "analyze_investigation",
    "apply_to_build_plan",
    "apply_to_investigation_plan",
    "build_evidence_store",
]
