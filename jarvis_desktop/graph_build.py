"""Desktop scan graph build policy — budgets, detail levels, lazy full graph."""

from __future__ import annotations

import os
import time
from typing import Any, Callable, Dict, Optional

from builder_core.bug_intelligence import depgraph

# Time budgets (seconds) for graph construction during desktop scan.
BUDGET_PRESCAN_MAX_SEC = 5.0
BUDGET_HIERARCHY_IMPORTS_SEC = 60.0
BUDGET_FULL_MODULE_SEC = 180.0

DETAIL_IMPORTS = depgraph.DETAIL_IMPORTS
DETAIL_FULL = depgraph.DETAIL_FULL


def graph_build_plan(*, massive_mode: bool, code_files: int, estimated_modules: int) -> Dict[str, Any]:
    """Choose graph detail level and time budget for a repository scan."""
    if massive_mode or code_files > 2500 or estimated_modules > 2000:
        return {
            "detail": DETAIL_IMPORTS,
            "time_budget_sec": BUDGET_HIERARCHY_IMPORTS_SEC,
            "lazy_full": True,
            "tier": "massive",
        }
    if code_files > 800 or estimated_modules > 600:
        return {
            "detail": DETAIL_FULL,
            "time_budget_sec": BUDGET_FULL_MODULE_SEC,
            "lazy_full": False,
            "tier": "medium",
        }
    return {
        "detail": DETAIL_FULL,
        "time_budget_sec": None,
        "lazy_full": False,
        "tier": "small",
    }


def build_scan_graph(
    repository_root: str,
    *,
    massive_mode: bool,
    code_files: int,
    estimated_modules: int,
    on_progress: Optional[Callable[[str, int, int], None]] = None,
) -> Dict[str, Any]:
    """Build dependency graph for desktop scan under tiered budgets."""
    plan = graph_build_plan(
        massive_mode=massive_mode,
        code_files=code_files,
        estimated_modules=estimated_modules,
    )
    started = time.time()

    def _progress(phase: str, current: int, total: int) -> None:
        if on_progress:
            on_progress(phase, current, total)

    graph = depgraph.build_graph(
        repository_root,
        detail=plan["detail"],
        time_budget_sec=plan["time_budget_sec"],
        on_progress=_progress,
    )
    elapsed = round(time.time() - started, 3)
    graph["jarvis_graph_build"] = {
        **plan,
        "elapsed_sec": elapsed,
        "timed_out": bool(graph.get("jarvis_timed_out")),
        "partial": bool(graph.get("jarvis_partial")),
    }
    return graph


def build_full_module_graph(
    repository_root: str,
    *,
    time_budget_sec: float = BUDGET_FULL_MODULE_SEC,
    on_progress: Optional[Callable[[str, int, int], None]] = None,
) -> Dict[str, Any]:
    """Lazy/on-demand full module graph (functions, calls, cross-file)."""
    def _progress(phase: str, current: int, total: int) -> None:
        if on_progress:
            on_progress(phase, current, total)

    return depgraph.build_graph(
        repository_root,
        detail=DETAIL_FULL,
        time_budget_sec=time_budget_sec,
        on_progress=_progress,
    )
