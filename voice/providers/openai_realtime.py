"""OpenAI streaming TTS provider — re-exports canonical implementation."""

from voice.providers.openai_realtime_tts import OpenAIRealtimeProvider, OpenAIRealtimeTtsProvider

__all__ = ["OpenAIRealtimeProvider", "OpenAIRealtimeTtsProvider"]
