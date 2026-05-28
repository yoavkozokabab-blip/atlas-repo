"""Deterministic symbol replay engine (analysis-only, no live execution)."""

from __future__ import annotations

import json
import random
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from config import TRADING_PROJECT_ROOT
from investigation.replay_cache import get_cache, set_cache
from investigation.replay_models import ReplayBar, ReplayResult, ReplayStep, stable_hash

DEFAULT_SEED = 46_101


def _read_text(path: Path, max_chars: int = 6000) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")[:max_chars]
    except OSError:
        return ""


def _latest_files(root: Path, suffixes: set[str], limit: int = 30) -> list[Path]:
    if not root.exists():
        return []
    files = [p for p in root.rglob("*") if p.is_file() and p.suffix.lower() in suffixes]
    return sorted(files, key=lambda p: p.stat().st_mtime, reverse=True)[:limit]


def _source_paths(symbol: str) -> list[Path]:
    roots = [
        TRADING_PROJECT_ROOT / "reports" / "live_paper",
        TRADING_PROJECT_ROOT / "reports" / "live_paper_trials",
        TRADING_PROJECT_ROOT / "reports" / "backtests",
        TRADING_PROJECT_ROOT / "backtests",
        TRADING_PROJECT_ROOT / "configs",
        TRADING_PROJECT_ROOT / "config",
        TRADING_PROJECT_ROOT / "universe",
        TRADING_PROJECT_ROOT / "services",
        TRADING_PROJECT_ROOT / "algo_scanner",
        TRADING_PROJECT_ROOT / "analytics",
    ]
    paths: list[Path] = []
    for root in roots:
        paths.extend(_latest_files(root, {".csv", ".json", ".txt", ".md", ".log", ".py", ".yaml", ".yml"}, limit=20))
    symbol_up = symbol.upper()
    ordered = [p for p in paths if symbol_up in str(p).upper() or symbol_up in _read_text(p, 1200).upper()]
    ordered.extend(p for p in paths if p not in ordered)
    seen: set[Path] = set()
    out: list[Path] = []
    for p in ordered:
        if p not in seen:
            seen.add(p)
            out.append(p)
    return out[:60]


def _extract_bars(symbol: str, paths: list[Path]) -> list[ReplayBar]:
    text = "\n".join(_read_text(p, 2500) for p in paths[:20])
    ts_hits = re.findall(r"20\d\d[-/]\d\d[-/]\d\d[ T]\d\d:\d\d(?::\d\d)?", text)
    price_hits = [float(x) for x in re.findall(r"\b(?:close|price|last|entry)[\"'=:\s]+([0-9]+(?:\.[0-9]+)?)", text, re.I)[:4]]
    base = price_hits[0] if price_hits else float(100 + (sum(ord(c) for c in symbol.upper()) % 50))
    timestamps = ts_hits[:3] or [
        "2026-01-01T09:30:00",
        "2026-01-01T09:35:00",
        "2026-01-01T09:40:00",
    ]
    bars: list[ReplayBar] = []
    for idx, ts in enumerate(timestamps[:3]):
        price = base + idx * 0.5
        bars.append(
            ReplayBar(
                index=idx,
                timestamp=ts.replace("/", "-").replace(" ", "T"),
                open=round(price - 0.2, 4),
                high=round(price + 0.8, 4),
                low=round(price - 0.6, 4),
                close=round(price, 4),
                volume=1000.0 + idx,
                complete=idx < len(timestamps[:3]) - 1,
            )
        )
    return bars


def _config_snapshot(paths: list[Path]) -> dict[str, Any]:
    config_paths = [p for p in paths if any(k in str(p).lower() for k in ("config", "settings", ".env"))]
    return {
        "paths": [str(p) for p in config_paths[:10]],
        "hash": stable_hash({str(p): _read_text(p, 1000) for p in config_paths[:10]}),
    }


def _universe_snapshot(paths: list[Path]) -> dict[str, Any]:
    uni_paths = [p for p in paths if any(k in str(p).lower() for k in ("universe", "symbols", "watchlist"))]
    symbols: set[str] = set()
    for path in uni_paths[:10]:
        symbols.update(re.findall(r"\b[A-Z][A-Z0-9.\-]{0,7}\b", _read_text(path, 3000)))
    return {
        "paths": [str(p) for p in uni_paths[:10]],
        "symbols": sorted(symbols)[:200],
        "hash": stable_hash(sorted(symbols)),
    }


def replay_symbol(symbol: str, *, seed: int = DEFAULT_SEED, partial: str | None = None) -> ReplayResult:
    symbol = (symbol or "AAPL").strip().upper()
    cache_key = stable_hash({"symbol": symbol, "seed": seed, "partial": partial})
    cached = get_cache(cache_key)
    if cached is not None:
        return cached
    paths = _source_paths(symbol)
    rng = random.Random(seed)
    config = _config_snapshot(paths)
    universe = _universe_snapshot(paths)
    bars = _extract_bars(symbol, paths)
    ordered_symbols = sorted(set(universe["symbols"] or [symbol]))
    score = round((sum(ord(c) for c in symbol) % 100) / 100 + rng.random() * 0.001, 6)
    stale = any("stale" in _read_text(p, 2000).lower() for p in paths[:15])
    execution_disabled = any(
        "n_execution_attempts" in _read_text(p, 2000).lower()
        or "execution_adapter_disabled" in _read_text(p, 2000).lower()
        for p in paths[:20]
    )
    max_open_reached = any("max_open" in _read_text(p, 2000).lower() for p in paths[:20])
    reasons: list[str] = []
    if stale:
        reasons.append("stale price guard observed in evidence")
    if execution_disabled:
        reasons.append("execution adapter/attempt path observed as disabled or zero")
    if max_open_reached:
        reasons.append("portfolio cap evidence observed")
    if not reasons:
        reasons.append("no rejection reason found; replay remains hypothesis")
    selected = bars[-2] if len(bars) > 1 else bars[-1]
    steps = [
        ReplayStep(
            "signal detection",
            {"symbol": symbol, "bar_index": selected.index, "timestamp": selected.timestamp},
            {"signal": score > 0.15, "price": selected.close},
            evidence_paths=[str(p) for p in paths[:4]],
        ),
        ReplayStep(
            "ranking",
            {"symbol_order": ordered_symbols[:20], "seed": seed},
            {"score": score, "rank": sorted(ordered_symbols).index(symbol) + 1 if symbol in ordered_symbols else 1},
            evidence_paths=[str(p) for p in paths[:4]],
        ),
        ReplayStep(
            "entry gate",
            {"stale_price": stale, "max_open_reached": max_open_reached},
            {"eligible": not stale and not max_open_reached},
            rejection_reason="; ".join(reasons) if (stale or max_open_reached) else "",
            evidence_paths=[str(p) for p in paths[:6]],
        ),
        ReplayStep(
            "delayed entry",
            {"selected_bar": selected.index},
            {"next_bar_index": min(selected.index + 1, bars[-1].index), "frozen": True},
            evidence_paths=[str(p) for p in paths[:6]],
        ),
        ReplayStep(
            "execution attempt",
            {"adapter_disabled": execution_disabled},
            {"execution_attempts": 0 if execution_disabled else 1},
            rejection_reason="execution path disabled/zero attempts" if execution_disabled else "",
            evidence_paths=[str(p) for p in paths[:8]],
        ),
        ReplayStep(
            "stop/target lifecycle",
            {"entry": selected.close},
            {"stop": round(selected.close * 0.95, 4), "target": round(selected.close * 1.1, 4)},
            evidence_paths=[str(p) for p in paths[:8]],
        ),
    ]
    payload = {
        "symbol": symbol,
        "bars": [b.__dict__ for b in bars],
        "score": score,
        "reasons": reasons,
        "paths": [str(p) for p in paths],
        "config": config,
        "universe": universe,
        "steps": [s.__dict__ for s in steps],
    }
    result = ReplayResult(
        symbol=symbol,
        frozen_at=datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        config_hash=config["hash"],
        universe_hash=universe["hash"],
        random_seed=seed,
        selected_bars=bars,
        ranking_scores={symbol: score},
        execution_attempts=0 if execution_disabled else 1,
        rejection_reasons=reasons,
        portfolio_before={"positions": 5 if max_open_reached else 0, "max_open_positions": 5},
        portfolio_after={"positions": 5 if max_open_reached else (1 if not execution_disabled else 0), "max_open_positions": 5},
        steps=steps,
        evidence_paths=[str(p) for p in paths[:20]],
        replay_hash=stable_hash(payload),
    )
    set_cache(cache_key, result)
    return result


def replay_latest_signal() -> ReplayResult:
    paths = _source_paths("AAPL")
    text = "\n".join(_read_text(p, 1500) for p in paths[:20])
    symbols = re.findall(r"\b[A-Z][A-Z0-9.\-]{0,7}\b", text)
    symbol = next((s for s in symbols if s not in {"HIGH", "LOW", "OPEN", "CLOSE"}), "AAPL")
    return replay_symbol(symbol)


def format_replay(result: ReplayResult) -> str:
    lines = [
        f"Deterministic replay: {result.symbol}",
        f"  replay_hash: {result.replay_hash}",
        f"  frozen_at: {result.frozen_at}",
        f"  config_hash: {result.config_hash}",
        f"  universe_hash: {result.universe_hash}",
        f"  random_seed: {result.random_seed}",
        "Selected bars:",
    ]
    for bar in result.selected_bars:
        lines.append(
            f"  - index={bar.index} timestamp={bar.timestamp} open={bar.open} high={bar.high} low={bar.low} close={bar.close} complete={bar.complete}"
        )
    lines.extend(
        [
            f"Ranking scores: {result.ranking_scores}",
            f"Execution attempts: {result.execution_attempts}",
            f"Rejection reasons: {', '.join(result.rejection_reasons)}",
            f"Portfolio before: {result.portfolio_before}",
            f"Portfolio after: {result.portfolio_after}",
            "Steps:",
        ]
    )
    for step in result.steps:
        lines.append(f"STEP {step.name}")
        lines.append(f"  inputs: {step.inputs}")
        lines.append(f"  outputs: {step.outputs}")
        if step.rejection_reason:
            lines.append(f"  rejection_reason: {step.rejection_reason}")
        lines.append(f"  state_delta: {step.state_delta}")
        for path in step.evidence_paths[:3]:
            lines.append(f"  evidence: {path}")
    return "\n".join(lines)
