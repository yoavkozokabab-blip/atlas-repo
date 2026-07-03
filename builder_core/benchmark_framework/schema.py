"""Phase 103 benchmark schemas and deterministic JSON helpers."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

TASK_TYPES = (
    "repository_understanding",
    "dependency_analysis",
    "impact_analysis",
    "architectural_risk",
    "contract_analysis",
    "verification_evidence",
    "confirmed_defect_detection",
    "fix_planning",
)

MODES = ("codex_alone", "atlas_plus_codex")


@dataclass
class BenchmarkTask:
    task_id: str
    repo_id: str
    repo_path: str
    task_type: str
    prompt: str
    expected_answer: str
    scoring_rubric: List[Dict[str, Any]] = field(default_factory=list)
    required_evidence: List[str] = field(default_factory=list)
    baseline_mode: str = ""
    atlas_mode: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "BenchmarkTask":
        known = set(cls.__dataclass_fields__)  # type: ignore[attr-defined]
        return cls(**{key: value for key, value in data.items() if key in known})


@dataclass
class RunLog:
    task_id: str
    mode: str
    model_tool_used: str = ""
    start_time: str = ""
    end_time: str = ""
    elapsed_seconds: float = 0.0
    estimated_input_tokens: int = 0
    estimated_output_tokens: int = 0
    raw_answer_path: str = ""
    score_path: str = ""
    notes: str = ""
    token_numbers_are_estimates: bool = True
    token_breakdown: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        payload = asdict(self)
        if not self.token_breakdown:
            payload.pop("token_breakdown", None)
        return payload

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RunLog":
        known = set(cls.__dataclass_fields__)  # type: ignore[attr-defined]
        return cls(**{key: value for key, value in data.items() if key in known})

    @property
    def estimated_total_tokens(self) -> int:
        return self.estimated_input_tokens + self.estimated_output_tokens


@dataclass
class ManualScore:
    task_id: str
    mode: str
    correctness: float
    evidence_quality: float
    completeness: float
    hallucination_risk: float
    task_success: bool
    true_positives: int = 0
    false_positives: int = 0
    false_negatives: int = 0
    notes: str = ""

    def to_dict(self) -> Dict[str, Any]:
        payload = asdict(self)
        payload["total_score"] = self.total_score
        payload["bug_finding_accuracy"] = self.bug_finding_accuracy
        return payload

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ManualScore":
        known = set(cls.__dataclass_fields__)  # type: ignore[attr-defined]
        return cls(**{key: value for key, value in data.items() if key in known})

    @property
    def total_score(self) -> float:
        """Return a 0..100 quality score; lower hallucination risk is better."""
        safe_from_hallucination = 5.0 - self.hallucination_risk
        return round(
            100.0
            * (self.correctness + self.evidence_quality + self.completeness + safe_from_hallucination)
            / 20.0,
            2,
        )

    @property
    def bug_finding_accuracy(self) -> Dict[str, Optional[float]]:
        precision_denominator = self.true_positives + self.false_positives
        recall_denominator = self.true_positives + self.false_negatives
        precision = (
            round(self.true_positives / precision_denominator, 4)
            if precision_denominator
            else None
        )
        recall = (
            round(self.true_positives / recall_denominator, 4)
            if recall_denominator
            else None
        )
        return {"precision": precision, "recall": recall}


def validate_task(data: Dict[str, Any]) -> List[str]:
    errors: List[str] = []
    required = (
        "task_id",
        "repo_id",
        "repo_path",
        "task_type",
        "prompt",
        "expected_answer",
        "scoring_rubric",
        "required_evidence",
        "baseline_mode",
        "atlas_mode",
    )
    for key in required:
        if key not in data:
            errors.append(f"missing required field: {key}")
    for key in ("task_id", "repo_id", "repo_path", "prompt", "expected_answer"):
        if key in data and not str(data.get(key, "")).strip():
            errors.append(f"{key} must be a non-empty string")
    if data.get("task_type") not in TASK_TYPES:
        errors.append(f"task_type must be one of {TASK_TYPES}")
    rubric = data.get("scoring_rubric")
    if not isinstance(rubric, list) or not rubric:
        errors.append("scoring_rubric must be a non-empty list")
    elif any(not isinstance(item, str) or not item.strip() for item in rubric):
        errors.append("scoring_rubric entries must be non-empty strings")
    evidence = data.get("required_evidence")
    if not isinstance(evidence, list):
        errors.append("required_evidence must be a list")
    elif any(not isinstance(item, str) or not item.strip() for item in evidence):
        errors.append("required_evidence entries must be non-empty strings")
    return errors


def validate_run_log(data: Dict[str, Any]) -> List[str]:
    errors: List[str] = []
    if not str(data.get("task_id", "")).strip():
        errors.append("run log missing task_id")
    if data.get("mode") not in MODES:
        errors.append(f"mode must be one of {MODES}")
    for name in ("elapsed_seconds", "estimated_input_tokens", "estimated_output_tokens"):
        value = data.get(name)
        if not isinstance(value, (int, float)) or isinstance(value, bool) or value < 0:
            errors.append(f"{name} must be a non-negative number")
    for name in ("raw_answer_path", "score_path"):
        if not str(data.get(name, "")).strip():
            errors.append(f"run log missing {name}")
    if data.get("token_numbers_are_estimates") is not True:
        errors.append("token_numbers_are_estimates must be true")
    breakdown = data.get("token_breakdown")
    if breakdown is not None and breakdown != {}:
        if not isinstance(breakdown, dict):
            errors.append("token_breakdown must be an object when present")
        else:
            for key in ("raw_prompt", "atlas_context", "final_prompt_package"):
                section = breakdown.get(key)
                if not isinstance(section, dict) or "estimated_tokens" not in section:
                    errors.append(f"token_breakdown.{key}.estimated_tokens required")
    return errors


def validate_manual_score(data: Dict[str, Any]) -> List[str]:
    errors: List[str] = []
    if not str(data.get("task_id", "")).strip():
        errors.append("manual score missing task_id")
    if data.get("mode") not in MODES:
        errors.append(f"mode must be one of {MODES}")
    for name in ("correctness", "evidence_quality", "completeness", "hallucination_risk"):
        value = data.get(name)
        if not isinstance(value, (int, float)) or isinstance(value, bool) or not 0 <= value <= 5:
            errors.append(f"{name} must be within [0, 5]")
    if not isinstance(data.get("task_success"), bool):
        errors.append("task_success must be a boolean")
    for name in ("true_positives", "false_positives", "false_negatives"):
        value = data.get(name, 0)
        if not isinstance(value, int) or isinstance(value, bool) or value < 0:
            errors.append(f"{name} must be a non-negative integer")
    return errors


def parse_timestamp(value: str) -> datetime:
    """Parse an ISO-8601 timestamp used by manually recorded benchmark runs."""
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def load_tasks(path: str) -> List[BenchmarkTask]:
    payload = load_json(path)
    raw = payload["tasks"] if isinstance(payload, dict) else payload
    if not isinstance(raw, list):
        raise ValueError("task file must contain a list or an object with a tasks list")
    return [BenchmarkTask.from_dict(item) for item in raw]


def validate_task_file(path: str) -> Dict[str, List[str]]:
    payload = load_json(path)
    raw = payload["tasks"] if isinstance(payload, dict) else payload
    if not isinstance(raw, list):
        return {"<file>": ["task file must contain a list or an object with a tasks list"]}
    failures: Dict[str, List[str]] = {}
    seen: set[str] = set()
    for item in raw:
        task_id = item.get("task_id", "<missing-task-id>") if isinstance(item, dict) else "<invalid-task>"
        errors = validate_task(item) if isinstance(item, dict) else ["task entry must be an object"]
        if task_id in seen:
            errors.append(f"duplicate task_id: {task_id}")
        seen.add(task_id)
        if errors:
            failures[task_id] = errors
    return failures


def dump_json(value: Any, path: str) -> None:
    import os

    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(value, handle, ensure_ascii=True, indent=2, sort_keys=True)
        handle.write("\n")


def load_json(path: str) -> Any:
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)
