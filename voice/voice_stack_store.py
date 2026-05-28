"""Persisted Phase 41 voice profile (engine, voice, emotion, device)."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from config import DATA_DIR, VOICE_STACK_PATH
from core.logger import setup_logger

logger = setup_logger("jarvis.voice.stack_store")

DEFAULT_FEMALE_VOICE = "en-US-JennyNeural"
DEFAULT_CINEMATIC_VOICE = "en-US-AriaNeural"


@dataclass
class VoiceStackProfile:
    engine: str = "edge_tts"
    voice: str = DEFAULT_FEMALE_VOICE
    emotion: str = "assistant"
    rate_raw: str = "+0%"
    output_device_index: int | None = None
    output_device_label: str = ""
    streaming_enabled: bool = True
    updated_at: str = ""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_voice_profile() -> VoiceStackProfile:
    path = Path(VOICE_STACK_PATH)
    if not path.is_file():
        return VoiceStackProfile(updated_at=_now())
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            return VoiceStackProfile()
        dev = raw.get("output_device_index")
        return VoiceStackProfile(
            engine=str(raw.get("engine", "edge_tts")),
            voice=str(raw.get("voice", DEFAULT_FEMALE_VOICE)),
            emotion=str(raw.get("emotion", "assistant")),
            rate_raw=str(raw.get("rate_raw", "+0%")),
            output_device_index=int(dev) if dev is not None and str(dev) != "" else None,
            output_device_label=str(raw.get("output_device_label", "")),
            streaming_enabled=bool(raw.get("streaming_enabled", True)),
            updated_at=str(raw.get("updated_at", "")),
        )
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        logger.warning("Could not load voice profile: %s", exc)
        return VoiceStackProfile()


def save_voice_profile(profile: VoiceStackProfile) -> None:
    path = Path(VOICE_STACK_PATH)
    path.parent.mkdir(parents=True, exist_ok=True)
    profile.updated_at = _now()
    try:
        path.write_text(
            json.dumps(asdict(profile), indent=2, ensure_ascii=True),
            encoding="utf-8",
        )
    except OSError as exc:
        logger.warning("Could not save voice profile: %s", exc)


def apply_voice_profile_to_runtime(profile: VoiceStackProfile | None = None) -> VoiceStackProfile:
    from voice.audio_devices import load_persisted_routing

    load_persisted_routing()
    """Apply persisted profile to in-process config + audio routing."""
    prof = profile or load_voice_profile()
    import config as cfg

    try:
        from voice.tts_backend import should_ignore_voice_stack_tts_engine

        if should_ignore_voice_stack_tts_engine():
            from voice.tts_backend import get_verified_normal_speech_backend

            verified = get_verified_normal_speech_backend() or ""
            cfg.TTS_ENGINE = "pyttsx3"
            cfg.TTS_FORCE_ENGINE = "pyttsx3"
            cfg.TTS_BACKEND = verified
            cfg.TTS_STREAMING_ENABLED = False
            logger.info(
                "Voice stack TTS engine ignored (stable verified backend=%s)",
                verified,
            )
            from voice.emotion_modes import get_emotion_preset

            preset = get_emotion_preset(prof.emotion)
            if preset:
                cfg.TTS_RATE_RAW = preset.rate_raw
            if prof.output_device_index is not None:
                from voice.audio_devices import set_session_output_device

                set_session_output_device(
                    prof.output_device_index, label=prof.output_device_label
                )
            return prof
    except Exception as exc:
        logger.debug("Verified-backend voice stack guard skipped: %s", exc)

    cfg.TTS_ENGINE = prof.engine
    cfg.TTS_VOICE = prof.voice
    cfg.TTS_RATE_RAW = prof.rate_raw
    cfg.TTS_STREAMING_ENABLED = prof.streaming_enabled

    from voice.emotion_modes import get_emotion_preset

    preset = get_emotion_preset(prof.emotion)
    if preset:
        cfg.TTS_VOICE = preset.edge_voice
        cfg.TTS_RATE_RAW = preset.rate_raw

    if prof.output_device_index is not None:
        from voice.audio_devices import set_session_output_device

        set_session_output_device(prof.output_device_index, label=prof.output_device_label)
    return prof


def set_female_voice() -> VoiceStackProfile:
    prof = load_voice_profile()
    prof.voice = DEFAULT_FEMALE_VOICE
    prof.engine = "edge_tts"
    prof.emotion = "assistant"
    save_voice_profile(prof)
    return apply_voice_profile_to_runtime(prof)


def set_cinematic_voice() -> VoiceStackProfile:
    prof = load_voice_profile()
    prof.voice = DEFAULT_CINEMATIC_VOICE
    prof.engine = "edge_tts"
    prof.emotion = "cinematic"
    prof.rate_raw = "+8%"
    save_voice_profile(prof)
    return apply_voice_profile_to_runtime(prof)


def set_emotion_mode(emotion: str) -> VoiceStackProfile:
    from voice.emotion_modes import get_emotion_preset

    preset = get_emotion_preset(emotion)
    if preset is None:
        raise ValueError(f"Unknown emotion: {emotion}")
    prof = load_voice_profile()
    prof.emotion = preset.name
    prof.voice = preset.edge_voice
    prof.rate_raw = preset.rate_raw
    save_voice_profile(prof)
    return apply_voice_profile_to_runtime(prof)


def set_engine(engine: str) -> VoiceStackProfile:
    prof = load_voice_profile()
    prof.engine = engine.strip().lower().replace("-", "_")
    save_voice_profile(prof)
    return apply_voice_profile_to_runtime(prof)


def reset_voice_profile_file() -> None:
    path = Path(VOICE_STACK_PATH)
    if path.is_file():
        try:
            path.unlink()
        except OSError:
            pass
