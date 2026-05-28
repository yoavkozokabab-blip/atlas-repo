"""Phase 37b — merge suggestions and optional continuation into CommandResult."""

from __future__ import annotations

from typing import Any

import config
from conversation.suggestion_engine import (
    build_continuation_prompt,
    build_suggestions,
)
from core.types import ActionStatus, CommandRequest, CommandResult, Intent


def enhance_command_result(
    request: CommandRequest,
    result: CommandResult,
    log_meta: dict[str, Any] | None = None,
) -> CommandResult:
    """
    Post-router envelope: suggestions + optional continuation line.
    Does not change intent, status, or execute anything.
    """
    del log_meta
    if not config.CONVERSATION_ENABLED:
        return result
    if not isinstance(result, CommandResult):
        return result
    if result.intent in (Intent.UNKNOWN, Intent.CLARIFY):
        return result
    if result.status != ActionStatus.SUCCESS:
        return result

    try:
        suggestions = build_suggestions(request, result)
        continuation = build_continuation_prompt(request, result, suggestions)

        summary = result.summary
        if continuation and continuation not in summary:
            summary = f"{summary.rstrip()}\n\n{continuation}"

        data = dict(result.data or {})
        data["conversation_enhanced"] = True
        data["continuation_offered"] = bool(continuation)
        if continuation:
            data["continuation_prompt"] = continuation[:200]

        return result.model_copy(
            update={
                "summary": summary,
                "next_suggestions": suggestions,
                "data": data,
            }
        )
    except Exception:
        return result
