"""Phase 59 human conversational runtime actions."""

from __future__ import annotations

from actions.base import BaseAction
from conversation.conversation_metrics import (
    benchmark_full_duplex_conversation,
    show_interruption_metrics,
)
from conversation.human_runtime import phase59_status, show_conversation_runtime
from conversation.memory_runtime import show_conversational_memory
from core.results import result_success
from core.types import CommandRequest, CommandResult, Intent


class _ReadOnlyPhase59Action(BaseAction):
    intent: str
    _fn = None

    def execute(self, request: CommandRequest) -> CommandResult:
        del request
        body = self._fn()
        return result_success(Intent(self.intent), body, data={"read_only": True})


class ShowConversationRuntimeAction(_ReadOnlyPhase59Action):
    intent = Intent.SHOW_CONVERSATION_RUNTIME.value
    _fn = staticmethod(show_conversation_runtime)


class ShowInterruptionMetricsAction(_ReadOnlyPhase59Action):
    intent = Intent.SHOW_INTERRUPTION_METRICS.value
    _fn = staticmethod(show_interruption_metrics)


class ShowConversationalMemoryAction(_ReadOnlyPhase59Action):
    intent = Intent.SHOW_CONVERSATIONAL_MEMORY.value
    _fn = staticmethod(show_conversational_memory)


class BenchmarkFullDuplexConversationAction(_ReadOnlyPhase59Action):
    intent = Intent.BENCHMARK_FULL_DUPLEX_CONVERSATION.value
    _fn = staticmethod(benchmark_full_duplex_conversation)


class Phase59StatusAction(_ReadOnlyPhase59Action):
    intent = Intent.PHASE59_STATUS.value
    _fn = staticmethod(phase59_status)
