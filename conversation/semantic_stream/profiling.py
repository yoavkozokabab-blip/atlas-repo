"""Latency budgets and profiling for semantic streaming."""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field

import config as cfg

_lock = threading.Lock()
_profiles: list["StreamSemanticProfile"] = []


@dataclass
class StreamSemanticProfile:
    partial_parse_ms: float = 0.0
    plan_ms: float = 0.0
    correction_ms: float = 0.0
    total_ms: float = 0.0
    over_budget: bool = False
    budget_ms: float = 0.0
    partial_len: int = 0
    intent: str = ""
    confidence: float = 0.0
    timestamp: float = field(default_factory=time.monotonic)

    def as_dict(self) -> dict[str, str]:
        return {
            "conv_parse_ms": f"{self.partial_parse_ms:.0f}",
            "conv_plan_ms": f"{self.plan_ms:.0f}",
            "conv_total_ms": f"{self.total_ms:.0f}",
            "conv_budget_ok": "no" if self.over_budget else "yes",
        }


def record_profile(profile: StreamSemanticProfile) -> None:
    global _profiles
    with _lock:
        _profiles.append(profile)
        _profiles = _profiles[-30:]


def get_last_profile() -> StreamSemanticProfile | None:
    with _lock:
        return _profiles[-1] if _profiles else None


def reset_profiles() -> None:
    global _profiles
    with _lock:
        _profiles.clear()


class BudgetTimer:
    """Context manager for budget enforcement."""

    def __init__(self) -> None:
        self.budget_ms = float(cfg.CONV_SEMANTIC_LATENCY_BUDGET_MS)
        self._t0 = 0.0
        self.partial_parse_ms = 0.0
        self.plan_ms = 0.0
        self.correction_ms = 0.0

    def __enter__(self) -> "BudgetTimer":
        self._t0 = time.perf_counter()
        return self

    def __exit__(self, *args) -> None:
        pass

    def mark_parse_done(self) -> None:
        self.partial_parse_ms = (time.perf_counter() - self._t0) * 1000.0

    def mark_plan_done(self) -> None:
        self.plan_ms = (time.perf_counter() - self._t0) * 1000.0 - self.partial_parse_ms

    def finish(
        self,
        *,
        partial_len: int,
        intent: str,
        confidence: float,
    ) -> StreamSemanticProfile:
        total = (time.perf_counter() - self._t0) * 1000.0
        prof = StreamSemanticProfile(
            partial_parse_ms=self.partial_parse_ms,
            plan_ms=self.plan_ms,
            correction_ms=self.correction_ms,
            total_ms=total,
            over_budget=total > self.budget_ms,
            budget_ms=self.budget_ms,
            partial_len=partial_len,
            intent=intent,
            confidence=confidence,
        )
        record_profile(prof)
        return prof
