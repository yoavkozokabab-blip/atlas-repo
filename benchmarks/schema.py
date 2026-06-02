"""Phase 130 — Atlas repository understanding benchmark schema."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

BENCHMARK_ROOT = Path(__file__).resolve().parent
REPOS_DIR = BENCHMARK_ROOT / "repos"
SUITE_PATH = BENCHMARK_ROOT / "atlas_benchmark_suite_v1.json"

CATEGORIES = ("feature_addition", "bug_investigation", "impact_analysis")
TASK_TYPES = ("build", "investigate", "impact")


@dataclass
class BenchmarkScenario:
    scenario_id: str
    category: str
    repository: str
    prompt: str
    task_type: str = "build"
    impact_target: str = ""
    expected_concept_id: str = ""
    expected_findings: List[str] = field(default_factory=list)
    expected_files: List[str] = field(default_factory=list)
    expected_insertion_points: List[str] = field(default_factory=list)
    expected_risks: List[str] = field(default_factory=list)
    expected_tests: List[str] = field(default_factory=list)
    notes: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "BenchmarkScenario":
        known = set(cls.__dataclass_fields__)  # type: ignore[attr-defined]
        return cls(**{k: v for k, v in data.items() if k in known})

    def repo_path(self) -> Path:
        import os

        if self.repository in ("FINAL_ALGO_TRADER",):
            return Path(os.environ.get("ATLAS_BENCHMARK_REPO", r"C:\FINAL_ALGO_TRADER"))
        return REPOS_DIR / self.repository


@dataclass
class ScenarioMetrics:
    file_precision: float = 0.0
    file_recall: float = 0.0
    insertion_point_correct: bool = False
    knowledge_correct: bool = False
    evidence_accuracy: float = 0.0
    risk_recall: float = 0.0
    test_recall: float = 0.0
    finding_recall: float = 0.0
    atlas_score: float = 0.0
    repository_understanding: float = 0.0
    knowledge_understanding: float = 0.0
    evidence_quality: float = 0.0
    investigation_quality: float = 0.0
    impact_analysis_quality: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class FailureRecord:
    scenario_id: str
    reason: str
    evidence_used: List[str] = field(default_factory=list)
    expected_evidence: List[str] = field(default_factory=list)
    missing_evidence: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class EvidenceAuditItem:
    scenario_id: str
    audit_type: str
    detail: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ScenarioResult:
    scenario: BenchmarkScenario
    ok: bool
    metrics: ScenarioMetrics
    recommended_files: List[str] = field(default_factory=list)
    actual_concept_id: str = ""
    actual_insertion: str = ""
    actual_findings: List[str] = field(default_factory=list)
    failures: List[FailureRecord] = field(default_factory=list)
    evidence_audits: List[EvidenceAuditItem] = field(default_factory=list)
    error: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "scenario_id": self.scenario.scenario_id,
            "category": self.scenario.category,
            "repository": self.scenario.repository,
            "prompt": self.scenario.prompt,
            "ok": self.ok,
            "metrics": self.metrics.to_dict(),
            "recommended_files": self.recommended_files,
            "actual_concept_id": self.actual_concept_id,
            "actual_insertion": self.actual_insertion,
            "actual_findings": self.actual_findings,
            "failures": [f.to_dict() for f in self.failures],
            "evidence_audits": [a.to_dict() for a in self.evidence_audits],
            "error": self.error,
        }


def load_suite(path: Optional[Path] = None) -> List[BenchmarkScenario]:
    p = path or SUITE_PATH
    raw = json.loads(p.read_text(encoding="utf-8"))
    return [BenchmarkScenario.from_dict(item) for item in raw.get("scenarios", [])]
