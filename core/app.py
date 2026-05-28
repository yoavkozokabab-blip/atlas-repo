"""Application orchestration."""

from __future__ import annotations

import time
import traceback

from rich.console import Console
from rich.panel import Panel

from brain.router import CommandRouter
from core.results import result_blocked
from core.runtime_state import RuntimeState, get_runtime_state
from core.types import ActionStatus, CommandResult, Intent
from voice.tts import TTSError, TTSService, resolve_tts_enabled

from core.logger import setup_logger

logger = setup_logger("jarvis.app")


class JarvisApp:
    """JARVIS console — text, voice, and tray share one command handler."""

    def __init__(
        self,
        *,
        speak_enabled: bool | None = None,
        runtime: RuntimeState | None = None,
        skip_bootstrap: bool = False,
    ) -> None:
        self.console = Console()
        self.router = CommandRouter()
        self.runtime = runtime or get_runtime_state()
        self._running = True

        if not skip_bootstrap:
            from core.runtime_bootstrap import (
                ensure_jarvis_runtime_bootstrapped,
                print_jarvis_runtime_diagnostics,
            )

            ensure_jarvis_runtime_bootstrapped(
                runtime=self.runtime,
                speak_enabled=speak_enabled,
            )
            print_jarvis_runtime_diagnostics(runtime=self.runtime)
        elif speak_enabled is not None:
            self.runtime.speak_enabled = speak_enabled
        elif not self.runtime.speak_enabled:
            from voice.tts import resolve_tts_enabled

            self.runtime.speak_enabled = resolve_tts_enabled(None)

        self.speak_enabled = self.runtime.speak_enabled
        self.tts = TTSService(enabled=self.speak_enabled)

    def handle_text_command(
        self,
        raw_text: str,
        *,
        input_mode: str = "text",
        transcribed_text: str | None = None,
        print_result: bool = True,
    ) -> CommandResult:
        """
        Single entry for console, voice, and tray.
        Always routes through classifier → security → registry.
        """
        self.speak_enabled = self.runtime.speak_enabled
        self.tts.enabled = self.speak_enabled

        text = raw_text.strip()
        try:
            from voice.tool_first_mode import is_tool_first_mode

            tool_first = is_tool_first_mode()
        except Exception:
            tool_first = False
        if tool_first and input_mode == "console":
            print_result = True
        try:
            from ui.quiet_mode import on_explicit_command

            on_explicit_command(text)
        except Exception:
            pass
        overlay_voice = self.runtime.overlay_enabled and input_mode in {
            "voice",
            "wakeword",
        }
        overlay_result = self.runtime.overlay_enabled and (
            overlay_voice or tool_first
        )

        if not text:
            result = result_blocked(
                Intent.UNKNOWN,
                "Empty command — nothing to execute.",
            )
            self.runtime.record_result(result.summary, result.error)
            if print_result:
                self._print_result(result)
            self._maybe_speak_result(result, input_mode=input_mode)
            if overlay_result:
                self._notify_overlay_result(result, input_mode=input_mode)
            return result

        self._publish_runtime_event(
            "command.received",
            input_mode=input_mode,
            text_preview=text[:120],
        )
        trace_id = ""
        t0 = time.perf_counter()
        try:
            from services.observability import get_observability

            obs = get_observability()
            trace_id = obs.start_trace(
                "command",
                input_mode=input_mode,
                text_chars=len(text),
            )
            obs.record_command_lifecycle(
                "received",
                trace_id=trace_id,
                input_mode=input_mode,
            )
        except Exception:
            obs = None

        try:
            result = self.router.route(
                text,
                input_mode=input_mode,
                transcribed_text=transcribed_text
                if transcribed_text is not None
                else (text if input_mode == "voice" else None),
            )
        except Exception as exc:
            duration_ms = (time.perf_counter() - t0) * 1000.0
            tb = traceback.format_exc()
            logger.exception(
                "command route failed input_mode=%s text=%r",
                input_mode,
                text[:80],
            )
            if obs is not None:
                obs.record_failure(
                    component="command",
                    error=exc,
                    context={"input_mode": input_mode, "trace_id": trace_id},
                )
                obs.record_command_lifecycle(
                    "failed",
                    trace_id=trace_id,
                    input_mode=input_mode,
                    duration_ms=duration_ms,
                    error=str(exc),
                )
                obs.finish_trace(
                    trace_id,
                    status="failed",
                    error=str(exc),
                    error_traceback=tb,
                )
            raise
        self.runtime.record_result(result.summary, result.error)
        self.runtime.increment_counter(f"intent:{result.intent.value}")
        self._publish_runtime_event(
            "command.completed",
            input_mode=input_mode,
            intent=result.intent.value,
            status=result.status.value,
            has_error=bool(result.error),
        )

        if print_result:
            self._print_result(result)
        try:
            from voice.diagnostic_speech import should_skip_result_speech
            from voice.tts_policy_trace import log_tts_policy_context

            log_tts_policy_context(
                stage="handle_text_command.before_speak",
                speak_enabled=self.speak_enabled,
                voice_path="handle_text_command",
                input_mode=input_mode,
                intent=result.intent.value,
                suppress_speech=should_skip_result_speech(result),
            )
        except Exception:
            pass
        self._maybe_speak_result(result, input_mode=input_mode)
        if overlay_result:
            if result.status == ActionStatus.FAILED:
                try:
                    from ui.overlay_app import notify_overlay_error

                    notify_overlay_error(result.error or result.summary)
                except Exception:
                    pass
            else:
                self._notify_overlay_result(result, input_mode=input_mode)

        if result.intent == Intent.SHUTDOWN_JARVIS and result.status == ActionStatus.SUCCESS:
            self._running = False
            self.runtime.stop()

        if obs is not None:
            duration_ms = (time.perf_counter() - t0) * 1000.0
            obs.record_command_lifecycle(
                "completed",
                trace_id=trace_id,
                input_mode=input_mode,
                intent=result.intent.value,
                status=result.status.value,
                duration_ms=duration_ms,
                error=result.error,
            )
            obs.finish_trace(
                trace_id,
                status=result.status.value,
                error=result.error,
                intent=result.intent.value,
            )

        return result

    def _publish_runtime_event(self, event: str, **payload: object) -> None:
        try:
            from core.event_bus import get_event_bus

            get_event_bus().publish_nowait(event, **payload)
        except Exception:
            pass

    def _notify_overlay_result(self, result: CommandResult, *, input_mode: str = "text") -> None:
        try:
            from ui.overlay_app import (
                notify_overlay_awaiting_confirmation,
                notify_overlay_result,
            )

            if result.status == ActionStatus.CONFIRMATION_REQUIRED:
                notify_overlay_awaiting_confirmation(intent=result.intent.value)
                return
            summary = result.summary
            speaking = False
            overlay_branch = "unset"
            try:
                from voice.tts_output_policy import evaluate_tts_output

                decision = evaluate_tts_output(
                    speak_enabled=self.speak_enabled,
                    voice_path="overlay_result",
                    input_mode=input_mode,
                    intent=result.intent.value,
                )
                if not self.speak_enabled or decision.overlay_status == "MUTED":
                    speaking = False
                    overlay_branch = "muted"
                elif decision.allowed or decision.session_active:
                    speaking = True
                    overlay_branch = "speaking_allowed"
                elif decision.overlay_status == "TTS BLOCKED":
                    from voice.tool_first_mode import TOOL_MODE_NOTICE

                    summary = f"{TOOL_MODE_NOTICE}\n{summary}"
                    speaking = False
                    overlay_branch = "tool_mode_notice_prepended"
                else:
                    overlay_branch = f"blocked_other:{decision.reason}"
            except Exception as exc:
                overlay_branch = "evaluate_exception_fallback"
                logger.warning(
                    "overlay TTS policy evaluate failed; fallback path: %s",
                    exc,
                    exc_info=True,
                )
                try:
                    from voice.tool_first_mode import TOOL_MODE_NOTICE, can_attempt_tts, is_tool_first_mode
                    from voice.tts_output_policy import conversational_session_has_priority

                    if is_tool_first_mode() and not conversational_session_has_priority():
                        summary = f"{TOOL_MODE_NOTICE}\n{summary}"
                    if is_tool_first_mode():
                        speaking = self.speak_enabled and can_attempt_tts()
                except Exception:
                    pass
            try:
                from voice.tts_policy_trace import log_tts_policy_context

                log_tts_policy_context(
                    stage="notify_overlay_result",
                    speak_enabled=self.speak_enabled,
                    voice_path="overlay_result",
                    input_mode=input_mode,
                    intent=result.intent.value,
                    extra={"overlay_branch": overlay_branch, "speaking": speaking},
                )
            except Exception:
                pass
            notify_overlay_result(
                summary,
                speaking=speaking,
                suggestions=result.next_suggestions,
                intent=result.intent.value,
            )
        except Exception as exc:
            logger.debug("Overlay result notify failed: %s", exc)

    def _maybe_speak_result(self, result: CommandResult, *, input_mode: str = "text") -> None:
        """Speak summary only; failures are warnings, never affect command status."""
        from voice.latency_tracker import mark_tts_failed, mark_tts_pending, mark_tts_skipped, set_tts_ms

        suppress_speech = False
        try:
            from voice.diagnostic_speech import should_skip_result_speech

            suppress_speech = should_skip_result_speech(result)
        except Exception:
            pass

        if not self.speak_enabled:
            mark_tts_skipped("speak_disabled")
            logger.debug("TTS skipped: speak_enabled=false")
            return

        if suppress_speech:
            mark_tts_skipped("skip_speak_flag")
            logger.debug("TTS skipped: skip_speak for intent=%s", result.intent.value)
            return

        try:
            from voice.tts_output_policy import evaluate_tts_output, log_tts_output_decision, notify_overlay_tts_blocked

            decision = evaluate_tts_output(
                speak_enabled=self.speak_enabled,
                voice_path="maybe_speak_result",
                input_mode=input_mode,
                intent=result.intent.value,
            )
            log_tts_output_decision(decision)
            try:
                from voice.tts_policy_trace import log_tts_policy_context

                log_tts_policy_context(
                    stage="maybe_speak_result.after_policy",
                    speak_enabled=self.speak_enabled,
                    voice_path="maybe_speak_result",
                    input_mode=input_mode,
                    intent=result.intent.value,
                    suppress_speech=suppress_speech,
                    decision=decision,
                )
            except Exception:
                pass
            if not decision.allowed:
                mark_tts_skipped(decision.reason)
                notify_overlay_tts_blocked(decision)
                logger.info("TTS blocked: %s", decision.reason)
                return
        except Exception:
            try:
                from voice.tool_first_mode import can_attempt_tts, is_tool_first_mode

                if is_tool_first_mode() and not can_attempt_tts():
                    mark_tts_skipped("tool_first_audio_deferred")
                    logger.debug("TTS skipped: tool-first mode without verified backend")
                    return
            except Exception:
                pass
        import time

        from config import TTS_ASYNC, TTS_FAST_SUMMARY_ENABLED
        from voice.diagnostic_speech import (
            compact_spoken_summary_for_result,
            is_read_only_diagnostic_result,
            speak_compact_diagnostic,
        )
        from voice.tts import first_sentence_for_speech

        if is_read_only_diagnostic_result(result):
            text_to_speak = compact_spoken_summary_for_result(result)
            if not text_to_speak:
                mark_tts_skipped("diagnostic_compact_empty")
                return
            t0 = time.perf_counter()
            try:
                if speak_compact_diagnostic(text_to_speak):
                    set_tts_ms((time.perf_counter() - t0) * 1000.0)
                    logger.debug(
                        "TTS spoke compact diagnostic for intent=%s chars=%s",
                        result.intent.value,
                        len(text_to_speak),
                    )
                else:
                    mark_tts_skipped("diagnostic_direct_failed")
            except Exception as exc:
                mark_tts_failed(str(exc))
                logger.warning("Diagnostic TTS failed: %s", exc)
            return

        text_to_speak = (result.summary or "").strip()
        if TTS_FAST_SUMMARY_ENABLED and result.status == ActionStatus.SUCCESS:
            lead = first_sentence_for_speech(result.summary)
            if lead:
                text_to_speak = lead.strip()

        if not text_to_speak:
            mark_tts_skipped("empty_summary")
            logger.debug("TTS skipped: empty summary for intent=%s", result.intent.value)
            return

        try:
            from conversation.human_runtime import (
                is_human_conversational_runtime_enabled,
                is_session_active,
                speak_result_conversationally,
            )

            if is_human_conversational_runtime_enabled() and is_session_active():
                t0 = time.perf_counter()
                spoken = bool(speak_result_conversationally(result))
                if spoken:
                    set_tts_ms((time.perf_counter() - t0) * 1000.0)
                    try:
                        from voice.tts_output_policy import log_speech_synthesis_started

                        log_speech_synthesis_started(
                            voice_path="maybe_speak_result",
                            provider="conversational",
                        )
                    except Exception:
                        pass
                    logger.debug(
                        "TTS spoke conversational stream for intent=%s",
                        result.intent.value,
                    )
                else:
                    mark_tts_skipped("conversational_stream_empty")
                return
        except Exception as exc:
            logger.debug("Conversational TTS path skipped: %s", exc)

        t0 = time.perf_counter()
        try:
            from voice.diagnostic_speech import speak_compact_diagnostic

            spoken = speak_compact_diagnostic(text_to_speak)
            if not spoken:
                spoken = self.tts.speak(text_to_speak)
            if not spoken:
                mark_tts_skipped("speak_returned_false")
                logger.warning("TTS speak() returned false for intent=%s", result.intent.value)
                return
            if TTS_ASYNC:
                mark_tts_pending()
            else:
                set_tts_ms((time.perf_counter() - t0) * 1000.0)
            logger.debug("TTS spoke summary for intent=%s async=%s", result.intent.value, TTS_ASYNC)
        except TTSError as exc:
            mark_tts_failed(str(exc))
            self.console.print(f"[yellow]TTS warning:[/] {exc}")
            logger.warning("TTS failed: %s", exc)
            if self.runtime.overlay_enabled:
                try:
                    from ui.overlay_app import notify_overlay_error

                    notify_overlay_error(f"TTS: {exc}"[:200])
                except Exception:
                    pass
        except Exception as exc:
            mark_tts_failed(str(exc))
            self.console.print(f"[yellow]TTS warning:[/] {exc}")
            logger.warning("TTS unexpected error: %s", exc)
            if self.runtime.overlay_enabled:
                try:
                    from ui.overlay_app import notify_overlay_error

                    notify_overlay_error(f"TTS: {exc}"[:200])
                except Exception:
                    pass

    def run(self) -> None:
        from ui.console_ui import run_console_loop

        tts_hint = " [bold]TTS on[/]" if self.speak_enabled else ""
        self.console.print(
            Panel(
                f"[bold cyan]JARVIS[/] — text mode{tts_hint}\n"
                "Hebrew/English commands. Type [bold]help[/] or [bold]quit[/].\n"
                "Destructive actions require yes/confirm/כן.\n"
                "Tray: [bold]python main.py --tray[/]",
                title="local_jarvis",
            )
        )
        run_console_loop(self)

    def _print_result(self, result: CommandResult) -> None:
        status_color = {
            ActionStatus.SUCCESS: "green",
            ActionStatus.FAILED: "red",
            ActionStatus.CLARIFICATION_NEEDED: "yellow",
            ActionStatus.CONFIRMATION_REQUIRED: "cyan",
            ActionStatus.NOT_IMPLEMENTED: "magenta",
            ActionStatus.BLOCKED: "red",
        }.get(result.status, "white")

        body = result.summary
        if result.error and result.status == ActionStatus.FAILED:
            body = f"{result.summary}\n[dim]Error: {result.error}[/]"

        self.console.print(
            Panel(
                body,
                title=f"[{status_color}]{result.intent.value}[/] ({result.status.value})",
            )
        )

        if result.next_suggestions:
            self.console.print("[dim]Suggestions:[/]")
            for tip in result.next_suggestions[:4]:
                self.console.print(f"  [dim]• {tip}[/]")

    def _print_help(self) -> None:
        examples = [
            "פתח קרסור / open cursor",
            "פתח את הדאשבורד / open dashboard",
            "תראה שגיאות אחרונות / show last errors",
            "מה אתה יודע לעשות / show capabilities",
            "Tray: python main.py --tray",
        ]
        self.console.print("[bold]Examples:[/]")
        for ex in examples:
            self.console.print(f"  • {ex}")
