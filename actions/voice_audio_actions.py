"""Voice debug and audio/TTS diagnostic actions."""

from __future__ import annotations

import time

from actions.base import BaseAction
from core.results import result_failed, result_success
from core.types import CommandRequest, CommandResult, Intent
from voice.audio_status import format_audio_status, get_audio_status, record_tts_success
from voice.tts import TTSError, TTSService
from voice.voice_debug_store import format_voice_debug_status, get_voice_debug_snapshot


class ShowVoiceDebugAction(BaseAction):
    intent = Intent.SHOW_VOICE_DEBUG.value

    def execute(self, request: CommandRequest) -> CommandResult:
        del request
        return result_success(
            Intent.SHOW_VOICE_DEBUG,
            format_voice_debug_status(),
            data={"snapshot": get_voice_debug_snapshot().__dict__},
        )


class ShowAudioStatusAction(BaseAction):
    intent = Intent.SHOW_AUDIO_STATUS.value

    def execute(self, request: CommandRequest) -> CommandResult:
        del request
        from voice.audio_status import (
            warn_if_legacy_completion_path_active,
            warn_stable_path_mismatch_if_needed,
        )

        warn_stable_path_mismatch_if_needed()
        warn_if_legacy_completion_path_active()
        status = get_audio_status()
        return result_success(
            Intent.SHOW_AUDIO_STATUS,
            format_audio_status(),
            data={
                "read_only": True,
                "engine": status.engine,
                "playback_backend": status.playback_backend,
                "fallback_active": status.fallback_active,
            },
        )


class ToolModeStatusAction(BaseAction):
    intent = Intent.TOOL_MODE_STATUS.value

    def execute(self, request: CommandRequest) -> CommandResult:
        del request
        from voice.tool_first_mode import format_tool_mode_status

        return result_success(Intent.TOOL_MODE_STATUS, format_tool_mode_status())


class ShowWakeDiagnosticsAction(BaseAction):
    intent = Intent.SHOW_WAKE_DIAGNOSTICS.value

    def execute(self, request: CommandRequest) -> CommandResult:
        del request
        from voice.wake_diagnostics import format_wake_diagnostics

        return result_success(Intent.SHOW_WAKE_DIAGNOSTICS, format_wake_diagnostics())


class ShowAudioDevicesAction(BaseAction):
    intent = Intent.SHOW_AUDIO_DEVICES.value

    def execute(self, request: CommandRequest) -> CommandResult:
        del request
        from voice.audio_devices import format_audio_devices_report

        return result_success(Intent.SHOW_AUDIO_DEVICES, format_audio_devices_report())


class TestLeftChannelAction(BaseAction):
    intent = Intent.TEST_LEFT_CHANNEL.value

    def execute(self, request: CommandRequest) -> CommandResult:
        del request
        from voice.audio_routing import test_left_channel

        result = test_left_channel()
        if result.ok:
            return result_success(Intent.TEST_LEFT_CHANNEL, result.message)
        return result_failed(Intent.TEST_LEFT_CHANNEL, result.message)


class TestRightChannelAction(BaseAction):
    intent = Intent.TEST_RIGHT_CHANNEL.value

    def execute(self, request: CommandRequest) -> CommandResult:
        del request
        from voice.audio_routing import test_right_channel

        result = test_right_channel()
        if result.ok:
            return result_success(Intent.TEST_RIGHT_CHANNEL, result.message)
        return result_failed(Intent.TEST_RIGHT_CHANNEL, result.message)


class TestAudioRoutingAction(BaseAction):
    intent = Intent.TEST_AUDIO_ROUTING.value

    def execute(self, request: CommandRequest) -> CommandResult:
        del request
        from voice.audio_routing import test_audio_routing

        result = test_audio_routing()
        if result.ok:
            return result_success(Intent.TEST_AUDIO_ROUTING, result.message)
        return result_failed(Intent.TEST_AUDIO_ROUTING, result.message)


class CycleAudioOutputAction(BaseAction):
    intent = Intent.CYCLE_AUDIO_OUTPUT.value

    def execute(self, request: CommandRequest) -> CommandResult:
        del request
        from voice.audio_routing import cycle_audio_output

        result = cycle_audio_output()
        if result.ok:
            return result_success(Intent.CYCLE_AUDIO_OUTPUT, result.message)
        return result_failed(Intent.CYCLE_AUDIO_OUTPUT, result.message)


class StopSpeechHardAction(BaseAction):
    intent = Intent.STOP_SPEECH_HARD.value

    def execute(self, request: CommandRequest) -> CommandResult:
        del request
        from voice.tts_watchdog import stop_speech_hard

        reason = stop_speech_hard()
        from voice.audio_status import format_audio_status

        return result_success(
            Intent.STOP_SPEECH_HARD,
            f"Hard stop applied: {reason}\n{format_audio_status()}",
        )


class ShowWindowsAudioRoutingAction(BaseAction):
    intent = Intent.SHOW_WINDOWS_AUDIO_ROUTING.value

    def execute(self, request: CommandRequest) -> CommandResult:
        del request
        from voice.windows_audio_routing import format_windows_audio_routing_report

        return result_success(
            Intent.SHOW_WINDOWS_AUDIO_ROUTING,
            format_windows_audio_routing_report(),
        )


class CycleWindowsPlaybackTargetAction(BaseAction):
    intent = Intent.CYCLE_WINDOWS_PLAYBACK_TARGET.value

    def execute(self, request: CommandRequest) -> CommandResult:
        del request
        from voice.windows_audio_routing import cycle_windows_playback_target

        ok, message = cycle_windows_playback_target()
        if ok:
            return result_success(Intent.CYCLE_WINDOWS_PLAYBACK_TARGET, message)
        return result_failed(Intent.CYCLE_WINDOWS_PLAYBACK_TARGET, message)


class AudioRouteProveAction(BaseAction):
    intent = Intent.AUDIO_ROUTE_PROVE.value

    def execute(self, request: CommandRequest) -> CommandResult:
        del request
        from voice.audio_route_prove import run_audio_route_prove

        report = run_audio_route_prove(gap_seconds=2.0)
        body = report.summary + "\n\n" + format_audio_status()
        ok = report.selected_backend is not None or any(
            s.user_heard for s in report.steps
        )
        if ok:
            return result_success(Intent.AUDIO_ROUTE_PROVE, body)
        return result_failed(Intent.AUDIO_ROUTE_PROVE, body)


class TestSubprocessSpeechAction(BaseAction):
    intent = Intent.TEST_SUBPROCESS_SPEECH.value

    def execute(self, request: CommandRequest) -> CommandResult:
        del request
        import time

        from voice.audio_status import set_selected_verified_audio_backend
        from voice.audio_verified import ask_user_audible_confirmation
        from voice.tts_subprocess import SUBPROCESS_BACKEND, build_pyttsx3_subprocess_argv
        from voice.tts_subprocess import speak_subprocess_pyttsx3

        phrase = "Jarvis subprocess speech test"
        t0 = time.perf_counter()
        argv = build_pyttsx3_subprocess_argv(phrase)
        try:
            result = speak_subprocess_pyttsx3(phrase)
            elapsed_ms = (time.perf_counter() - t0) * 1000.0
            lines = [
                f"Subprocess test finished ({elapsed_ms:.0f} ms).",
                f"  exit_code: {result.exit_code}",
                f"  stdout: {result.stdout.strip() or '(empty)'}",
                f"  stderr: {result.stderr.strip() or '(empty)'}",
            ]
            if not result.ok:
                lines.append("Engine failed — verified backend NOT set.")
                return result_failed(
                    Intent.TEST_SUBPROCESS_SPEECH,
                    "\n".join(lines) + f"\n{format_audio_status()}",
                )
            heard = ask_user_audible_confirmation(
                "Did you hear the subprocess speech test? say yes or no"
            )
            if heard is True:
                set_selected_verified_audio_backend(SUBPROCESS_BACKEND)
                lines.append(
                    f"Verified backend set to {SUBPROCESS_BACKEND}. Normal speech unlocked."
                )
            else:
                lines.append(
                    "Verified backend NOT set. Normal JARVIS speech remains blocked."
                )
            return result_success(Intent.TEST_SUBPROCESS_SPEECH, "\n".join(lines))
        except Exception as exc:
            return result_failed(
                Intent.TEST_SUBPROCESS_SPEECH,
                f"Subprocess speech error: {exc}\n{format_audio_status()}",
            )


class ForceShellTtsTestAction(BaseAction):
    intent = Intent.FORCE_SHELL_TTS_TEST.value

    def execute(self, request: CommandRequest) -> CommandResult:
        del request
        import time

        from config import PROJECT_ROOT
        from voice.audio_status import set_selected_verified_audio_backend
        from voice.audio_verified import ask_user_audible_confirmation
        from voice.tts_subprocess import (
            SHELL_SUBPROCESS_BACKEND,
            build_shell_exact_argv,
            run_shell_exact_pyttsx3,
        )

        t0 = time.perf_counter()
        argv = build_shell_exact_argv()
        cmd_display = f"cd {PROJECT_ROOT}\n{' '.join(argv)}"
        try:
            result = run_shell_exact_pyttsx3()
            elapsed_ms = (time.perf_counter() - t0) * 1000.0
            lines = [
                "Force shell TTS test (exact shell command).",
                f"  command: {cmd_display}",
                f"  elapsed_ms: {elapsed_ms:.0f}",
                f"  exit_code: {result.exit_code}",
                f"  stdout: {result.stdout.strip() or '(empty)'}",
                f"  stderr: {result.stderr.strip() or '(empty)'}",
            ]
            if not result.ok:
                lines.append("Exit non-zero — verified backend NOT set.")
                return result_failed(
                    Intent.FORCE_SHELL_TTS_TEST,
                    "\n".join(lines) + f"\n{format_audio_status()}",
                )
            heard = ask_user_audible_confirmation(
                "Did you hear the shell TTS test? say yes or no"
            )
            if heard is True:
                set_selected_verified_audio_backend(SHELL_SUBPROCESS_BACKEND)
                lines.append(
                    f"Verified backend set to {SHELL_SUBPROCESS_BACKEND}. "
                    "Normal speech and SPEAK overlay unlocked."
                )
            else:
                lines.append(
                    "Verified backend NOT set. Normal JARVIS speech remains blocked."
                )
            return result_success(Intent.FORCE_SHELL_TTS_TEST, "\n".join(lines))
        except Exception as exc:
            return result_failed(
                Intent.FORCE_SHELL_TTS_TEST,
                f"Shell TTS test error: {exc}\n{format_audio_status()}",
            )


class ForceDirectPyttsx3NormalModeAction(BaseAction):
    intent = Intent.FORCE_DIRECT_PYTTSX3_NORMAL_MODE.value

    def execute(self, request: CommandRequest) -> CommandResult:
        del request
        from voice.audio_status import set_force_direct_normal_mode
        from voice.tts_pyttsx3 import NORMAL_DIRECT_SPEAKER, speak_pyttsx3_direct

        set_force_direct_normal_mode(True)
        same_object = NORMAL_DIRECT_SPEAKER is speak_pyttsx3_direct
        return result_success(
            Intent.FORCE_DIRECT_PYTTSX3_NORMAL_MODE,
            (
                "Forced normal JARVIS speech to direct pyttsx3 (test 1 function).\n"
                f"  NORMAL_DIRECT_SPEAKER is speak_pyttsx3_direct: {same_object}\n"
                f"  Run 'audio route prove' and answer yes/no to verify audible output.\n"
                f"{format_audio_status()}"
            ),
        )


class TestNormalSpeechPathAction(BaseAction):
    intent = Intent.TEST_NORMAL_SPEECH.value

    def execute(self, request: CommandRequest) -> CommandResult:
        del request
        import time

        phrase = "Jarvis normal speech path test"
        svc = TTSService(enabled=True)
        t0 = time.perf_counter()
        try:
            ok = svc.speak(phrase)
            elapsed_ms = (time.perf_counter() - t0) * 1000.0
            if not ok:
                return result_failed(
                    Intent.TEST_NORMAL_SPEECH,
                    f"Normal speech path returned false.\n{format_audio_status()}",
                )
            from voice.audio_status import get_audio_status
            from voice.audio_verified import has_verified_audio_backend
            from voice.tts_backend import (
                get_verified_normal_speech_backend,
                normal_speech_must_not_use_edge_tts,
            )

            status = get_audio_status()
            last_path = (status.normal_speech_last_path or "").strip().lower()
            if normal_speech_must_not_use_edge_tts() and last_path in {
                "edge_tts",
                "edge",
            }:
                return result_failed(
                    Intent.TEST_NORMAL_SPEECH,
                    (
                        "Normal speech used edge_tts but a verified backend is set.\n"
                        f"  expected: {get_verified_normal_speech_backend()}\n"
                        f"  last normal path: {status.normal_speech_last_path}\n"
                        f"{format_audio_status()}"
                    ),
                )
            if has_verified_audio_backend():
                expected = get_verified_normal_speech_backend()
                equivalent = {
                    "direct_pyttsx3": {"direct_pyttsx3", "pyttsx3_direct"},
                    "subprocess_pyttsx3": {"subprocess_pyttsx3"},
                    "shell_subprocess_pyttsx3": {"shell_subprocess_pyttsx3"},
                }
                allowed = equivalent.get(str(expected or "").lower(), {str(expected or "").lower()})
                if last_path and expected and last_path not in allowed:
                    return result_failed(
                        Intent.TEST_NORMAL_SPEECH,
                        (
                            "Normal speech backend mismatch.\n"
                            f"  expected: {expected}\n"
                            f"  last normal path: {status.normal_speech_last_path}\n"
                            f"{format_audio_status()}"
                        ),
                    )
            return result_success(
                Intent.TEST_NORMAL_SPEECH,
                (
                    f"Normal speech path OK ({elapsed_ms:.0f} ms).\n"
                    f"  path: TTSService.speak (same as command summaries)\n"
                    f"  last normal path: {status.normal_speech_last_path or 'n/a'}\n"
                    f"{format_audio_status()}"
                ),
            )
        except TTSError as exc:
            return result_failed(
                Intent.TEST_NORMAL_SPEECH,
                f"Normal speech path failed: {exc}\n{format_audio_status()}",
            )


class TestDirectSpeechAction(BaseAction):
    intent = Intent.TEST_DIRECT_SPEECH.value

    def execute(self, request: CommandRequest) -> CommandResult:
        del request
        body, ok = _run_direct_speech_test()
        if ok:
            return result_success(
                Intent.TEST_DIRECT_SPEECH,
                body + "\n  tip: run 'verify direct speech backend' to unlock normal speech in stable mode.",
            )
        return result_failed(Intent.TEST_DIRECT_SPEECH, body)


def _run_direct_speech_test(*, phrase: str = "Jarvis direct speech test") -> tuple[str, bool]:
    import time

    from voice.tts_pyttsx3 import NORMAL_DIRECT_SPEAKER

    advanced_note = ""
    try:
        import config as cfg

        if not getattr(cfg, "VOICE_RUNTIME_STABLE", False) and not cfg.TTS_SAFE_MODE:
            advanced_note = (
                "\n  note: advanced TTS path is active; use VOICE_RUNTIME_MODE=stable "
                "if normal speech fails."
            )
    except Exception:
        pass
    t0 = time.perf_counter()
    try:
        NORMAL_DIRECT_SPEAKER(phrase, rate_raw="", record_user_success=False)
        elapsed_ms = (time.perf_counter() - t0) * 1000.0
        from voice.tts_playback_trace import get_playback_snapshot

        snap = get_playback_snapshot()
        body = (
            f"Direct pyttsx3 speech OK ({elapsed_ms:.0f} ms).\n"
            f"  path: pyttsx3.init → say → runAndWait (no streaming/routing)\n"
            f"  failures: {snap.failure_count}\n"
            f"{format_audio_status()}{advanced_note}"
        )
        return body, True
    except Exception as exc:
        return f"Direct speech failed: {exc}\n{format_audio_status()}{advanced_note}", False


class VerifyDirectSpeechBackendAction(BaseAction):
    intent = Intent.VERIFY_DIRECT_SPEECH_BACKEND.value

    def execute(self, request: CommandRequest) -> CommandResult:
        del request
        from voice.audio_status import apply_verified_direct_pyttsx3_backend
        from voice.audio_verified import ask_user_audible_confirmation
        from voice.tts_backend import DIRECT_PYTTSX3_BACKEND

        body, ok = _run_direct_speech_test(phrase="Jarvis direct speech verification test")
        if not ok:
            return result_failed(Intent.VERIFY_DIRECT_SPEECH_BACKEND, body)
        heard = ask_user_audible_confirmation(
            "Did you hear the direct speech verification test? say yes or no"
        )
        lines = [body, ""]
        if heard is True:
            apply_verified_direct_pyttsx3_backend(user_heard=True)
            lines.append(
                f"Verified backend set to {DIRECT_PYTTSX3_BACKEND}. "
                "Normal speech will use direct pyttsx3 (subprocess not required)."
            )
            lines.append(format_audio_status())
            return result_success(Intent.VERIFY_DIRECT_SPEECH_BACKEND, "\n".join(lines))
        lines.append(
            "Verified backend NOT set. Normal JARVIS speech remains blocked in stable mode."
        )
        lines.append(format_audio_status())
        return result_failed(Intent.VERIFY_DIRECT_SPEECH_BACKEND, "\n".join(lines))


class ForceVerifiedDirectSpeechAction(BaseAction):
    intent = Intent.FORCE_VERIFIED_DIRECT_SPEECH.value

    def execute(self, request: CommandRequest) -> CommandResult:
        raw = (request.raw_text or "").strip().lower()
        if "confirm" not in raw:
            return result_failed(
                Intent.FORCE_VERIFIED_DIRECT_SPEECH,
                "Confirmation required. Say: force verified direct speech confirm",
            )
        from voice.audio_status import apply_verified_direct_pyttsx3_backend
        from voice.audio_verified import ask_user_audible_confirmation
        from voice.tts_backend import DIRECT_PYTTSX3_BACKEND

        approved = ask_user_audible_confirmation(
            "Force verified direct pyttsx3 backend without subprocess? say yes or no"
        )
        if approved is not True:
            return result_failed(
                Intent.FORCE_VERIFIED_DIRECT_SPEECH,
                "Force verified direct speech cancelled.\n" + format_audio_status(),
            )
        apply_verified_direct_pyttsx3_backend(user_heard=True)
        return result_success(
            Intent.FORCE_VERIFIED_DIRECT_SPEECH,
            (
                f"Verified backend forced to {DIRECT_PYTTSX3_BACKEND}.\n"
                "  subprocess verification not required\n"
                "  normal speech path: speak_pyttsx3_direct\n"
                f"{format_audio_status()}"
            ),
        )


class VoiceSmokeTestAction(BaseAction):
    intent = Intent.VOICE_SMOKE_TEST.value

    def execute(self, request: CommandRequest) -> CommandResult:
        del request
        import config as cfg
        from pathlib import Path

        from voice.runtime_mode import format_stable_mode_banner, is_stable_voice_mode
        from voice.stt_diagnostics import snapshot as stt_snap
        from voice.transcriber import get_stt_status
        from voice.voice_debug_store import get_voice_debug_snapshot
        from voice.wake_diagnostics import format_wake_diagnostics

        lines: list[str] = ["Voice smoke test (local only)"]
        lines.append(format_stable_mode_banner())
        lines.append(
            f"  wake: enabled={cfg.WAKE_WORD_ENABLED} threshold={cfg.WAKE_WORD_THRESHOLD} "
            f"listen_s={cfg.WAKE_MAX_LISTEN_SECONDS}"
        )
        lines.append(
            f"  STT: engine={cfg.STT_ENGINE} model={cfg.STT_MODEL} device={cfg.STT_DEVICE_REQUEST} "
            f"streaming={cfg.STT_STREAMING_BUFFER_ENABLED} multipass={cfg.STT_MULTIPASS_ENABLED}"
        )
        lines.append(
            f"  TTS: engine={cfg.TTS_ENGINE} force={cfg.TTS_FORCE_ENGINE} async={cfg.TTS_ASYNC} "
            f"streaming={cfg.TTS_STREAMING_ENABLED} safe={cfg.TTS_SAFE_MODE}"
        )

        dbg = get_voice_debug_snapshot()
        diag = stt_snap()
        lines.append(f"  last transcript raw: {dbg.last_raw_transcript or '(none)'}")
        lines.append(f"  last transcript norm: {dbg.last_normalized_transcript or '(none)'}")
        lines.append(f"  last error (audio): {get_audio_status().last_error or '(none)'}")
        lines.append(f"  empty wake streak: {diag.consecutive_empty_wake}")

        tts_line = "  direct pyttsx3: skipped (set TTS_ENABLED=true to run)"
        if cfg.TTS_ENABLED:
            try:
                from voice.tts_pyttsx3 import speak_pyttsx3_direct

                speak_pyttsx3_direct("Jarvis voice smoke test.", rate_raw="")
                tts_line = "  direct pyttsx3: OK"
            except Exception as exc:
                tts_line = f"  direct pyttsx3: FAILED ({exc})"
        lines.append(tts_line)

        sample_paths = [
            Path("data/voice_smoke_sample.wav"),
            Path("tests/fixtures/voice_smoke_sample.wav"),
        ]
        stt_line = "  sample STT: no sample wav (optional data/voice_smoke_sample.wav)"
        for sp in sample_paths:
            if sp.is_file():
                try:
                    from voice.transcriber import transcribe_wake_audio_fast

                    result = transcribe_wake_audio_fast(sp)
                    stt_line = f"  sample STT ({sp.name}): {result.text!r}"
                except Exception as exc:
                    stt_line = f"  sample STT ({sp.name}): FAILED ({exc})"
                break
        lines.append(stt_line)
        lines.append("")
        lines.append(format_wake_diagnostics())
        if is_stable_voice_mode():
            lines.append("Stable mode is ACTIVE — advanced STT/TTS paths are disabled.")

        ok = "FAILED" not in tts_line and "FAILED" not in stt_line
        intent = Intent.VOICE_SMOKE_TEST
        if ok:
            return result_success(intent, "\n".join(lines))
        return result_failed(intent, "\n".join(lines))


class ShowTtsThreadsAction(BaseAction):
    intent = Intent.SHOW_TTS_THREADS.value

    def execute(self, request: CommandRequest) -> CommandResult:
        del request
        from voice.tts_thread_status import format_tts_threads

        return result_success(Intent.SHOW_TTS_THREADS, format_tts_threads())


class TestVoiceOutputAction(BaseAction):
    intent = Intent.TEST_VOICE_OUTPUT.value

    def execute(self, request: CommandRequest) -> CommandResult:
        del request
        phrase = "JARVIS voice test. Audio output is working."
        t0 = time.perf_counter()
        try:
            ok = TTSService(enabled=True).speak(phrase)
            elapsed_ms = (time.perf_counter() - t0) * 1000.0
            if not ok:
                return result_failed(
                    Intent.TEST_VOICE_OUTPUT,
                    "TTS disabled or returned no audio.",
                )
            record_tts_success(provider="test_voice_output", text_preview=phrase)
            return result_success(
                Intent.TEST_VOICE_OUTPUT,
                f"Voice test OK ({elapsed_ms:.0f} ms).\n{format_audio_status()}",
            )
        except TTSError as exc:
            return result_failed(
                Intent.TEST_VOICE_OUTPUT,
                f"Voice test failed: {exc}\n{format_audio_status()}",
            )


class CalibrateVoiceAction(BaseAction):
    intent = Intent.CALIBRATE_VOICE.value

    def execute(self, request: CommandRequest) -> CommandResult:
        del request
        from config import VOICE_CALIBRATION_MAX_SAMPLES
        from voice.voice_calibration import load_calibration_prompts, run_voice_calibration

        result = run_voice_calibration()
        prompts = load_calibration_prompts()
        prompt_lines = "\n".join(f"  {i + 1}. {p}" for i, p in enumerate(prompts))
        samples = "\n".join(
            f"  - expected={item.expected_phrase!r} heard={item.heard_transcript!r}"
            for item in result.samples
        )
        summary = (
            "Voice calibration v2 (local only — no audio leaves this machine).\n"
            f"Say up to {VOICE_CALIBRATION_MAX_SAMPLES} commands via push-to-talk or wake:\n"
            f"{prompt_lines}\n"
            "JARVIS will compare expected vs heard and store safe correction pairs.\n"
            f"Calibration file: {result.path}\n"
            f"Recommended VOICE_PROFILE={result.recommended_profile}\n"
            "Pending samples:\n"
            f"{samples or '  (none)'}"
        )
        return result_success(
            Intent.CALIBRATE_VOICE,
            summary,
            data={
                "path": str(result.path),
                "recommended_profile": result.recommended_profile,
                "sample_count": len(result.samples),
            },
        )


class DiagnoseVoiceRuntimeAction(BaseAction):
    intent = Intent.DIAGNOSE_VOICE_RUNTIME.value

    def execute(self, request: CommandRequest) -> CommandResult:
        del request
        from core.runtime_state import get_runtime_state
        from ui.overlay_app import get_overlay_controller
        from voice.audio_status import get_audio_status
        from voice.stt_diagnostics import snapshot as stt_diag_snapshot
        from voice.transcriber import get_stt_status
        from voice.wakeword_loop import get_active_detector

        rt = get_runtime_state()
        stt = get_stt_status()
        diag = stt_diag_snapshot()
        audio = get_audio_status()
        ctrl = get_overlay_controller()
        overlay = ctrl._state.snapshot()
        detector = get_active_detector()
        detector_thread = getattr(detector, "_thread", None)
        wake_active = bool(detector_thread and detector_thread.is_alive())
        try:
            from voice.microphone import check_microphone_available

            check_microphone_available()
            mic = "available"
        except Exception as exc:
            mic = f"degraded: {exc}"

        empty_rate = 0.0
        if diag.transcribe_count:
            empty_rate = diag.empty_transcript_count / max(1, diag.transcribe_count)
        voice_debug = get_voice_debug_snapshot()
        recommendations: list[str] = []
        if not wake_active and rt.wake_word_enabled:
            recommendations.append("restart wake listener from tray")
        if "degraded" in mic:
            recommendations.append("check Windows microphone input device")
        if not stt.model_loaded:
            recommendations.append("run show stt status or preload STT model")
        if audio.last_success is False:
            recommendations.append("run test voice output")
        if overlay.phase.value in {"recording", "transcribing"}:
            recommendations.append("reset jarvis runtime to clear stuck overlay phase")
        if empty_rate > 0.3:
            recommendations.append("try VOICE_PROFILE=balanced or accurate")
        if not recommendations:
            recommendations.append("no safe recovery needed")

        lines = [
            "Voice runtime diagnosis",
            f"  wake_listener_active: {'yes' if wake_active else 'no'}",
            f"  wake_session_active: {'yes' if rt.wake_word_listening_active else 'no'}",
            f"  mic_input: {mic}",
            f"  stt_model_loaded: {'yes' if stt.model_loaded else 'no'}",
            f"  stt_model: {stt.model}",
            f"  stt_backend_device: {stt.backend}/{stt.device}",
            f"  last_transcript_at: {voice_debug.last_transcript_at or 'n/a'}",
            f"  empty_transcript_rate: {empty_rate:.2f}",
            f"  tts_last_success: {audio.last_success}",
            f"  tts_last_error: {audio.last_error or 'n/a'}",
            f"  overlay_phase: {overlay.phase.value}",
            f"  overlay_visible: {'yes' if overlay.visible else 'no'}",
            f"  audio_output_likely: {'yes' if audio.last_success or audio.output_device else 'unknown'}",
            "  recommended_safe_steps:",
        ]
        lines.extend(f"    - {item}" for item in recommendations)
        return result_success(
            Intent.DIAGNOSE_VOICE_RUNTIME,
            "\n".join(lines),
            data={"recommendations": recommendations},
        )


class ResetJarvisRuntimeAction(BaseAction):
    intent = Intent.RESET_JARVIS_RUNTIME.value

    def execute(self, request: CommandRequest) -> CommandResult:
        del request
        from ui.overlay_app import get_overlay_controller
        from voice.audio_status import reset_audio_status
        from voice.stt_diagnostics import reset_stt_diagnostics
        from voice.tts_status import reset_tts_status_cache
        from voice.voice_debug_store import reset_voice_debug_store
        from services.runtime_monitor import reset_runtime_monitor

        get_overlay_controller()._state.reset()
        reset_runtime_monitor()
        reset_voice_debug_store()
        reset_stt_diagnostics()
        from voice.wake_diagnostics import reset_wake_diagnostics

        reset_wake_diagnostics()
        reset_tts_status_cache()
        reset_audio_status()
        try:
            TTSService(enabled=False).reset_engine()
        except Exception:
            pass
        return result_success(
            Intent.RESET_JARVIS_RUNTIME,
            (
                "Runtime display and voice diagnostics reset. "
                "Logs, audit trail, memory, approvals, and wake architecture were left intact."
            ),
            data={"destructive_cleanup": False},
        )


class TestStreamingSttAction(BaseAction):
    intent = Intent.TEST_STREAMING_STT.value

    def execute(self, request: CommandRequest) -> CommandResult:
        del request
        from voice.streaming_stt.test_harness import run_streaming_stt_test

        try:
            import config as cfg

            listen_s = float(getattr(cfg, "STT_STREAM_TEST_SECONDS", 8.0))
        except Exception:
            listen_s = 8.0
        result = run_streaming_stt_test(listen_seconds=listen_s, use_live_mic=True)
        body = result.report
        if result.error:
            body += f"\n  error: {result.error}"
        data = {
            "read_only": True,
            "skip_speak": True,
            "stream_alive": result.stream_alive,
            "first_partial_ms": result.first_partial_ms,
            "partial_updates": result.partial_updates,
        }
        if result.ok:
            return result_success(Intent.TEST_STREAMING_STT, body, data=data)
        return result_failed(Intent.TEST_STREAMING_STT, body, data=data)
