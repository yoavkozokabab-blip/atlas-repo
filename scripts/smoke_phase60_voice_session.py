"""Phase 60 smoke: wakeword -> question -> follow-up -> stop listening."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from conversation.human_runtime import run_human_conversation_session
from core.types import CommandRequest, Intent
from voice.streaming_stt.stream_session import StreamingSttResult


class _App:
    session = None

    def handle_text_command(self, raw_text, **kwargs):
        del kwargs
        from core.results import result_success

        return result_success(Intent.UNKNOWN, f"Handled: {raw_text}")


def _turn(text: str, partials: int = 1) -> StreamingSttResult:
    return StreamingSttResult(
        text=text,
        partial_updates=partials,
        decode_ms=12.0,
        record_seconds=1.0,
        endpoint_silence_ms=1200.0,
    )


def main() -> None:
    queue = [_turn("what is today's top priority"), _turn("and what should i do next"), _turn("stop listening", 0)]

    def _capture(**kwargs):
        on_partial = kwargs.get("on_partial")
        item = queue.pop(0) if queue else _turn("", 0)
        if on_partial and item.partial_updates:
            on_partial("partial")
        return item

    with patch("voice.continuous_mic.capture_turn", side_effect=_capture), patch(
        "conversation.human_runtime.handle_conversational_turn",
        return_value={"text": "ok", "provider": "mock_provider"},
    ), patch(
        "conversation.llm_streaming.speak_streaming_response",
        return_value="mock_provider",
    ):
        result = run_human_conversation_session(app=_App())
    assert int(result.get("turns", 0)) >= 2, result
    print("OK Phase60 smoke wakeword->followup->stop")


if __name__ == "__main__":
    main()

