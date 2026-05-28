"""Phase 34 — personal knowledge base."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from actions.knowledge_actions import (
    IndexProjectAction,
    RememberThisAction,
    SearchProjectKnowledgeAction,
    ShowMemoryAction,
)
from actions.registry import ActionRegistry
from brain.intent_classifier import classify_rules
from core.types import ActionStatus, CommandRequest, Intent
from memory.project_indexer import index_projects, load_project_index
from memory.redaction import redact_text, validate_safe_text
from memory.store import PersonalMemoryStore, get_personal_memory, reset_personal_memory


@pytest.fixture(autouse=True)
def _mem_paths(tmp_path, monkeypatch):
    monkeypatch.setattr("memory.store.MEMORY_STORE_PATH", tmp_path / "memory_store.json")
    monkeypatch.setattr(
        "memory.project_indexer.PROJECT_INDEX_PATH",
        tmp_path / "project_index.json",
    )
    monkeypatch.setattr("config.MEMORY_STORE_PATH", tmp_path / "memory_store.json")
    monkeypatch.setattr("config.PROJECT_INDEX_PATH", tmp_path / "project_index.json")
    monkeypatch.setattr("config.MEMORY_ENABLED", True)
    monkeypatch.setattr("config.PROJECT_INDEXING_ENABLED", True)
    monkeypatch.setattr("config.PROJECT_INDEX_MAX_FILE_KB", 8)
    reset_personal_memory()
    yield
    reset_personal_memory()


def test_remember_stores_safe_entry():
    store = PersonalMemoryStore()
    entry = store.remember(
        "I prefer dashboard on port 8077",
        category="preference",
        tags=["dashboard"],
    )
    assert entry.entry_id.startswith("mem_")
    assert "8077" in entry.text
    data = json.loads(store.path.read_text(encoding="utf-8"))
    assert len(data["entries"]) == 1


def test_redaction_removes_secrets():
    with pytest.raises(Exception):
        validate_safe_text("api_key=supersecret12345")
    out = redact_text("token=abc123 password=x")
    assert "abc123" not in out
    assert "REDACTED" in out


def test_forget_hides_not_deletes():
    store = PersonalMemoryStore()
    store.remember("keep me visible", tags=["visible"])
    store.remember("hide this note", tags=["hide_me"])
    assert store.forget("hide_me") == 1
    visible = store.list_visible()
    assert len(visible) == 1
    assert visible[0].text.startswith("keep")
    raw = json.loads(store.path.read_text(encoding="utf-8"))
    assert len(raw["entries"]) == 2
    assert sum(1 for e in raw["entries"] if e.get("hidden")) == 1


def test_show_memory_excludes_hidden():
    store = PersonalMemoryStore()
    store.remember("alpha note")
    store.forget("alpha")
    store.remember("beta note")
    body = store.format_summary()
    assert "beta" in body
    assert "alpha" not in body


def test_project_indexing_skips_blocked(tmp_path, monkeypatch):
    root = tmp_path / "proj"
    (root / "node_modules").mkdir(parents=True)
    (root / "node_modules" / "bad.py").write_text("x = 1\n", encoding="utf-8")
    (root / ".env").write_text("SECRET=1\n", encoding="utf-8")
    (root / "ok.py").write_text('"""module"""\ndef foo():\n    pass\n', encoding="utf-8")
    monkeypatch.setattr(
        "memory.project_indexer._allowlisted_roots",
        lambda: [("test_proj", root)],
    )
    count, _ = index_projects(max_files_per_root=50)
    assert count == 1
    idx = load_project_index()
    paths = [f["path"] for f in idx["projects"]["test_proj"]["files"]]
    assert "ok.py" in paths
    assert not any("node_modules" in p for p in paths)
    assert not any(".env" in p for p in paths)


def test_oversized_file_skipped(tmp_path, monkeypatch):
    root = tmp_path / "big"
    root.mkdir()
    huge = root / "huge.py"
    huge.write_text("x" * 20000, encoding="utf-8")
    monkeypatch.setattr("memory.project_indexer._allowlisted_roots", lambda: [("t", root)])
    monkeypatch.setattr("config.PROJECT_INDEX_MAX_FILE_KB", 1)
    monkeypatch.setattr("memory.project_indexer.PROJECT_INDEX_MAX_FILE_KB", 1)
    count, _ = index_projects()
    assert count == 0


def test_search_returns_summaries_only(tmp_path, monkeypatch):
    root = tmp_path / "src"
    root.mkdir()
    (root / "alpha.py").write_text("def ranking_filter():\n    pass\n", encoding="utf-8")
    monkeypatch.setattr("memory.project_indexer._allowlisted_roots", lambda: [("t", root)])
    index_projects()
    r = SearchProjectKnowledgeAction().execute(
        CommandRequest(raw_text="search project knowledge ranking")
    )
    assert r.status == ActionStatus.SUCCESS
    assert "ranking" in r.summary.lower()
    assert "x = 1" not in r.summary
    assert len(r.summary) < 2000


def test_corrupted_store_degrades():
    path = get_personal_memory().path
    path.write_text("{broken", encoding="utf-8")
    assert get_personal_memory().list_visible() == []


def test_classify_and_registry():
    assert classify_rules("remember this my note").intent == Intent.REMEMBER_THIS
    assert classify_rules("show memory").intent == Intent.SHOW_MEMORY
    reg = ActionRegistry()
    assert reg.has(Intent.INDEX_PROJECT.value)


def test_router_path_unchanged():
    from brain.router import CommandRouter

    router = CommandRouter()
    r = router.route("show capabilities")
    assert r.status == ActionStatus.SUCCESS
