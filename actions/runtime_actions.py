"""Runtime feature flags (voice, TTS, wake word, overlay)."""

from __future__ import annotations

import config

from actions.base import BaseAction
from core.results import result_success
from core.runtime_state import get_runtime_state
from core.types import CommandRequest, CommandResult, Intent


class ShowRuntimeStatusAction(BaseAction):
    intent = Intent.SHOW_RUNTIME_STATUS.value

    def execute(self, request: CommandRequest) -> CommandResult:
        del request
        rt = get_runtime_state()
        try:
            from services.runtime_monitor import get_runtime_monitor

            stability = get_runtime_monitor().status_snapshot()
        except Exception:
            stability = {}
        try:
            from core.event_bus import get_event_bus

            event_bus = get_event_bus().stats()
        except Exception:
            event_bus = {}
        try:
            from services.high_performance_runtime import get_high_performance_runtime

            performance = get_high_performance_runtime().status()
        except Exception:
            performance = {}
        try:
            from services.observability import get_observability

            observability = get_observability().snapshot()
        except Exception:
            observability = {}
        lines = [
            "JARVIS runtime status",
            "",
            "Config (.env):",
            f"  VOICE_ENABLED={config.VOICE_ENABLED}",
            f"  TTS_ENABLED={config.TTS_ENABLED}",
            f"  WAKE_WORD_ENABLED={config.WAKE_WORD_ENABLED}",
            f"  OVERLAY_ENABLED={config.OVERLAY_ENABLED}",
            f"  OVERLAY_STYLE={config.OVERLAY_STYLE}",
            f"  WAKE_GREETING_ENABLED={config.WAKE_GREETING_ENABLED}",
            f"  JARVIS_USER_NAME={config.JARVIS_USER_NAME}",
            f"  STT_LANGUAGE={config.STT_LANGUAGE}",
            f"  STT_MODEL={config.STT_MODEL}",
            f"  STT_ENABLE_NORMALIZATION={config.STT_ENABLE_NORMALIZATION}",
            "",
            "Active session:",
            f"  voice={rt.voice_enabled}",
            f"  speak (TTS)={rt.speak_enabled}",
            f"  wake_word={rt.wake_word_enabled}",
            f"  overlay={rt.overlay_enabled}",
            f"  tray={rt.tray_enabled}",
            f"  running={rt.running}",
            "",
            "Stability:",
            f"  runtime_monitor={stability.get('overall', 'unknown')}",
            f"  event_bus_queue={event_bus.get('queue', {}).get('size', 'n/a')}",
            f"  event_bus_dropped={event_bus.get('queue', {}).get('dropped', 'n/a')}",
            f"  traces_recorded={len(observability.get('traces', []))}",
            f"  failures_tracked={len(observability.get('failures', {}))}",
            f"  overlay_fps={observability.get('overlay', {}).get('fps', 'n/a')}",
        ]
        accel = performance.get("acceleration") or {}
        if accel:
            lines.append(f"  workload_device={accel.get('preferred_device')}")
            lines.append(f"  gpu_enabled={accel.get('gpu_enabled')}")
            lines.append(f"  workload_batch_size={accel.get('batch_size')}")
        workers = performance.get("workers") or {}
        if workers:
            lines.append(f"  background_workers={workers.get('alive_workers')}")
            lines.append(f"  background_queue={workers.get('queue_size')}")
        memory = stability.get("memory") or {}
        if memory:
            lines.append(f"  rss_mb={memory.get('rss_mb')}")
            lines.append(f"  memory_growth_mb={memory.get('growth_mb')}")
        issues = stability.get("issues") or []
        if issues:
            lines.append("  issues:")
            for issue in issues[:5]:
                msg = issue.get("message") if isinstance(issue, dict) else str(issue)
                lines.append(f"    - {msg}")
        if rt.wake_word_last_error:
            lines.append(f"  wake_word_last_error={rt.wake_word_last_error}")
        summary = "\n".join(lines)
        return result_success(
            Intent.SHOW_RUNTIME_STATUS,
            summary,
            data={
                "config": {
                    "voice_enabled": config.VOICE_ENABLED,
                    "tts_enabled": config.TTS_ENABLED,
                    "wake_word_enabled": config.WAKE_WORD_ENABLED,
                    "overlay_enabled": config.OVERLAY_ENABLED,
                    "overlay_style": config.OVERLAY_STYLE,
                    "stt_language": config.STT_LANGUAGE,
                    "stt_model": config.STT_MODEL,
                },
                "runtime": {
                    "voice_enabled": rt.voice_enabled,
                    "speak_enabled": rt.speak_enabled,
                    "wake_word_enabled": rt.wake_word_enabled,
                    "overlay_enabled": rt.overlay_enabled,
                },
                "stability": stability,
                "event_bus": event_bus,
                "performance": performance,
                "observability": observability,
            },
        )
