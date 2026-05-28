"""Browser task planner for multi-step agent loop (Phase 62)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class BrowserTaskPlan:
    user_goal: str
    current_page: str
    needed_steps: tuple[str, ...]
    risks: tuple[str, ...]
    next_action: str
    success_criteria: tuple[str, ...]

    def format(self) -> str:
        lines = [
            "Browser task plan:",
            f"  user_goal: {self.user_goal or 'n/a'}",
            f"  current_page: {self.current_page or 'n/a'}",
            "  needed_steps:",
            *[f"    - {s}" for s in self.needed_steps],
            "  risks:",
            *[f"    - {r}" for r in self.risks],
            f"  next_action: {self.next_action}",
            "  success_criteria:",
            *[f"    - {s}" for s in self.success_criteria],
        ]
        return "\n".join(lines)


def plan_browser_task(*, goal: str, current_page: str, has_search_results: bool) -> BrowserTaskPlan:
    g = (goal or "").strip()
    steps = [
        "Open a visible browser session.",
        "Search for goal-relevant sources.",
        "Open the best visible non-ad result.",
        "Extract key facts and summarize.",
        "Save a research report with evidence links.",
    ]
    risks = [
        "Low-quality or sponsored results can mislead ranking.",
        "Stale pages may not match the latest facts.",
        "Risky actions (login/submit/buy/download/delete/send/credentials) require approval.",
    ]
    if has_search_results:
        next_action = "open the best result"
    elif g:
        next_action = f"find information about {g}"
    else:
        next_action = "search web for a concrete query"
    success = (
        "A visible page is opened for the target topic.",
        "Key facts are extracted from current page text/headings.",
        "A browser research report is written with URL/title/screenshot.",
    )
    return BrowserTaskPlan(
        user_goal=g or "general browser research",
        current_page=current_page or "n/a",
        needed_steps=tuple(steps),
        risks=tuple(risks),
        next_action=next_action,
        success_criteria=success,
    )

