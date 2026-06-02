"""Autonomous Agent Stack v1 — bounded run limits."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RunLimits:
    max_steps: int = 12
    max_sources: int = 4
    max_runtime_seconds: float = 90.0
    max_recovery_per_step: int = 2

    def as_dict(self) -> dict[str, float | int]:
        return {
            "max_steps": self.max_steps,
            "max_sources": self.max_sources,
            "max_runtime_seconds": self.max_runtime_seconds,
            "max_recovery_per_step": self.max_recovery_per_step,
        }
