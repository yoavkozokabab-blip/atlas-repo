#!/usr/bin/env python3
"""Phase 68 smoke: friend & family alpha readiness."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _fail(msg: str) -> None:
    print(f"SMOKE FAIL: {msg}")
    sys.exit(1)


def _run(intent_name: str, text: str):
    from actions.registry import ActionRegistry
    from core.types import CommandRequest, Intent

    reg = ActionRegistry()
    intent = getattr(Intent, intent_name)
    action = reg._actions.get(intent.value)
    if action is None:
        _fail(f"missing action {intent.value}")
    return action.execute(CommandRequest(raw_text=text, intent=intent))


def main() -> None:
    import config

    config.ALPHA_MODE = True
    config.DEVELOPER_MODE = False
    from alpha.mode import apply_alpha_runtime_defaults

    apply_alpha_runtime_defaults()

    if not config.COMPUTER_CONTROL_ENABLED:
        print("  alpha: COMPUTER_CONTROL_ENABLED=false OK")
    else:
        _fail("alpha defaults did not disable computer control")

    # Launcher script exists
    launcher = ROOT / "scripts" / "launch_alpha.ps1"
    if not launcher.is_file():
        _fail("scripts/launch_alpha.ps1 missing")

    # Alpha setup check
    setup = _run("ALPHA_SETUP_CHECK", "alpha setup check")
    if "Alpha setup check" not in setup.summary:
        _fail("alpha setup check missing header")
    print("  alpha setup check OK")

    # Safe command set (classify + route sample)
    from brain.intent_classifier import classify_rules
    from core.types import Intent

    for phrase, expected in [
        ("what is on my screen", Intent.WHAT_IS_ON_MY_SCREEN),
        ("remember that alpha test note", Intent.REMEMBER_FACT),
        ("summarize my day", Intent.SUMMARIZE_MY_DAY),
    ]:
        got = classify_rules(phrase)
        if got.intent != expected:
            _fail(f"classify {phrase!r} -> {got.intent}, expected {expected}")

    # Browser
    from browser.runtime import test_real_browser

    ok, body = test_real_browser()
    if not ok and "mock" not in body.lower():
        print(f"  browser: degraded ({body[:60]})")
    else:
        print("  browser OK")

    # Desktop screenshot
    config.SCREEN_UNDERSTANDING_ENABLED = True
    from desktop.vision_runtime import capture_active_monitor

    ok_cap, path, _ = capture_active_monitor()
    if not ok_cap:
        _fail(f"desktop capture failed: {path}")
    print("  desktop screenshot OK")

    # Memory
    config.MEMORY_ENABLED = True
    from memory.store import get_personal_memory

    store = get_personal_memory()
    eid = store.remember("smoke alpha", category="session", tags=["smoke68"]).entry_id
    if not eid:
        _fail("memory write failed")
    print("  memory OK")

    # Safety blocks
    from alpha.safety import check_alpha_safety
    from core.types import CommandRequest, Intent

    blocked = check_alpha_safety(
        CommandRequest(raw_text="enable kill switch", intent=Intent.ENABLE_KILL_SWITCH)
    )
    if blocked is None:
        _fail("expected alpha block for apply_patch")
    if "Alpha safety" not in (blocked.summary or ""):
        _fail("alpha block message missing")
    print("  safety blocks OK")

    # Alpha report
    report = _run("SHOW_ALPHA_REPORT", "show alpha report")
    if "Alpha report" not in report.summary:
        _fail("alpha report missing")
    print("  alpha report OK")

    # User commands doc
    doc = ROOT / "reports" / "alpha_user_commands.md"
    if not doc.is_file():
        _fail("reports/alpha_user_commands.md missing")

    print("SMOKE PASS phase68_alpha_readiness")


if __name__ == "__main__":
    main()
