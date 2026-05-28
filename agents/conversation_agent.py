"""Conversation Agent — voice, STT, TTS, context (Phase 70 facade)."""

from __future__ import annotations

from agents.base import AgentCapability, AgentId
from core.types import CommandRequest, CommandResult

_AGENT_ID = AgentId.CONVERSATION

_CAPABILITY = AgentCapability(
    agent_id=_AGENT_ID,
    name="Conversation Agent",
    owns=(
        "voice input/output",
        "speech-to-text",
        "text-to-speech",
        "conversation context",
        "wakeword sessions",
        "fast ack / latency hints",
    ),
    runtime_modules=(
        "voice/voice_loop.py",
        "voice/wakeword_loop.py",
        "voice/transcriber.py",
        "voice/tts.py",
        "voice/conversational_runtime.py",
        "voice/real_voice_conversation.py",
        "conversation/context_store.py",
        "conversation/human_runtime.py",
        "assistant/conversation_state.py",
        "actions/voice_audio_actions.py",
        "actions/tts_actions.py",
        "actions/stt_actions.py",
    ),
)


class ConversationAgent:
    """Facade over existing conversation/voice runtimes."""

    agent_id = _AGENT_ID
    capability = _CAPABILITY

    def classify_context(self) -> dict:
        from conversation.context_store import get_classify_context

        return get_classify_context()

    def append_turn(
        self,
        *,
        raw_text: str,
        intent: str,
        status: str,
        summary: str,
        input_mode: str = "text",
    ) -> None:
        from conversation.context_store import append_turn

        append_turn(
            raw_text=raw_text,
            intent=intent,
            status=status,
            summary=summary,
            input_mode=input_mode,
        )

    def transcribe(self, audio_path: str) -> str:
        from voice.transcriber import transcribe_audio

        return transcribe_audio(audio_path)

    def speak(self, text: str) -> bool:
        from voice.tts import TTSService

        return bool(TTSService().speak(text))

    def run_real_voice_test(self) -> tuple[bool, str]:
        from voice.real_voice_conversation import run_real_voice_conversation_test

        return run_real_voice_conversation_test()

    def execute_via_registry(self, request: CommandRequest) -> CommandResult:
        """Delegates to existing ActionRegistry (no new command paths)."""
        from actions.registry import ActionRegistry

        return ActionRegistry().execute(request)


_conversation_agent: ConversationAgent | None = None


def get_conversation_agent() -> ConversationAgent:
    global _conversation_agent
    if _conversation_agent is None:
        _conversation_agent = ConversationAgent()
    return _conversation_agent
