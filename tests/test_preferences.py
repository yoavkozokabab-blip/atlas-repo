"""Preferences store tests."""

from pathlib import Path

import pytest

from brain.preferences import PreferencesStore, reset_preferences_store
from brain.storage_safe import UnsafeStorageError


@pytest.fixture
def pref_store(tmp_path: Path, monkeypatch):
    reset_preferences_store()
    path = tmp_path / "preferences.json"
    monkeypatch.setattr("brain.preferences.PREFERENCES_PATH", path)
    store = PreferencesStore(path)
    yield store
    reset_preferences_store()


def test_set_list_delete_preference(pref_store: PreferencesStore):
    pref_store.set_preference("language", "hebrew")
    assert pref_store.get_preference("language") is not None
    data = pref_store.list_preferences()
    assert "language" in data
    assert pref_store.delete_preference("language")
    assert pref_store.get_preference("language") is None


def test_preference_secret_blocked(pref_store: PreferencesStore):
    with pytest.raises(UnsafeStorageError):
        pref_store.set_preference("token", "Bearer sk-abcdef123456789012345678")
