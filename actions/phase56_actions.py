"""Phase 56 real-time conversational runtime actions."""

from __future__ import annotations

from actions.base import BaseAction
from assistant.conversation_state import (
    is_continuous_listening,
    record_turn,
    resume_previous_topic,
    set_continuous_listening,
    show_conversation_state,
    summarize_current_conversation,
    what_are_we_discussing,
)
from assistant.engineering_execution import (
    explain_patch_risks,
    propose_engineering_patch,
    simulate_engineering_patch,
    validate_engineering_patch,
)
from assistant.proactive_assistant import show_proactive_suggestions
from assistant.project_intelligence import (
    explain_architecture,
    explain_this_project,
    generate_project_roadmap,
    prepare_investor_summary,
    show_project_intelligence,
)
from core.results import result_success
from core.types import CommandRequest, CommandResult, Intent
from voice.interruption_manager import on_user_speech_detected, resume_interrupted_response
from voice.streaming_pipeline import (
    get_streaming_pipeline,
    phase56_status,
    reset_streaming_pipeline_for_tests,
    show_realtime_runtime,
)


class _ReadOnlyPhase56Action(BaseAction):
    intent: str
    _fn = None

    def execute(self, request: CommandRequest) -> CommandResult:
        del request
        body = self._fn()
        return result_success(Intent(self.intent), body, data={"read_only": True})


class WhatAreWeDiscussingAction(_ReadOnlyPhase56Action):
    intent = Intent.WHAT_ARE_WE_DISCUSSING.value
    _fn = staticmethod(what_are_we_discussing)


class SummarizeCurrentConversationAction(_ReadOnlyPhase56Action):
    intent = Intent.SUMMARIZE_CURRENT_CONVERSATION.value
    _fn = staticmethod(summarize_current_conversation)


class ResumePreviousTopicAction(_ReadOnlyPhase56Action):
    intent = Intent.RESUME_PREVIOUS_TOPIC.value
    _fn = staticmethod(resume_previous_topic)


class ShowConversationStateAction(_ReadOnlyPhase56Action):
    intent = Intent.SHOW_CONVERSATION_STATE.value
    _fn = staticmethod(show_conversation_state)


class ExplainThisProjectAction(_ReadOnlyPhase56Action):
    intent = Intent.EXPLAIN_THIS_PROJECT.value
    _fn = staticmethod(explain_this_project)


class PrepareInvestorSummaryAction(_ReadOnlyPhase56Action):
    intent = Intent.PREPARE_INVESTOR_SUMMARY.value
    _fn = staticmethod(prepare_investor_summary)


class ExplainArchitectureAction(_ReadOnlyPhase56Action):
    intent = Intent.EXPLAIN_ARCHITECTURE.value
    _fn = staticmethod(explain_architecture)


class GenerateProjectRoadmapAction(_ReadOnlyPhase56Action):
    intent = Intent.GENERATE_PROJECT_ROADMAP.value
    _fn = staticmethod(generate_project_roadmap)


class ShowProjectIntelligenceAction(_ReadOnlyPhase56Action):
    intent = Intent.SHOW_PROJECT_INTELLIGENCE.value
    _fn = staticmethod(show_project_intelligence)


class ProposeEngineeringPatchAction(_ReadOnlyPhase56Action):
    intent = Intent.PROPOSE_ENGINEERING_PATCH.value
    _fn = staticmethod(propose_engineering_patch)


class SimulateEngineeringPatchAction(_ReadOnlyPhase56Action):
    intent = Intent.SIMULATE_ENGINEERING_PATCH.value
    _fn = staticmethod(simulate_engineering_patch)


class ValidateEngineeringPatchAction(_ReadOnlyPhase56Action):
    intent = Intent.VALIDATE_ENGINEERING_PATCH.value
    _fn = staticmethod(validate_engineering_patch)


class ExplainPatchRisksAction(_ReadOnlyPhase56Action):
    intent = Intent.EXPLAIN_PATCH_RISKS.value
    _fn = staticmethod(explain_patch_risks)


class ShowProactiveSuggestionsAction(_ReadOnlyPhase56Action):
    intent = Intent.SHOW_PROACTIVE_SUGGESTIONS.value
    _fn = staticmethod(show_proactive_suggestions)


class ShowRealtimeRuntimeAction(_ReadOnlyPhase56Action):
    intent = Intent.SHOW_REALTIME_RUNTIME.value
    _fn = staticmethod(show_realtime_runtime)


class Phase56StatusAction(_ReadOnlyPhase56Action):
    intent = Intent.PHASE56_STATUS.value
    _fn = staticmethod(phase56_status)


class StartContinuousListeningAction(BaseAction):
    intent = Intent.START_CONTINUOUS_LISTENING.value

    def execute(self, request: CommandRequest) -> CommandResult:
        del request
        pipe = get_streaming_pipeline()
        pipe.start()
        set_continuous_listening(True)
        body = (
            "Continuous conversational listening enabled.\n"
            "  streaming pipeline: active\n"
            "  barge-in: enabled when CONV_INTERRUPTION_ENABLED\n"
            "  tip: speak naturally; JARVIS will endpoint on silence."
        )
        return result_success(Intent.START_CONTINUOUS_LISTENING, body)


class StopContinuousListeningAction(BaseAction):
    intent = Intent.STOP_CONTINUOUS_LISTENING.value

    def execute(self, request: CommandRequest) -> CommandResult:
        del request
        pipe = get_streaming_pipeline()
        pipe.stop()
        set_continuous_listening(False)
        active = is_continuous_listening()
        body = f"Continuous listening stopped.\n  active: {'yes' if active else 'no'}"
        return result_success(Intent.STOP_CONTINUOUS_LISTENING, body)


def simulate_barge_in_for_tests(*, speaking_text: str = "Interrupted JARVIS response.") -> str:
    """Test helper: preserve speaking text and simulate user barge-in."""
    from unittest.mock import patch

    from voice.interruption_manager import on_jarvis_speech_started, reset_interruption_manager_for_tests

    reset_interruption_manager_for_tests()
    reset_streaming_pipeline_for_tests()
    on_jarvis_speech_started(speaking_text)
    with patch("voice.speech_controller.barge_in_if_speaking", return_value=True):
        result = on_user_speech_detected(partial_text="user interrupt")
    paused = resume_interrupted_response()
    record_turn(
        raw_text="user interrupt",
        intent="stop_continuous_listening",
        summary=paused or speaking_text,
        input_mode="voice",
    )
    return (
        f"barge_in stopped_tts={result.stopped_tts} "
        f"preserved={result.preserved_response} paused_chars={len(paused or '')}"
    )
