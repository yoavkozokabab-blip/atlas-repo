"""Phase 62 smoke: real browser agent loop."""

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
    open_res = _run("OPEN_BROWSER", "open browser")
    assert "BROWSER" in open_res.summary.upper(), open_res.summary

    search_res = _run("FIND_INFORMATION_ABOUT", "find information about Nvidia earnings summary")
    assert "Browser task plan" in search_res.summary, search_res.summary
    assert "query: Nvidia earnings summary" in search_res.summary, search_res.summary

    best_res = _run("OPEN_BEST_RESULT", "open the best result")
    assert ("http://" in best_res.summary.lower()) or ("https://" in best_res.summary.lower()), best_res.summary

    page_res = _run("SUMMARIZE_THIS_PAGE", "summarize current page")
    assert "Summary for " in page_res.summary, page_res.summary

    report_res = _run("SAVE_BROWSER_RESEARCH_REPORT", "save browser research report")
    assert "Saved browser research report:" in report_res.summary, report_res.summary

    print("SMOKE PASS phase62_browser_agent_loop")


if __name__ == "__main__":
    main()

