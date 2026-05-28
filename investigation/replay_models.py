"""Deterministic replay data models."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any


def stable_json(data: Any) -> str:
    return json.dumps(data, sort_keys=True, ensure_ascii=True, separators=(",", ":"))


def stable_hash(data: Any) -> str:
    return hashlib.sha256(stable_json(data).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class ReplayBar:
    index: int
    timestamp: str
    open: float
    high: float
    low: float
    close: float
    volume: float = 0.0
    complete: bool = True


@dataclass(frozen=True)
class ReplayStep:
    name: str
    inputs: dict[str, Any]
    outputs: dict[str, Any]
    rejection_reason: str = ""
    state_delta: dict[str, Any] = field(default_factory=dict)
    evidence_paths: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class ReplayResult:
    symbol: str
    frozen_at: str
    config_hash: str
    universe_hash: str
    random_seed: int
    selected_bars: list[ReplayBar]
    ranking_scores: dict[str, float]
    execution_attempts: int
    rejection_reasons: list[str]
    portfolio_before: dict[str, Any]
    portfolio_after: dict[str, Any]
    steps: list[ReplayStep]
    evidence_paths: list[str]
    replay_hash: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ReplayDiff:
    symbol: str
    status: str
    first_divergence: str
    live_bar: ReplayBar | None
    backtest_bar: ReplayBar | None
    divergence_reasons: list[str]
    evidence_paths: list[str]
    confidence: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class HypothesisVerification:
    title: str
    status: str
    evidence_count: int
    replay_confirmation: bool
    contradictory_evidence: list[str]
    reproducibility_score: float
    confidence_before: float
    confidence_after: float
    evidence_paths: list[str]
    rationale: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class CausalityNode:
    node_id: str
    event: str
    confidence: float
    evidence_paths: list[str]


@dataclass(frozen=True)
class CausalityEdge:
    source: str
    target: str
    cause: str
    confidence: float


@dataclass(frozen=True)
class ReplaySnapshot:
    created_at: str
    symbol: str
    replay: dict[str, Any]
    diff: dict[str, Any] | None
    hypotheses: list[dict[str, Any]]
    evidence_references: list[str]
    metadata: dict[str, Any]

    @classmethod
    def build(
        cls,
        *,
        symbol: str,
        replay: ReplayResult,
        diff: ReplayDiff | None,
        hypotheses: list[HypothesisVerification],
    ) -> "ReplaySnapshot":
        evidence = sorted(
            set(
                replay.evidence_paths
                + (diff.evidence_paths if diff else [])
                + [p for h in hypotheses for p in h.evidence_paths]
            )
        )
        return cls(
            created_at=datetime.now(timezone.utc).isoformat(),
            symbol=symbol,
            replay=replay.to_dict(),
            diff=diff.to_dict() if diff else None,
            hypotheses=[h.to_dict() for h in hypotheses],
            evidence_references=evidence,
            metadata={
                "read_only": True,
                "live_execution": False,
                "random_seed": replay.random_seed,
                "replay_hash": replay.replay_hash,
            },
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
