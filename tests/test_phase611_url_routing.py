from __future__ import annotations

from core.types import CommandRequest, Intent


def test_https_preserved_and_open_website_intent() -> None:
    from brain.intent_classifier import classify_rules
    from brain.command_parser import enrich_request

    req = classify_rules("open website https://www.nvidia.com")
    assert req.intent == Intent.OPEN_WEBSITE
    req2 = enrich_request(req)
    assert req2.params.get("url") == "https://www.nvidia.com"


def test_open_app_rejects_urls() -> None:
    from actions.app_actions import OpenAppAction

    action = OpenAppAction()
    res = action.execute(
        CommandRequest(
            raw_text="open app https://www.nvidia.com",
            intent=Intent.OPEN_APP,
            params={"app": "https://www.nvidia.com"},
        )
    )
    assert "detected_url_not_app" in res.summary


def test_browser_navigation_truth_success() -> None:
    from browser.runtime import get_browser_runtime_state, navigate_to_url

    body = navigate_to_url("https://example.com")
    st = get_browser_runtime_state()
    assert st.browser_process_alive is True
    assert bool((st.active_tab_title or "").strip())
    assert "example.com" in (st.current_url or "").lower()
    assert st.last_action_success is True
    assert body

