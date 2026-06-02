"""Autonomous Agent Stack v1 — multi-source browser provider.

Extends the Phase 71 PlaywrightBrowserProvider via SUBCLASS (no edits to
tooluse/provider.py or any legacy file) to add the read-only multi-source
methods the autonomous executor needs: search(), results(), open_index().

There is no mock branch: is_real() is inherited and returns False when
Playwright/Chromium is unavailable. The executor treats that as
BLOCKED_UNAVAILABLE — never success.
"""

from __future__ import annotations

from typing import Protocol

from tooluse.contracts import Observation, PlanStep, RiskLevel, StepKind, StepOutcome
from tooluse.provider import PlaywrightBrowserProvider


class AutonomyProvider(Protocol):
    def is_real(self) -> bool: ...
    def observe(self) -> Observation: ...
    def search(self, query: str) -> StepOutcome: ...
    def results(self) -> list[dict[str, str]]: ...
    def open_index(self, index: int) -> StepOutcome: ...
    def close(self) -> None: ...


_SEARCH_STEP = PlanStep(
    index=0, kind=StepKind.SEARCH, description="search",
    risk=RiskLevel.EXTERNAL, requires_approval=True,
)


class AutonomousBrowserProvider(PlaywrightBrowserProvider):
    """Real provider: reuses Phase 71 search/extraction; adds indexed opening."""

    def search(self, query: str) -> StepOutcome:
        # Reuse the inherited, real DDG/Marginalia search + organic extraction.
        return self.execute(PlanStep(
            index=0, kind=StepKind.SEARCH, description="search",
            risk=RiskLevel.EXTERNAL, requires_approval=True, target=query,
        ))

    def results(self) -> list[dict[str, str]]:
        return list(getattr(self, "_results", []) or [])

    def open_index(self, index: int) -> StepOutcome:
        rows = self.results()
        if index < 0 or index >= len(rows):
            return StepOutcome(ok=False, detail=f"no result at index {index}")
        self._cursor = index   # inherited cursor used by _do_open_result
        return self._do_open_result()
