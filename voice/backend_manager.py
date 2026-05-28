"""TTS backend manager — provider selection, failover, interruptibility (Phase 56/57)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from core.logger import setup_logger

logger = setup_logger("jarvis.voice.backend_manager")


@dataclass(frozen=True)
class BackendChoice:
    provider: str
    streaming: bool
    interruptible: bool
    latency_class: str
    reason: str = ""
    fallback_only: bool = False

    @property
    def supports_interruptions(self) -> bool:
        return self.interruptible


_SUPPORTED = (
    "realtime",
    "openai_realtime",
    "elevenlabs",
    "piper",
    "edge_tts",
    "xtts",
    "pyttsx3_fallback",
    "pyttsx3",
    "pyttsx3_direct",
    "subprocess_pyttsx3",
    "azure",
)


def primary_backend_name() -> str:
    try:
        import config as cfg

        return (getattr(cfg, "TTS_PRIMARY_BACKEND", "") or "realtime").strip().lower()
    except Exception:
        return "realtime"


def fallback_backend_name() -> str:
    try:
        import config as cfg

        return (getattr(cfg, "TTS_FALLBACK_BACKEND", "") or "pyttsx3_direct").strip().lower()
    except Exception:
        return "pyttsx3_direct"


def list_supported_backends() -> tuple[str, ...]:
    return _SUPPORTED


def choose_backend(*, prefer_low_latency: bool = True, require_interruptible: bool = True) -> BackendChoice:
    import config as cfg

    try:
        from voice.realtime_tts import is_realtime_tts_enabled, pyttsx3_fallback_only
        from voice.tts_backend import prefer_direct_pyttsx3, get_verified_normal_speech_backend
        from voice.tts_playback_trace import is_tts_safe_mode, must_use_direct_pyttsx3

        if is_tts_safe_mode() or must_use_direct_pyttsx3() or prefer_direct_pyttsx3():
            verified = get_verified_normal_speech_backend() or fallback_backend_name()
            return BackendChoice(
                provider=verified,
                streaming=False,
                interruptible=True,
                latency_class="medium",
                reason="verified_direct_or_safe_mode",
                fallback_only=False,
            )

        if primary_backend_name() == "realtime" and is_realtime_tts_enabled():
            from voice.providers.registry import select_provider

            provider = select_provider(
                prefer=(getattr(cfg, "REALTIME_TTS_PREFERRED", "") or "").strip()
            )
            if provider is not None and not provider.fallback_only:
                return BackendChoice(
                    provider=provider.name,
                    streaming=True,
                    interruptible=require_interruptible,
                    latency_class=provider.health().latency_class,
                    reason="realtime_provider_selected",
                    fallback_only=False,
                )
            if pyttsx3_fallback_only():
                return BackendChoice(
                    provider="pyttsx3_fallback",
                    streaming=False,
                    interruptible=True,
                    latency_class="high",
                    reason="realtime_failover_exhausted",
                    fallback_only=True,
                )
    except Exception:
        pass

    configured = (getattr(cfg, "TTS_FORCE_ENGINE", "") or getattr(cfg, "TTS_ENGINE", "") or "edge_tts").lower()
    if configured in {"elevenlabs", "openai", "openai_realtime", "azure"}:
        return BackendChoice(
            provider=configured,
            streaming=True,
            interruptible=True,
            latency_class="low" if prefer_low_latency else "medium",
            reason="configured_cloud_voice",
        )

    if getattr(cfg, "TTS_STREAMING_ENABLED", True) and configured == "edge_tts":
        return BackendChoice(
            provider="edge_tts",
            streaming=True,
            interruptible=True,
            latency_class="low",
            reason="streaming_edge_default",
        )

    return BackendChoice(
        provider="pyttsx3_fallback",
        streaming=False,
        interruptible=True,
        latency_class="high",
        reason="emergency_local_fallback",
        fallback_only=True,
    )


def health_check() -> dict[str, Any]:
    choice = choose_backend()
    try:
        from voice.providers.registry import get_provider_health

        providers = [
            {
                "name": item.name,
                "available": item.available,
                "fallback_only": item.fallback_only,
                "latency_class": item.latency_class,
                "reason": item.reason,
            }
            for item in get_provider_health()
        ]
    except Exception as exc:
        providers = [{"error": str(exc)}]
    return {
        "primary_backend": primary_backend_name(),
        "fallback_backend": fallback_backend_name(),
        "selected": choice.provider,
        "streaming": choice.streaming,
        "supports_interruptions": choice.supports_interruptions,
        "providers": providers,
    }


def latency_metrics() -> str:
    from voice.voice_latency_metrics import format_voice_latency_status

    return format_voice_latency_status()


def cancel() -> bool:
    from voice.interruption_manager import cancel as interruption_cancel

    return interruption_cancel()


def speak_stream(text: str, *, backend: BackendChoice | None = None, preferred_provider: str = "") -> str:
    """Stream speech via realtime providers first; pyttsx3 only after failover."""
    choice = backend or choose_backend()
    safe = (text or "").strip()
    if not safe:
        return ""

    from voice.realtime_tts import is_realtime_tts_enabled, pyttsx3_fallback_only, speak_realtime

    if choice.fallback_only and choice.provider in {"pyttsx3_fallback", "pyttsx3", "pyttsx3_direct"}:
        if not pyttsx3_fallback_only():
            logger.warning("pyttsx3 requested but not in fallback-only mode")
        return speak_with_backend(text, backend=choice, preferred_provider="pyttsx3_fallback")

    if is_realtime_tts_enabled() and primary_backend_name() == "realtime":
        return speak_realtime(safe, preferred_provider=preferred_provider or choice.provider)

    return speak_with_backend(text, backend=choice, preferred_provider=preferred_provider)


def speak_with_backend(
    text: str,
    *,
    backend: BackendChoice | None = None,
    preferred_provider: str = "",
) -> str:
    choice = backend or choose_backend()
    safe = (text or "").strip()
    if not safe:
        return ""
    try:
        from voice.interruption_manager import on_jarvis_speech_finished, on_jarvis_speech_started
        from voice.realtime_tts import is_realtime_tts_enabled, pyttsx3_fallback_only, speak_realtime
        from voice.streaming_player import is_stop_requested

        on_jarvis_speech_started(safe)
        if choice.provider in {"pyttsx3_direct", "direct_pyttsx3"}:
            if pyttsx3_fallback_only() and is_realtime_tts_enabled():
                provider = speak_realtime(safe, preferred_provider="pyttsx3_fallback")
            else:
                from voice.tts_pyttsx3 import NORMAL_DIRECT_SPEAKER

                NORMAL_DIRECT_SPEAKER(safe, rate_raw="", record_user_success=False)
                provider = choice.provider
        elif choice.fallback_only or choice.provider in {"pyttsx3_fallback", "pyttsx3"}:
            provider = speak_realtime(safe, preferred_provider=preferred_provider or "pyttsx3_fallback")
        elif is_realtime_tts_enabled():
            provider = speak_realtime(
                safe,
                preferred_provider=preferred_provider or choice.provider,
            )
        else:
            from voice.speech_controller import speak_text

            provider = speak_text(safe) or choice.provider
        on_jarvis_speech_finished(interrupted=is_stop_requested())
        return provider
    except Exception as exc:
        logger.warning("speak_with_backend failed (%s): %s", choice.provider, exc)
        try:
            from voice.interruption_manager import on_jarvis_speech_finished

            on_jarvis_speech_finished(interrupted=True)
        except Exception:
            pass
        raise


def show_backend_status() -> str:
    from voice.providers.provider_health import show_realtime_provider_status

    choice = choose_backend()
    health = health_check()
    lines = [
        "Voice backend manager (Phase 57):",
        f"  primary backend: {health['primary_backend']}",
        f"  fallback backend: {health['fallback_backend']}",
        f"  selected: {choice.provider}",
        f"  streaming: {'yes' if choice.streaming else 'no'}",
        f"  interruptible: {'yes' if choice.interruptible else 'no'}",
        f"  latency class: {choice.latency_class}",
        f"  fallback only: {'yes' if choice.fallback_only else 'no'}",
        f"  reason: {choice.reason}",
        "  provider health:",
    ]
    for item in health.get("providers", []):
        if "error" in item:
            lines.append(f"    - error: {item['error']}")
            continue
        lines.append(
            f"    - {item['name']}: {'ok' if item['available'] else 'missing'} "
            f"fallback_only={item['fallback_only']}"
        )
    lines.append("")
    lines.append(show_realtime_provider_status())
    return "\n".join(lines)
