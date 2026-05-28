"""50 strict recovery scenarios (Phase 67 — 80% real target)."""

from __future__ import annotations

from pathlib import Path

from validation.strict_framework import StrictCategoryMeasurement, run_strict_category
from validation.strict_graders import (
    grade_recovery_browser,
    grade_recovery_capability,
)

_CATEGORY = "Recovery After Failures"


def _recovery_scenarios() -> list:
    from validation.strict_framework import StrictScenarioFn

    scenarios: list[tuple[str, StrictScenarioFn]] = []

    for i in range(12):

        def _mk_browser() -> StrictScenarioFn:
            def _run():
                from browser.runtime import get_browser_runtime_state, recover_browser_session

                before = get_browser_runtime_state()
                ok, msg = recover_browser_session()
                after = get_browser_runtime_state()
                restored = ok and after.browser_process_alive and after.last_action_success
                return grade_recovery_browser(ok, msg, recovered=restored)

            return _run

        scenarios.append((f"recovery_browser_{i+1:02d}", _mk_browser()))

    for i in range(10):

        def _mk_nav() -> StrictScenarioFn:
            def _run():
                from browser.runtime import get_browser_runtime_state, recover_navigation

                before_ok = get_browser_runtime_state().last_action_success
                ok, msg = recover_navigation("https://example.com")
                after = get_browser_runtime_state()
                restored = ok and after.browser_process_alive and bool(after.current_url)
                return grade_recovery_capability(
                    ok,
                    restored,
                    "browser_nav",
                    msg,
                    evidence_path=after.last_screenshot_path or "",
                    before_ok=before_ok,
                )

            return _run

        scenarios.append((f"recovery_nav_{i+1:02d}", _mk_nav()))

    for i in range(10):

        def _mk_desktop() -> StrictScenarioFn:
            def _run():
                from desktop.control_runtime import recover_desktop_operator
                from desktop.vision_runtime import capture_active_monitor

                _ok0, path0, _ = capture_active_monitor()
                ok_rec, msg = recover_desktop_operator()
                ok_after, path_after, _ = capture_active_monitor()
                restored = ok_rec and ok_after and Path(path_after).is_file()
                return grade_recovery_capability(
                    ok_rec,
                    restored,
                    "desktop",
                    msg,
                    evidence_path=path_after or path0 or "",
                    before_ok=False,
                )

            return _run

        scenarios.append((f"recovery_desktop_{i+1:02d}", _mk_desktop()))

    for i in range(8):

        def _mk_memory() -> StrictScenarioFn:
            def _run():
                from memory.repair import repair_memory_store

                body = repair_memory_store()
                ok = "repair complete" in body.lower()
                return grade_recovery_capability(ok, ok, "memory", body[:80])

            return _run

        scenarios.append((f"recovery_memory_{i+1:02d}", _mk_memory()))

    for i in range(5):

        def _mk_tts() -> StrictScenarioFn:
            def _run():
                from voice.tts_recovery import recover_tts_and_speak

                ok, msg = recover_tts_and_speak()
                return grade_recovery_capability(ok, ok, "tts", msg)

            return _run

        scenarios.append((f"recovery_tts_{i+1:02d}", _mk_tts()))

    for i in range(5):

        def _mk_browser_restart() -> StrictScenarioFn:
            def _run():
                from browser.runtime import get_browser_runtime_state, recover_browser_session

                st = get_browser_runtime_state()
                before_ok = st.browser_process_alive and st.last_action_success
                ok, msg = recover_browser_session()
                after = get_browser_runtime_state()
                restored = ok and after.browser_process_alive
                return grade_recovery_capability(
                    ok,
                    restored,
                    "browser_restart",
                    msg,
                    evidence_path=after.last_screenshot_path or "",
                    before_ok=before_ok,
                )

            return _run

        scenarios.append((f"recovery_browser_restart_{i+1:02d}", _mk_browser_restart()))

    return scenarios


def measure_recovery() -> StrictCategoryMeasurement:
    return run_strict_category(_CATEGORY, _recovery_scenarios())
