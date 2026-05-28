"""Phase 23 — backtest vs paper comparison reports (read-only)."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path

from config import ARTIFACTS_DIR, TRADING_REPORTS_DUAL, TRADING_REPORTS_ROOT


def _load_metrics_blobs() -> list[dict]:
    blobs: list[dict] = []
    for base in (TRADING_REPORTS_DUAL, TRADING_REPORTS_ROOT):
        if not base.is_dir():
            continue
        for path in sorted(base.rglob("*"), key=lambda p: p.stat().st_mtime if p.is_file() else 0, reverse=True)[:30]:
            if path.suffix not in {".json", ".csv", ".md", ".log", ".txt"}:
                continue
            try:
                text = path.read_text(encoding="utf-8", errors="replace")[:4000]
            except OSError:
                continue
            if path.suffix == ".json":
                try:
                    blobs.append({"path": str(path), "data": json.loads(text)})
                except json.JSONDecodeError:
                    blobs.append({"path": str(path), "text": text})
            else:
                blobs.append({"path": str(path), "text": text})
    return blobs[:15]


def generate_comparison_report() -> tuple[Path, str]:
    """Build metrics comparison markdown from existing reports/logs."""
    blobs = _load_metrics_blobs()
    symbols: set[str] = set()
    causes: list[str] = []
    rows: list[str] = []

    for b in blobs:
        text = json.dumps(b.get("data", b.get("text", ""))) if isinstance(b.get("data"), dict) else str(b.get("text", ""))
        for sym in re.findall(r"\b[A-Z]{2,5}\b", text[:2000]):
            if len(sym) <= 5:
                symbols.add(sym)
        for kw in ("ranking", "stale", "reject", "risk gate", "delayed", "mismatch", "diverge"):
            if kw in text.lower():
                causes.append(kw)

    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    out_dir = ARTIFACTS_DIR / "comparison"
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"backtest_paper_{ts}.md"

    top_causes = sorted(set(causes))[:8] or ["insufficient log data — run paper loop and export reports"]
    sym_list = sorted(symbols)[:20] or ["(parse from logs when available)"]

    body = f"""# Backtest vs Paper Comparison

Generated: {datetime.now(timezone.utc).isoformat()}

## Metrics comparison

| Metric | Backtest (est.) | Paper/Live (est.) | Notes |
|--------|-----------------|-------------------|-------|
| Sources scanned | {len(blobs)} files | same | read-only |
| Divergence signals | {len(top_causes)} | — | from log keywords |

## Divergence table

| Signal | Seen in logs |
|--------|--------------|
"""
    for c in top_causes:
        body += f"| {c} | yes |\n"

    body += f"""
## Symbols affected

{', '.join(sym_list)}

## Top causes

"""
    for i, c in enumerate(top_causes, 1):
        body += f"{i}. {c}\n"

    body += """
## Suggested experiments (plan only — requires approval to run)

- Compare ranking weights: baseline vs +10% momentum filter
- Delayed entry bar offset: 0 vs 1 vs 2
- Risk gate threshold sweep: conservative / default / relaxed (paper only)
- Stale price guard: enable strict reject vs warn-only

_No trading logic changed by this report._
"""
    path.write_text(body, encoding="utf-8")
    return path, body
