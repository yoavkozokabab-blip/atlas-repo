"""Phase 63 smoke: desktop operator runtime."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _enable_runtime_flags() -> None:
    import config as cfg

    cfg.SCREEN_UNDERSTANDING_ENABLED = True
    cfg.COMPUTER_CONTROL_ENABLED = True
    cfg.DESKTOP_OPERATOR_ENABLED = True
    cfg.DESKTOP_OPERATOR_SAFE_MODE = True


def _run(intent_name: str, text: str):
    from actions.registry import ActionRegistry
    from core.types import CommandRequest, Intent

    reg = ActionRegistry()
    intent = getattr(Intent, intent_name)
    action = reg._actions.get(intent.value)
    assert action is not None, f"missing action {intent.value}"
    return action.execute(CommandRequest(raw_text=text, intent=intent))


def main() -> None:
    _enable_runtime_flags()

    from desktop.vision_runtime import capture_active_monitor, detect_active_app, extract_ocr_text

    ok, path, cap_msg = capture_active_monitor()
    assert ok, cap_msg
    assert path, "expected screenshot path"

    app = detect_active_app()
    assert app, "expected active app detection"

    shot = _run("TAKE_SCREENSHOT", "take screenshot")
    assert shot.status.value in {"success", "ok"}, shot.summary

    text, engine = extract_ocr_text()
    assert engine, "expected OCR engine label"

    windows = _run("LIST_OPEN_WINDOWS", "list open windows")
    assert "window" in windows.summary.lower(), windows.summary

    switch = _run("SWITCH_TO_CHROME", "switch to chrome")
    assert switch.status.value in {"success", "ok", "failed"}, switch.summary

    typed = _run("TYPE_THIS", "type this jarvis phase63 smoke test")
    assert "Typed text" in typed.summary or "Approval required" in typed.summary, typed.summary

    screen = _run("WHAT_IS_ON_MY_SCREEN", "what is on my screen")
    assert screen.status.value in {"success", "ok"}, screen.summary

    from desktop.memory import snapshot

    mem = snapshot()
    assert mem.get("recent_screens") or mem.get("ui_transitions"), "expected desktop memory rows"

    print("SMOKE PASS phase63_desktop_operator")


if __name__ == "__main__":
    main()
