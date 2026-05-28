"""Read-only JARVIS marketing website product audit actions."""

from __future__ import annotations

from actions.base import BaseAction
from core.results import result_success
from core.types import CommandRequest, CommandResult, Intent
from website_audit.inspector import inspect_website_project


class InspectWebsiteProjectAction(BaseAction):
    intent = Intent.INSPECT_WEBSITE_PROJECT.value

    def execute(self, request: CommandRequest) -> CommandResult:
        del request
        body = inspect_website_project()
        return result_success(
            Intent.INSPECT_WEBSITE_PROJECT,
            body,
            data={"read_only": True, "audit_only": True},
        )
