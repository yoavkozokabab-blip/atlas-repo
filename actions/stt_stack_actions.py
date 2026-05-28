"""Phase 42 STT stack diagnostics actions."""

from __future__ import annotations

from actions.base import BaseAction
from core.results import result_success
from core.types import CommandRequest, CommandResult, Intent
from voice.stt_engines.registry import list_available_stt_engines, list_registered_stt_engines
from voice.transcriber import format_stt_status, get_stt_status


class ListSttEnginesAction(BaseAction):
    intent = Intent.LIST_STT_ENGINES.value

    def execute(self, request: CommandRequest) -> CommandResult:
        del request
        lines = ["STT engines (Phase 42)"]
        for name in list_registered_stt_engines():
            lines.append(f"  - {name}")
        lines.append("")
        lines.append("Availability:")
        for name, status in list_available_stt_engines():
            lines.append(f"  {name}: {status}")
        return result_success(Intent.LIST_STT_ENGINES, "\n".join(lines))


class ShowSttStackStatusAction(BaseAction):
    intent = Intent.SHOW_STT_STACK_STATUS.value

    def execute(self, request: CommandRequest) -> CommandResult:
        del request
        from config import (
            STT_AUTO_LANGUAGE_DETECT,
            STT_ECHO_CANCELLATION_ENABLED,
            STT_ENGINE_CHAIN,
            STT_FUSION_ENABLED,
            STT_INTENT_CORRECTION_ENABLED,
            STT_NOISE_SUPPRESSION_ENABLED,
            STT_PARTIAL_STREAMING_ENABLED,
            STT_RETRY_MAX_ATTEMPTS,
            STT_STACK_ENABLED,
            STT_TRANSCRIPT_REPAIR_ENABLED,
            STT_VOICE_FINGERPRINT_ENABLED,
        )
        from voice.stt_stack.voice_fingerprint import load_fingerprint

        status = get_stt_status()
        fp = load_fingerprint()
        lines = [
            format_stt_status(status),
            "",
            "STT stack (Phase 42)",
            f"  Stack enabled: {STT_STACK_ENABLED}",
            f"  Engine chain: {STT_ENGINE_CHAIN}",
            f"  Fusion: {STT_FUSION_ENABLED}",
            f"  Partial streaming: {STT_PARTIAL_STREAMING_ENABLED}",
            f"  Intent correction: {STT_INTENT_CORRECTION_ENABLED}",
            f"  Transcript repair: {STT_TRANSCRIPT_REPAIR_ENABLED}",
            f"  Voice fingerprint: {STT_VOICE_FINGERPRINT_ENABLED}",
            f"  Noise suppression: {STT_NOISE_SUPPRESSION_ENABLED}",
            f"  Echo cancellation: {STT_ECHO_CANCELLATION_ENABLED}",
            f"  Auto language detect: {STT_AUTO_LANGUAGE_DETECT}",
            f"  Retry max attempts: {STT_RETRY_MAX_ATTEMPTS}",
            f"  Fingerprint samples: {fp.sample_count}",
            f"  Grammar min score (adapted): {fp.grammar_min_score}",
        ]
        return result_success(
            Intent.SHOW_STT_STACK_STATUS,
            "\n".join(lines),
            data={"stack_enabled": STT_STACK_ENABLED},
        )
