"""Push-to-talk voice input loop."""

from __future__ import annotations

import time
from pathlib import Path
from typing import TYPE_CHECKING

from rich.panel import Panel

from core.runtime_state import RuntimeState
from voice.latency_tracker import (
    begin_voice_command,
    finish_and_log,
    set_record_ms,
    set_transcribe_ms,
    set_transcript,
)
from voice.microphone import MicrophoneError, record_until_enter, record_until_hotkey
from voice.stt_handling import LOW_CONFIDENCE_OVERLAY_MSG, notify_low_confidence, record_stt_result
from voice.transcriber import (
    TranscriptionError,
    get_last_transcription_feedback,
    transcribe_audio_detailed,
)
from voice.command_input import prepare_command_text

if TYPE_CHECKING:
    from core.app import JarvisApp
    from core.types import CommandResult


def process_voice_transcript(
    app: "JarvisApp",
    text: str,
    *,
    input_mode: str = "voice",
    print_result: bool = True,
    source: str = "voice",
) -> None:
    """
    Shared STT → router path for push-to-talk and wake-word sessions.
    Wake word never executes commands except through this function.
    """
    raw_text = text
    text = prepare_command_text(text)
    set_transcript(text)
    try:
        from voice.voice_debug_store import record_transcript_debug

        record_transcript_debug(raw=raw_text, normalized=text)
    except Exception:
        pass
    lower = text.strip().lower()
    if lower in {"quit", "exit", "q"}:
        app.console.print("[yellow]Goodbye.[/]")
        app._running = False
        app.runtime.stop()
        return
    if lower == "help":
        app._print_help()
        return
    if not text.strip():
        return
    result = app.handle_text_command(
        text,
        input_mode=input_mode,
        transcribed_text=text,
        print_result=print_result,
    )
    from config import TTS_ASYNC, TTS_ENABLED

    wait_tts = bool(
        TTS_ASYNC
        and TTS_ENABLED
        and app.speak_enabled
        and result
        and getattr(result, "summary", "")
    )
    finish_and_log(wait_for_tts=wait_tts)
    return result


def process_console_command(
    app: "JarvisApp",
    text: str,
    *,
    tray_app: object | None = None,
    print_result: bool = False,
) -> CommandResult | None:
    """
    Operator console → classify → same router path as wake/voice.
    Runs off the stdin thread; does not block wake listener.
    """
    from brain.intent_classifier import classify_rules
    from core.results import result_blocked, result_success
    from core.types import ActionStatus, CommandResult, Intent
    from runtime.background_tasks import TASK_CONTROL_INTENTS, get_engine
    from runtime.result_stream import ResultStream

    del tray_app
    text = prepare_command_text(text)
    if not text.strip():
        print("[CONSOLE] empty command — not executed.", flush=True)
        return result_blocked(Intent.UNKNOWN, "Empty command.")

    request = classify_rules(text)
    engine = get_engine()

    if engine.should_run_async(request.intent, input_mode="console"):
        try:
            task_id = engine.submit(app, text, request.intent)
        except RuntimeError as exc:
            with ResultStream.start(text) as stream:
                stream.result_line(str(exc), severity="error")
                return result_blocked(request.intent, str(exc))
        msg = (
            f"Background task {task_id} started for {request.intent.value.replace('_', ' ')}. "
            f"Use 'show running tasks' or 'cancel task {task_id}'."
        )
        print(f"[RESULT] {msg}", flush=True)
        return result_success(
            request.intent,
            msg,
            data={"task_id": task_id, "background": True},
        )

    with ResultStream.start(text) as stream:
        stream.progress("executing command...")
        result = app.handle_text_command(
            text,
            input_mode="console",
            transcribed_text=text,
            print_result=print_result,
        )
        if request.intent not in TASK_CONTROL_INTENTS:
            stream.render_completion(result)
        else:
            preview = (result.summary or "")[:160].replace("\n", " ")
            if preview:
                stream.result_line(preview)
            stream.complete(status=getattr(result.status, "value", str(result.status)), result=result)

    status = result.status.value if hasattr(result.status, "value") else str(result.status)
    if request.intent in TASK_CONTROL_INTENTS:
        summary_preview = (result.summary or "")[:160].replace("\n", " ")
        print(f"[CONSOLE] execution result={status} {summary_preview}", flush=True)
    if result.status == ActionStatus.CONFIRMATION_REQUIRED:
        print("[CONSOLE] confirmation required — reply yes/no in this console.", flush=True)
    return result


def run_voice_loop(
    app: "JarvisApp",
    *,
    hotkey: bool = False,
    runtime: RuntimeState | None = None,
) -> None:
    """
    Record → transcribe → route through the same text pipeline as console mode.
    Voice never bypasses router/security/registry.
    """
    tts_note = (
        "\nTTS: summaries will be spoken after each command."
        if app.speak_enabled
        else ""
    )
    app.console.print(
        Panel(
            "[bold cyan]JARVIS Voice[/] — push-to-talk\n"
            "Record → transcribe → same safe command pipeline.\n"
            "Say [bold]help[/] or [bold]quit[/] after transcription.\n"
            "Confirm destructive actions with yes/כן after transcription."
            f"{tts_note}",
            title="local_jarvis --voice",
        )
    )

    record_fn = record_until_hotkey if hotkey else record_until_enter
    state = runtime or app.runtime
    state.set_voice(True)

    import threading

    from core.thread_registry import get_thread_registry

    current = threading.current_thread()
    registry = get_thread_registry()
    if current.name == "jarvis-voice":
        registry.register("jarvis-voice-loop", current)
    else:
        registry.register_fn(
            "jarvis-voice-loop",
            lambda: app._running and state.running and state.voice_enabled,
        )

    # VF-4 fix: track consecutive microphone errors for exponential backoff.
    # Without this the loop spins at CPU-max speed when the mic is disconnected.
    _mic_error_count = 0

    while app._running and state.running and state.voice_enabled:
        wav_path: Path | None = None
        begin_voice_command(source="push_to_talk")
        t_record = time.perf_counter()
        try:
            if state.overlay_enabled:
                from ui.overlay_app import notify_overlay_listening

                notify_overlay_listening()
            wav_path = record_fn()
            set_record_ms((time.perf_counter() - t_record) * 1000.0)
            _mic_error_count = 0  # reset backoff counter on successful capture
        except MicrophoneError as exc:
            _mic_error_count += 1
            # Exponential backoff: 1s, 2s, 4s, 8s … capped at 30s.
            delay = min(2.0 ** (_mic_error_count - 1), 30.0)
            app.console.print(
                f"[red]Microphone error:[/] {exc} "
                f"(retry in {delay:.0f}s, attempt {_mic_error_count})"
            )
            try:
                from ui.overlay_app import notify_overlay_error

                notify_overlay_error(str(exc))
            except Exception:
                pass
            finish_and_log()
            time.sleep(delay)
            continue

        if wav_path is None:
            finish_and_log()
            continue

        try:
            if state.overlay_enabled:
                from ui.overlay_app import notify_overlay_transcribing

                notify_overlay_transcribing()
            t_stt = time.perf_counter()
            stt_result = transcribe_audio_detailed(wav_path)
            transcribe_ms = (time.perf_counter() - t_stt) * 1000.0
            set_transcribe_ms(transcribe_ms)
            text = stt_result.text or ""
            normalized_text = prepare_command_text(text)
            record_stt_result(
                stt_result,
                transcribe_ms=transcribe_ms,
                empty=not bool(normalized_text.strip()),
                raw_text=text,
                normalized_text=normalized_text,
            )
            if state.overlay_enabled:
                from ui.overlay_app import notify_overlay_thinking, notify_overlay_transcript

                notify_overlay_transcript(text)
                notify_overlay_thinking()
            if getattr(stt_result, "low_confidence", False):
                notify_low_confidence(
                    app,
                    overlay_enabled=state.overlay_enabled,
                    speak_prompt=False,
                )
            feedback = get_last_transcription_feedback()
            if feedback:
                app.console.print(f"[dim]STT tip: {feedback}[/]")
            process_voice_transcript(
                app,
                text,
                input_mode="voice",
                print_result=True,
            )
        except TranscriptionError as exc:
            app.console.print(f"[red]Transcription failed:[/] {exc}")
            try:
                from ui.overlay_app import notify_overlay_error

                notify_overlay_error(str(exc))
            except Exception:
                pass
        finally:
            try:
                if wav_path is not None and wav_path.exists():
                    wav_path.unlink(missing_ok=True)
            except OSError:
                pass

    try:
        get_thread_registry().deregister("jarvis-voice-loop")
    except Exception:
        pass
