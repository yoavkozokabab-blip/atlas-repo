"""Phase 34 — personal knowledge base actions."""

from __future__ import annotations

import re

import config
from actions.base import BaseAction
from config import MEMORY_ENABLED, PROJECT_INDEXING_ENABLED
from core.results import result_blocked, result_failed, result_success
from core.types import CommandRequest, CommandResult, Intent
from memory.graph import (
    build_memory_graph,
    format_graph_search_results,
    format_memory_graph,
    graph_counts,
    search_memory_graph,
)
from memory.project_indexer import format_project_search_results, index_projects
from memory.redaction import UnsafeMemoryError
from memory.search import search_project_index
from memory.store import get_personal_memory


def _extract_remember_this(text: str) -> str:
    for pat in (
        r"remember\s+this\s+(.+)",
        r"remember\s+that\s+(.+)",
        r"זכור\s+זה\s+(.+)",
        r"זכור\s+ש(?:אני\s+)?(.+)",
    ):
        m = re.search(pat, text, re.I | re.DOTALL)
        if m:
            return m.group(1).strip()
    return text.strip()


def _parse_category(text: str) -> str | None:
    lower = text.lower()
    for cat in ("preference", "trading", "workflow", "study", "project"):
        if f"category:{cat}" in lower or f"[{cat}]" in lower:
            return cat
    return None


class RememberThisAction(BaseAction):
    intent = Intent.REMEMBER_THIS.value

    def execute(self, request: CommandRequest) -> CommandResult:
        if not MEMORY_ENABLED:
            return result_blocked(Intent.REMEMBER_THIS, "Memory is disabled.")
        body = _extract_remember_this(request.raw_text)
        if not body:
            return result_failed(Intent.REMEMBER_THIS, "Say what to remember after 'remember this'.")
        category = (
            str(request.params.get("category") or "").strip()
            or _parse_category(body)
            or "personal_note"
        )
        tags_raw = request.params.get("tags") or []
        tags = tags_raw if isinstance(tags_raw, list) else [str(tags_raw)]
        try:
            entry = get_personal_memory().remember(
                body,
                category=category,
                tags=[str(t) for t in tags if t],
                source=str(request.params.get("source") or "command"),
            )
        except UnsafeMemoryError as exc:
            return result_blocked(Intent.REMEMBER_THIS, str(exc), error=str(exc))
        return result_success(
            Intent.REMEMBER_THIS,
            f"Remembered [{entry.category}] {entry.entry_id}: {entry.text[:200]}",
            data={"entry_id": entry.entry_id},
        )


class ShowMemoryAction(BaseAction):
    intent = Intent.SHOW_MEMORY.value

    def execute(self, request: CommandRequest) -> CommandResult:
        if not MEMORY_ENABLED:
            return result_blocked(Intent.SHOW_MEMORY, "Memory is disabled.")
        category = (request.params.get("category") or "").strip() or None
        body = get_personal_memory().format_summary(category=category or None)
        return result_success(Intent.SHOW_MEMORY, body)


class IndexProjectAction(BaseAction):
    intent = Intent.INDEX_PROJECT.value

    def execute(self, request: CommandRequest) -> CommandResult:
        if not PROJECT_INDEXING_ENABLED:
            return result_blocked(
                Intent.INDEX_PROJECT,
                "Project indexing is disabled.",
            )
        count, msg = index_projects()
        return result_success(
            Intent.INDEX_PROJECT,
            msg,
            data={"files_indexed": count},
        )


class SearchProjectKnowledgeAction(BaseAction):
    intent = Intent.SEARCH_PROJECT_KNOWLEDGE.value

    def execute(self, request: CommandRequest) -> CommandResult:
        query = (request.params.get("query") or "").strip()
        if not query:
            raw = request.raw_text or ""
            for prefix in (
                "search project knowledge",
                "search project",
                "find in project",
            ):
                if raw.lower().startswith(prefix):
                    query = raw[len(prefix) :].strip()
                    break
        if not query:
            return result_failed(
                Intent.SEARCH_PROJECT_KNOWLEDGE,
                "Provide a search term.",
            )
        hits = search_project_index(query)
        body = format_project_search_results(hits, query)
        return result_success(
            Intent.SEARCH_PROJECT_KNOWLEDGE,
            body,
            data={"count": len(hits)},
        )


def _extract_graph_query(text: str) -> str:
    raw = (text or "").strip()
    lowered = raw.lower()
    for prefix in (
        "search memory graph",
        "search knowledge graph",
        "find memory link",
        "graph search",
        "find in memory graph",
    ):
        if lowered.startswith(prefix):
            return raw[len(prefix) :].strip()
    return raw


class ShowMemoryGraphAction(BaseAction):
    intent = Intent.SHOW_MEMORY_GRAPH.value

    def execute(self, request: CommandRequest) -> CommandResult:
        if not config.MEMORY_ENABLED and not config.PROJECT_INDEXING_ENABLED:
            return result_blocked(
                Intent.SHOW_MEMORY_GRAPH,
                "Memory graph is unavailable because memory and project indexing are disabled.",
            )
        snapshot = build_memory_graph(
            include_memory=config.MEMORY_ENABLED,
            include_projects=config.PROJECT_INDEXING_ENABLED,
        )
        counts = graph_counts(snapshot)
        return result_success(
            Intent.SHOW_MEMORY_GRAPH,
            format_memory_graph(snapshot),
            data={
                "node_count": len(snapshot.nodes),
                "edge_count": len(snapshot.edges),
                "nodes_by_type": counts,
                "warnings": snapshot.warnings,
            },
        )


class SearchMemoryGraphAction(BaseAction):
    intent = Intent.SEARCH_MEMORY_GRAPH.value

    def execute(self, request: CommandRequest) -> CommandResult:
        if not config.MEMORY_ENABLED and not config.PROJECT_INDEXING_ENABLED:
            return result_blocked(
                Intent.SEARCH_MEMORY_GRAPH,
                "Memory graph search is unavailable because memory and project indexing are disabled.",
            )
        query = str(request.params.get("query") or "").strip()
        if not query:
            query = _extract_graph_query(request.raw_text)
        if not query:
            return result_failed(
                Intent.SEARCH_MEMORY_GRAPH,
                "Provide a graph search term.",
            )
        snapshot = build_memory_graph(
            include_memory=config.MEMORY_ENABLED,
            include_projects=config.PROJECT_INDEXING_ENABLED,
        )
        hits = search_memory_graph(query, snapshot=snapshot)
        return result_success(
            Intent.SEARCH_MEMORY_GRAPH,
            format_graph_search_results(hits, query),
            data={
                "count": len(hits),
                "node_count": len(snapshot.nodes),
                "edge_count": len(snapshot.edges),
                "warnings": snapshot.warnings,
            },
        )
