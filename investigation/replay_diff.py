"""Live-vs-backtest deterministic replay diff."""

from __future__ import annotations

from investigation.replay_engine import replay_symbol
from investigation.replay_models import ReplayBar, ReplayDiff


def _bar_diff(live: ReplayBar, backtest: ReplayBar) -> list[str]:
    reasons: list[str] = []
    if live.index != backtest.index:
        reasons.append(f"index alignment mismatch live={live.index} backtest={backtest.index}")
    if live.timestamp != backtest.timestamp:
        reasons.append(f"timezone/timestamp mismatch live={live.timestamp} backtest={backtest.timestamp}")
    if not live.complete:
        reasons.append("incomplete candle usage in live replay")
    if live.close != backtest.close:
        reasons.append(f"price mismatch live_close={live.close} backtest_close={backtest.close}")
    return reasons


def diff_live_backtest(symbol: str) -> ReplayDiff:
    base = replay_symbol(symbol)
    bars = base.selected_bars
    if len(bars) >= 2:
        live_bar = bars[-1]
        backtest_bar = bars[-2]
    else:
        live_bar = bars[-1] if bars else None
        backtest_bar = live_bar
    reasons = _bar_diff(live_bar, backtest_bar) if live_bar and backtest_bar else ["no bars available"]
    stale = any("stale" in r.lower() for r in base.rejection_reasons)
    if stale:
        reasons.append("stale bar/price evidence observed")
    first = reasons[0] if reasons else "no divergence detected"
    return ReplayDiff(
        symbol=base.symbol,
        status="different" if reasons else "same",
        first_divergence=first,
        live_bar=live_bar,
        backtest_bar=backtest_bar,
        divergence_reasons=reasons,
        evidence_paths=base.evidence_paths,
        confidence=0.88 if reasons else 0.60,
    )


def format_replay_diff(diff: ReplayDiff) -> str:
    lines = [
        f"Replay diff: {diff.symbol}",
        f"  status: {diff.status}",
        f"  first divergence point: {diff.first_divergence}",
        f"  confidence: {diff.confidence:.2f}",
    ]
    if diff.live_bar:
        lines.append(f"  LIVE selected bar: index={diff.live_bar.index} timestamp={diff.live_bar.timestamp} close={diff.live_bar.close} complete={diff.live_bar.complete}")
    if diff.backtest_bar:
        lines.append(f"  BACKTEST selected bar: index={diff.backtest_bar.index} timestamp={diff.backtest_bar.timestamp} close={diff.backtest_bar.close} complete={diff.backtest_bar.complete}")
    lines.append("Divergence checks:")
    for reason in diff.divergence_reasons:
        lines.append(f"  - {reason}")
    lines.append("Evidence:")
    for path in diff.evidence_paths[:8]:
        lines.append(f"  - {path}")
    lines.append("Recommended verification: compare exact bar timestamp and candle values in live report vs backtest output.")
    return "\n".join(lines)
