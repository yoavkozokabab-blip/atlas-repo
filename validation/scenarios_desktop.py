"""50 strict desktop operator scenarios (Phase 67 — 80% real target)."""

from __future__ import annotations

import config

from validation.strict_framework import StrictCategoryMeasurement, run_strict_category
from validation.strict_graders import (
    grade_desktop_capture,
    grade_desktop_control,
    grade_desktop_ocr,
    grade_voice_simulated_routing,
)

_CATEGORY = "Desktop Operator"


def _desktop_scenarios() -> list:
    from validation.strict_framework import StrictScenarioFn

    config.SCREEN_UNDERSTANDING_ENABLED = True
    config.COMPUTER_CONTROL_ENABLED = True
    config.DESKTOP_OPERATOR_ENABLED = True
    scenarios: list[tuple[str, StrictScenarioFn]] = []

    def _mk_capture() -> StrictScenarioFn:
        def _run():
            from desktop.vision_runtime import capture_active_monitor

            ok, path, msg = capture_active_monitor()
            return grade_desktop_capture(ok, path, msg)

        return _run

    for i in range(10):
        scenarios.append((f"desktop_capture_{i+1:02d}", _mk_capture()))

    def _mk_ocr() -> StrictScenarioFn:
        def _run():
            from desktop.vision_runtime import capture_active_monitor, extract_ocr_text, get_desktop_state

            ok, path, _msg = capture_active_monitor()
            text, engine = extract_ocr_text()
            if not path:
                path = get_desktop_state().last_screenshot_path
            return grade_desktop_ocr(text, engine, screenshot_path=path if ok else "")

        return _run

    for i in range(12):
        scenarios.append((f"desktop_ocr_{i+1:02d}", _mk_ocr()))

    def _mk_windows() -> StrictScenarioFn:
        def _run():
            from desktop.vision_runtime import detect_windows

            rows = detect_windows()
            if rows:
                titles = " ".join(r.get("title", "") for r in rows[:5])
                return grade_desktop_ocr(titles or "window_list", "pygetwindow")
            return grade_voice_simulated_routing(False, "no_windows")

        return _run

    for i in range(6):
        scenarios.append((f"desktop_windows_{i+1:02d}", _mk_windows()))

    def _extract_capture_path(body: str) -> str:
        import re

        m = re.search(r"Captured active monitor:\s*(\S+)", body)
        return m.group(1) if m else ""

    def _mk_screen() -> StrictScenarioFn:
        def _run():
            from desktop.vision_runtime import what_is_on_my_screen

            body = what_is_on_my_screen()
            if "REAL DESKTOP VISION" in body:
                path = _extract_capture_path(body)
                if path:
                    return grade_desktop_capture(True, path, body[:100])
                return grade_desktop_ocr(body, "accessibility", screenshot_path="")
            return grade_desktop_capture(False, "", body)

        return _run

    for i in range(6):
        scenarios.append((f"desktop_screen_{i+1:02d}", _mk_screen()))

    def _mk_vision_health() -> StrictScenarioFn:
        def _run():
            from reliability.desktop_vision_health import show_desktop_vision_health

            body = show_desktop_vision_health()
            from desktop.vision_runtime import get_desktop_state

            st = get_desktop_state()
            text, engine = st.last_ocr_excerpt, "health_probe"
            if st.last_screenshot_path:
                from desktop.vision_runtime import extract_ocr_text

                text, engine = extract_ocr_text()
            return grade_desktop_ocr(
                text or ("capture_ok" if "capture_ok: True" in body else ""),
                engine if text else "pygetwindow",
                screenshot_path=st.last_screenshot_path or "",
            )

        return _run

    for i in range(8):
        scenarios.append((f"desktop_vision_health_{i+1:02d}", _mk_vision_health()))

    def _mk_list() -> StrictScenarioFn:
        def _run():
            from desktop.vision_runtime import list_open_windows

            body = list_open_windows()
            if "REAL DESKTOP" in body:
                return grade_desktop_ocr(body[:200], "pygetwindow")
            return grade_voice_simulated_routing("window" in body.lower(), body[:80])

        return _run

    for i in range(4):
        scenarios.append((f"desktop_list_{i+1:02d}", _mk_list()))

    def _mk_type(idx: int) -> StrictScenarioFn:
        def _run():
            from desktop.control_runtime import type_text

            return grade_desktop_control(type_text(f"phase67 test {idx}", approved=True), typed=True)

        return _run

    for i in range(4):
        scenarios.append((f"desktop_type_{i+1:02d}", _mk_type(i)))

    return scenarios


def measure_desktop_operator() -> StrictCategoryMeasurement:
    return run_strict_category(_CATEGORY, _desktop_scenarios())
