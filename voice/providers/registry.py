"""Realtime provider registry with automatic failover (Phase 57)."""

from __future__ import annotations

from core.logger import setup_logger
from voice.providers.base import ProviderHealth, RealtimeTtsProvider, SpeechProsody
from voice.providers.elevenlabs_streaming import ElevenLabsStreamingProvider
from voice.providers.openai_realtime_tts import OpenAIRealtimeTtsProvider
from voice.providers.piper_local import PiperLocalProvider
from voice.providers.pyttsx3_fallback import Pyttsx3FallbackProvider

logger = setup_logger("jarvis.voice.providers.registry")

_PROVIDERS: dict[str, RealtimeTtsProvider] = {
    "openai_realtime": OpenAIRealtimeTtsProvider(),
    "openai": OpenAIRealtimeTtsProvider(),
    "elevenlabs": ElevenLabsStreamingProvider(),
    "piper": PiperLocalProvider(),
    "pyttsx3_fallback": Pyttsx3FallbackProvider(),
    "pyttsx3": Pyttsx3FallbackProvider(),
}


def _default_order() -> tuple[str, ...]:
    try:
        import config as cfg

        raw = (getattr(cfg, "REALTIME_TTS_PROVIDER_ORDER", "") or "").strip()
        if raw:
            return tuple(p.strip().lower() for p in raw.split(",") if p.strip())
    except Exception:
        pass
    return ("openai_realtime", "elevenlabs", "piper", "pyttsx3_fallback")


def get_provider(name: str) -> RealtimeTtsProvider | None:
    return _PROVIDERS.get((name or "").strip().lower())


def get_provider_chain() -> tuple[RealtimeTtsProvider, ...]:
    out: list[RealtimeTtsProvider] = []
    seen: set[str] = set()
    for name in _default_order():
        provider = get_provider(name)
        if provider is None or provider.name in seen:
            continue
        seen.add(provider.name)
        out.append(provider)
    if not out:
        out.append(Pyttsx3FallbackProvider())
    return tuple(out)


def get_provider_health() -> list[ProviderHealth]:
    return [provider.health() for provider in get_provider_chain()]


def select_provider(*, prefer: str = "") -> RealtimeTtsProvider | None:
    if prefer:
        provider = get_provider(prefer)
        if provider is not None and provider.is_available() and not provider.fallback_only:
            return provider
    for provider in get_provider_chain():
        if provider.fallback_only:
            continue
        if provider.is_available():
            return provider
    for provider in get_provider_chain():
        if provider.is_available():
            return provider
    return None


def speak_with_failover(
    text: str,
    *,
    voice: str = "",
    rate_raw: str = "",
    prosody: SpeechProsody | None = None,
    preferred: str = "",
):
    """Return (provider_name, chunk_iterator, provider) trying providers in priority order."""
    errors: list[str] = []
    tried: set[str] = set()
    candidates: list[RealtimeTtsProvider] = []
    if preferred:
        p = get_provider(preferred)
        if p is not None and not p.fallback_only:
            candidates.append(p)
    for provider in get_provider_chain():
        if provider.fallback_only:
            continue
        if provider.name in tried:
            continue
        candidates.append(provider)
    # pyttsx3 emergency fallback only after all streaming providers fail
    for provider in get_provider_chain():
        if not provider.fallback_only:
            continue
        if provider.name in tried:
            continue
        candidates.append(provider)

    failover_from = ""
    for provider in candidates:
        if provider.name in tried:
            continue
        tried.add(provider.name)
        if not provider.is_available():
            errors.append(f"{provider.name}: unavailable")
            continue
        try:
            chunks = provider.stream(text, voice=voice, rate_raw=rate_raw, prosody=prosody)
            if failover_from:
                logger.info("TTS failover: %s -> %s", failover_from, provider.name)
            return provider.name, chunks, provider
        except Exception as exc:
            errors.append(f"{provider.name}: {exc}")
            logger.warning("Provider %s failed: %s", provider.name, exc)
            failover_from = provider.name
    raise RuntimeError("All realtime providers failed: " + "; ".join(errors))
