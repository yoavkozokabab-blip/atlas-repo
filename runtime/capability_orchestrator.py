"""Capability dependency graph and runtime state propagation."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CapabilityNode:
    name: str
    deps: tuple[str, ...]
    healthy: bool
    degraded: bool = False


def dependency_graph() -> dict[str, tuple[str, ...]]:
    return {
        "browser_runtime": ("runtime_monitor",),
        "streaming_conversation": ("audio_runtime", "wakeword", "tts_runtime"),
        "memory_runtime": ("runtime_monitor",),
        "tool_trust": ("memory_runtime", "runtime_monitor"),
        "operator_loop": ("streaming_conversation", "memory_runtime", "tool_trust"),
    }


def propagate_health(health: dict[str, bool]) -> dict[str, str]:
    graph = dependency_graph()
    out: dict[str, str] = {}
    for node, deps in graph.items():
        if not health.get(node, True):
            out[node] = "failed"
            continue
        if any(not health.get(dep, True) for dep in deps):
            out[node] = "degraded"
        else:
            out[node] = "healthy"
    return out


def recovery_sequence(failed: str) -> list[str]:
    graph = dependency_graph()
    order = ["runtime_monitor", "audio_runtime", "wakeword", "tts_runtime", "browser_runtime", "memory_runtime", "tool_trust", "streaming_conversation", "operator_loop"]
    if failed not in graph:
        return order
    deps = list(graph.get(failed, ()))
    deps.append(failed)
    deps.extend([n for n in order if n not in deps])
    return deps

