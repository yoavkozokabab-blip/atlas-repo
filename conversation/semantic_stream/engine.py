"""Semantic streaming conversation engine orchestrator."""

from __future__ import annotations

import time
from dataclasses import dataclass, field

import config as cfg
from conversation.semantic_stream.action_planner import ActionPlan, build_action_plan
from conversation.semantic_stream.confidence_tracker import ConfidenceTimeline, record_confidence
from conversation.semantic_stream.conversation_graph import (
    record_intent_candidate,
    record_utterance_partial,
    reset_conversation_graph,
)
from conversation.semantic_stream.correction_handler import apply_realtime_correction
from conversation.semantic_stream.interruption_handler import (
    InterruptionEvent,
    handle_streaming_interruption,
)
from conversation.semantic_stream.multi_intent import MultiIntentPlan, decompose_utterance
from conversation.semantic_stream.profiling import BudgetTimer, StreamSemanticProfile
from conversation.semantic_stream.reformulation import reformulate_with_context
from conversation.semantic_stream.turn_taking import TurnPhase, get_turn_state, reset_turn_state
from core.logger import setup_logger

logger = setup_logger("jarvis.conversation.semantic_stream")

_last_snapshot: "ConversationStreamSnapshot | None" = None
_last_partial_processed_at: float = 0.0
_previous_partial: str = ""


@dataclass
class ConversationStreamSnapshot:
    partial_text: str = ""
    reformulated_text: str = ""
    correction_applied: bool = False
    primary_intent: str = ""
    confidence: float = 0.0
    confidence_stable: bool = False
    multi_intent: MultiIntentPlan | None = None
    action_plan: ActionPlan | None = None
    turn_phase: str = ""
    interrupted: bool = False
    profile: StreamSemanticProfile | None = None
    planned_actions: tuple[str, ...] = ()
    graph_turn: int = 0


def get_last_stream_snapshot() -> ConversationStreamSnapshot | None:
    return _last_snapshot


def reset_conversation_stream() -> None:
    global _last_snapshot, _last_partial_processed_at, _previous_partial
    reset_conversation_graph()
    reset_turn_state()
    from conversation.semantic_stream.confidence_tracker import reset_confidence_tracker
    from conversation.semantic_stream.profiling import reset_profiles

    reset_confidence_tracker()
    reset_profiles()
    _last_snapshot = None
    _last_partial_processed_at = 0.0
    _previous_partial = ""


def on_partial_transcript(
    partial_text: str,
    *,
    session_context: object | None = None,
    speech_detected: bool = False,
    is_final: bool = False,
) -> ConversationStreamSnapshot:
    """
    Realtime semantic parse during speech. Never executes — planning/classify only.
    """
    global _last_snapshot, _last_partial_processed_at, _previous_partial

    if not cfg.CONVERSATION_SEMANTIC_STREAM_ENABLED:
        snap = ConversationStreamSnapshot(partial_text=partial_text)
        _last_snapshot = snap
        return snap

    now = time.monotonic()
    min_gap = max(0.04, cfg.CONV_SEMANTIC_UPDATE_MIN_MS / 1000.0)
    if not is_final and (now - _last_partial_processed_at) < min_gap:
        return _last_snapshot or ConversationStreamSnapshot(partial_text=partial_text)
    _last_partial_processed_at = now

    if cfg.CONV_INTERRUPTION_ENABLED:
        interrupt = handle_streaming_interruption(speech_detected=speech_detected)
    else:
        turn_idle = get_turn_state()
        interrupt = InterruptionEvent(
            detected=False,
            barge_in_triggered=False,
            turn_phase=turn_idle.phase.value,
        )
    turn = get_turn_state()
    if speech_detected or partial_text.strip():
        turn.on_partial()

    snap = ConversationStreamSnapshot(partial_text=partial_text)
    with BudgetTimer() as timer:
        if cfg.CONV_CORRECTION_ENABLED:
            corrected = apply_realtime_correction(
                partial_text,
                previous_text=_previous_partial,
            )
        else:
            from conversation.semantic_stream.correction_handler import CorrectionResult

            corrected = CorrectionResult(applied=False, stripped_text=partial_text)
        timer.correction_ms = 0.0
        if cfg.CONV_REFORMULATION_ENABLED:
            reformulated, ref_reason = reformulate_with_context(corrected.stripped_text)
        else:
            reformulated, ref_reason = corrected.stripped_text, ""
        snap.correction_applied = corrected.applied
        snap.reformulated_text = reformulated

        try:
            from language.semantic_context import build_semantic_context
            from language.semantic_intent import understand_semantic

            sem_ctx = build_semantic_context(session_context)
            sem = understand_semantic(
                partial_text,
                normalized=reformulated,
                context=sem_ctx,
            )
            timer.mark_parse_done()
            intent = sem.candidate_intent or ""
            conf = sem.confidence
            if sem.meets_threshold() and cfg.CONV_CONTEXT_CARRY_ENABLED:
                record_intent_candidate(intent, confidence=conf, source=sem.source)
        except Exception as exc:
            logger.debug("semantic stream parse: %s", exc)
            intent = ""
            conf = 0.0

        if not intent:
            try:
                from voice.streaming_stt.intent_prefetch import prefetch_intent

                pf = prefetch_intent(reformulated, session_context=session_context)
                if pf is not None:
                    intent = pf.intent
                    conf = pf.confidence
                    if cfg.CONV_CONTEXT_CARRY_ENABLED:
                        record_intent_candidate(intent, confidence=conf, source="prefetch")
            except Exception:
                pass

        timeline: ConfidenceTimeline = record_confidence(
            intent=intent,
            confidence=conf,
            partial_text=reformulated,
        )
        snap.primary_intent = timeline.latest_intent
        snap.confidence = timeline.latest_confidence
        snap.confidence_stable = timeline.stable

        if cfg.CONV_MULTI_INTENT_ENABLED:
            snap.multi_intent = decompose_utterance(reformulated)
        if cfg.CONV_ACTION_PLAN_ENABLED:
            snap.action_plan = build_action_plan(
                reformulated,
                session_context=session_context,
            )
            if snap.action_plan.actions:
                snap.planned_actions = tuple(a.intent for a in snap.action_plan.actions)
        timer.mark_plan_done()

        if cfg.CONV_CONTEXT_CARRY_ENABLED:
            record_utterance_partial(
                reformulated,
                confidence=conf,
                is_final=is_final,
            )
        if is_final:
            turn.on_endpoint()

        snap.turn_phase = turn.phase.value
        snap.interrupted = interrupt.detected
        from conversation.semantic_stream.conversation_graph import get_conversation_graph

        snap.graph_turn = get_conversation_graph().turn_index
        snap.profile = timer.finish(
            partial_len=len(reformulated),
            intent=snap.primary_intent,
            confidence=snap.confidence,
        )

    _previous_partial = partial_text
    _last_snapshot = snap

    try:
        from voice.streaming_stt.realtime_metrics import RealtimeSttMetrics, get_realtime_metrics, publish_metrics

        base = get_realtime_metrics()
        merged = RealtimeSttMetrics(
            partial_interval_ms=base.partial_interval_ms if base else 100.0,
            last_partial_ms=snap.profile.total_ms if snap.profile else 0.0,
            last_decode_ms=base.last_decode_ms if base else 0.0,
            buffer_seconds=base.buffer_seconds if base else 0.0,
            partial_count=base.partial_count if base else 0,
            prefetch_intent=snap.primary_intent,
            prefetch_confidence=snap.confidence,
            stream_active=True,
            gpu_first=bool(cfg.STT_STREAM_GPU_FIRST),
        )
        publish_metrics(merged)
    except Exception:
        pass

    try:
        from ui.overlay_app import notify_overlay_conversation_stream

        notify_overlay_conversation_stream(snap)
    except Exception:
        pass

    if snap.profile and snap.profile.over_budget:
        logger.warning(
            "semantic stream over budget %.0fms > %.0fms intent=%s",
            snap.profile.total_ms,
            snap.profile.budget_ms,
            snap.primary_intent,
        )

    return snap


def on_jarvis_speaking_start() -> None:
    get_turn_state().on_jarvis_speak_start()


def on_jarvis_speaking_end() -> None:
    get_turn_state().on_jarvis_speak_end()
