"""Phase 49 autonomous operational healing actions."""

from __future__ import annotations

from actions.base import BaseAction
from core.results import result_confirmation_required, result_success
from core.types import CommandRequest, CommandResult, Intent
from runtime.healing_engine import (
    clear_stale_locks,
    phase49_status,
    recover_overlay,
    recover_voice_system,
    restart_dashboard,
    restart_failed_worker,
    restart_operator_console,
    restart_wake_listener,
    show_healing_actions,
    show_runtime_health,
    show_stuck_workers,
    validate_runtime_integrity,
)


class _ReadOnlyPhase49Action(BaseAction):
    intent: str
    _fn = None

    def execute(self, request: CommandRequest) -> CommandResult:
        del request
        body = self._fn()
        return result_success(Intent(self.intent), body, data={"read_only": True})


class _ConfirmHealingAction(BaseAction):
    intent: str
    _fn = None
    confirmation_id: str = ""

    def execute(self, request: CommandRequest) -> CommandResult:
        raw = (request.raw_text or "").lower()
        confirmed = bool(request.confirmed or "confirm" in raw)
        if not confirmed:
            return result_confirmation_required(
                Intent(self.intent),
                f"{self.intent.replace('_', ' ')} requires explicit confirmation.",
                confirmation_id=self.confirmation_id or self.intent,
            )
        body = self._fn(confirmed=True)
        return result_success(Intent(self.intent), body, data={"confirmed": True})


class ShowRuntimeHealthAction(_ReadOnlyPhase49Action):
    intent = Intent.SHOW_RUNTIME_HEALTH.value
    _fn = staticmethod(show_runtime_health)


class ShowHealingActionsAction(_ReadOnlyPhase49Action):
    intent = Intent.SHOW_HEALING_ACTIONS.value
    _fn = staticmethod(show_healing_actions)


class ShowStuckWorkersAction(_ReadOnlyPhase49Action):
    intent = Intent.SHOW_STUCK_WORKERS.value
    _fn = staticmethod(show_stuck_workers)


class ValidateRuntimeIntegrityAction(_ReadOnlyPhase49Action):
    intent = Intent.VALIDATE_RUNTIME_INTEGRITY.value
    _fn = staticmethod(validate_runtime_integrity)


class Phase49StatusAction(_ReadOnlyPhase49Action):
    intent = Intent.PHASE49_STATUS.value
    _fn = staticmethod(phase49_status)


class ClearStaleLocksAction(_ConfirmHealingAction):
    intent = Intent.CLEAR_STALE_LOCKS.value
    confirmation_id = "clear_stale_locks"
    _fn = staticmethod(clear_stale_locks)


class RecoverOverlayAction(_ConfirmHealingAction):
    intent = Intent.RECOVER_OVERLAY.value
    confirmation_id = "recover_overlay"
    _fn = staticmethod(recover_overlay)


class RecoverVoiceSystemAction(_ConfirmHealingAction):
    intent = Intent.RECOVER_VOICE_SYSTEM.value
    confirmation_id = "recover_voice_system"
    _fn = staticmethod(recover_voice_system)


class RestartDashboardAction(_ConfirmHealingAction):
    intent = Intent.RESTART_DASHBOARD.value
    confirmation_id = "restart_dashboard"
    _fn = staticmethod(restart_dashboard)


class RestartWakeListenerAction(_ConfirmHealingAction):
    intent = Intent.RESTART_WAKE_LISTENER.value
    confirmation_id = "restart_wake_listener"
    _fn = staticmethod(restart_wake_listener)


class RestartOperatorConsoleAction(_ConfirmHealingAction):
    intent = Intent.RESTART_OPERATOR_CONSOLE.value
    confirmation_id = "restart_operator_console"
    _fn = staticmethod(restart_operator_console)


class RestartFailedWorkerAction(BaseAction):
    intent = Intent.RESTART_FAILED_WORKER.value

    def execute(self, request: CommandRequest) -> CommandResult:
        raw = (request.raw_text or "").lower()
        confirmed = bool(request.confirmed or "confirm" in raw)
        worker = str(request.params.get("worker") or "")
        for token in raw.split():
            if token in {"overlay", "voice", "tts", "dashboard", "wake", "console", "operator_console", "wake_listener"}:
                worker = token
                break
        if not confirmed:
            return result_confirmation_required(
                Intent.RESTART_FAILED_WORKER,
                "Restart failed worker requires confirmation (e.g. restart failed worker overlay confirm).",
                confirmation_id="restart_failed_worker",
            )
        body = restart_failed_worker(worker, confirmed=True)
        return result_success(Intent.RESTART_FAILED_WORKER, body, data={"worker": worker, "confirmed": True})
