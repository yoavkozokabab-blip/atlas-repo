"""Phase 61.1 smoke: open website URL routing and browser truth."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _run(intent_name: str, text: str, params: dict | None = None):
    from actions.registry import ActionRegistry
    from core.types import CommandRequest, Intent

    reg = ActionRegistry()
    intent = getattr(Intent, intent_name)
    action = reg._actions.get(intent.value)
    assert action is not None, f"missing action {intent.value}"
    return action.execute(CommandRequest(raw_text=text, intent=intent, params=params or {}))


def main() -> None:
    _ = _run("OPEN_BROWSER", "open browser")
    open_site = _run("OPEN_WEBSITE", "open website https://www.nvidia.com", params={"url": "https://www.nvidia.com"})
    page = _run("WHAT_TAB_IS_ACTIVE", "what page am i on")
    summary = _run("SUMMARIZE_THIS_PAGE", "summarize current page")

    from browser.runtime import get_browser_runtime_state

    st = get_browser_runtime_state()
    assert "REAL VISIBLE BROWSER" in (open_site.summary + "\n" + summary.summary), open_site.summary
    assert "nvidia.com" in (st.current_url or "").lower(), st.current_url
    assert bool((st.active_tab_title or "").strip()), st.active_tab_title
    assert st.last_action_success is True
    assert "open_app" not in (open_site.summary or "").lower()
    assert "url:" in page.summary.lower()
    print("SMOKE PASS phase611_open_website")


if __name__ == "__main__":
    main()

