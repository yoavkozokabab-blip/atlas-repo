"""Phase 65 smoke: product hardening across all tracks."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _run(intent_name: str, text: str):
    from actions.registry import ActionRegistry
    from core.types import CommandRequest, Intent

    reg = ActionRegistry()
    intent = getattr(Intent, intent_name)
    action = reg._actions.get(intent.value)
    assert action is not None, f"missing {intent.value}"
    return action.execute(CommandRequest(raw_text=text, intent=intent))


def main() -> None:
    import config as cfg

    cfg.SCREEN_UNDERSTANDING_ENABLED = True
    cfg.MEMORY_ENABLED = True

    voice = _run("SHOW_VOICE_HEALTH", "show voice health")
    assert "Voice health" in voice.summary

    memory = _run("REPAIR_MEMORY_STORE", "repair memory store")
    assert "repair complete" in memory.summary.lower()

    browser = _run("SHOW_BROWSER_HEALTH", "show browser health")
    assert "Browser health" in browser.summary

    desktop = _run("SHOW_DESKTOP_OPERATOR_HEALTH", "show desktop operator health")
    assert "Desktop operator health" in desktop.summary

    system = _run("SHOW_SYSTEM_HEALTH", "show system health")
    assert "runtime_health_score" in system.summary

    perf = _run("SHOW_PERFORMANCE_REPORT", "show performance report")
    assert "startup_ms" in perf.summary

    inbox = _run("SUMMARIZE_MY_INBOX", "summarize my inbox")
    assert "MOCK MODE" in inbox.summary

    from reliability.product_readiness import generate_product_readiness_report

    report = generate_product_readiness_report()
    assert "Product Readiness Report" in report

    print("SMOKE PASS phase65_product_hardening")


if __name__ == "__main__":
    main()
