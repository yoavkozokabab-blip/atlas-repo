"""In-session conversation memory graph (utterances + intent links, no execution)."""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import Any

_lock = threading.Lock()
_graph: "ConversationMemoryGraph | None" = None


@dataclass
class GraphNode:
    node_id: str
    kind: str  # utterance | intent | correction | plan
    text: str = ""
    intent: str = ""
    confidence: float = 0.0
    timestamp: float = field(default_factory=time.monotonic)
    meta: dict[str, Any] = field(default_factory=dict)


@dataclass
class GraphEdge:
    source_id: str
    target_id: str
    relation: str  # continues | corrects | decomposes | prefetches


@dataclass
class ConversationMemoryGraph:
    nodes: list[GraphNode] = field(default_factory=list)
    edges: list[GraphEdge] = field(default_factory=list)
    active_utterance_id: str = ""
    last_intent_id: str = ""
    turn_index: int = 0

    def add_node(self, node: GraphNode) -> GraphNode:
        self.nodes.append(node)
        if len(self.nodes) > 40:
            drop = self.nodes.pop(0)
            self.edges = [
                e for e in self.edges if e.source_id != drop.node_id and e.target_id != drop.node_id
            ]
        return node

    def link(self, source_id: str, target_id: str, relation: str) -> None:
        self.edges.append(GraphEdge(source_id, target_id, relation))

    def last_utterance(self) -> GraphNode | None:
        for node in reversed(self.nodes):
            if node.kind == "utterance":
                return node
        return None

    def recent_intents(self, *, limit: int = 5) -> list[GraphNode]:
        out: list[GraphNode] = []
        for node in reversed(self.nodes):
            if node.kind == "intent":
                out.append(node)
            if len(out) >= limit:
                break
        return list(reversed(out))


def get_conversation_graph() -> ConversationMemoryGraph:
    global _graph
    with _lock:
        if _graph is None:
            _graph = ConversationMemoryGraph()
        return _graph


def reset_conversation_graph() -> None:
    global _graph
    with _lock:
        _graph = ConversationMemoryGraph()


def record_utterance_partial(
    text: str,
    *,
    confidence: float = 0.0,
    is_final: bool = False,
) -> GraphNode:
    g = get_conversation_graph()
    node_id = f"utt-{int(time.monotonic() * 1000)}"
    node = GraphNode(
        node_id=node_id,
        kind="utterance",
        text=text[:500],
        confidence=confidence,
        meta={"final": is_final, "partial": not is_final},
    )
    g.add_node(node)
    if g.active_utterance_id:
        g.link(g.active_utterance_id, node_id, "continues")
    g.active_utterance_id = node_id
    if is_final:
        g.turn_index += 1
    return node


def record_intent_candidate(intent: str, *, confidence: float, source: str) -> GraphNode:
    g = get_conversation_graph()
    node_id = f"int-{intent}-{int(time.monotonic() * 1000)}"
    node = GraphNode(
        node_id=node_id,
        kind="intent",
        intent=intent,
        confidence=confidence,
        meta={"source": source},
    )
    g.add_node(node)
    if g.active_utterance_id:
        g.link(g.active_utterance_id, node_id, "prefetches")
    g.last_intent_id = node_id
    return node
