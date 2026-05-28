"""Phase 37e — latency polish (fast ack, fast TTS, async persistence)."""

from __future__ import annotations

import time
from unittest.mock import MagicMock, patch

import pytest

from brain.router import CommandRouter
from config import CONFIRMATION_REQUIRED_INTENTS
from conversation.latency_hints import build_fast_ack, deliver_fast_ack, redact_fast_ack
from core.results import result_success
from core.session import SessionState
from core.types import ActionStatus, CommandRequest, CommandResult, Intent
from reliability.async_persistence import schedule_persistence
from voice.tts import first_sentence_for_speech


@pytest.fixture
def router():
    return CommandRouter(session=SessionState())


def test_fast_ack_after_classify_before_execute(router):
    order: list[str] = []

    def _ack(*_a, **_k):
        order.append("ack")

    def _process(_req):
        order.append("execute")
        return result_success(Intent.SHOW_CAPABILITIES, "Done.")

    with (
        patch("brain.router.classify") as clf,
        patch.object(router, "_emit_fast_ack", side_effect=lambda r, m: (_ack(), order.append("emit"))),
        patch.object(router, "_process", side_effect=_process),
        patch.object(router, "_finalize"),
        patch("conversation.response_enhancer.enhance_command_result", side_effect=lambda _r, res, _m: res),
    ):
        clf.return_value = CommandRequest(
            raw_text="show capabilities",
            intent=Intent.SHOW_CAPABILITIES,
            confidence=0.95,
        )
        router.route("show capabilities")
    assert order.index("emit") < order.index("execute")


def test_confirm_required_ack_message():
    req = CommandRequest(
        raw_text="shutdown jarvis",
        intent=Intent.SHUTDOWN_JARVIS,
        confidence=0.95,
    )
    ack = build_fast_ack(req)
    assert ack == "I need confirmation before doing that."
    assert "shutdown" not in ack.lower() or "confirmation" in ack.lower()


def test_screen_intent_ack():
    req = CommandRequest(raw_text="describe screen", intent=Intent.DESCRIBE_SCREEN, confidence=0.9)
    assert build_fast_ack(req) == "Looking at your screen..."


def test_open_intent_ack():
    req = CommandRequest(raw_text="open chrome", intent=Intent.OPEN_CHROME, confidence=0.9)
    assert build_fast_ack(req) == "Opening..."


def test_fast_ack_redacts_sensitive_text():
    out = redact_fast_ack("password=secret123 token=abc")
    assert "secret123" not in out
    assert "REDACTED" in out or "redacted" in out.lower()


def test_disabled_fast_ack(monkeypatch):
    monkeypatch.setattr("conversation.latency_hints.CONVERSATION_FAST_ACK_ENABLED", False)
    req = CommandRequest(raw_text="x", intent=Intent.SHOW_CAPABILITIES, confidence=0.9)
    assert build_fast_ack(req) == ""


def test_deliver_fast_ack_calls_overlay(monkeypatch):
    monkeypatch.setattr("conversation.latency_hints.CONVERSATION_FAST_ACK_ENABLED", True)
    called: list[str] = []

    def _overlay(text: str, *, intent: str = "") -> None:
        called.append(text)

    with patch("ui.overlay_app.notify_overlay_fast_ack", side_effect=_overlay):
        deliver_fast_ack("Got it — checking...", input_mode="text", speak=False)
    assert called == ["Got it — checking..."]


def test_first_sentence_for_tts():
    text = "Line one is here.\nLine two follows.\nWould you also like me to help?"
    lead = first_sentence_for_speech(text)
    assert lead.startswith("Line one")
    assert "Line two" not in lead


def test_async_persistence_failure_non_fatal(router, monkeypatch):
    monkeypatch.setattr("config.ASYNC_PERSISTENCE_ENABLED", True)
    monkeypatch.setattr("reliability.async_persistence.ASYNC_PERSISTENCE_ENABLED", True)

    def _boom():
        raise OSError("disk full")

    with (
        patch("brain.router.classify") as clf,
        patch.object(router.registry, "execute") as ex,
        patch.object(router, "_emit_fast_ack"),
        patch.object(router, "_finalize", side_effect=_boom),
        patch("conversation.response_enhancer.enhance_command_result", side_effect=lambda _r, res, _m: res),
    ):
        clf.return_value = CommandRequest(
            raw_text="show capabilities",
            intent=Intent.SHOW_CAPABILITIES,
            confidence=0.95,
        )
        ex.return_value = result_success(Intent.SHOW_CAPABILITIES, "OK.")
        result = router.route("show capabilities")
    assert result.status == ActionStatus.SUCCESS
    time.sleep(0.15)


def test_sync_persistence_when_async_disabled(router, monkeypatch):
    monkeypatch.setattr("config.ASYNC_PERSISTENCE_ENABLED", False)
    monkeypatch.setattr("reliability.async_persistence.ASYNC_PERSISTENCE_ENABLED", False)
    finalized: list[str] = []

    def _fin(*_a, **_k):
        finalized.append("yes")

    with (
        patch("brain.router.classify") as clf,
        patch.object(router.registry, "execute") as ex,
        patch.object(router, "_emit_fast_ack"),
        patch.object(router, "_finalize", side_effect=_fin),
        patch("conversation.response_enhancer.enhance_command_result", side_effect=lambda _r, res, _m: res),
    ):
        clf.return_value = CommandRequest(
            raw_text="x",
            intent=Intent.SHOW_CAPABILITIES,
            confidence=0.9,
        )
        ex.return_value = result_success(Intent.SHOW_CAPABILITIES, "OK.")
        router.route("x")
    assert finalized == ["yes"]


def test_tts_fast_summary_flag_exists(monkeypatch):
    from config import TTS_FAST_SUMMARY_ENABLED

    assert TTS_FAST_SUMMARY_ENABLED is True or TTS_FAST_SUMMARY_ENABLED is False


def test_confirm_intent_in_required_set():
    assert Intent.SHUTDOWN_JARVIS.value in CONFIRMATION_REQUIRED_INTENTS
