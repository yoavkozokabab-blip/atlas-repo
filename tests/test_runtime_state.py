"""Runtime state tests."""

from core.runtime_state import RuntimeState, get_runtime_state, reset_runtime_state


def test_defaults_safe():
    reset_runtime_state()
    state = RuntimeState()
    assert state.voice_enabled is False
    assert state.speak_enabled is False
    assert state.running is True
    assert state.last_result_summary == ""
    assert state.wake_word_enabled is False
    assert state.wake_word_listening_active is False


def test_toggles_work():
    state = RuntimeState()
    state.set_voice(True)
    state.set_speak(True)
    state.set_overlay(True)
    assert state.voice_enabled
    assert state.speak_enabled
    assert state.overlay_enabled
    state.stop()
    assert state.running is False


def test_record_result_truncates():
    state = RuntimeState()
    state.record_result("x" * 1000, "err" * 500)
    assert len(state.last_result_summary) <= 500
    assert state.last_error is not None
    assert len(state.last_error) <= 200


def test_wake_word_state_fields():
    state = RuntimeState()
    state.set_wake_word(True)
    state.record_wake_detection(0.87)
    assert state.wake_word_enabled
    assert state.wake_word_last_score == 0.87
    assert state.wake_word_detection_count == 1
    assert state.acquire_wake_listening_session()
    assert state.wake_word_listening_active
    state.release_wake_listening_session()
    assert not state.wake_word_listening_active


def test_singleton():
    reset_runtime_state()
    a = get_runtime_state()
    b = get_runtime_state()
    assert a is b
