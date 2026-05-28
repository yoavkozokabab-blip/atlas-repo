"""Auto-generate minimal verification fixtures (does not run tests)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from config import PROJECT_ROOT
from investigation.replay_diff import diff_live_backtest
from investigation.replay_engine import replay_symbol

GENERATED_DIR = PROJECT_ROOT / "tests" / "generated"


def build_verification_fixture(symbol: str = "AAPL") -> Path:
    GENERATED_DIR.mkdir(parents=True, exist_ok=True)
    replay = replay_symbol(symbol)
    diff = diff_live_backtest(symbol)
    payload = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "read_only": True,
        "symbol": replay.symbol,
        "replay_hash": replay.replay_hash,
        "fixtures": {
            "two_bar_mismatch": [bar.__dict__ for bar in replay.selected_bars[:2]],
            "delayed_entry": [s.__dict__ for s in replay.steps if s.name == "delayed entry"],
            "stale_price": [r for r in replay.rejection_reasons if "stale" in r.lower()],
            "ranking_order": replay.ranking_scores,
        },
        "diff": diff.to_dict(),
        "evidence_paths": replay.evidence_paths,
    }
    path = GENERATED_DIR / "replay_bar_alignment_fixture.json"
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=True), encoding="utf-8")
    return path


def format_fixture_report(symbol: str = "AAPL") -> str:
    path = build_verification_fixture(symbol)
    return (
        f"Verification fixture generated (not executed): {path}\n"
        "Includes: 2-bar mismatch fixture, delayed-entry replay fixture, stale-price fixture, ranking-order fixture.\n"
        "Next step: review fixture, then explicitly request a test run if desired."
    )
