"""Memory store tests."""

import json
from pathlib import Path

import pytest

from brain.memory import MemoryStore, get_memory, reset_memory_store
from brain.storage_safe import UnsafeStorageError


@pytest.fixture
def mem_store(tmp_path: Path, monkeypatch):
    monkeypatch.setattr("config.MEMORY_ENABLED", False)
    reset_memory_store()
    from memory.store import reset_personal_memory

    reset_personal_memory()
    path = tmp_path / "memory.json"
    backups = tmp_path / "backups"
    monkeypatch.setattr("brain.memory.MEMORY_PATH", path)
    monkeypatch.setattr("brain.memory.BACKUPS_DIR", backups)
    store = MemoryStore(path)
    yield store
    reset_memory_store()


def test_add_list_search_delete_memory(mem_store: MemoryStore):
    mem_store.add_memory("project_root", r"C:\FINAL_ALGO_TRADER", category="fact")
    items = mem_store.list_memory()
    assert len(items) == 1
    hits = mem_store.search_memory("FINAL")
    assert len(hits) == 1
    assert mem_store.delete_memory("project_root")
    assert mem_store.list_memory() == []


def test_backup_created_before_write(mem_store: MemoryStore, tmp_path: Path):
    mem_store.add_memory("a", "1")
    mem_store.add_memory("b", "2")
    backups = list((tmp_path / "backups").glob("memory_*.json"))
    assert len(backups) >= 1


def test_secret_memory_blocked(mem_store: MemoryStore):
    with pytest.raises(UnsafeStorageError):
        mem_store.add_memory("key", "API_KEY=supersecret12345")


def test_corrupt_memory_fails_gracefully(tmp_path: Path, monkeypatch):
    monkeypatch.setattr("config.MEMORY_ENABLED", False)
    reset_memory_store()
    path = tmp_path / "memory.json"
    path.write_text("{bad", encoding="utf-8")
    monkeypatch.setattr("brain.memory.MEMORY_PATH", path)
    store = MemoryStore(path)
    assert store.list_memory() == []


def test_memory_does_not_execute():
    from actions.memory_actions import ListMemoryAction
    from core.types import CommandRequest, Intent

    action = ListMemoryAction()
    result = action.execute(CommandRequest(raw_text="list", intent=Intent.LIST_MEMORY))
    assert result.status.value == "success"
    assert (
        "Stored memory" in result.summary
        or "No stored" in result.summary
        or "No memory" in result.summary
    )


def test_remember_requires_explicit_intent():
    from brain.intent_classifier import classify_rules
    from core.types import Intent

    req = classify_rules("open cursor")
    assert req.intent == Intent.OPEN_CURSOR
    assert req.intent != Intent.REMEMBER_FACT
