"""Phase 36 - read-only memory graph over memory and project knowledge."""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import asdict, dataclass, field
from typing import Any

from memory.project_indexer import load_project_index
from memory.redaction import extract_keywords, redact_text
from memory.store import get_personal_memory

MAX_MEMORY_ENTRIES = 100
MAX_PROJECT_FILES = 250
MAX_NODE_SUMMARY_CHARS = 220
MAX_FORMATTED_NODES = 12
MAX_RELATED_LABELS = 6


@dataclass(frozen=True)
class GraphNode:
    node_id: str
    node_type: str
    label: str
    summary: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class GraphEdge:
    source: str
    target: str
    relation: str
    evidence: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class MemoryGraphSnapshot:
    nodes: list[GraphNode]
    edges: list[GraphEdge]
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "nodes": [n.to_dict() for n in self.nodes],
            "edges": [e.to_dict() for e in self.edges],
            "warnings": list(self.warnings),
        }


def _clean_label(value: Any, *, max_len: int = MAX_NODE_SUMMARY_CHARS) -> str:
    return redact_text(str(value or "").strip(), max_len=max_len)


def _slug(value: str, *, fallback: str = "unknown") -> str:
    raw = (value or "").strip().lower()
    slug = re.sub(r"[^a-z0-9_.:-]+", "_", raw).strip("_")
    return (slug[:120] or fallback).strip("_") or fallback


def _node_id(prefix: str, value: str) -> str:
    return f"{prefix}:{_slug(value)}"


def _add_node(nodes: dict[str, GraphNode], node: GraphNode) -> None:
    if not node.node_id or node.node_id in nodes:
        return
    nodes[node.node_id] = node


def _add_edge(edges: set[tuple[str, str, str]], edge: GraphEdge) -> None:
    if not edge.source or not edge.target or edge.source == edge.target:
        return
    edges.add((edge.source, edge.target, edge.relation))


def _keyword_nodes(
    text: str,
    *,
    nodes: dict[str, GraphNode],
    edges: set[tuple[str, str, str]],
    source_id: str,
    relation: str,
    limit: int = 8,
) -> None:
    safe_text = redact_text(text, max_len=2000)
    for kw in extract_keywords(safe_text, limit=limit):
        kid = _node_id("keyword", kw)
        _add_node(
            nodes,
            GraphNode(
                node_id=kid,
                node_type="keyword",
                label=kw,
            ),
        )
        _add_edge(edges, GraphEdge(source=source_id, target=kid, relation=relation))


def _project_files(project: dict[str, Any]) -> list[dict[str, Any]]:
    rows = project.get("files", [])
    if not isinstance(rows, list):
        return []
    return [r for r in rows if isinstance(r, dict)][:MAX_PROJECT_FILES]


def build_memory_graph(
    *,
    include_memory: bool = True,
    include_projects: bool = True,
) -> MemoryGraphSnapshot:
    """Build a derived graph without mutating memory or project index."""
    nodes: dict[str, GraphNode] = {}
    edges: set[tuple[str, str, str]] = set()
    warnings: list[str] = []

    if include_memory:
        try:
            entries = get_personal_memory().list_visible(limit=MAX_MEMORY_ENTRIES)
        except Exception:
            entries = []
            warnings.append("Personal memory unavailable; graph used safe partial data.")

        for entry in entries:
            mem_id = _node_id("memory", entry.entry_id)
            category = _clean_label(entry.category, max_len=80) or "personal_note"
            summary = _clean_label(entry.text)
            _add_node(
                nodes,
                GraphNode(
                    node_id=mem_id,
                    node_type="memory",
                    label=entry.entry_id,
                    summary=summary,
                    metadata={
                        "category": category,
                        "source": _clean_label(entry.source, max_len=80),
                        "created_at": _clean_label(entry.created_at, max_len=80),
                    },
                ),
            )

            cat_id = _node_id("category", category)
            _add_node(
                nodes,
                GraphNode(
                    node_id=cat_id,
                    node_type="category",
                    label=category,
                ),
            )
            _add_edge(edges, GraphEdge(source=mem_id, target=cat_id, relation="categorized_as"))

            for tag in entry.tags[:10]:
                safe_tag = _clean_label(tag, max_len=80)
                if not safe_tag:
                    continue
                tag_id = _node_id("tag", safe_tag)
                _add_node(
                    nodes,
                    GraphNode(node_id=tag_id, node_type="tag", label=safe_tag),
                )
                _add_edge(edges, GraphEdge(source=mem_id, target=tag_id, relation="tagged"))

            _keyword_nodes(
                f"{entry.text} {' '.join(entry.tags)} {entry.category}",
                nodes=nodes,
                edges=edges,
                source_id=mem_id,
                relation="mentions_keyword",
            )

    if include_projects:
        try:
            index = load_project_index()
            projects = index.get("projects", {})
            if not isinstance(projects, dict):
                projects = {}
        except Exception:
            projects = {}
            warnings.append("Project index unavailable; graph used safe partial data.")

        for project_name in sorted(projects):
            project = projects.get(project_name)
            if not isinstance(project, dict):
                continue
            project_id = _node_id("project", project_name)
            _add_node(
                nodes,
                GraphNode(
                    node_id=project_id,
                    node_type="project",
                    label=_clean_label(project_name, max_len=120),
                    summary=_clean_label(project.get("root", ""), max_len=180),
                    metadata={"indexed_at": _clean_label(project.get("indexed_at", ""), max_len=80)},
                ),
            )

            for row in _project_files(project):
                rel_path = _clean_label(row.get("path", ""), max_len=180)
                if not rel_path:
                    continue
                file_id = _node_id("file", f"{project_name}:{rel_path}")
                summary = _clean_label(row.get("summary") or row.get("snippet") or "")
                _add_node(
                    nodes,
                    GraphNode(
                        node_id=file_id,
                        node_type="file",
                        label=rel_path,
                        summary=summary,
                        metadata={
                            "project": _clean_label(project_name, max_len=120),
                            "modified_at": _clean_label(row.get("modified_at", ""), max_len=80),
                        },
                    ),
                )
                _add_edge(edges, GraphEdge(source=project_id, target=file_id, relation="contains"))

                kw_text = f"{rel_path} {summary}"
                raw_keywords = row.get("keywords", [])
                if isinstance(raw_keywords, list):
                    kw_text += " " + " ".join(str(k) for k in raw_keywords[:12])
                _keyword_nodes(
                    kw_text,
                    nodes=nodes,
                    edges=edges,
                    source_id=file_id,
                    relation="mentions_keyword",
                    limit=10,
                )

    sorted_nodes = sorted(nodes.values(), key=lambda n: (n.node_type, n.node_id))
    sorted_edges = [
        GraphEdge(source=src, target=dst, relation=rel)
        for src, dst, rel in sorted(edges, key=lambda e: (e[2], e[0], e[1]))
    ]
    return MemoryGraphSnapshot(nodes=sorted_nodes, edges=sorted_edges, warnings=warnings)


def _neighbor_labels(snapshot: MemoryGraphSnapshot, node_id: str) -> list[str]:
    node_by_id = {node.node_id: node for node in snapshot.nodes}
    related: set[str] = set()
    for edge in snapshot.edges:
        other_id = ""
        if edge.source == node_id:
            other_id = edge.target
        elif edge.target == node_id:
            other_id = edge.source
        if other_id and other_id in node_by_id:
            related.add(node_by_id[other_id].label)
    return sorted(related)[:MAX_RELATED_LABELS]


def search_memory_graph(
    query: str,
    *,
    snapshot: MemoryGraphSnapshot | None = None,
    limit: int = 12,
) -> list[dict[str, Any]]:
    """Search graph nodes by label, summary, type, and related labels."""
    q = (query or "").strip().lower()
    if not q:
        return []
    snap = snapshot or build_memory_graph()
    hits: list[tuple[int, str, dict[str, Any]]] = []

    for node in snap.nodes:
        label = node.label.lower()
        summary = node.summary.lower()
        node_type = node.node_type.lower()
        meta_blob = " ".join(str(v) for v in node.metadata.values()).lower()
        related = _neighbor_labels(snap, node.node_id)
        related_blob = " ".join(related).lower()
        score = 0
        if q == node.node_id.lower() or q == label:
            score += 8
        if q in label:
            score += 5
        if q in summary:
            score += 3
        if q in node_type:
            score += 2
        if q in meta_blob:
            score += 1
        if q in related_blob:
            score += 1
        if score <= 0:
            continue
        hits.append(
            (
                score,
                node.node_id,
                {
                    "node_id": node.node_id,
                    "type": node.node_type,
                    "label": node.label,
                    "summary": node.summary,
                    "related": related,
                    "score": score,
                },
            )
        )

    hits.sort(key=lambda item: (-item[0], item[1]))
    return [hit for _, _, hit in hits[: max(1, limit)]]


def graph_counts(snapshot: MemoryGraphSnapshot) -> dict[str, int]:
    return dict(Counter(node.node_type for node in snapshot.nodes))


def format_memory_graph(snapshot: MemoryGraphSnapshot) -> str:
    counts = graph_counts(snapshot)
    lines = [
        "Memory graph (read-only)",
        f"Nodes: {len(snapshot.nodes)} | Edges: {len(snapshot.edges)}",
    ]
    if counts:
        parts = [f"{key}={counts[key]}" for key in sorted(counts)]
        lines.append("Types: " + ", ".join(parts))
    if snapshot.warnings:
        lines.append("Warnings: " + " | ".join(snapshot.warnings))

    lines.append("")
    lines.append("Sample nodes:")
    if not snapshot.nodes:
        lines.append("  - No graph nodes yet. Add memory or run index project first.")
    else:
        for node in snapshot.nodes[:MAX_FORMATTED_NODES]:
            detail = f" - {node.summary[:120]}" if node.summary else ""
            lines.append(f"  - [{node.node_type}] {node.label}{detail}")

    lines.append("")
    lines.append("Graph is derived from stored summaries only; no actions were executed.")
    return "\n".join(lines)


def format_graph_search_results(hits: list[dict[str, Any]], query: str) -> str:
    if not hits:
        return f"No memory graph matches for '{query}'."

    lines = [f"Memory graph search: '{query}'", ""]
    for i, hit in enumerate(hits, 1):
        lines.append(f"{i}. [{hit.get('type', '?')}] {hit.get('label', '')}")
        summary = str(hit.get("summary") or "")
        if summary:
            lines.append(f"   summary: {summary[:180]}")
        related = hit.get("related") or []
        if related:
            lines.append("   related: " + ", ".join(str(x)[:80] for x in related[:MAX_RELATED_LABELS]))
    lines.append("")
    lines.append("Read-only graph search; no workflow or automation was run.")
    return "\n".join(lines)
