"""Phase 33 — approval inbox actions."""

from __future__ import annotations

import re
import time

from actions.base import BaseAction
from approvals.inbox import (
    clear_inbox,
    format_approvals_report,
    get_pending_item,
    list_approval_items,
    update_item_status,
)
from brain.command_parser import enrich_request
from core import confirmation
from core.results import result_failed, result_success
from core.types import CommandRequest, CommandResult, Intent


def _item_id_from_request(request: CommandRequest) -> str | None:
    item_id = (request.params.get("item_id") or request.params.get("id") or "").strip()
    if item_id:
        return item_id
    raw = (request.raw_text or "").strip()
    for prefix in (
        r"^approve pending action\s+",
        r"^reject pending action\s+",
    ):
        m = re.sub(prefix, "", raw, flags=re.I).strip()
        if m and m != raw:
            return m
    return None


class ShowApprovalsAction(BaseAction):
    intent = Intent.SHOW_APPROVALS.value

    def execute(self, request: CommandRequest) -> CommandResult:
        del request
        items = list_approval_items()
        return result_success(
            Intent.SHOW_APPROVALS,
            format_approvals_report(items),
            data={"count": len(items), "pending": sum(1 for i in items if i.status == "pending")},
        )


class ApprovePendingActionAction(BaseAction):
    intent = Intent.APPROVE_PENDING_ACTION.value

    def __init__(self, registry=None) -> None:
        self._registry = registry

    def _registry_or_default(self):
        if self._registry is not None:
            return self._registry
        from actions.registry import ActionRegistry

        return ActionRegistry()

    def execute(self, request: CommandRequest) -> CommandResult:
        item = get_pending_item(_item_id_from_request(request))
        if item is None:
            return result_failed(
                Intent.APPROVE_PENDING_ACTION,
                "No pending approval in inbox.",
            )

        from brain.router import CommandRouter

        cmd = CommandRequest(
            raw_text=item.safe_payload.get("raw_text", item.intent),
            intent=Intent(item.intent),
            confidence=1.0,
            params=dict(item.safe_payload.get("params") or {}),
            confirmed=True,
            confirmation_id=item.confirmation_id,
        )
        cmd = enrich_request(cmd)

        registry = self._registry_or_default()
        router = CommandRouter(registry=registry)
        started = time.perf_counter()
        result = router._process(cmd, skip_confirmation=True)
        router._finalize(result, cmd, started, log_meta={"input_mode": "approval_inbox"})

        confirmation.cancel(item.confirmation_id)
        update_item_status(item.item_id, "completed")
        return result


class RejectPendingActionAction(BaseAction):
    intent = Intent.REJECT_PENDING_ACTION.value

    def execute(self, request: CommandRequest) -> CommandResult:
        item = get_pending_item(_item_id_from_request(request))
        if item is None:
            return result_failed(
                Intent.REJECT_PENDING_ACTION,
                "No pending approval to reject.",
            )
        confirmation.cancel(item.confirmation_id)
        update_item_status(item.item_id, "rejected")
        return result_success(
            Intent.REJECT_PENDING_ACTION,
            f"Rejected approval {item.item_id} ({item.intent}). Action was not executed.",
        )


class ClearApprovalsAction(BaseAction):
    intent = Intent.CLEAR_APPROVALS.value

    def execute(self, request: CommandRequest) -> CommandResult:
        del request
        removed, kept = clear_inbox()
        return result_success(
            Intent.CLEAR_APPROVALS,
            f"Cleared {removed} item(s). {kept} active/pending item(s) retained.",
        )
