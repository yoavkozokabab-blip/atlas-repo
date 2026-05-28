"""Helpers for building structured CommandResult objects."""

from __future__ import annotations

from typing import Any

from core.types import ActionStatus, CommandResult, Intent


def result_success(
    intent: Intent,
    summary: str,
    *,
    data: dict[str, Any] | None = None,
    next_suggestions: list[str] | None = None,
) -> CommandResult:
    return CommandResult(
        intent=intent,
        status=ActionStatus.SUCCESS,
        summary=summary,
        data=data or {},
        next_suggestions=next_suggestions or [],
    )


def result_failed(
    intent: Intent,
    summary: str,
    *,
    error: str | None = None,
    data: dict[str, Any] | None = None,
    next_suggestions: list[str] | None = None,
) -> CommandResult:
    return CommandResult(
        intent=intent,
        status=ActionStatus.FAILED,
        summary=summary,
        error=error or summary,
        data=data or {},
        next_suggestions=next_suggestions or [],
    )


def result_clarification(
    intent: Intent,
    summary: str,
    *,
    next_suggestions: list[str] | None = None,
) -> CommandResult:
    return CommandResult(
        intent=intent,
        status=ActionStatus.CLARIFICATION_NEEDED,
        summary=summary,
        next_suggestions=next_suggestions
        or ["Try rephrasing with more detail.", "Type help for examples."],
    )


def result_confirmation_required(
    intent: Intent,
    summary: str,
    confirmation_id: str,
    *,
    next_suggestions: list[str] | None = None,
) -> CommandResult:
    return CommandResult(
        intent=intent,
        status=ActionStatus.CONFIRMATION_REQUIRED,
        summary=summary,
        requires_confirmation=True,
        confirmation_id=confirmation_id,
        next_suggestions=next_suggestions
        or ["Reply yes / confirm / כן to proceed.", "Reply no / cancel / לא to abort."],
    )


def result_blocked(intent: Intent, summary: str, *, error: str | None = None) -> CommandResult:
    return CommandResult(
        intent=intent,
        status=ActionStatus.BLOCKED,
        summary=summary,
        error=error or summary,
    )


def result_not_implemented(intent: Intent, summary: str) -> CommandResult:
    return CommandResult(
        intent=intent,
        status=ActionStatus.NOT_IMPLEMENTED,
        summary=summary,
    )
