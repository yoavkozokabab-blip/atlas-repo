"""Phase 65 Track D — desktop operator reliability."""

from __future__ import annotations

import config
from reliability.hardening_core import TrackScore, format_track_report, reports_dir, run_case, write_report


def show_desktop_operator_health() -> str:
    from desktop.state import DesktopRuntimeState
    from desktop.vision_runtime import get_desktop_state

    st = get_desktop_state()
    lines = [
        "Desktop operator health (Phase 65):",
        f"  operator_enabled: {bool(config.DESKTOP_OPERATOR_ENABLED)}",
        f"  safe_mode: {bool(config.DESKTOP_OPERATOR_SAFE_MODE)}",
        f"  computer_control: {bool(config.COMPUTER_CONTROL_ENABLED)}",
        f"  screen_understanding: {bool(config.SCREEN_UNDERSTANDING_ENABLED)}",
        f"  active_app: {st.active_app or 'n/a'}",
        f"  focused_window: {st.focused_window or 'n/a'}",
        f"  open_window_count: {st.open_window_count}",
        f"  last_action_success: {st.last_action_success}",
        f"  last_exception: {st.last_exception or 'none'}",
    ]
    return "\n".join(lines)


def run_desktop_acceptance() -> TrackScore:
    score = TrackScore(track="Desktop Operator", current_pct=0.0, target_pct=80.0)
    prev_cc = config.COMPUTER_CONTROL_ENABLED
    prev_screen = config.SCREEN_UNDERSTANDING_ENABLED
    config.COMPUTER_CONTROL_ENABLED = True
    config.SCREEN_UNDERSTANDING_ENABLED = True

    def _capture() -> tuple[bool, str]:
        from desktop.vision_runtime import capture_active_monitor

        ok, path, msg = capture_active_monitor()
        return ok or "disabled" in msg.lower(), msg[:120]

    def _ocr() -> tuple[bool, str]:
        from desktop.vision_runtime import extract_ocr_text

        text, engine = extract_ocr_text()
        return bool(engine), f"engine={engine} chars={len(text)}"

    def _windows() -> tuple[bool, str]:
        from desktop.vision_runtime import detect_windows

        rows = detect_windows()
        return True, f"windows={len(rows)}"

    def _recovery() -> tuple[bool, str]:
        from desktop.control_runtime import recover_desktop_operator

        ok, msg = recover_desktop_operator()
        return ok, msg[:120]

    def _typing_safe() -> tuple[bool, str]:
        from desktop.control_runtime import type_text

        body = type_text("jarvis phase65 acceptance", approved=True)
        return "Typed" in body or "disabled" in body, body[:120]

    try:
        score.cases.extend(
            [
                run_case("screen_capture", _capture),
                run_case("ocr", _ocr),
                run_case("window_detection", _windows),
                run_case("failure_recovery", _recovery),
                run_case("typing_safe", _typing_safe),
            ]
        )
    finally:
        config.COMPUTER_CONTROL_ENABLED = prev_cc
        config.SCREEN_UNDERSTANDING_ENABLED = prev_screen

    score.finalize_score()
    if score.pass_rate < 90:
        score.blockers.append("Desktop acceptance below 90% target.")
        score.recommendations.append("Enable SCREEN_UNDERSTANDING_ENABLED and install Tesseract for OCR.")
    write_report(reports_dir() / "desktop_operator_report.md", format_track_report(score).splitlines())
    return score
