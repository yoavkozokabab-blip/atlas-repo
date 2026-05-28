"""Symbol-level replay reports."""

from __future__ import annotations

from investigation.replay_engine import format_replay, replay_latest_signal, replay_symbol
from investigation.replay_timeline import remember_replay


def replay_symbol_report(symbol: str) -> str:
    result = remember_replay(replay_symbol(symbol))
    return format_replay(result)


def replay_latest_signal_report() -> str:
    result = remember_replay(replay_latest_signal())
    return format_replay(result)


def trace_signal_lifecycle(symbol: str = "AAPL") -> str:
    replay = remember_replay(replay_symbol(symbol))
    lines = [f"Signal lifecycle trace: {replay.symbol}"]
    for step in replay.steps:
        if step.name in {"signal detection", "ranking", "entry gate", "delayed entry"}:
            lines.append(f"- {step.name}")
            lines.append(f"  inputs: {step.inputs}")
            lines.append(f"  outputs: {step.outputs}")
            if step.rejection_reason:
                lines.append(f"  rejection_reason: {step.rejection_reason}")
            for path in step.evidence_paths[:3]:
                lines.append(f"  evidence: {path}")
    return "\n".join(lines)


def trace_execution_lifecycle(symbol: str = "AAPL") -> str:
    replay = remember_replay(replay_symbol(symbol))
    lines = [f"Execution lifecycle trace: {replay.symbol}"]
    for step in replay.steps:
        if step.name in {"entry gate", "execution attempt", "stop/target lifecycle"}:
            lines.append(f"- {step.name}")
            lines.append(f"  inputs: {step.inputs}")
            lines.append(f"  outputs: {step.outputs}")
            if step.rejection_reason:
                lines.append(f"  rejection_reason: {step.rejection_reason}")
            for path in step.evidence_paths[:3]:
                lines.append(f"  evidence: {path}")
    return "\n".join(lines)
