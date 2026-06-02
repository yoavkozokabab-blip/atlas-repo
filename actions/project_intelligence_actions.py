"""Read-only Project Intelligence action — delegates to project_intelligence engine."""

from __future__ import annotations

from actions.base import BaseAction
from core.logger import setup_logger
from core.types import CommandRequest, CommandResult, Intent
from project_intelligence.engine import answer_question

logger = setup_logger("jarvis.actions.project_intelligence")


class AnswerProjectQuestionAction(BaseAction):
    """Read-only project intelligence for free-form builder questions about JARVIS."""

    intent = Intent.ANSWER_PROJECT_QUESTION.value

    def execute(self, request: CommandRequest) -> CommandResult:
        question = (
            request.params.get("query")
            or request.params.get("question")
            or request.raw_text
        ).strip()

        if not question:
            from core.results import result_failed

            return result_failed(
                Intent.ANSWER_PROJECT_QUESTION,
                "No question provided. Ask something like: 'Why was Phase 73A built?'",
            )

        logger.info("project_intelligence question=%r", question[:120])
        return answer_question(question)
