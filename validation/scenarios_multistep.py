"""50 strict multi-step scenarios (Phase 67 — 85% real, 3+ real steps)."""

from __future__ import annotations

import config

from validation.strict_framework import StrictCategoryMeasurement, run_strict_category
from validation.strict_graders import (
    combine_multistep,
    grade_browser_after_action,
    grade_coding_filesystem,
    grade_desktop_capture,
    grade_desktop_ocr,
    grade_memory_recall,
    grade_memory_write,
)

_CATEGORY = "Multi-Step Task Completion"


def _multistep_scenarios() -> list:
    from validation.strict_framework import StrictScenarioFn

    config.MEMORY_ENABLED = True
    config.SCREEN_UNDERSTANDING_ENABLED = True
    scenarios: list[tuple[str, StrictScenarioFn]] = []

    for i in range(15):

        def _mk_browser_flow(idx: int = i) -> StrictScenarioFn:
            def _run():
                from browser.runtime import find_information_about, open_browser, summarize_current_page
                from memory.store import get_personal_memory

                tag = f"browser_flow_{idx}"
                store = get_personal_memory()
                steps = [
                    grade_browser_after_action(open_browser("about:blank"), require_url=False),
                    grade_browser_after_action(find_information_about(f"topic flow {idx}")),
                    grade_memory_write(
                        bool(store.remember(f"research {tag}", category="session", tags=["phase67", tag]).entry_id),
                        tag,
                    ),
                    grade_browser_after_action(summarize_current_page()),
                ]
                return combine_multistep(steps, min_real_steps=3)

            return _run

        scenarios.append((f"multistep_browser_{i+1:02d}", _mk_browser_flow()))

    for i in range(10):

        def _mk_desktop_flow(idx: int = i) -> StrictScenarioFn:
            def _run():
                from desktop.vision_runtime import capture_active_monitor, extract_ocr_text, get_desktop_state
                from memory.store import get_personal_memory

                tag = f"desktop_flow_{idx}"
                store = get_personal_memory()
                ok, path, msg = capture_active_monitor()
                s1 = grade_desktop_capture(ok, path, msg)
                text, engine = extract_ocr_text()
                s2 = grade_desktop_ocr(text or msg, engine, screenshot_path=path or get_desktop_state().last_screenshot_path)
                s3 = grade_memory_write(
                    bool(store.remember(f"screen {tag}", category="session", tags=["phase67", tag]).entry_id),
                    tag,
                )
                return combine_multistep([s1, s2, s3], min_real_steps=3)

            return _run

        scenarios.append((f"multistep_desktop_{i+1:02d}", _mk_desktop_flow()))

    for i in range(10):

        def _mk_coding_flow(idx: int = i) -> StrictScenarioFn:
            def _run():
                from phase45_investigation import explain_latest_error, hunt_algorithm_bugs, inspect_project
                from reliability.coding_health import score_patch_recommendation, validate_patch_path

                s1 = grade_coding_filesystem("project" in inspect_project().lower(), "inspect")
                s2 = grade_coding_filesystem(bool(hunt_algorithm_bugs() or explain_latest_error()), "analyze")
                conf, _ = score_patch_recommendation("config", ["config.py"])
                ok_path, msg = validate_patch_path("config.py")
                s3 = grade_coding_filesystem(ok_path and conf >= 0.5, f"patch {msg}")
                return combine_multistep([s1, s2, s3], min_real_steps=3)

            return _run

        scenarios.append((f"multistep_coding_{i+1:02d}", _mk_coding_flow()))

    for i in range(15):

        def _mk_memory_flow(idx: int = i) -> StrictScenarioFn:
            def _run():
                from memory.store import get_personal_memory

                tag = f"flow_{idx}"
                store = get_personal_memory()
                s1 = grade_memory_write(
                    bool(
                        store.remember(f"multistep {tag}", category="session", tags=["phase67", tag]).entry_id
                    ),
                    tag,
                )
                hits = store.search_memory(tag)
                s2 = grade_memory_recall(len(hits) > 0, f"hits={len(hits)}")
                sem = store.semantic_search(tag, limit=3)
                s3 = grade_memory_recall(len(sem) > 0, f"semantic={len(sem)}")
                return combine_multistep([s1, s2, s3], min_real_steps=3)

            return _run

        scenarios.append((f"multistep_memory_{i+1:02d}", _mk_memory_flow()))

    return scenarios


def measure_multistep_tasks() -> StrictCategoryMeasurement:
    return run_strict_category(_CATEGORY, _multistep_scenarios())
