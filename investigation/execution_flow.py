"""Phase 46.6 execution flow reconstruction — step-by-step signal lifecycle debugger (read-only)."""

from __future__ import annotations

import json
import re
from collections import Counter
from dataclasses import asdict, dataclass, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from config import PROJECT_ROOT, TRADING_PROJECT_ROOT
from investigation.execution_investigation import (
    _adapter_state,
    _collect_evidence,
    _derive_counts,
    _detect_blockers,
    _extract_int,
    _extract_str,
    _read,
)

FLOW_REPORT_DIR = PROJECT_ROOT / "reports" / "jarvis_investigations" / "execution_flow"

_LAST_FLOW: "ExecutionFlowAudit | None" = None

LIFECYCLE_STEPS: tuple[str, ...] = (
    "signal detected",
    "eligible",
    "last bar relevance",
    "duplicate check",
    "already in position check",
    "overlap check",
    "max positions check",
    "exposure/risk check",
    "market open check",
    "kill switch check",
    "adapter health",
    "order attempt",
)

STEP_PATTERNS: dict[str, tuple[str, ...]] = {
    "last bar relevance": (r"not_relevant_to_last_bar", r"last_closed_bar", r"signal_detection_mode"),
    "duplicate check": (r"duplicate", r"dedup", r"already attempted"),
    "already in position check": (r"already in position", r"already_in_position", r"existing position"),
    "overlap check": (r"overlap", r"conflicting signal"),
    "max positions check": (r"max_open", r"max_positions", r"max positions", r"position cap"),
    "exposure/risk check": (r"exposure", r"risk check", r"risk_check", r"risk budget", r"portfolio.*limit"),
    "market open check": (r"market closed", r"market_closed", r"outside market hours"),
    "kill switch check": (r"kill_switch", r"kill switch", r"kill_switch_enabled"),
    "adapter health": (r"executiondisabledadapter", r"execution.*disabled", r"adapter.*disabled", r"dry_run"),
    "delayed entry failure": (r"delayed entry", r"delayed_entry", r"next bar entry"),
}

EXPECTED_BLOCKERS = frozenset(
    {
        "dry run mode",
        "market closed",
        "kill switch check",
        "max positions reached",
        "already in position",
    }
)


@dataclass(frozen=True)
class LifecycleStep:
    name: str
    passed: bool
    detail: str
    evidence_path: str
    snippet: str
    expected: bool


@dataclass(frozen=True)
class SignalLifecycle:
    symbol: str
    signal_date: str
    eligible: bool
    order_attempt: bool
    final_block_reason: str
    steps: list[LifecycleStep]
    suspicious: bool


@dataclass(frozen=True)
class ExecutionFlowAudit:
    created_at: str
    files_scanned: int
    signals_generated: int
    signals_eligible: int
    signals_blocked: int
    n_execution_attempts: int
    n_execution_accepted: int
    top_blocker: str
    lifecycles: list[SignalLifecycle]
    dead_causes: list[tuple[str, int, str]]
    evidence_paths: list[str]
    report_json: str = ""
    report_markdown: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _symbols(text: str) -> list[str]:
    symbols = re.findall(r"\b[A-Z][A-Z0-9.\-]{0,7}\b", text)
    ignored = {"OPEN", "HIGH", "LOW", "CLOSE", "TRUE", "FALSE", "JSON", "UTC", "CSV", "LONG", "SHORT"}
    return [s for s in symbols if s not in ignored]


def _timestamps(text: str) -> list[str]:
    return [
        m.replace("/", "-").replace(" ", "T")
        for m in re.findall(
            r"20\d\d[-/]\d\d[-/]\d\d(?:[ T]\d\d:\d\d(?::\d\d)?(?:[+\-]\d\d:?\d\d|Z)?)?",
            text,
        )
    ]


def _find_evidence(patterns: tuple[str, ...], files: list[Path], haystack: str) -> tuple[str, str, bool]:
    for path in files[:80]:
        text = _read(path, 12000)
        if not any(re.search(pat, text, re.I) for pat in patterns):
            continue
        for line in text.splitlines():
            if any(re.search(pat, line, re.I) for pat in patterns):
                return str(path), line.strip()[:260], True
        return str(path), text[:260], True
    if any(re.search(pat, haystack, re.I) for pat in patterns):
        return "combined evidence", haystack[:260], True
    return "", "", False


def _step(
    name: str,
    *,
    passed: bool,
    detail: str,
    evidence_path: str = "",
    snippet: str = "",
    expected: bool = False,
) -> LifecycleStep:
    return LifecycleStep(
        name=name,
        passed=passed,
        detail=detail,
        evidence_path=evidence_path,
        snippet=snippet,
        expected=expected,
    )


def _evaluate_step(
    step_name: str,
    *,
    files: list[Path],
    combined: str,
    symbol_text: str,
) -> LifecycleStep:
    hay = f"{combined}\n{symbol_text}".lower()
    if step_name == "signal detected":
        detected = bool(re.search(r"signal|n_new_signals|live_signals", hay, re.I))
        path, snippet, hit = _find_evidence((r"signal", r"n_new_signals"), files, hay)
        return _step(
            step_name,
            passed=detected,
            detail="signal evidence found" if detected else "no signal evidence",
            evidence_path=path,
            snippet=snippet,
        )
    if step_name == "eligible":
        eligible_hint = _extract_int(combined, "n_signals_eligible")
        blocked = _extract_int(combined, "n_signals_blocked")
        passed = eligible_hint is None or (eligible_hint or 0) > 0
        if blocked and eligible_hint is not None:
            passed = eligible_hint > 0
        path, snippet, _ = _find_evidence((r"eligible", r"n_signals_eligible", r"n_new_signals"), files, hay)
        return _step(
            step_name,
            passed=passed,
            detail=f"eligible={passed}",
            evidence_path=path,
            snippet=snippet,
        )
    if step_name == "order attempt":
        attempts = _extract_int(combined, "n_execution_attempts") or 0
        passed = attempts > 0
        path, snippet, _ = _find_evidence((r"n_execution_attempts", r"execution_order_events"), files, hay)
        return _step(
            step_name,
            passed=passed,
            detail=f"attempts={attempts}",
            evidence_path=path,
            snippet=snippet,
        )
    if step_name == "adapter health":
        adapter, dry_run, disabled = _adapter_state(combined)
        passed = disabled == "no" and dry_run != "true"
        path, snippet, _ = _find_evidence(STEP_PATTERNS["adapter health"], files, hay)
        detail = f"adapter={adapter} dry_run={dry_run} disabled={disabled}"
        return _step(
            step_name,
            passed=passed,
            detail=detail,
            evidence_path=path,
            snippet=snippet or detail,
            expected=dry_run == "true" or disabled == "yes",
        )

    patterns = STEP_PATTERNS.get(step_name, ())
    hit = any(re.search(pat, hay, re.I) for pat in patterns) if patterns else False
    path, snippet, _ = _find_evidence(patterns, files, hay) if patterns else ("", "", False)
    # Gate passed when blocker pattern NOT found (check cleared).
    passed = not hit
    expected = step_name.replace(" check", "") in {"market open", "kill switch"} or hit
    detail = "blocked" if hit else "clear"
    return _step(
        step_name,
        passed=passed,
        detail=detail,
        evidence_path=path,
        snippet=snippet,
        expected=expected,
    )


def _build_lifecycle(
    symbol: str,
    *,
    files: list[Path],
    combined: str,
    blockers: list[Any],
) -> SignalLifecycle:
    symbol_hits: list[str] = []
    signal_date = "unknown"
    for path in files[:60]:
        text = _read(path, 10000)
        if symbol not in text and symbol.replace("-", ".") not in text:
            continue
        symbol_hits.append(str(path))
        ts = _timestamps(text)
        if ts:
            signal_date = ts[0][:10]
    symbol_text = "\n".join(_read(Path(p), 4000) for p in symbol_hits[:8] if Path(p).exists())

    steps = [_evaluate_step(name, files=files, combined=combined, symbol_text=symbol_text) for name in LIFECYCLE_STEPS]
    eligible_step = next(s for s in steps if s.name == "eligible")
    attempt_step = next(s for s in steps if s.name == "order attempt")

    failing = [s for s in steps if not s.passed and s.name not in {"signal detected"}]
    final_block = failing[0].name if failing else "none"
    for blocker in blockers[:10]:
        reason = getattr(blocker, "reason", str(blocker))
        for step in steps:
            if not step.passed and reason.lower() in step.name.lower():
                final_block = reason
                break

    reason_if_no = _extract_str(combined, "reason_if_no_attempt")
    if reason_if_no:
        final_block = reason_if_no.replace("_", " ")

    suspicious = bool(failing) and attempt_step.passed is False and not any(s.expected for s in failing)
    if final_block in {"execution disabled adapter", "not relevant to last bar"}:
        suspicious = True

    return SignalLifecycle(
        symbol=symbol,
        signal_date=signal_date,
        eligible=eligible_step.passed,
        order_attempt=attempt_step.passed,
        final_block_reason=final_block,
        steps=steps,
        suspicious=suspicious,
    )


def _discover_symbols(files: list[Path], combined: str, limit: int = 12) -> list[str]:
    found: list[str] = []
    for path in files[:40]:
        if "signal" not in str(path).lower() and "execution" not in str(path).lower():
            continue
        found.extend(_symbols(_read(path, 8000)))
    if not found:
        found = _symbols(combined)
    uniq: list[str] = []
    for sym in found:
        if sym not in uniq:
            uniq.append(sym)
        if len(uniq) >= limit:
            break
    return uniq or ["AAPL"]


def run_execution_flow_reconstruction() -> ExecutionFlowAudit:
    global _LAST_FLOW
    from runtime.result_stream import stream_progress, stream_result

    stream_progress("scanning reports...")
    files, combined = _collect_evidence()
    stream_progress("analyzing execution blockers...")
    blockers = _detect_blockers(files, combined)
    signals, eligible, blocked, attempts, accepted = _derive_counts(combined, blockers)
    symbols = _discover_symbols(files, combined)
    stream_progress("building symbol lifecycles...")
    lifecycles = [_build_lifecycle(sym, files=files, combined=combined, blockers=blockers) for sym in symbols[:8]]

    cause_counts: Counter[str] = Counter()
    for lc in lifecycles:
        if lc.order_attempt:
            continue
        cause_counts[lc.final_block_reason] += 1
        for step in lc.steps:
            if not step.passed and step.name not in {"signal detected", "order attempt"}:
                cause_counts[step.name] += 1
    for blocker in blockers:
        cause_counts[blocker.reason] += blocker.count

    dead_causes = [(reason, count, "blocked signal lifecycle") for reason, count in cause_counts.most_common(20)]
    top_blocker = blockers[0].reason if blockers else (dead_causes[0][0] if dead_causes else "none")
    if top_blocker and top_blocker != "none":
        stream_result(f"top blocker: {top_blocker}")

    audit = ExecutionFlowAudit(
        created_at=datetime.now(timezone.utc).isoformat(),
        files_scanned=len(files),
        signals_generated=signals,
        signals_eligible=eligible,
        signals_blocked=blocked,
        n_execution_attempts=attempts,
        n_execution_accepted=accepted,
        top_blocker=top_blocker,
        lifecycles=lifecycles,
        dead_causes=dead_causes,
        evidence_paths=[str(p) for p in files[:25]],
    )
    stream_progress("saving execution flow report...")
    _LAST_FLOW = _save_flow(audit)
    return _LAST_FLOW


def _latest_flow() -> ExecutionFlowAudit:
    global _LAST_FLOW
    if _LAST_FLOW is None:
        _LAST_FLOW = run_execution_flow_reconstruction()
    return _LAST_FLOW


def _save_flow(audit: ExecutionFlowAudit) -> ExecutionFlowAudit:
    FLOW_REPORT_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    json_path = FLOW_REPORT_DIR / f"{ts}_execution_flow.json"
    md_path = FLOW_REPORT_DIR / f"{ts}_execution_flow.md"
    payload = audit.to_dict()
    payload["report_json"] = str(json_path)
    payload["report_markdown"] = str(md_path)
    json_path.write_text(json.dumps(payload, indent=2, ensure_ascii=True), encoding="utf-8")
    md_path.write_text(_format_report_markdown(payload), encoding="utf-8")
    return replace(audit, report_json=str(json_path), report_markdown=str(md_path))


def _format_report_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Execution Flow Report",
        f"Generated: {payload['created_at']}",
        "## Summary",
        f"- Signals generated: {payload['signals_generated']}",
        f"- Signals eligible: {payload['signals_eligible']}",
        f"- Signals blocked: {payload['signals_blocked']}",
        f"- Execution attempts: {payload['n_execution_attempts']}",
        f"- Top blocker: {payload['top_blocker']}",
        "## Dead Signal Causes",
    ]
    for reason, count, note in payload.get("dead_causes", [])[:20]:
        lines.append(f"- {reason}: count={count} ({note})")
    lines.append("## Signal Lifecycles")
    for lc in payload.get("lifecycles", [])[:10]:
        lines.append(f"### {lc['symbol']} ({lc['signal_date']})")
        lines.append(f"- final block: {lc['final_block_reason']} suspicious={lc['suspicious']}")
        for step in lc.get("steps", []):
            status = "PASS" if step["passed"] else "FAIL"
            lines.append(f"  - [{status}] {step['name']}: {step['detail']}")
    lines.append("## Recommended Verification")
    lines.extend(
        [
            "- Confirm last-bar signal mode vs eligible symbols on final candle.",
            "- Inspect entry_blocks / reason_if_no_attempt in execution_decision_summary.json.",
            "- Verify adapter is not ExecutionDisabledAdapter when paper trading is expected.",
            "- Check kill_switch and max_open settings against open positions.",
        ]
    )
    return "\n".join(lines)


def _format_lifecycle(lc: SignalLifecycle) -> list[str]:
    lines = [
        f"Symbol: {lc.symbol} date: {lc.signal_date}",
        f"  eligible: {lc.eligible}",
        f"  order attempt: {lc.order_attempt}",
        f"  final block reason: {lc.final_block_reason}",
        f"  suspicious: {lc.suspicious}",
        "  steps:",
    ]
    for step in lc.steps:
        status = "PASS" if step.passed else "FAIL"
        expected = " expected" if step.expected else ""
        suspicious = " suspicious" if (not step.passed and not step.expected) else ""
        lines.append(f"    [{status}] {step.name}: {step.detail}{expected}{suspicious}")
        if step.evidence_path:
            lines.append(f"      evidence: {step.evidence_path}")
        if step.snippet:
            lines.append(f"      snippet: {step.snippet}")
    return lines


def _find_lifecycle(symbol: str, audit: ExecutionFlowAudit | None = None) -> SignalLifecycle:
    audit = audit or _latest_flow()
    symbol = symbol.upper()
    for lc in audit.lifecycles:
        if lc.symbol == symbol:
            return lc
    files, combined = _collect_evidence()
    blockers = _detect_blockers(files, combined)
    return _build_lifecycle(symbol, files=files, combined=combined, blockers=blockers)


def trace_signal_to_execution(symbol: str = "AAPL") -> str:
    audit = _latest_flow()
    lc = _find_lifecycle(symbol, audit)
    lines = [f"Signal-to-execution trace: {lc.symbol}", *_format_lifecycle(lc)]
    lines.append("Suggested verification: compare this gate sequence with execution_decision_summary.json entry_blocks.")
    return "\n".join(lines)


def trace_blocked_signal(symbol: str = "AAPL") -> str:
    audit = _latest_flow()
    lc = _find_lifecycle(symbol, audit)
    lines = [f"Blocked signal trace: {lc.symbol}"]
    blocked_steps = [s for s in lc.steps if not s.passed]
    if not blocked_steps:
        lines.append("No failing gates detected; signal may be blocked downstream.")
    for step in blocked_steps:
        tag = "expected" if step.expected else "suspicious"
        lines.append(f"- {step.name}: {step.detail} ({tag})")
        lines.append(f"  evidence: {step.evidence_path or 'none'}")
        lines.append(f"  snippet: {step.snippet or step.detail}")
    lines.append(f"Final block reason: {lc.final_block_reason}")
    return "\n".join(lines)


def explain_top_execution_blocker() -> str:
    audit = _latest_flow()
    lines = [
        "Top execution blocker explanation:",
        f"  top blocker: {audit.top_blocker}",
        f"  signals blocked: {audit.signals_blocked}",
        f"  execution attempts: {audit.n_execution_attempts}",
    ]
    for reason, count, note in audit.dead_causes[:5]:
        lines.append(f"- {reason}: count={count} ({note})")
    lines.append("Suggested verification:")
    if "last bar" in audit.top_blocker.lower():
        lines.append("  - Run with a symbol that has a signal on the last closed bar.")
    if "disabled" in audit.top_blocker.lower() or "adapter" in audit.top_blocker.lower():
        lines.append("  - Enable paper adapter instead of ExecutionDisabledAdapter.")
    if "kill" in audit.top_blocker.lower():
        lines.append("  - Inspect kill_switch_enabled in live summary/config.")
    if "overlap" in audit.top_blocker.lower() or "max position" in audit.top_blocker.lower():
        lines.append("  - Review open positions and overlap policy.")
    lines.append("  - Compare live_signals.csv rows to execution_order_events.csv.")
    return "\n".join(lines)


def reconstruct_execution_flow() -> str:
    audit = run_execution_flow_reconstruction()
    lines = [
        "Execution flow reconstruction (read-only):",
        f"  files scanned: {audit.files_scanned}",
        f"  signals generated: {audit.signals_generated}",
        f"  signals eligible: {audit.signals_eligible}",
        f"  signals blocked: {audit.signals_blocked}",
        f"  execution attempts: {audit.n_execution_attempts}",
        f"  top blocker: {audit.top_blocker}",
        "  symbol lifecycles:",
    ]
    for lc in audit.lifecycles[:8]:
        fail = next((s.name for s in lc.steps if not s.passed and s.name not in {"signal detected"}), "none")
        lines.append(
            f"    - {lc.symbol} eligible={lc.eligible} attempt={lc.order_attempt} "
            f"first_fail={fail} final={lc.final_block_reason}"
        )
    lines.append(f"  report json: {audit.report_json}")
    return "\n".join(lines)


def show_signal_lifecycle_timeline() -> str:
    audit = _latest_flow()
    lines = ["Signal lifecycle timeline:"]
    for lc in audit.lifecycles[:10]:
        lines.append(f"--- {lc.symbol} ({lc.signal_date}) ---")
        for idx, step in enumerate(lc.steps, start=1):
            mark = "OK" if step.passed else "BLOCK"
            lines.append(f"  {idx}. [{mark}] {step.name}: {step.detail}")
        lines.append(f"  => final: {lc.final_block_reason} attempt={lc.order_attempt}")
    return "\n".join(lines)


def rank_dead_signal_causes() -> str:
    audit = _latest_flow()
    lines = ["Ranked dead signal causes:"]
    if not audit.dead_causes:
        lines.append("- No dead-signal causes identified.")
    for idx, (reason, count, note) in enumerate(audit.dead_causes[:20], start=1):
        lines.append(f"{idx}. {reason} count={count} note={note}")
    return "\n".join(lines)


def simulate_unblock_scenario(scenario: str = "top") -> str:
    audit = _latest_flow()
    target = audit.top_blocker if scenario in {"top", "", "default"} else scenario.replace("_", " ")
    lines = [
        "Unblock scenario simulation (preview-only, no code/config changes):",
        f"  scenario: remove/mitigate blocker '{target}'",
        f"  current attempts: {audit.n_execution_attempts}",
        f"  current blocked: {audit.signals_blocked}",
    ]
    affected = [lc for lc in audit.lifecycles if target.lower() in lc.final_block_reason.lower()]
    if not affected:
        affected = [lc for lc in audit.lifecycles if not lc.order_attempt][:3]
    for lc in affected[:5]:
        lines.append(f"  - {lc.symbol}: would attempt order if '{target}' cleared (simulated)")
    lines.append("Estimated impact: +{} simulated attempt(s)".format(len(affected)))
    lines.append("Rollback: no changes applied; rerun reconstruct execution flow after real fix.")
    return "\n".join(lines)


def propose_execution_fix() -> str:
    audit = _latest_flow()
    top = audit.top_blocker.lower()
    lines = [
        "Execution fix proposal (preview-only):",
        f"  problem: eligible signals blocked; top blocker={audit.top_blocker}",
        f"  affected symbols: {', '.join(lc.symbol for lc in audit.lifecycles[:8]) or 'unknown'}",
        "  proposed changes:",
    ]
    if "disabled" in top or "adapter" in top:
        lines.append("    - Switch execution adapter from disabled stub to paper adapter.")
    if "dry run" in top:
        lines.append("    - Set dry_run=false for paper verification run (after adapter enabled).")
    if "last bar" in top:
        lines.append("    - Align signal_detection_mode with symbols that actually signal on last closed bar.")
    if "kill" in top:
        lines.append("    - Disable kill_switch_enabled after confirming risk posture.")
    if "max position" in top or "overlap" in top:
        lines.append("    - Raise max_open or resolve overlapping symbol entries before next cycle.")
    if "market closed" in top:
        lines.append("    - Restrict live entries to market hours or use delayed entry policy explicitly.")
    if len(lines) <= 4:
        lines.append("    - Inspect execution_decision_summary.json entry_blocks for explicit reason codes.")
    lines.extend(
        [
            "  tests to run:",
            "    - reconstruct execution flow",
            "    - compare signal count to order attempts",
            "  rollback:",
            "    - restore prior adapter/dry_run/kill_switch settings from config snapshot",
        ]
    )
    return "\n".join(lines)


def generate_execution_flow_report() -> str:
    audit = run_execution_flow_reconstruction()
    return (
        "Execution flow report saved:\n"
        f"  JSON: {audit.report_json}\n"
        f"  Markdown: {audit.report_markdown}\n\n"
        f"Top blocker: {audit.top_blocker}\n"
        f"Signals: generated={audit.signals_generated} eligible={audit.signals_eligible} "
        f"blocked={audit.signals_blocked} attempts={audit.n_execution_attempts}"
    )
