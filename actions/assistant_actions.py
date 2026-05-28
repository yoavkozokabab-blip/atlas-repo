"""Phase 40c — assistant explain/plan actions."""

from __future__ import annotations

from actions.base import BaseAction
from config import ASSISTANT_MODE_ENABLED
from core.results import result_failed, result_success
from core.types import CommandRequest, CommandResult, Intent
from assistant.explain_rules import build_explain_report
from assistant.plan_rules import build_plan_report


class AssistantExplainAction(BaseAction):
    intent = Intent.ASSISTANT_EXPLAIN.value

    def execute(self, request: CommandRequest) -> CommandResult:
        if not ASSISTANT_MODE_ENABLED:
            return result_failed(
                Intent.ASSISTANT_EXPLAIN,
                "Assistant mode disabled. Set ASSISTANT_MODE_ENABLED=true.",
            )
        topic = str(request.params.get("topic") or request.raw_text or "")
        text = build_explain_report(focus="general", topic=topic)
        return result_success(
            Intent.ASSISTANT_EXPLAIN,
            text,
            next_suggestions=["suggest next steps", "make a plan", "run diagnostics"],
        )


class AssistantPlanAction(BaseAction):
    intent = Intent.ASSISTANT_PLAN.value

    def execute(self, request: CommandRequest) -> CommandResult:
        if not ASSISTANT_MODE_ENABLED:
            return result_failed(
                Intent.ASSISTANT_PLAN,
                "Assistant mode disabled. Set ASSISTANT_MODE_ENABLED=true.",
            )
        goal = str(request.params.get("goal") or request.raw_text or "")
        text = build_plan_report(goal)
        return result_success(
            Intent.ASSISTANT_PLAN,
            text,
            next_suggestions=["what am i doing", "start task", "run diagnostics"],
        )
