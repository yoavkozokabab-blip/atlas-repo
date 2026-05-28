"""Replay timeline formatting and compression."""

from __future__ import annotations

from investigation.replay_engine import replay_latest_signal, replay_symbol
from investigation.replay_models import ReplayResult

_LAST_REPLAY: ReplayResult | None = None


def remember_replay(result: ReplayResult) -> ReplayResult:
    global _LAST_REPLAY
    _LAST_REPLAY = result
    return result


def latest_replay() -> ReplayResult:
    return _LAST_REPLAY or remember_replay(replay_latest_signal())


def build_timeline(result: ReplayResult | None = None, *, compress: bool = True) -> list[str]:
    result = result or latest_replay()
    lines = [f"Replay timeline for {result.symbol} (hash={result.replay_hash})"]
    for i, step in enumerate(result.steps, 1):
        reason = f" rejection={step.rejection_reason}" if step.rejection_reason else ""
        lines.append(f"{i}. {step.name}: inputs={step.inputs} outputs={step.outputs}{reason}")
        if not compress:
            for path in step.evidence_paths[:4]:
                lines.append(f"   evidence: {path}")
    return lines


def format_timeline(result: ReplayResult | None = None) -> str:
    return "\n".join(build_timeline(result, compress=False))
