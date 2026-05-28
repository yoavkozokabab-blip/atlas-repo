"""Replay snapshot export."""

from __future__ import annotations

import json
from pathlib import Path

from config import PROJECT_ROOT
from investigation.hypothesis_verifier import verify_all_hypotheses
from investigation.replay_diff import diff_live_backtest
from investigation.replay_engine import replay_symbol
from investigation.replay_models import ReplaySnapshot

SNAPSHOT_DIR = PROJECT_ROOT / "reports" / "jarvis_investigations" / "replays"


def export_replay_snapshot(symbol: str = "AAPL") -> Path:
    SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
    replay = replay_symbol(symbol)
    diff = diff_live_backtest(symbol)
    hypotheses = verify_all_hypotheses(symbol=symbol)
    snap = ReplaySnapshot.build(symbol=replay.symbol, replay=replay, diff=diff, hypotheses=hypotheses)
    path = SNAPSHOT_DIR / f"{replay.symbol.lower()}_{replay.replay_hash[:12]}_snapshot.json"
    path.write_text(json.dumps(snap.to_dict(), indent=2, ensure_ascii=True), encoding="utf-8")
    return path


def format_snapshot_report(symbol: str = "AAPL") -> str:
    path = export_replay_snapshot(symbol)
    return (
        f"Replay snapshot exported: {path}\n"
        "Snapshot includes config, timestamps, replay output, hypothesis state, evidence references, and reproducibility metadata."
    )
