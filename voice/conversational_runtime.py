"""Phase 61 conversational runtime execution helpers."""

from __future__ import annotations

import time


def promote_wakeword_session(app: object) -> str:
    try:
        from conversation.human_runtime import run_human_conversation_session

        run_human_conversation_session(app=app)
        return "wakeword session promoted to continuous conversational runtime"
    except Exception as exc:
        return f"wakeword promotion failed: {exc}"


def recover_conversation_timeout(*, timeout_seconds: float = 45.0) -> str:
    try:
        from conversation.human_runtime import end_session, start_session

        end_session(reason="timeout_recovery")
        time.sleep(0.05)
        start_session(timeout_seconds=timeout_seconds)
        return "conversation timeout recovered"
    except Exception as exc:
        return f"conversation timeout recovery failed: {exc}"


def barge_in_cancel() -> bool:
    try:
        from voice.speech_controller import barge_in_if_speaking

        return bool(barge_in_if_speaking())
    except Exception:
        return False

