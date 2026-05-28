"""Intent registry consistency and classifier import smoke tests."""

from __future__ import annotations


def test_required_phase_intent_members_exist():
    from core.intent_validation import REQUIRED_PHASE_INTENT_MEMBERS, validate_required_intent_enums
    from core.types import Intent

    for member in REQUIRED_PHASE_INTENT_MEMBERS:
        assert hasattr(Intent, member), member
    assert validate_required_intent_enums() == []


def test_classifier_modules_import():
    import brain.english_voice_phrases  # noqa: F401
    import brain.intent_classifier  # noqa: F401


def test_test_streaming_stt_in_allowed_and_implemented():
    from config import ALLOWED_INTENTS, IMPLEMENTED_INTENTS
    from core.types import Intent

    value = Intent.TEST_STREAMING_STT.value
    assert value == "test_streaming_stt"
    assert value in ALLOWED_INTENTS
    assert value in IMPLEMENTED_INTENTS


def test_english_voice_phrase_test_streaming_stt():
    from brain.english_voice_phrases import match_english_voice_phrase
    from core.types import Intent

    match = match_english_voice_phrase("test streaming stt")
    assert match is not None
    assert match.intent == Intent.TEST_STREAMING_STT


def test_validate_intent_registry_consistency():
    import brain.english_voice_phrases  # noqa: F401
    import brain.intent_classifier  # noqa: F401
    from core.intent_validation import format_validation_report, validate_intent_registry_consistency

    issues = validate_intent_registry_consistency()
    assert issues == [], format_validation_report(issues)


def test_phase46_classifier_phrases():
    from brain.intent_classifier import classify_rules
    from core.types import Intent

    expected = {
        "run historical validation sweep": Intent.RUN_HISTORICAL_VALIDATION_SWEEP,
        "audit execution path": Intent.AUDIT_EXECUTION_PATH,
        "explain zero execution attempts": Intent.EXPLAIN_ZERO_EXECUTION_ATTEMPTS,
        "show execution blockers": Intent.SHOW_EXECUTION_BLOCKERS,
        "rank execution block reasons": Intent.RANK_EXECUTION_BLOCK_REASONS,
        "inspect execution adapter": Intent.INSPECT_EXECUTION_ADAPTER,
        "compare signal count to order attempts": Intent.COMPARE_SIGNAL_COUNT_TO_ORDER_ATTEMPTS,
        "generate execution investigation report": Intent.GENERATE_EXECUTION_INVESTIGATION_REPORT,
    }
    for phrase, intent in expected.items():
        assert classify_rules(phrase).intent == intent
