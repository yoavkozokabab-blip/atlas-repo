"""50 strict memory recall scenarios (Phase 66.1)."""

from __future__ import annotations

import config

from validation.strict_framework import StrictCategoryMeasurement, run_strict_category
from validation.strict_graders import grade_memory_recall, grade_memory_write

_CATEGORY = "Memory Recall"


def _memory_scenarios() -> list:
    from validation.strict_framework import StrictScenarioFn

    config.MEMORY_ENABLED = True
    scenarios: list[tuple[str, StrictScenarioFn]] = []

    def _mk_remember(t: str) -> StrictScenarioFn:
        def _run():
            from memory.store import get_personal_memory

            entry = get_personal_memory().remember(
                f"validation fact {t}",
                category="session",
                tags=["phase66", t],
                ttl_seconds=7200,
            )
            return grade_memory_write(bool(entry.entry_id), entry.entry_id)

        return _run

    def _mk_retrieve(t: str) -> StrictScenarioFn:
        def _run():
            from memory.store import get_personal_memory

            store = get_personal_memory()
            store.remember(f"validation fact {t}", category="session", tags=["phase66", t])
            hits = store.search_memory(t)
            ok = len(hits) > 0
            if not ok:
                ok = len(store.semantic_search(t, limit=3)) > 0
            return grade_memory_recall(ok, f"hits={len(hits)}")

        return _run

    for i in range(50):
        tag = f"phase66_mem_{i+1:02d}"
        if i % 2 == 0:
            scenarios.append((f"memory_remember_{i+1:02d}", _mk_remember(tag)))
        else:
            scenarios.append((f"memory_retrieve_{i+1:02d}", _mk_retrieve(tag)))

    return scenarios


def measure_memory_recall() -> StrictCategoryMeasurement:
    return run_strict_category(_CATEGORY, _memory_scenarios())
