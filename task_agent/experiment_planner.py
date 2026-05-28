"""Phase 24 — experiment grid planner (plan only, no execution)."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from config import ARTIFACTS_DIR


def build_experiment_plan(topic: str = "") -> tuple[Path, str]:
    """Generate experiment grid proposal (requires separate approval to run)."""
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    out_dir = ARTIFACTS_DIR / "experiments"
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"experiment_plan_{ts}.md"
    topic_line = topic.strip() or "trading algorithm tuning"

    body = f"""# Experiment Plan (preview only)

Topic: {topic_line}
Status: **DRAFT — not executed**

## Grid: filters

| Variant | Filter change |
|---------|---------------|
| F0 | baseline |
| F1 | min volume +20% |
| F2 | exclude low liquidity |

## Grid: risk params

| Variant | risk_per_trade | max_positions |
|---------|----------------|---------------|
| R0 | default | default |
| R1 | -25% | same |
| R2 | same | -1 position |

## Grid: delayed entry

| Variant | delay bars | notes |
|---------|------------|-------|
| D0 | 0 | immediate |
| D1 | 1 | align with paper |
| D2 | 2 | stress test |

## Grid: ranking variants

| Variant | ranking |
|---------|---------|
| K0 | current |
| K1 | momentum weight +0.1 |
| K2 | mean-reversion tie-break |

## Execution policy

- Long backtests / paper runs require explicit approval per step.
- No live trading execution from JARVIS.
- Suggested command after approval: supervised `run task step` with approved backtest step.

"""
    path.write_text(body, encoding="utf-8")
    return path, body
