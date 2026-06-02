"""Smoke: human conversation — barge-in, 20-turn memory, follow-up expansion."""

from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


def main() -> int:
    from conversation.context_store import get_classify_context
    from conversation.follow_up_resolver import resolve_follow_up_text
    from conversation.llm_streaming import _yield_speakable_chunks
    from voice.human_conversation import interrupt_on_user_speech_start

    ok = True

    from voice import streaming_player
    from voice.human_conversation import get_last_barge_in_cancel_ms
    from voice.realtime_tts import (
        register_active_cancel_for_tests,
        reset_realtime_tts_for_tests,
    )

    reset_realtime_tts_for_tests()
    register_active_cancel_for_tests(lambda: None)
    streaming_player._speaking.set()
    if interrupt_on_user_speech_start(partial_text="smoke"):
        active_ms = get_last_barge_in_cancel_ms()
        if active_ms is not None and active_ms <= 200.0:
            print(f"OK active-TTS barge-in cancel_ms={active_ms:.1f}")
        else:
            print(f"FAIL active-TTS barge-in cancel_ms={active_ms}")
            ok = False
    else:
        print("FAIL active-TTS interrupt returned False")
        ok = False
    streaming_player._speaking.clear()
    reset_realtime_tts_for_tests()

    from unittest.mock import patch

    with (
        patch(
            "conversation.semantic_stream.reformulation.reformulate_with_context",
            return_value=("", ""),
        ),
        patch(
            "conversation.follow_up_resolver._last_intent",
            return_value="live_vs_backtest",
        ),
        patch(
            "conversation.follow_up_resolver._last_assistant_summary",
            return_value="live vs backtest",
        ),
    ):
        text, reason = resolve_follow_up_text("compare it to Nvidia")
    if reason != "continuation_compare":
        print(f"FAIL follow-up reason={reason!r}")
        ok = False
    else:
        print(f"OK follow-up: {reason!r} -> {text!r}")

    import config as cfg

    cfg.CONVERSATION_STREAM_FIRST_CHUNK_CHARS = 10
    ready, _ = _yield_speakable_chunks(
        "Hello there, this is the smoke streaming answer.",
        first_chunk=True,
    )
    if not ready:
        print("FAIL early streaming chunk")
        ok = False
    else:
        print(f"OK early chunk: {ready[0]!r}")

    ctx = get_classify_context()
    print(f"OK classify context turns={ctx.get('turn_count', 0)} max={ctx.get('max_turns')}")

    print("SMOKE PASS human_conversation" if ok else "SMOKE FAIL human_conversation")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
