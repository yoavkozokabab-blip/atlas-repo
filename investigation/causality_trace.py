"""Causality chain graph from replay steps."""

from __future__ import annotations

from investigation.replay_engine import replay_symbol
from investigation.replay_models import CausalityEdge, CausalityNode


def build_causality(symbol: str = "AAPL") -> tuple[list[CausalityNode], list[CausalityEdge]]:
    replay = replay_symbol(symbol)
    nodes: list[CausalityNode] = []
    for i, step in enumerate(replay.steps, 1):
        event = step.name
        if step.rejection_reason:
            event = f"{event}: {step.rejection_reason}"
        nodes.append(
            CausalityNode(
                node_id=f"c{i}",
                event=event,
                confidence=0.85 if step.evidence_paths else 0.45,
                evidence_paths=step.evidence_paths[:5],
            )
        )
    edges = [
        CausalityEdge(
            source=nodes[i].node_id,
            target=nodes[i + 1].node_id,
            cause=f"{nodes[i].event} affects {nodes[i + 1].event}",
            confidence=min(nodes[i].confidence, nodes[i + 1].confidence),
        )
        for i in range(len(nodes) - 1)
    ]
    return nodes, edges


def format_causality_graph(symbol: str = "AAPL") -> str:
    nodes, edges = build_causality(symbol)
    lines = [f"Causality graph for {symbol.upper()}"]
    lines.append("Nodes:")
    for node in nodes:
        lines.append(f"- {node.node_id}: {node.event} confidence={node.confidence:.2f}")
        for path in node.evidence_paths[:2]:
            lines.append(f"  evidence: {path}")
    lines.append("Edges:")
    for edge in edges:
        lines.append(f"- {edge.source} -> {edge.target}: {edge.cause} confidence={edge.confidence:.2f}")
    return "\n".join(lines)
