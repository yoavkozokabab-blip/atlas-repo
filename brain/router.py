"""Command router: classify → validate → confirm → execute → log."""

from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path

from config import (
    COMMAND_HISTORY_PATH,
    CONFIDENCE_THRESHOLD,
    CONFIRMATION_REQUIRED_INTENTS,
    SESSION_MEMORY_ENABLED,
    SESSION_SUMMARY_EVERY_N,
    WORKSPACE_AWARENESS_ENABLED,
)
from actions.registry import ActionRegistry
from brain.aliases import resolve_alias
from brain.command_parser import enrich_request, resolve_follow_up
from brain.intent_classifier import classify
from core import confirmation
from core.results import result_confirmation_required, result_failed
from core.security import validate_intent
from core.session import SessionState
from core.types import ActionStatus, CommandRequest, CommandResult, Intent

from core.logger import setup_logger

logger = setup_logger("jarvis.router")


class CommandRouter:
    """Central pipeline for text commands."""

    def __init__(
        self,
        registry: ActionRegistry | None = None,
        session: SessionState | None = None,
    ) -> None:
        self.registry = registry or ActionRegistry()
        self.session = session or SessionState.load()
        self._command_count = 0
        COMMAND_HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)

    def route(
        self,
        text: str,
        *,
        input_mode: str = "text",
        transcribed_text: str | None = None,
    ) -> CommandResult:
        """Route user text through the full pipeline."""
        started = time.perf_counter()
        log_meta = {"input_mode": input_mode, "transcribed_text": transcribed_text}

        if confirmation.is_confirm_phrase(text):
            result = self._handle_confirmation_yes(text)
            return self._complete(
                result,
                CommandRequest(raw_text=text),
                started,
                log_meta=log_meta,
            )

        if confirmation.is_cancel_phrase(text):
            result = self._handle_confirmation_no()
            return self._complete(
                result,
                CommandRequest(raw_text=text),
                started,
                log_meta=log_meta,
            )

        alias_request = resolve_alias(text)
        if alias_request is not None:
            request = enrich_request(alias_request)
            return self._run_classified_pipeline(
                request, started, log_meta=log_meta, classified=True
            )

        follow = resolve_follow_up(text, self.session)
        if follow is not None:
            request = enrich_request(follow)
            return self._run_classified_pipeline(
                request, started, log_meta=log_meta, classified=True
            )

        track_voice_latency = input_mode in ("voice", "wakeword")
        t_classify = time.perf_counter()
        request = classify(text, session_context=self.session)
        classify_ms = (time.perf_counter() - t_classify) * 1000.0
        request = enrich_request(request)
        if track_voice_latency:
            try:
                from voice.latency_tracker import set_route_timing

                set_route_timing(classify_ms=classify_ms, execute_ms=0.0, intent=request.intent.value)
            except Exception:
                pass
        return self._run_classified_pipeline(
            request,
            started,
            log_meta=log_meta,
            classified=True,
            track_voice_latency=track_voice_latency,
            classify_ms=classify_ms,
        )

    def _run_classified_pipeline(
        self,
        request: CommandRequest,
        started: float,
        *,
        log_meta: dict | None = None,
        classified: bool = False,
        track_voice_latency: bool = False,
        classify_ms: float = 0.0,
    ) -> CommandResult:
        """Fast ack after classification, then security/confirm/execute."""
        if classified:
            self._emit_fast_ack(request, log_meta or {})
        guard_result = self._apply_voice_guard(request, log_meta or {})
        if guard_result is not None:
            return self._complete(guard_result, request, started, log_meta=log_meta)
        t_execute = time.perf_counter()
        result = self._process(request)
        execute_ms = (time.perf_counter() - t_execute) * 1000.0
        if track_voice_latency:
            try:
                from voice.latency_tracker import mark_first_response, set_route_timing

                set_route_timing(
                    classify_ms=classify_ms,
                    execute_ms=execute_ms,
                    intent=request.intent.value,
                )
                mark_first_response()
            except Exception:
                pass
        return self._complete(result, request, started, log_meta=log_meta)

    def _emit_fast_ack(self, request: CommandRequest, log_meta: dict) -> None:
        try:
            from conversation.latency_hints import build_fast_ack, deliver_fast_ack

            ack = build_fast_ack(request)
            if not ack:
                return
            log_meta["fast_ack"] = ack[:120]
            try:
                import config as cfg

                speak_ack = not getattr(cfg, "VOICE_LATENCY_INSTANT", False)
            except Exception:
                speak_ack = True
            deliver_fast_ack(
                ack,
                input_mode=str(log_meta.get("input_mode", "text")),
                speak=speak_ack,
                intent=request.intent.value,
            )
        except Exception as exc:
            logger.debug("Fast ack skipped: %s", exc)

    def _apply_voice_guard(
        self,
        request: CommandRequest,
        log_meta: dict,
    ) -> CommandResult | None:
        input_mode = str(log_meta.get("input_mode", "text"))
        if input_mode not in ("voice", "wakeword"):
            return None
        try:
            from voice.voice_command_guard import evaluate_voice_command
        except Exception:
            return None

        decision = evaluate_voice_command(request, input_mode=input_mode)
        if decision is None:
            return None
        if decision.blocked:
            from core.results import result_blocked, result_clarification

            if decision.reason == "filler_transcript":
                return result_blocked(
                    request.intent,
                    "I didn't catch a command — still listening.",
                )
            return result_clarification(
                request.intent,
                "I didn't catch a clear command. Please say what you'd like me to do.",
            )
        if decision.requires_confirmation and not request.confirmed:
            cid = confirmation.create_confirmation(
                request.intent.value,
                {
                    "raw_text": request.raw_text,
                    "params": request.params,
                },
            )
            self._record_approval_inbox(cid, request)
            self.session.set_pending_confirmation(cid, request.intent.value)
            msg = decision.confirmation_message or (
                f"'{request.intent.value}' requires confirmation."
            )
            return result_confirmation_required(
                request.intent,
                f"{msg} Reply yes/confirm or no/cancel (id: {cid}).",
                cid,
            )
        return None

    def _complete(
        self,
        result: CommandResult,
        request: CommandRequest,
        started: float,
        *,
        log_meta: dict | None = None,
    ) -> CommandResult:
        """Phase 37 — enhance response, persist context, log (same return path)."""
        if isinstance(result, CommandResult):
            try:
                from conversation.response_enhancer import enhance_command_result

                result = enhance_command_result(request, result, log_meta)
            except Exception as exc:
                logger.debug("Conversation enhance skipped: %s", exc)
        meta = log_meta or {}

        def _persist() -> None:
            self._finalize(result, request, started, log_meta=meta)

        try:
            from reliability.async_persistence import schedule_persistence

            schedule_persistence(_persist)
        except Exception as exc:
            logger.debug("Async persistence schedule failed: %s", exc)
            _persist()
        return result

    def _handle_confirmation_yes(self, text: str) -> CommandResult:
        pending = confirmation.get_pending_confirmation()
        if pending is None:
            return result_failed(
                Intent.UNKNOWN,
                "No pending action to confirm.",
            )
        confirmed = confirmation.confirm(pending.confirmation_id)
        self._sync_inbox_status(pending.confirmation_id, "completed")
        if confirmed is None:
            return result_failed(
                Intent.UNKNOWN,
                "Confirmation expired or invalid. Please repeat the command.",
            )
        self.session.clear_pending_confirmation()
        intent = Intent(confirmed.action_name)
        request = CommandRequest(
            raw_text=confirmed.payload.get("raw_text", text),
            intent=intent,
            confidence=1.0,
            params=confirmed.payload.get("params", {}),
            confirmed=True,
            confirmation_id=confirmed.confirmation_id,
        )
        request = enrich_request(request)
        return self._process(request, skip_confirmation=True)

    def _handle_confirmation_no(self) -> CommandResult:
        pending = confirmation.get_pending_confirmation()
        if pending:
            confirmation.cancel(pending.confirmation_id)
            self._sync_inbox_status(pending.confirmation_id, "rejected")
        self.session.clear_pending_confirmation()
        return CommandResult(
            intent=Intent.UNKNOWN,
            status=ActionStatus.SUCCESS,
            summary="Action cancelled.",
        )

    def _process(
        self,
        request: CommandRequest,
        *,
        skip_confirmation: bool = False,
    ) -> CommandResult:
        logger.info(
            "classified intent=%s confidence=%.2f text=%r",
            request.intent.value,
            request.confidence,
            request.raw_text[:80],
        )

        if (
            request.confidence < CONFIDENCE_THRESHOLD
            and request.intent not in (Intent.UNKNOWN, Intent.CLARIFY)
        ):
            request = request.model_copy(update={"intent": Intent.CLARIFY})

        security_result = validate_intent(request)
        if security_result is not None:
            return security_result

        try:
            from alpha.safety import check_alpha_safety, intent_requires_alpha_approval

            alpha_block = check_alpha_safety(request)
            if alpha_block is not None:
                return alpha_block
            alpha_extra_confirm = (
                not skip_confirmation
                and intent_requires_alpha_approval(request.intent.value)
                and not request.confirmed
            )
        except Exception:
            alpha_extra_confirm = False

        if (
            not skip_confirmation
            and (
                request.intent.value in CONFIRMATION_REQUIRED_INTENTS
                or alpha_extra_confirm
            )
            and not request.confirmed
        ):
            cid = confirmation.create_confirmation(
                request.intent.value,
                {
                    "raw_text": request.raw_text,
                    "params": request.params,
                },
            )
            self._record_approval_inbox(cid, request)
            self.session.set_pending_confirmation(cid, request.intent.value)
            return result_confirmation_required(
                request.intent,
                f"'{request.intent.value}' requires confirmation. "
                f"Reply yes/confirm/כן (id: {cid}) or no/cancel/לא.",
                cid,
            )

        return self.registry.execute(request)

    def _finalize(
        self,
        result: CommandResult,
        request: CommandRequest,
        started: float,
        *,
        log_meta: dict | None = None,
    ) -> None:
        duration_ms = int((time.perf_counter() - started) * 1000)
        self._log_command(request, result, duration_ms, log_meta=log_meta or {})
        self._audit_command(request, result, duration_ms, log_meta=log_meta or {})
        try:
            from alpha.session_log import log_alpha_command

            log_alpha_command(request, result, latency_ms=duration_ms, log_meta=log_meta or {})
        except Exception:
            pass
        self.session.update_from_result(
            raw_text=request.raw_text,
            intent=result.intent.value,
            summary=result.summary,
            data=result.data,
        )
        self.session.save()
        try:
            from conversation.context_store import append_turn

            append_turn(
                raw_text=request.raw_text,
                intent=result.intent.value,
                status=result.status.value,
                summary=result.summary,
                input_mode=(log_meta or {}).get("input_mode", "text"),
            )
        except Exception as exc:
            logger.debug("Conversation append_turn skipped: %s", exc)
        try:
            from assistant.conversation_state import record_turn

            record_turn(
                raw_text=request.raw_text,
                intent=result.intent.value,
                summary=result.summary,
                status=result.status.value,
                input_mode=(log_meta or {}).get("input_mode", "text"),
            )
        except Exception as exc:
            logger.debug("Conversation state record_turn skipped: %s", exc)
        if WORKSPACE_AWARENESS_ENABLED:
            try:
                from operating.workspace_context import refresh_workspace_context

                refresh_workspace_context(self.session)
            except Exception as exc:
                logger.debug("Workspace refresh skipped: %s", exc)
        if SESSION_MEMORY_ENABLED:
            try:
                from memory.session_memory import append_session_event, persist_session_summary

                append_session_event(
                    result.intent.value,
                    result.status.value,
                    result.summary,
                )
                try:
                    from memory.task_memory import record_command

                    record_command(result.intent.value, result.summary)
                except Exception:
                    pass
                self._command_count += 1
                if SESSION_SUMMARY_EVERY_N > 0 and self._command_count % SESSION_SUMMARY_EVERY_N == 0:
                    persist_session_summary()
            except Exception as exc:
                logger.debug("Session memory hook skipped: %s", exc)

    def _log_command(
        self,
        request: CommandRequest,
        result: CommandResult,
        duration_ms: int,
        *,
        log_meta: dict | None = None,
    ) -> None:
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "raw_text": request.raw_text,
            "intent": request.intent.value,
            "confidence": request.confidence,
            "status": result.status.value,
            "summary": result.summary[:500],
            "requires_confirmation": result.requires_confirmation,
            "error": result.error,
            "duration_ms": duration_ms,
            "input_mode": (log_meta or {}).get("input_mode", "text"),
            "classifier_source": getattr(request, "classifier_source", "rules"),
        }
        transcribed = (log_meta or {}).get("transcribed_text")
        if transcribed:
            entry["transcribed_text"] = str(transcribed)[:500]
        try:
            with Path(COMMAND_HISTORY_PATH).open("a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except OSError as exc:
            logger.warning("Failed to write command history: %s", exc)

    def _record_approval_inbox(self, confirmation_id: str, request: CommandRequest) -> None:
        try:
            from approvals.inbox import record_pending_approval

            record_pending_approval(
                confirmation_id,
                request,
                summary=f"{request.intent.value} requires confirmation.",
            )
        except Exception as exc:
            logger.debug("Approval inbox record skipped: %s", exc)

    def _sync_inbox_status(self, confirmation_id: str, status: str) -> None:
        try:
            from approvals.inbox import update_by_confirmation_id

            update_by_confirmation_id(confirmation_id, status)
        except Exception as exc:
            logger.debug("Approval inbox sync skipped: %s", exc)

    def _audit_command(
        self,
        request: CommandRequest,
        result: CommandResult,
        duration_ms: int,
        *,
        log_meta: dict | None = None,
    ) -> None:
        """Append redacted audit entry; failures must not affect the command."""
        try:
            from diagnostics.command_audit import append_audit_event

            if not append_audit_event(
                request, result, duration_ms, log_meta=log_meta or {}
            ):
                logger.debug("Command audit append returned false")
        except Exception as exc:
            logger.debug("Command audit skipped: %s", exc)
