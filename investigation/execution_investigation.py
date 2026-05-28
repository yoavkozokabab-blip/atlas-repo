"""Phase 46.5 execution eligibility and order attempt investigation (read-only)."""

from __future__ import annotations

import json
import re
from collections import Counter
from dataclasses import asdict, dataclass, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from config import PROJECT_ROOT, TRADING_PROJECT_ROOT

EXECUTION_REPORT_DIR = PROJECT_ROOT / "reports" / "jarvis_investigations" / "execution"
REPORT_SUFFIXES = {".json", ".csv", ".txt", ".md", ".log"}
MAX_FILES = 240

_LAST_AUDIT: "ExecutionInvestigationAudit | None" = None

BLOCKER_PATTERNS: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    ("execution disabled adapter", "critical", (r"executiondisabledadapter", r"execution.*disabled", r"execution_disabled", r"adapter.*disabled")),
    ("dry run mode", "high", (r"\"dry_run\"\s*:\s*true", r"\bdry_run=true\b", r"\bdry run\b")),
    ("not relevant to last bar", "high", (r"not_relevant_to_last_bar", r"last_closed_bar", r"signal_detection_mode")),
    ("max positions reached", "high", (r"max_open", r"max_positions", r"max positions", r"position cap")),
    ("exposure limit", "high", (r"exposure", r"portfolio.*limit", r"risk budget")),
    ("duplicate block", "medium", (r"duplicate", r"already attempted", r"dedup")),
    ("entry trigger failure", "medium", (r"entry_trigger", r"trigger.*fail", r"confirmation.*fail")),
    ("delayed entry failure", "medium", (r"delayed entry", r"delayed_entry", r"next bar entry")),
    ("market closed", "medium", (r"market closed", r"market_closed", r"outside market hours")),
    ("stale price guard", "medium", (r"stale price", r"stale_price", r"stale quote")),
    ("already in position", "medium", (r"already in position", r"already_in_position", r"existing position")),
    ("overlap block", "medium", (r"overlap", r"conflicting signal")),
    ("risk check rejection", "medium", (r"risk check", r"risk_check", r"risk reject")),
    ("order cap per run/day", "medium", (r"order cap", r"orders_per_day", r"daily order limit")),
    ("allowed symbols filter", "medium", (r"allowed symbols", r"symbol filter", r"not in universe")),
)


@dataclass(frozen=True)
class ExecutionBlocker:
    reason: str
    severity: str
    count: int
    evidence_path: str
    snippet: str


@dataclass(frozen=True)
class ExecutionInvestigationAudit:
    created_at: str
    files_scanned: int
    signals_generated: int
    signals_eligible: int
    signals_blocked: int
    n_execution_attempts: int
    n_execution_accepted: int
    adapter_mode: str
    dry_run_status: str
    execution_disabled_status: str
    top_blocker: str
    blockers: list[ExecutionBlocker]
    evidence_paths: list[str]
    recommended_verification: list[str]
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
        TRADING_PROJECT_ROOT / "reports",
        PROJECT_ROOT / "reports" / "jarvis_investigations",
    ]


def _read(path: Path, max_chars: int = 16000) -> str:
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
    keywords = (
        "execution",
        "signal",
        "order",
        "live_summary",
        "paper",
        "adapter",
        "reject",
        "block",
    )
    ranked = sorted(
        set(out),
        key=lambda p: (
            1 if any(k in str(p).lower() for k in keywords) else 0,
            p.stat().st_mtime if p.exists() else 0,
        ),
        reverse=True,
    )
    return ranked[:MAX_FILES]


def _extract_int(text: str, label: str) -> int | None:
    patterns = [
        rf'"{label}"\s*:\s*(-?\d+)',
        rf"\b{label}\b\s*[=:]\s*(-?\d+)",
    ]
    for pat in patterns:
        m = re.search(pat, text, re.I)
        if m:
            try:
                return int(m.group(1))
            except ValueError:
                continue
    return None


def _extract_str(text: str, label: str) -> str | None:
    patterns = [
        rf'"{label}"\s*:\s*"([^"]+)"',
        rf"\b{label}\b\s*[=:]\s*'?\"?([A-Za-z0-9_\- ]+)",
    ]
    for pat in patterns:
        m = re.search(pat, text, re.I)
        if m:
            return m.group(1).strip()
    return None


def _symbols(text: str) -> list[str]:
    symbols = re.findall(r"\b[A-Z][A-Z0-9.\-]{0,7}\b", text)
    ignored = {"OPEN", "HIGH", "LOW", "CLOSE", "TRUE", "FALSE", "JSON", "UTC", "CSV", "LONG", "SHORT"}
    return [s for s in symbols if s not in ignored]


def _score_file(path: Path) -> int:
    name = str(path).lower()
    score = 0
    for token, weight in (
        ("execution_decision_summary", 40),
        ("execution_order_events", 35),
        ("live_summary", 25),
        ("live_signals", 20),
        ("entry_blocks", 15),
        ("execution", 10),
        ("signal", 8),
        ("order", 8),
    ):
        if token in name:
            score += weight
    return score


def _collect_evidence() -> tuple[list[Path], str]:
    files = _iter_files()
    files = sorted(files, key=_score_file, reverse=True)
    combined = "\n".join(_read(p) for p in files[:80])
    return files, combined


def _detect_blockers(files: list[Path], combined: str) -> list[ExecutionBlocker]:
    blockers: list[ExecutionBlocker] = []
    counts: Counter[str] = Counter()
    evidence: dict[str, tuple[str, str]] = {}
    for reason, severity, patterns in BLOCKER_PATTERNS:
        for path in files[:120]:
            text = _read(path, 12000)
            hay = text.lower()
            if not any(re.search(pat, hay, re.I) for pat in patterns):
                continue
            counts[reason] += 1
            if reason not in evidence:
                for line in text.splitlines():
                    lower = line.lower()
                    if any(re.search(pat, lower, re.I) for pat in patterns):
                        evidence[reason] = (str(path), line.strip()[:260])
                        break
                if reason not in evidence:
                    evidence[reason] = (str(path), text[:260])
    for reason, severity, _ in BLOCKER_PATTERNS:
        count = counts.get(reason, 0)
        if count <= 0:
            continue
        path, snippet = evidence.get(reason, ("unknown", ""))
        blockers.append(
            ExecutionBlocker(
                reason=reason,
                severity=severity,
                count=count,
                evidence_path=path,
                snippet=snippet,
            )
        )
    # Parse explicit entry_blocks / reason_if_no_attempt from JSON-ish text.
    for path in files[:40]:
        text = _read(path, 12000)
        for label in ("reason_if_no_attempt", "entry_block_reason", "rejection_reason", "reason"):
            value = _extract_str(text, label)
            if value and value.lower() not in {"none", "null", ""}:
                key = value.replace("_", " ")
                counts[key] += 1
                if key not in evidence:
                    evidence[key] = (str(path), f'"{label}": "{value}"')
    known_reasons = {reason for reason, _, _ in BLOCKER_PATTERNS}
    for key, count in counts.most_common(30):
        if key in known_reasons or any(b.reason == key for b in blockers):
            continue
        path, snippet = evidence.get(key, ("unknown", key))
        blockers.append(
            ExecutionBlocker(
                reason=key,
                severity="medium",
                count=count,
                evidence_path=path,
                snippet=snippet[:260],
            )
        )
    blockers.sort(key=lambda b: (-b.count, b.severity != "critical", b.severity != "high", b.reason))
    return blockers[:50]


def _derive_counts(combined: str, blockers: list[ExecutionBlocker]) -> tuple[int, int, int, int, int]:
    signals = _extract_int(combined, "n_new_signals")
    if signals is None:
        signals = _extract_int(combined, "signals_generated")
    if signals is None:
        signals = _extract_int(combined, "n_signals")
    attempts = _extract_int(combined, "n_execution_attempts")
    accepted = _extract_int(combined, "n_execution_accepted")
    eligible = _extract_int(combined, "n_signals_eligible")
    blocked = _extract_int(combined, "n_signals_blocked")
    if signals is None:
        signals = max(attempts or 0, accepted or 0, 0)
    if attempts is None:
        attempts = 0
    if accepted is None:
        accepted = 0
    if eligible is None:
        eligible = max(signals - (blocked or 0), accepted, 0)
    if blocked is None:
        blocked = max(signals - attempts, 0)
    return signals, eligible, blocked, attempts, accepted


def _adapter_state(combined: str) -> tuple[str, str, str]:
    adapter = _extract_str(combined, "execution_adapter") or _extract_str(combined, "adapter") or "unknown"
    if re.search(r'\"dry_run\"\s*:\s*true|\bdry_run=true\b|\bdry run enabled\b', combined, re.I):
        dry_run = "true"
    elif re.search(r'\"dry_run\"\s*:\s*false|\bdry_run=false\b', combined, re.I):
        dry_run = "false"
    else:
        dry_run = "unknown"
    disabled = "yes" if re.search(r"executiondisabledadapter|execution.*disabled|adapter.*disabled", combined, re.I) else "no"
    if adapter.lower().endswith("disabledadapter") or "disabled" in adapter.lower():
        disabled = "yes"
    return adapter, dry_run, disabled


def _recommended_verification(audit: ExecutionInvestigationAudit) -> list[str]:
    recs = [
        "Confirm execution adapter is enabled for paper/live mode (not ExecutionDisabledAdapter).",
        "Verify dry_run flag matches intended environment.",
        "Check signal_detection_mode vs eligible last-bar signals.",
        "Inspect entry_blocks and reason_if_no_attempt in execution_decision_summary.json.",
        "Compare live_signals.csv rows to execution_order_events.csv attempt events.",
    ]
    top = audit.top_blocker.lower()
    if "last bar" in top:
        recs.insert(0, "Run one symbol with a signal on the last closed bar and confirm attempt counter increments.")
    if "disabled" in top:
        recs.insert(0, "Switch adapter from disabled stub to paper adapter and rerun one dry-run cycle.")
    if "dry run" in top:
        recs.insert(0, "Set dry_run=false in paper config only after adapter verification.")
    if "max position" in top or "exposure" in top:
        recs.insert(0, "Review open positions and portfolio caps before next signal cycle.")
    return recs[:8]


def run_execution_investigation() -> ExecutionInvestigationAudit:
    global _LAST_AUDIT
    files, combined = _collect_evidence()
    blockers = _detect_blockers(files, combined)
    signals, eligible, blocked, attempts, accepted = _derive_counts(combined, blockers)
    adapter, dry_run, disabled = _adapter_state(combined)
    top_blocker = blockers[0].reason if blockers else "none identified"
    evidence_paths = [str(p) for p in files[:25]]
    audit = ExecutionInvestigationAudit(
        created_at=datetime.now(timezone.utc).isoformat(),
        files_scanned=len(files),
        signals_generated=signals,
        signals_eligible=eligible,
        signals_blocked=blocked,
        n_execution_attempts=attempts,
        n_execution_accepted=accepted,
        adapter_mode=adapter,
        dry_run_status=dry_run,
        execution_disabled_status=disabled,
        top_blocker=top_blocker,
        blockers=blockers,
        evidence_paths=evidence_paths,
        recommended_verification=[],
    )
    audit = replace(audit, recommended_verification=_recommended_verification(audit))
    _LAST_AUDIT = _save_audit(audit)
    return _LAST_AUDIT


def _latest_audit() -> ExecutionInvestigationAudit:
    global _LAST_AUDIT
    if _LAST_AUDIT is None:
        _LAST_AUDIT = run_execution_investigation()
    return _LAST_AUDIT


def _save_audit(audit: ExecutionInvestigationAudit) -> ExecutionInvestigationAudit:
    EXECUTION_REPORT_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    json_path = EXECUTION_REPORT_DIR / f"{ts}_execution_investigation.json"
    md_path = EXECUTION_REPORT_DIR / f"{ts}_execution_investigation.md"
    payload = audit.to_dict()
    payload["report_json"] = str(json_path)
    payload["report_markdown"] = str(md_path)
    json_path.write_text(json.dumps(payload, indent=2, ensure_ascii=True), encoding="utf-8")
    md_path.write_text(_format_report_markdown(payload), encoding="utf-8")
    return replace(audit, report_json=str(json_path), report_markdown=str(md_path))


def _format_report_markdown(payload: dict[str, Any]) -> str:
    blockers = payload.get("blockers", [])
    return "\n".join(
        [
            "# Execution Investigation Report",
            f"Generated: {payload['created_at']}",
            "## Summary",
            f"- Files scanned: {payload['files_scanned']}",
            f"- Signals generated: {payload['signals_generated']}",
            f"- Signals eligible: {payload['signals_eligible']}",
            f"- Signals blocked: {payload['signals_blocked']}",
            f"- Execution attempts: {payload['n_execution_attempts']}",
            f"- Execution accepted: {payload['n_execution_accepted']}",
            f"- Adapter mode: {payload['adapter_mode']}",
            f"- Dry run: {payload['dry_run_status']}",
            f"- Execution disabled: {payload['execution_disabled_status']}",
            f"- Top blocker: {payload['top_blocker']}",
            "## Block Reasons",
            "\n".join(
                f"- [{b['severity']}] {b['reason']} count={b['count']} evidence={b['evidence_path']}"
                for b in blockers[:30]
            )
            or "- None",
            "## Evidence Paths",
            "\n".join(f"- {p}" for p in payload.get("evidence_paths", [])[:25]) or "- None",
            "## Recommended Verification",
            "\n".join(f"- {x}" for x in payload.get("recommended_verification", [])[:10]) or "- None",
        ]
    )


def _summary(audit: ExecutionInvestigationAudit) -> str:
    return "\n".join(
        [
            "Execution investigation (read-only)",
            f"  files scanned: {audit.files_scanned}",
            f"  signals generated: {audit.signals_generated}",
            f"  signals eligible: {audit.signals_eligible}",
            f"  signals blocked: {audit.signals_blocked}",
            f"  execution attempts: {audit.n_execution_attempts}",
            f"  execution accepted: {audit.n_execution_accepted}",
            f"  adapter mode: {audit.adapter_mode}",
            f"  dry run: {audit.dry_run_status}",
            f"  execution disabled: {audit.execution_disabled_status}",
            f"  top blocker: {audit.top_blocker}",
            f"  report json: {audit.report_json}",
            f"  report markdown: {audit.report_markdown}",
        ]
    )


def audit_execution_path() -> str:
    audit = run_execution_investigation()
    lines = [_summary(audit), "Top evidence paths:"]
    lines.extend(f"  - {p}" for p in audit.evidence_paths[:10])
    return "\n".join(lines)


def explain_zero_execution_attempts() -> str:
    audit = _latest_audit()
    lines = [
        "Zero execution attempts explanation:",
        f"  signals generated: {audit.signals_generated}",
        f"  execution attempts: {audit.n_execution_attempts}",
        f"  execution accepted: {audit.n_execution_accepted}",
        f"  adapter mode: {audit.adapter_mode}",
        f"  execution disabled: {audit.execution_disabled_status}",
        f"  dry run: {audit.dry_run_status}",
        f"  top blocker: {audit.top_blocker}",
    ]
    if audit.n_execution_attempts == 0:
        lines.append("Likely causes:")
        for blocker in audit.blockers[:8]:
            lines.append(f"  - {blocker.reason} (severity={blocker.severity}, hits={blocker.count})")
            lines.append(f"    evidence: {blocker.evidence_path}")
            lines.append(f"    snippet: {blocker.snippet}")
    else:
        lines.append("Attempts are non-zero; inspect accepted vs rejected order events for downstream failures.")
    lines.append("Recommended verification:")
    lines.extend(f"  - {x}" for x in audit.recommended_verification[:5])
    return "\n".join(lines)


def trace_signal_to_order(symbol: str = "AAPL") -> str:
    symbol = (symbol or "AAPL").strip().upper()
    audit = _latest_audit()
    lines = [f"Signal-to-order trace: {symbol}"]
    hits: list[tuple[str, str]] = []
    for path_str in audit.evidence_paths[:40]:
        path = Path(path_str)
        if not path.exists():
            continue
        text = _read(path, 12000)
        if symbol not in text and symbol.replace("-", ".") not in text:
            continue
        for line in text.splitlines():
            lower = line.lower()
            if symbol.lower() in lower or symbol.replace("-", ".").lower() in lower:
                if any(k in lower for k in ("signal", "order", "execution", "attempt", "reject", "block", "entry")):
                    hits.append((str(path), line.strip()[:260]))
    if not hits:
        lines.append(f"No direct {symbol} signal/order evidence found in scanned files.")
        lines.append("Showing global execution path clues instead:")
        for blocker in audit.blockers[:5]:
            lines.append(f"  - {blocker.reason}: {blocker.evidence_path}")
        return "\n".join(lines)
    lines.append("Evidence chain:")
    for path, snippet in hits[:25]:
        lines.append(f"  - {path}")
        lines.append(f"    {snippet}")
    lines.append(
        f"Summary: signals={audit.signals_generated} attempts={audit.n_execution_attempts} accepted={audit.n_execution_accepted}"
    )
    return "\n".join(lines)


def show_execution_blockers() -> str:
    audit = _latest_audit()
    lines = [
        "Execution blockers:",
        f"  signals blocked: {audit.signals_blocked}",
        f"  top blocker: {audit.top_blocker}",
    ]
    if not audit.blockers:
        lines.append("- No explicit blocker clues found.")
    for blocker in audit.blockers[:25]:
        lines.append(f"- [{blocker.severity}] {blocker.reason} count={blocker.count}")
        lines.append(f"  evidence path: {blocker.evidence_path}")
        lines.append(f"  snippet: {blocker.snippet}")
    return "\n".join(lines)


def rank_execution_block_reasons() -> str:
    audit = _latest_audit()
    lines = ["Ranked execution block reasons:"]
    if not audit.blockers:
        lines.append("- No ranked block reasons found.")
    for idx, blocker in enumerate(audit.blockers[:20], start=1):
        lines.append(
            f"{idx}. {blocker.reason} severity={blocker.severity} count={blocker.count} evidence={blocker.evidence_path}"
        )
    return "\n".join(lines)


def inspect_execution_adapter() -> str:
    audit = _latest_audit()
    lines = [
        "Execution adapter inspection:",
        f"  adapter mode: {audit.adapter_mode}",
        f"  dry run status: {audit.dry_run_status}",
        f"  execution disabled: {audit.execution_disabled_status}",
        f"  attempts: {audit.n_execution_attempts}",
        f"  accepted: {audit.n_execution_accepted}",
    ]
    adapter_hits: list[str] = []
    for path_str in audit.evidence_paths[:30]:
        path = Path(path_str)
        if not path.exists():
            continue
        text = _read(path, 8000)
        if re.search(r"execution_adapter|executiondisabledadapter|adapter", text, re.I):
            for line in text.splitlines():
                if re.search(r"execution_adapter|executiondisabledadapter|adapter|dry_run", line, re.I):
                    adapter_hits.append(f"{path}: {line.strip()[:220]}")
    if adapter_hits:
        lines.append("Adapter evidence:")
        lines.extend(f"  - {hit}" for hit in adapter_hits[:20])
    else:
        lines.append("No adapter-specific evidence lines found.")
    if audit.execution_disabled_status == "yes":
        lines.append("Recommended fix: enable paper/live execution adapter instead of disabled stub.")
    return "\n".join(lines)


def compare_signal_count_to_order_attempts() -> str:
    audit = _latest_audit()
    conversion = 0.0
    if audit.signals_generated > 0:
        conversion = round((audit.n_execution_attempts / audit.signals_generated) * 100.0, 2)
    lines = [
        "Signal count vs order attempts:",
        f"  signals generated: {audit.signals_generated}",
        f"  signals eligible: {audit.signals_eligible}",
        f"  signals blocked: {audit.signals_blocked}",
        f"  execution attempts: {audit.n_execution_attempts}",
        f"  execution accepted: {audit.n_execution_accepted}",
        f"  attempt conversion: {conversion}%",
        f"  top blocker: {audit.top_blocker}",
    ]
    if audit.signals_generated > 0 and audit.n_execution_attempts == 0:
        lines.append("Diagnosis: signals exist but no order attempts recorded.")
        lines.append(f"Most likely blocker: {audit.top_blocker}")
    return "\n".join(lines)


def generate_execution_investigation_report() -> str:
    audit = run_execution_investigation()
    return (
        "Execution investigation report saved:\n"
        f"  JSON: {audit.report_json}\n"
        f"  Markdown: {audit.report_markdown}\n\n"
        f"{_summary(audit)}"
    )
