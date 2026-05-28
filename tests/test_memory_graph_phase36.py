"""Phase 36 - read-only memory graph."""

from __future__ import annotations

import json
import uuid
from pathlib import Path

import pytest

from actions.knowledge_actions import SearchMemoryGraphAction, ShowMemoryGraphAction
from actions.registry import ActionRegistry
from brain.intent_classifier import classify_rules
from core.types import ActionStatus, CommandRequest, Intent
from memory.graph import build_memory_graph, search_memory_graph
from memory.project_indexer import index_projects
from memory.store import PersonalMemoryStore
import memory.store as memory_store

TEST_BASE = Path("tests_tmp") / "memory_graph_phase36"


@pytest.fixture(autouse=True)
def _graph_paths(monkeypatch):
    test_root = TEST_BASE / uuid.uuid4().hex[:10]
    test_root.mkdir(parents=True, exist_ok=True)
    memory_path = test_root / "memory_store.json"
    index_path = test_root / "project_index.json"
    monkeypatch.setattr("memory.store.MEMORY_STORE_PATH", memory_path)
    monkeypatch.setattr("memory.store.MEMORY_ENABLED", True)
    monkeypatch.setattr("config.MEMORY_STORE_PATH", memory_path)
    monkeypatch.setattr("config.MEMORY_ENABLED", True)
    monkeypatch.setattr("memory.project_indexer.PROJECT_INDEX_PATH", index_path)
    monkeypatch.setattr("memory.project_indexer.PROJECT_INDEXING_ENABLED", True)
    monkeypatch.setattr("config.PROJECT_INDEX_PATH", index_path)
    monkeypatch.setattr("config.PROJECT_INDEXING_ENABLED", True)
    memory_store._store = None
    yield test_root
    memory_store._store = None


def test_graph_builds_memory_category_tag_keyword_links():
    store = PersonalMemoryStore()
    entry = store.remember(
        "Router security registry path must stay intact.",
        category="project",
        tags=["router", "security"],
    )

    snapshot = build_memory_graph(include_projects=False)
    node_types = {node.node_type for node in snapshot.nodes}
    relations = {edge.relation for edge in snapshot.edges}
    labels = {node.label for node in snapshot.nodes}

    assert "memory" in node_types
    assert "category" in node_types
    assert "tag" in node_types
    assert "keyword" in node_types
    assert "categorized_as" in relations
    assert "tagged" in relations
    assert entry.entry_id in labels


def test_graph_includes_project_index_summaries_only(monkeypatch, _graph_paths):
    root = _graph_paths / "project"
    root.mkdir()
    (root / "router.py").write_text(
        '"""routing module"""\ndef route_command():\n    return "ok"\n',
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "memory.project_indexer._allowlisted_roots",
        lambda: [("demo", root)],
    )
    count, _ = index_projects()
    assert count == 1

    snapshot = build_memory_graph(include_memory=False)
    hits = search_memory_graph("route", snapshot=snapshot)
    assert any(hit["type"] in {"file", "keyword"} for hit in hits)
    blob = json.dumps(snapshot.to_dict(), ensure_ascii=False)
    assert "route_command" in blob
    assert "return \"ok\"" not in blob


def test_graph_redacts_stored_secret_like_text():
    path = PersonalMemoryStore().path
    path.write_text(
        json.dumps(
            {
                "entries": [
                    {
                        "entry_id": "mem_secret",
                        "category": "project",
                        "text": "api_key=supersecret12345",
                        "tags": ["token=abc123"],
                        "created_at": "2026-01-01T00:00:00+00:00",
                        "source": "test",
                        "hidden": False,
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    snapshot = build_memory_graph(include_projects=False)
    blob = json.dumps(snapshot.to_dict(), ensure_ascii=False)

    assert "supersecret12345" not in blob
    assert "abc123" not in blob
    assert "REDACTED" in blob


def test_graph_actions_classify_and_register():
    show = classify_rules("show memory graph")
    search = classify_rules("search memory graph router")

    assert show.intent == Intent.SHOW_MEMORY_GRAPH
    assert search.intent == Intent.SEARCH_MEMORY_GRAPH
    assert search.params["query"] == "router"
    registry = ActionRegistry()
    assert registry.has(Intent.SHOW_MEMORY_GRAPH.value)
    assert registry.has(Intent.SEARCH_MEMORY_GRAPH.value)


def test_show_memory_graph_action_returns_safe_counts():
    PersonalMemoryStore().remember("Graph should be inspectable.", tags=["graph"])
    result = ShowMemoryGraphAction().execute(
        CommandRequest(raw_text="show memory graph", intent=Intent.SHOW_MEMORY_GRAPH)
    )

    assert result.status == ActionStatus.SUCCESS
    assert "read-only" in result.summary.lower()
    assert result.data["node_count"] >= 1
    assert result.data["edge_count"] >= 1


def test_search_memory_graph_action_uses_query_param():
    PersonalMemoryStore().remember("The router validates intents before registry.", tags=["router"])
    result = SearchMemoryGraphAction().execute(
        CommandRequest(
            raw_text="search memory graph router",
            intent=Intent.SEARCH_MEMORY_GRAPH,
            params={"query": "router"},
        )
    )

    assert result.status == ActionStatus.SUCCESS
    assert result.data["count"] >= 1
    assert "router" in result.summary.lower()


def test_graph_blocks_when_memory_and_indexing_disabled(monkeypatch):
    monkeypatch.setattr("config.MEMORY_ENABLED", False)
    monkeypatch.setattr("config.PROJECT_INDEXING_ENABLED", False)

    result = ShowMemoryGraphAction().execute(
        CommandRequest(raw_text="show memory graph", intent=Intent.SHOW_MEMORY_GRAPH)
    )

    assert result.status == ActionStatus.BLOCKED


def test_graph_module_has_no_execution_imports():
    text = (Path(__file__).resolve().parents[1] / "memory" / "graph.py").read_text(
        encoding="utf-8"
    )
    forbidden = ("subprocess", "os.system", "Popen", "pyautogui", "pynput")
    for item in forbidden:
        assert item not in text
