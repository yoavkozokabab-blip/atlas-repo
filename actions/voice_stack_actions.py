"""Phase 41 — premium voice stack actions."""

from __future__ import annotations

from actions.base import BaseAction
from core.results import result_failed, result_success
from core.types import CommandRequest, CommandResult, Intent
from voice.emotion_modes import VALID_EMOTIONS, format_emotion_catalog, get_emotion_preset
from voice.engines.registry import get_engine, get_engine_chain, list_all_voices, list_registered_engines
from voice.speech_controller import stop_speaking
from voice.tts import TTSService
from voice.tts_benchmark import run_tts_benchmark
from voice.voice_stack_store import (
    apply_voice_profile_to_runtime,
    load_voice_profile,
    set_cinematic_voice,
    set_emotion_mode,
    set_engine,
    set_female_voice,
)


class ListVoicesAction(BaseAction):
    intent = Intent.LIST_VOICES.value

    def execute(self, request: CommandRequest) -> CommandResult:
        del request
        lines = ["Available TTS voices (sample):"]
        for v in list_all_voices()[:25]:
            lines.append(f"  [{v.engine}] {v.voice_id} — {v.label}")
        lines.append(f"Engines: {', '.join(list_registered_engines())}")
        prof = load_voice_profile()
        lines.append(
            f"Active profile: engine={prof.engine} voice={prof.voice} emotion={prof.emotion}"
        )
        return result_success(Intent.LIST_VOICES, "\n".join(lines))


class SwitchVoiceAction(BaseAction):
    intent = Intent.SWITCH_VOICE.value

    def execute(self, request: CommandRequest) -> CommandResult:
        raw = (request.raw_text or "").lower()
        target = ""
        for name in list_registered_engines():
            if name.replace("_", " ") in raw or name in raw:
                target = name
                break
        if not target:
            chain = [e.name for e in get_engine_chain() if e.is_available()]
            return result_success(
                Intent.SWITCH_VOICE,
                "Say which engine to use: " + ", ".join(chain),
            )
        prof = set_engine(target)
        return result_success(
            Intent.SWITCH_VOICE,
            f"Switched TTS engine to {prof.engine}. Voice={prof.voice}",
        )


class SetFemaleVoiceAction(BaseAction):
    intent = Intent.SET_FEMALE_VOICE.value

    def execute(self, request: CommandRequest) -> CommandResult:
        del request
        prof = set_female_voice()
        TTSService(enabled=True).speak("Female assistant voice active.")
        return result_success(
            Intent.SET_FEMALE_VOICE,
            f"Female neural voice set: {prof.voice} (engine {prof.engine})",
        )


class SetCinematicVoiceAction(BaseAction):
    intent = Intent.SET_CINEMATIC_VOICE.value

    def execute(self, request: CommandRequest) -> CommandResult:
        del request
        prof = set_cinematic_voice()
        TTSService(enabled=True).speak("Cinematic voice profile engaged.")
        return result_success(
            Intent.SET_CINEMATIC_VOICE,
            f"Cinematic voice set: {prof.voice} rate {prof.rate_raw}",
        )


class SetVoiceEmotionAction(BaseAction):
    intent = Intent.SET_VOICE_EMOTION.value

    def execute(self, request: CommandRequest) -> CommandResult:
        raw = (request.raw_text or "").lower()
        emotion = ""
        for key in VALID_EMOTIONS:
            if key in raw:
                emotion = key
                break
        if not emotion:
            return result_success(Intent.SET_VOICE_EMOTION, format_emotion_catalog())
        try:
            prof = set_emotion_mode(emotion)
        except ValueError as exc:
            return result_failed(Intent.SET_VOICE_EMOTION, str(exc))
        preset = get_emotion_preset(emotion)
        msg = f"Emotion mode: {emotion}"
        if preset:
            msg += f" — {preset.description}"
        TTSService(enabled=True).speak(f"{emotion} voice mode active.")
        return result_success(Intent.SET_VOICE_EMOTION, f"{msg}\nVoice: {prof.voice}")


class BenchmarkTtsAction(BaseAction):
    intent = Intent.BENCHMARK_TTS.value

    def execute(self, request: CommandRequest) -> CommandResult:
        del request
        report = run_tts_benchmark()
        return result_success(Intent.BENCHMARK_TTS, report)


class StopSpeakingAction(BaseAction):
    intent = Intent.STOP_SPEAKING.value

    def execute(self, request: CommandRequest) -> CommandResult:
        del request
        stop_speaking()
        return result_success(Intent.STOP_SPEAKING, "Speech interrupted (barge-in).")
