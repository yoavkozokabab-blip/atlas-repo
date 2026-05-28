"""STT status and benchmark (read-only diagnostics)."""

from __future__ import annotations

from actions.base import BaseAction
from core.results import result_success
from core.types import CommandRequest, CommandResult, Intent
from voice.stt_benchmark import run_stt_benchmark
from voice.transcriber import format_stt_status, get_stt_status


class ShowSttStatusAction(BaseAction):
    intent = Intent.SHOW_STT_STATUS.value

    def execute(self, request: CommandRequest) -> CommandResult:
        del request
        status = get_stt_status()
        summary = format_stt_status(status)
        return result_success(
            Intent.SHOW_STT_STATUS,
            summary,
            data={
                "engine": status.engine,
                "backend": status.backend,
                "model": status.model,
                "language": status.language,
                "device": status.device,
                "acceleration": status.acceleration,
                "compute_type": status.compute_type,
                "normalization_enabled": status.normalization_enabled,
                "model_loaded": status.model_loaded,
            },
        )


class BenchmarkSttAction(BaseAction):
    intent = Intent.BENCHMARK_STT.value

    def execute(self, request: CommandRequest) -> CommandResult:
        del request
        summary = run_stt_benchmark()
        return result_success(Intent.BENCHMARK_STT, summary)
