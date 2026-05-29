"""Phase 71 — dry-run action planner for bounded, read-only browser tasks.

``build_search_open_summarize_plan`` is the only plan shape this phase emits:
search → open the most relevant result → summarize what is visible.

Planning is pure: it constructs an :class:`ActionPlan` and never touches the
network or a browser.  Forbidden goals (payments/orders/bookings/etc.) are
rejected with :class:`ForbiddenGoalError` before any plan is produced.
"""

from __future__ import annotations

from tooluse.contracts import (
    ActionPlan,
    ForbiddenGoalError,
    PlanStep,
    RiskLevel,
    StepKind,
    scan_forbidden,
)


def build_search_open_summarize_plan(goal: str, *, query: str | None = None) -> ActionPlan:
    """
    Build the bounded plan: open session → search → open best result → summarize.

    Raises ForbiddenGoalError when the goal requests an irreversible action.
    """
    goal = (goal or "").strip()
    if not goal:
        raise ValueError("goal must be non-empty")

    forbidden = scan_forbidden(goal)
    if forbidden is not None:
        raise ForbiddenGoalError(
            f"Goal rejected — contains forbidden action '{forbidden}'. "
            "Phase 71 is read-only: no payments, orders, bookings, submits, "
            "logins, downloads, deletes, or sends."
        )

    search_query = (query or goal).strip()

    steps = (
        PlanStep(
            index=1,
            kind=StepKind.OPEN_SESSION,
            description="Launch a real, isolated browser session.",
            risk=RiskLevel.EXTERNAL,
            requires_approval=True,
            success_criteria=("A real browser provider is connected.",),
        ),
        PlanStep(
            index=2,
            kind=StepKind.SEARCH,
            description=f"Search the web for: {search_query}",
            risk=RiskLevel.EXTERNAL,
            requires_approval=True,
            target=search_query,
            success_criteria=(
                "At least one organic result link is extracted.",
                "The search engine results page is loaded.",
            ),
        ),
        PlanStep(
            index=3,
            kind=StepKind.OPEN_RESULT,
            description="Open the most relevant non-ad result.",
            risk=RiskLevel.EXTERNAL,
            requires_approval=True,
            success_criteria=(
                "The browser navigates away from the search engine host.",
                "The opened page has a non-empty title.",
            ),
        ),
        PlanStep(
            index=4,
            kind=StepKind.SUMMARIZE,
            description="Summarize the visible content of the opened page.",
            risk=RiskLevel.READ_ONLY,         # reads already-loaded page; no fetch
            requires_approval=False,
            success_criteria=("Non-trivial visible text is summarized.",),
        ),
    )
    return ActionPlan(goal=goal, steps=steps)
