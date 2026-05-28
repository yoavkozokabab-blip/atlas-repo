"""LLM intent classifier tests (mocked Ollama)."""

import json
from unittest.mock import MagicMock, patch

import pytest

from brain.intent_classifier import classify, classify_rules
from brain.llm_intent_classifier import (
    LLMIntentClassifier,
    validate_llm_payload,
)
from core.types import Intent
from integrations.ollama_client import OllamaError


def _mock_client(payload: dict) -> MagicMock:
    client = MagicMock()
    client.classify_intent.return_value = payload
    return client


def test_valid_llm_intent_accepted():
    payload = {
        "intent": "show_last_errors",
        "confidence": 0.86,
        "params": {},
        "reason": "user wants errors",
    }
    ic = validate_llm_payload(payload)
    assert ic.valid
    assert ic.intent == "show_last_errors"
    assert ic.confidence == 0.86


def test_unknown_intent_rejected():
    payload = {
        "intent": "delete_all_files",
        "confidence": 0.99,
        "params": {},
    }
    ic = validate_llm_payload(payload)
    assert not ic.valid
    assert ic.intent == Intent.CLARIFY.value


def test_forbidden_shell_key_rejected():
    payload = {
        "intent": "show_last_errors",
        "confidence": 0.9,
        "params": {},
        "shell": "rm -rf /",
    }
    ic = validate_llm_payload(payload)
    assert not ic.valid


def test_low_confidence_rejected():
    payload = {
        "intent": "open_cursor",
        "confidence": 0.4,
        "params": {},
    }
    ic = validate_llm_payload(payload)
    assert not ic.valid


def test_malformed_json_from_ollama():
    client = MagicMock()
    client.classify_intent.side_effect = OllamaError("Could not parse JSON")
    llm = LLMIntentClassifier(client=client)
    ic = llm.classify("something vague maybe")
    assert not ic.valid


def test_ollama_unavailable_falls_back(monkeypatch):
    from core.types import IntentClassification

    monkeypatch.setattr("brain.intent_classifier.LLM_CLASSIFIER_ENABLED", True)
    monkeypatch.setattr("brain.intent_classifier.LLM_FALLBACK_TO_RULES", True)

    invalid = IntentClassification(
        intent=Intent.CLARIFY.value,
        confidence=0.0,
        reason="down",
        classifier_source="clarification",
        valid=False,
    )
    with patch("brain.llm_intent_classifier.LLMIntentClassifier") as LLMCls:
        LLMCls.return_value.classify.return_value = invalid
        req = classify("open cursor")
    assert req.intent == Intent.OPEN_CURSOR
    assert req.classifier_source == "rules"


def test_rules_when_llm_disabled(monkeypatch):
    monkeypatch.setattr("brain.intent_classifier.LLM_CLASSIFIER_ENABLED", False)
    with patch("brain.llm_intent_classifier.LLMIntentClassifier") as LLMCls:
        req = classify("פתח קרסור")
        LLMCls.assert_not_called()
    assert req.intent == Intent.OPEN_CURSOR
    assert req.classifier_source == "rules"


def test_high_confidence_rule_skips_llm(monkeypatch):
    monkeypatch.setattr("brain.intent_classifier.LLM_CLASSIFIER_ENABLED", True)
    with patch("brain.llm_intent_classifier.LLMIntentClassifier") as LLMCls:
        req = classify("פתח קרסור")
        LLMCls.assert_not_called()
    assert req.intent == Intent.OPEN_CURSOR
    assert req.confidence >= 0.9


def test_hebrew_messy_command_via_mocked_llm(monkeypatch):
    monkeypatch.setattr("brain.intent_classifier.LLM_CLASSIFIER_ENABLED", True)
    monkeypatch.setattr("brain.intent_classifier.CONFIDENCE_THRESHOLD", 0.99)

    messy = "אולי תראה לי שגיאות מהלוגים בבקשה"
    rule = classify_rules(messy)
    assert rule.confidence < 0.99

    payload = {
        "intent": "show_last_errors",
        "confidence": 0.88,
        "params": {"query": "errors"},
        "reason": "messy Hebrew",
    }
    with patch("brain.llm_intent_classifier.LLMIntentClassifier") as LLMCls:
        LLMCls.return_value.classify.return_value = validate_llm_payload(payload)
        req = classify(messy)
    assert req.intent == Intent.SHOW_LAST_ERRORS
    assert req.classifier_source == "llm"
    assert req.params.get("query") == "errors"


def test_llm_cannot_bypass_implemented_intents():
    """Intent allowed in ALLOWED_INTENTS but not IMPLEMENTED_INTENTS must be rejected."""
    payload = {
        "intent": "open_task_manager",
        "confidence": 0.95,
        "params": {},
    }
    ic = validate_llm_payload(payload)
    assert not ic.valid
    assert ic.intent == Intent.CLARIFY.value


def test_search_code_text_params():
    payload = {
        "intent": "search_code_text",
        "confidence": 0.91,
        "params": {"query": "max_positions_reached"},
        "reason": "code search",
    }
    ic = validate_llm_payload(payload)
    assert ic.valid
    assert ic.params["query"] == "max_positions_reached"


def test_classify_orchestration_llm_success(monkeypatch):
    monkeypatch.setattr("brain.intent_classifier.LLM_CLASSIFIER_ENABLED", True)
    monkeypatch.setattr("brain.intent_classifier.CONFIDENCE_THRESHOLD", 0.99)

    vague = "אפשר לבדוק אם המערכת של הדאשבורד חיה כרגע"
    rule = classify_rules(vague)
    assert rule.confidence < 0.99

    payload = {
        "intent": "show_dashboard_health",
        "confidence": 0.87,
        "params": {},
        "reason": "dashboard",
    }
    valid_ic = validate_llm_payload(payload)
    with patch("brain.llm_intent_classifier.LLMIntentClassifier") as LLMCls:
        LLMCls.return_value.classify.return_value = valid_ic
        req = classify(vague)
    assert req.intent == Intent.SHOW_DASHBOARD_HEALTH
    assert req.classifier_source == "llm"


def test_llm_workflow_intents_valid():
    for intent_name in ("list_workflows", "run_workflow", "explain_workflow"):
        ic = validate_llm_payload(
            {"intent": intent_name, "confidence": 0.9, "params": {"workflow": "trading_health_check"}, "reason": "wf"}
        )
        assert ic.valid, intent_name


def test_llm_diagnostics_intents_valid():
    for intent_name in (
        "run_diagnostics",
        "diagnose_dashboard",
        "diagnose_trading_loop",
        "diagnose_recent_errors",
        "analyze_current_screen",
        "explain_last_failure",
        "suggest_next_steps",
    ):
        ic = validate_llm_payload(
            {"intent": intent_name, "confidence": 0.9, "params": {}, "reason": "diag"}
        )
        assert ic.valid, intent_name


def test_llm_vision_intents_valid():
    for intent_name in (
        "describe_screen",
        "read_screen_text",
        "detect_screen_errors",
        "get_active_window",
        "take_screenshot",
        "list_visible_windows",
    ):
        ic = validate_llm_payload(
            {"intent": intent_name, "confidence": 0.9, "params": {}, "reason": "vision"}
        )
        assert ic.valid, intent_name
        assert ic.intent == intent_name


def test_forbidden_command_key_in_params():
    payload = {
        "intent": "open_cursor",
        "confidence": 0.9,
        "params": {"command": "format c:"},
    }
    ic = validate_llm_payload(payload)
    assert not ic.valid
