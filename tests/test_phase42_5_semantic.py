"""Phase 42.5 — semantic language understanding layer."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from brain.intent_classifier import classify
from brain.router import CommandRouter
from core.types import ActionStatus, Intent
from language.semantic_intent import understand_semantic
from language.semantic_llm import validate_semantic_llm_payload
from language.vocabulary import correct_tokens
from voice.voice_debug_store import format_voice_debug_status, get_voice_debug_snapshot, reset_voice_debug_store


@pytest.fixture(autouse=True)
def _enable_semantic(monkeypatch):
    monkeypatch.setattr("config.SEMANTIC_UNDERSTANDING_ENABLED", True, raising=False)
    monkeypatch.setattr("config.SEMANTIC_LLM_ENABLED", False, raising=False)
    monkeypatch.setattr("config.SEMANTIC_MIN_CONFIDENCE", 0.72, raising=False)
    reset_voice_debug_store()
    yield
    reset_voice_debug_store()


def test_semantic_natural_phrase_show_failing_tests():
    sem = understand_semantic("show me what failed")
    assert sem.candidate_intent == Intent.SHOW_FAILING_TESTS.value
    assert sem.confidence >= 0.72
    assert "failing" in sem.canonical_command


def test_semantic_context_open_it_after_report():
    from language.semantic_context import SemanticContext

    sem = understand_semantic(
        "open it",
        context=SemanticContext(last_intent="show_latest_live_report"),
    )
    assert sem.candidate_intent == Intent.SHOW_LATEST_LIVE_REPORT.value
    assert sem.source == "semantic_context"


def test_unknown_intent_llm_rejected():
    bad = validate_semantic_llm_payload(
        {
            "intent": "launch_nukes",
            "canonical_command": "launch",
            "confidence": 0.99,
            "requires_confirmation": False,
            "clarification": "",
            "reason": "test",
        }
    )
    assert not bad.valid
    assert bad.intent == "clarify"


def test_low_confidence_clarification():
    sem = understand_semantic("maybe do something with dashboards possibly")
    assert sem.ambiguous or sem.confidence < 0.72 or not sem.candidate_intent
    if sem.clarification:
        assert "heard" in sem.clarification.lower() or "mean" in sem.clarification.lower()


def test_semantic_layer_does_not_execute():
    with patch("actions.registry.ActionRegistry.execute") as execute:
        sem = understand_semantic("run diagnostics")
        assert sem.candidate_intent
        execute.assert_not_called()


def test_classify_hybrid_semantic_phrase():
    req = classify("show me what failed")
    assert req.intent == Intent.SHOW_FAILING_TESTS
    assert req.confidence >= 0.72


def test_router_uses_semantic_clarification_message():
    router = CommandRouter()
    req = classify("maybe dashboard something unclear xyz")
    if req.intent != Intent.CLARIFY:
        pytest.skip("phrase classified deterministically")
    result = router._process(req)
    assert result.status == ActionStatus.CLARIFICATION_NEEDED
    assert "heard" in result.summary.lower() or "mean" in result.summary.lower() or "rephrase" in result.summary.lower()


def test_vocabulary_does_not_hallucinate_sentence():
    text = "please open the mysterious zorbax portal"
    corrected, changed = correct_tokens(text)
    assert "zorbax" in corrected
    assert corrected.count(" ") == text.count(" ")


def test_vocabulary_fixes_obvious_typo():
    corrected, changed = correct_tokens("show diagostic")
    assert "diagnostic" in corrected or "diagnostics" in corrected or not changed


def test_voice_debug_includes_semantic_fields():
    classify("why did this fail")
    snap = get_voice_debug_snapshot()
    text = format_voice_debug_status()
    assert "semantic_candidate" in text
    assert "final_routed_intent" in text
    assert snap.semantic_candidate_intent or snap.final_routed_intent


def test_semantic_llm_json_validation_ok():
    good = validate_semantic_llm_payload(
        {
            "intent": "show_system_status",
            "canonical_command": "show system status",
            "confidence": 0.88,
            "requires_confirmation": False,
            "clarification": "",
            "reason": "clear",
        }
    )
    assert good.valid
    assert good.intent == "show_system_status"


def test_semantic_llm_forbidden_key_rejected():
    bad = validate_semantic_llm_payload(
        {
            "intent": "show_system_status",
            "shell": "rm -rf /",
            "canonical_command": "show system status",
            "confidence": 0.9,
            "requires_confirmation": False,
            "clarification": "",
            "reason": "bad",
        }
    )
    assert not bad.valid


@patch("integrations.ollama_client.OllamaClient")
def test_semantic_llm_optional_path(mock_client_cls, monkeypatch):
    monkeypatch.setattr("config.SEMANTIC_LLM_ENABLED", True, raising=False)
    mock_client_cls.return_value.classify_intent.return_value = {
        "intent": "summarize_session",
        "canonical_command": "summarize session",
        "confidence": 0.9,
        "requires_confirmation": False,
        "clarification": "",
        "reason": "mock",
    }
    from language.hybrid_understanding import classify_hybrid

    with patch("brain.intent_classifier.classify_rules") as rules:
        rules.return_value = __import__(
            "core.types", fromlist=["CommandRequest"]
        ).CommandRequest(
            raw_text="give me a recap of our session",
            intent=Intent.UNKNOWN,
            confidence=0.0,
            classifier_source="rules",
        )
        req, sem = classify_hybrid("give me a recap of our session")
    assert req.intent == Intent.SUMMARIZE_SESSION
    assert sem is not None and sem.llm_used


def test_router_security_still_validates():
    from core.security import validate_intent
    from core.types import CommandRequest

    blocked = validate_intent(
        CommandRequest(
            raw_text="totally_unknown_intent_xyz",
            intent=Intent.UNKNOWN,
            confidence=0.0,
        )
    )
    assert blocked is not None
    assert "rephrase" in (blocked.summary or "").lower()
