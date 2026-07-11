"""Normalized benchmark records."""

from __future__ import annotations

import hashlib
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any

from .tasks import BenchmarkTask, RepositorySpec
from .tokens import estimated_token_metric, unavailable_token_metric


CONDITIONS = (
    "codex_no_atlas",
    "codex_with_atlas",
    "cursor_no_atlas",
    "cursor_with_atlas",
)


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def prompt_hash(prompt: str) -> str:
    return hashlib.sha256(prompt.encode("utf-8")).hexdigest()


def condition_name(agent: str, atlas_enabled: bool) -> str:
    return f"{agent}_{'with' if atlas_enabled else 'no'}_atlas"


def anonymous_id(seed: str) -> str:
    return "run_" + hashlib.sha256(seed.encode("utf-8")).hexdigest()[:12]


@dataclass
class RunnerInfo:
    agent: str
    atlas_enabled: bool
    provider: str
    adapter: str
    model: str | None = None
    tool_version: str | None = None
    system_instructions_fingerprint: str | None = None


@dataclass
class TokenUsage:
    user_prompt_tokens: dict[str, Any] = field(default_factory=unavailable_token_metric)
    system_context_tokens: dict[str, Any] = field(default_factory=unavailable_token_metric)
    output_tokens: dict[str, Any] = field(default_factory=unavailable_token_metric)
    total_tokens: dict[str, Any] = field(default_factory=unavailable_token_metric)
    atlas_mcp_response_tokens: dict[str, Any] = field(default_factory=unavailable_token_metric)


@dataclass
class Observations:
    latency_ms: int | None = None
    time_to_first_tool_call_ms: int | None = None
    time_to_first_useful_answer_ms: int | None = None
    atlas_indexing_ms: int | None = None
    mcp_retrieval_latency_ms: int | None = None
    token_usage: TokenUsage = field(default_factory=TokenUsage)
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    atlas_calls: list[dict[str, Any]] = field(default_factory=list)
    files_opened: list[str] = field(default_factory=list)
    search_calls: int | None = None
    file_read_calls: int | None = None
    failed_tool_calls: int | None = None
    retries: int = 0
    errors: list[str] = field(default_factory=list)
    telemetry_quality: dict[str, str] = field(default_factory=dict)


@dataclass
class Score:
    correctness: int
    completeness: int
    citation_accuracy: int
    evidence_quality: int
    hallucination_avoidance: int
    actionability: int
    strict_success: bool
    source: str
    notes: str = ""

    @property
    def total_score(self) -> int:
        return (
            self.correctness
            + self.completeness
            + self.citation_accuracy
            + self.evidence_quality
            + self.hallucination_avoidance
            + self.actionability
        )

    @property
    def accuracy_percent(self) -> float:
        return round((self.total_score / 30.0) * 100.0, 3)

    def to_dict(self) -> dict[str, Any]:
        raw = asdict(self)
        raw["total_score"] = self.total_score
        raw["accuracy_percent"] = self.accuracy_percent
        return raw


@dataclass
class RunRecord:
    schema_version: int
    run_id: str
    anonymous_id: str
    run_set_id: str | None
    created_at: str
    started_at: str | None
    ended_at: str | None
    status: str
    condition: str
    task_id: str
    repository_id: str
    repository_commit_sha: str
    category: str
    difficulty: str
    prompt_sha256: str
    prompt: str
    runner: RunnerInfo
    response_text: str = ""
    observations: Observations = field(default_factory=Observations)
    scores: dict[str, Any] = field(default_factory=dict)
    condition_evidence: dict[str, Any] = field(default_factory=dict)
    cold_start: bool | None = None
    notes: str = ""

    @classmethod
    def pending(
        cls,
        *,
        task: BenchmarkTask,
        repo: RepositorySpec,
        agent: str,
        atlas_enabled: bool,
        repeat: int,
        run_set_id: str,
    ) -> "RunRecord":
        created = now_iso()
        condition = condition_name(agent, atlas_enabled)
        seed = f"{run_set_id}:{task.task_id}:{condition}:r{repeat}"
        run_id = f"{task.task_id}_{condition}_r{repeat}_{run_set_id}"
        obs = Observations()
        obs.token_usage.user_prompt_tokens = estimated_token_metric(task.prompt)
        obs.telemetry_quality = {
            "user_prompt_tokens": "estimated",
            "system_context_tokens": "unavailable",
            "output_tokens": "unavailable",
            "latency": "unavailable",
            "tool_calls": "unavailable",
            "files_opened": "unavailable",
        }
        return cls(
            schema_version=2,
            run_id=run_id,
            anonymous_id=anonymous_id(seed),
            run_set_id=run_set_id,
            created_at=created,
            started_at=None,
            ended_at=None,
            status="pending_manual_or_external_run",
            condition=condition,
            task_id=task.task_id,
            repository_id=task.repository_id,
            repository_commit_sha=repo.commit_sha,
            category=task.category,
            difficulty=task.difficulty,
            prompt_sha256=prompt_hash(task.prompt),
            prompt=task.prompt,
            runner=RunnerInfo(
                agent=agent,
                atlas_enabled=atlas_enabled,
                provider=agent,
                adapter="atlas" if atlas_enabled else "no_atlas",
            ),
            observations=obs,
        )

    def to_dict(self) -> dict[str, Any]:
        raw = asdict(self)
        token_usage = raw["observations"]["token_usage"]
        raw["observations"]["token_usage"] = token_usage
        return raw
