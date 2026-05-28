"""Phase 46.4 price integrity and candle consistency checks (read-only)."""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from config import PROJECT_ROOT, TRADING_PROJECT_ROOT

PRICE_REPORT_DIR = PROJECT_ROOT / "reports" / "jarvis_investigations" / "price_integrity"
REPORT_SUFFIXES = {".json", ".csv", ".txt", ".md", ".log"}
MAX_FILES = 240

_LAST_AUDIT: "PriceIntegrityAudit | None" = None


@dataclass(frozen=True)
class CandleRecord:
    source: str
    symbol: str
    timestamp: str
    open: float | None
    high: float | None
    low: float | None
    close: float | None
    adjusted: bool
    evidence_path: str
    snippet: str


@dataclass(frozen=True)
class PriceMismatch:
    symbol: str
    timestamp: str
    live_ohlc: dict[str, float | None]
    backtest_ohlc: dict[str, float | None]
    delta_pct: float | None
    likely_source: str
    evidence_path: str
    snippet: str


@dataclass(frozen=True)
class PriceIntegrityAudit:
    created_at: str
    records_scanned: int
    files_scanned: int
    mismatches: list[PriceMismatch]
    duplicate_bars: list[str]
    timestamp_issues: list[str]
    adjusted_price_evidence: list[str]
    cache_drift_evidence: list[str]
    affected_symbols: list[str]
    affected_dates: list[str]
    report_json: str = ""
    report_markdown: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _roots() -> list[Path]:
    return [
        TRADING_PROJECT_ROOT / "reports" / "live_paper",
        TRADING_PROJECT_ROOT / "reports" / "live_paper" / "dual",
        TRADING_PROJECT_ROOT / "reports" / "live_paper" / "state",
        TRADING_PROJECT_ROOT / "reports" / "live_paper_trials",
        TRADING_PROJECT_ROOT / "reports" / "backtests",
        TRADING_PROJECT_ROOT / "backtests",
        TRADING_PROJECT_ROOT / "data",
        TRADING_PROJECT_ROOT / "cache",
        TRADING_PROJECT_ROOT / "caches",
        TRADING_PROJECT_ROOT / "reports",
        PROJECT_ROOT / "reports" / "jarvis_investigations",
    ]


def _read(path: Path, max_chars: int = 12000) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")[:max_chars]
    except OSError:
        return ""


def _iter_files() -> list[Path]:
    out: list[Path] = []
    for root in _roots():
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if len(out) >= MAX_FILES:
                break
            if path.is_file() and path.suffix.lower() in REPORT_SUFFIXES:
                out.append(path)
    return sorted(set(out), key=lambda p: p.stat().st_mtime if p.exists() else 0, reverse=True)[:MAX_FILES]


def _source_kind(path: Path) -> str:
    text = str(path).lower()
    if "backtest" in text:
        return "backtest"
    if "live_paper" in text or "live" in text or "paper" in text:
        return "live"
    if "cache" in text or "data" in text:
        return "cache"
    return "unknown"


def _as_float(value: str | None) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _symbols(text: str) -> list[str]:
    symbols = re.findall(r"\b[A-Z][A-Z0-9.\-]{0,7}\b", text)
    ignored = {"OPEN", "HIGH", "LOW", "CLOSE", "TRUE", "FALSE", "JSON", "UTC", "CAGR", "MFE"}
    return [s for s in symbols if s not in ignored]


def _timestamps(text: str) -> list[str]:
    return [m.replace("/", "-").replace(" ", "T") for m in re.findall(r"20\d\d[-/]\d\d[-/]\d\d[ T]\d\d:\d\d(?::\d\d)?(?:[+\-]\d\d:?\d\d|Z)?", text)]


def _extract_labeled_float(text: str, label: str) -> float | None:
    patterns = [
        rf'"{label}"\s*:\s*"?(-?\d+(?:\.\d+)?)"?',
        rf"\b{label}\b\s*[=:]\s*'?\"?(-?\d+(?:\.\d+)?)",
        rf"\b{label}_{'price' if label == 'close' else ''}\b\s*[=:]\s*'?\"?(-?\d+(?:\.\d+)?)",
    ]
    for pat in patterns:
        m = re.search(pat, text, re.I)
        if m:
            return _as_float(m.group(1))
    return None


def _extract_records_from_text(path: Path, text: str) -> list[CandleRecord]:
    records: list[CandleRecord] = []
    source = _source_kind(path)
    chunks = re.split(r"\n(?=\{|\[|[A-Z][A-Z0-9.\-]{0,7}\b)", text)
    for chunk in chunks[:200]:
        if not any(k in chunk.lower() for k in ("close", "open", "high", "low", "ohlc", "price", "selected_bar")):
            continue
        syms = _symbols(chunk)
        symbol = syms[0] if syms else "UNKNOWN"
        ts = (_timestamps(chunk) or _timestamps(text) or ["unknown"])[0]
        close = _extract_labeled_float(chunk, "close") or _extract_labeled_float(chunk, "live_close") or _extract_labeled_float(chunk, "backtest_close")
        if close is None:
            close = _extract_labeled_float(chunk, "price")
        rec = CandleRecord(
            source=source,
            symbol=symbol,
            timestamp=ts,
            open=_extract_labeled_float(chunk, "open"),
            high=_extract_labeled_float(chunk, "high"),
            low=_extract_labeled_float(chunk, "low"),
            close=close,
            adjusted=bool(re.search(r"adj(?:usted)?[_ ]?close|split|dividend", chunk, re.I)),
            evidence_path=str(path),
            snippet=" ".join(chunk.strip().split())[:260],
        )
        if rec.close is not None:
            records.append(rec)
    # Special case for reports that only say live_close/backtest_close in same line.
    for line in text.splitlines():
        lower = line.lower()
        if "live_close" in lower or "backtest_close" in lower or "price mismatch" in lower:
            syms = _symbols(line)
            ts = (_timestamps(line) or _timestamps(text) or ["unknown"])[0]
            if "live_close" in lower:
                records.append(
                    CandleRecord(source="live", symbol=syms[0] if syms else "UNKNOWN", timestamp=ts, open=None, high=None, low=None, close=_extract_labeled_float(line, "live_close"), adjusted=False, evidence_path=str(path), snippet=line.strip()[:260])
                )
            if "backtest_close" in lower:
                records.append(
                    CandleRecord(source="backtest", symbol=syms[0] if syms else "UNKNOWN", timestamp=ts, open=None, high=None, low=None, close=_extract_labeled_float(line, "backtest_close"), adjusted=False, evidence_path=str(path), snippet=line.strip()[:260])
                )
    return records


def _collect_records() -> tuple[list[CandleRecord], list[Path]]:
    files = _iter_files()
    records: list[CandleRecord] = []
    for path in files:
        records.extend(_extract_records_from_text(path, _read(path)))
    return records, files


def _ohlc(record: CandleRecord) -> dict[str, float | None]:
    return {"open": record.open, "high": record.high, "low": record.low, "close": record.close}


def _delta_pct(a: float | None, b: float | None) -> float | None:
    if a is None or b in (None, 0):
        return None
    return round(((a - b) / b) * 100.0, 4)


def _likely_source(live: CandleRecord, backtest: CandleRecord) -> str:
    hay = f"{live.snippet} {backtest.snippet} {live.evidence_path} {backtest.evidence_path}".lower()
    if "adj" in hay or "split" in hay or "dividend" in hay:
        return "adjusted vs unadjusted price usage"
    if "cache" in hay or "yahoo" in hay:
        return "Yahoo/cache drift or data refresh timing"
    if live.timestamp != backtest.timestamp:
        return "timestamp/timezone/index alignment mismatch"
    if "execution" in hay or "fill" in hay:
        return "execution price vs signal close source"
    return "close price source mismatch"


def run_price_integrity_audit() -> PriceIntegrityAudit:
    global _LAST_AUDIT
    records, files = _collect_records()
    live = [r for r in records if r.source == "live"]
    backtest = [r for r in records if r.source == "backtest"]
    mismatches: list[PriceMismatch] = []
    for lrec in live:
        candidates = [b for b in backtest if b.symbol == lrec.symbol and b.timestamp == lrec.timestamp]
        if not candidates:
            candidates = [b for b in backtest if b.symbol == lrec.symbol]
        for brec in candidates[:2]:
            if lrec.close is None or brec.close is None:
                continue
            delta = _delta_pct(lrec.close, brec.close)
            if delta is not None and abs(delta) > 0.0001:
                mismatches.append(
                    PriceMismatch(
                        symbol=lrec.symbol,
                        timestamp=lrec.timestamp if lrec.timestamp != "unknown" else brec.timestamp,
                        live_ohlc=_ohlc(lrec),
                        backtest_ohlc=_ohlc(brec),
                        delta_pct=delta,
                        likely_source=_likely_source(lrec, brec),
                        evidence_path=lrec.evidence_path,
                        snippet=f"LIVE: {lrec.snippet} | BACKTEST: {brec.snippet}"[:500],
                    )
                )
                break
    seen: dict[tuple[str, str, str], int] = {}
    for rec in records:
        key = (rec.source, rec.symbol, rec.timestamp)
        seen[key] = seen.get(key, 0) + 1
    duplicate_bars = [f"{src}:{sym}:{ts} count={count}" for (src, sym, ts), count in seen.items() if count > 1 and ts != "unknown"][:50]
    timestamp_issues = [
        f"{r.evidence_path}: {r.symbol} timestamp={r.timestamp} source={r.source}"
        for r in records
        if r.timestamp == "unknown" or "+" in r.timestamp or r.timestamp.endswith("Z")
    ][:50]
    adjusted = [f"{r.evidence_path}: {r.symbol} {r.timestamp} adjusted price clue" for r in records if r.adjusted][:50]
    cache_drift = [str(p) for p in files if any(k in str(p).lower() for k in ("cache", "yahoo", "data"))][:50]
    affected_symbols = sorted({m.symbol for m in mismatches if m.symbol != "UNKNOWN"})
    affected_dates = sorted({m.timestamp[:10] for m in mismatches if m.timestamp != "unknown"})
    audit = PriceIntegrityAudit(
        created_at=datetime.now(timezone.utc).isoformat(),
        records_scanned=len(records),
        files_scanned=len(files),
        mismatches=mismatches[:100],
        duplicate_bars=duplicate_bars,
        timestamp_issues=timestamp_issues,
        adjusted_price_evidence=adjusted,
        cache_drift_evidence=cache_drift,
        affected_symbols=affected_symbols[:50],
        affected_dates=affected_dates[:50],
    )
    _LAST_AUDIT = _save_audit(audit)
    return _LAST_AUDIT


def _latest_audit() -> PriceIntegrityAudit:
    global _LAST_AUDIT
    if _LAST_AUDIT is None:
        _LAST_AUDIT = run_price_integrity_audit()
    return _LAST_AUDIT


def _save_audit(audit: PriceIntegrityAudit) -> PriceIntegrityAudit:
    PRICE_REPORT_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    json_path = PRICE_REPORT_DIR / f"{ts}_price_integrity.json"
    md_path = PRICE_REPORT_DIR / f"{ts}_price_integrity.md"
    payload = audit.to_dict()
    payload["report_json"] = str(json_path)
    payload["report_markdown"] = str(md_path)
    json_path.write_text(json.dumps(payload, indent=2, ensure_ascii=True), encoding="utf-8")
    md_path.write_text(_format_report_markdown(payload), encoding="utf-8")
    return replace(audit, report_json=str(json_path), report_markdown=str(md_path))


def _format_report_markdown(payload: dict[str, Any]) -> str:
    mismatches = payload.get("mismatches", [])
    return "\n".join(
        [
            "# Price Integrity Report",
            f"Generated: {payload['created_at']}",
            "## Summary",
            f"- Records scanned: {payload['records_scanned']}",
            f"- Files scanned: {payload['files_scanned']}",
            f"- Mismatches: {len(mismatches)}",
            f"- Affected symbols: {', '.join(payload.get('affected_symbols', [])) or 'none'}",
            f"- Affected dates: {', '.join(payload.get('affected_dates', [])) or 'none'}",
            "## Close Price Mismatches",
            "\n".join(
                f"- {m['symbol']} {m['timestamp']} delta={m['delta_pct']}% source={m['likely_source']} evidence={m['evidence_path']}"
                for m in mismatches[:50]
            ) or "- None",
            "## Duplicate Bars",
            "\n".join(f"- {x}" for x in payload.get("duplicate_bars", [])[:30]) or "- None",
            "## Timestamp Issues",
            "\n".join(f"- {x}" for x in payload.get("timestamp_issues", [])[:30]) or "- None",
            "## Adjusted Price Evidence",
            "\n".join(f"- {x}" for x in payload.get("adjusted_price_evidence", [])[:30]) or "- None",
            "## Cache Drift Evidence",
            "\n".join(f"- {x}" for x in payload.get("cache_drift_evidence", [])[:30]) or "- None",
            "## Recommended Verification",
            "- Compare raw provider candles for affected symbol/date.",
            "- Confirm adjusted vs unadjusted close policy.",
            "- Check timezone normalization before index alignment.",
            "- Verify live signal close and execution/fill price are distinct fields.",
        ]
    )


def audit_price_integrity() -> str:
    audit = run_price_integrity_audit()
    return _summary(audit)


def _summary(audit: PriceIntegrityAudit) -> str:
    return "\n".join(
        [
            "Price integrity audit (read-only)",
            f"  records scanned: {audit.records_scanned}",
            f"  files scanned: {audit.files_scanned}",
            f"  close mismatches: {len(audit.mismatches)}",
            f"  affected symbols: {', '.join(audit.affected_symbols[:20]) or 'none'}",
            f"  affected dates: {', '.join(audit.affected_dates[:20]) or 'none'}",
            f"  report json: {audit.report_json}",
            f"  report markdown: {audit.report_markdown}",
        ]
    )


def find_close_price_mismatches() -> str:
    audit = _latest_audit()
    lines = ["Close price mismatches:"]
    if not audit.mismatches:
        lines.append("- No live/backtest close mismatches found in local evidence.")
    for m in audit.mismatches[:30]:
        lines.append(f"- {m.symbol} {m.timestamp} delta={m.delta_pct}%")
        lines.append(f"  live OHLC: {m.live_ohlc}")
        lines.append(f"  backtest OHLC: {m.backtest_ohlc}")
        lines.append(f"  likely source: {m.likely_source}")
        lines.append(f"  evidence path: {m.evidence_path}")
        lines.append(f"  snippet: {m.snippet}")
        lines.append("  recommended verification: compare provider raw candle and normalized strategy candle for same timestamp.")
    return "\n".join(lines)


def compare_candle_sources() -> str:
    audit = _latest_audit()
    sources = {
        "live/backtest mismatches": len(audit.mismatches),
        "duplicate timestamps": len(audit.duplicate_bars),
        "timestamp alignment issues": len(audit.timestamp_issues),
        "adjusted price clues": len(audit.adjusted_price_evidence),
        "cache/data drift clues": len(audit.cache_drift_evidence),
    }
    lines = ["Candle source comparison:"]
    lines.extend(f"- {k}: {v}" for k, v in sources.items())
    for m in audit.mismatches[:10]:
        lines.append(f"  evidence: {m.evidence_path} :: {m.symbol} {m.timestamp} delta={m.delta_pct}%")
    return "\n".join(lines)


def trace_price_source(symbol: str = "AAPL") -> str:
    symbol = symbol.upper()
    audit = _latest_audit()
    lines = [f"Price source trace: {symbol}"]
    hits = [m for m in audit.mismatches if m.symbol == symbol]
    if not hits:
        lines.append("No direct mismatch for symbol; showing source clues from scanned files.")
        for path in (audit.cache_drift_evidence + audit.adjusted_price_evidence + audit.timestamp_issues)[:15]:
            lines.append(f"- evidence: {path}")
        return "\n".join(lines)
    for m in hits[:20]:
        lines.append(f"- {m.timestamp}: live_close={m.live_ohlc.get('close')} backtest_close={m.backtest_ohlc.get('close')} delta={m.delta_pct}%")
        lines.append(f"  likely source: {m.likely_source}")
        lines.append(f"  evidence path: {m.evidence_path}")
        lines.append(f"  snippet: {m.snippet}")
    return "\n".join(lines)


def inspect_data_cache_drift() -> str:
    audit = _latest_audit()
    lines = ["Data/cache drift inspection:"]
    if not audit.cache_drift_evidence:
        lines.append("- No cache/data/Yahoo paths found in scanned evidence.")
    lines.extend(f"- evidence: {p}" for p in audit.cache_drift_evidence[:40])
    lines.append("Recommended verification: compare cached candle file mtime and values with report generation timestamp.")
    return "\n".join(lines)


def check_timestamp_alignment() -> str:
    audit = _latest_audit()
    lines = ["Timestamp alignment check:"]
    if not audit.timestamp_issues:
        lines.append("- No timezone/unknown timestamp clues found.")
    lines.extend(f"- {x}" for x in audit.timestamp_issues[:40])
    lines.append("Recommended verification: normalize to UTC before sort_index/MultiIndex flattening and compare exact candle keys.")
    return "\n".join(lines)


def check_adjusted_price_usage() -> str:
    audit = _latest_audit()
    lines = ["Adjusted price usage check:"]
    if not audit.adjusted_price_evidence:
        lines.append("- No adjusted/split/dividend clues found.")
    lines.extend(f"- {x}" for x in audit.adjusted_price_evidence[:40])
    lines.append("Recommended verification: confirm both live and backtest use the same adjusted/unadjusted close policy.")
    return "\n".join(lines)


def check_duplicate_bars() -> str:
    audit = _latest_audit()
    lines = ["Duplicate bar check:"]
    if not audit.duplicate_bars:
        lines.append("- No duplicate source/symbol/timestamp records found.")
    lines.extend(f"- {x}" for x in audit.duplicate_bars[:40])
    lines.append("Recommended verification: dedupe after timezone normalization and before signal/ranking.")
    return "\n".join(lines)


def generate_price_integrity_report() -> str:
    audit = run_price_integrity_audit()
    return f"Price integrity report saved:\n  JSON: {audit.report_json}\n  Markdown: {audit.report_markdown}\n\n{_summary(audit)}"
