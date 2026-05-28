"""Phase 61.1 smoke: truthful visible browser execution."""

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
    assert action is not None, f"missing action {intent.value}"
    return action.execute(CommandRequest(raw_text=text, intent=intent))


def main() -> None:
    # 1) test real visible browser
    test_res = _run("TEST_REAL_BROWSER", "test real browser")
    assert "REAL VISIBLE BROWSER" in test_res.summary, test_res.summary

    # 2) route url via open website preserving https
    open_url = _run("OPEN_WEBSITE", "open website https://www.nvidia.com")
    assert "https://www.nvidia.com" in open_url.summary.lower(), open_url.summary

    # 3) current page visibility
    page = _run("WHAT_TAB_IS_ACTIVE", "what page am i on")
    assert "url:" in page.summary.lower(), page.summary

    # 4) summarize current page routes to browser summarizer
    summ = _run("SUMMARIZE_THIS_PAGE", "summarize current page")
    assert "Summary for " in summ.summary, summ.summary

    from browser.runtime import get_browser_runtime_state

    st = get_browser_runtime_state()
    assert st.browser_process_alive is True
    assert st.browser_visible is True
    assert st.last_action_success is True

    print("SMOKE PASS phase611_real_browser_visible")


if __name__ == "__main__":
    main()

