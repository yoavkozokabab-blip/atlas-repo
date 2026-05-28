"""Phase 47 safe patch preview for execution state cleanup (read-only, no production writes)."""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from config import PROJECT_ROOT, TRADING_PROJECT_ROOT
from investigation.execution_investigation import (
    _adapter_state,
    _collect_evidence,
    _derive_counts,
    _extract_int,
    _extract_str,
    _read,
)

CLEANUP_REPORT_DIR = PROJECT_ROOT / "reports" / "jarvis_investigations" / "execution_cleanup"

_LAST_PREVIEW: "ExecutionCleanupPreview | None" = None


@dataclass(frozen=True)
class StalePosition:
    symbol: str
    entry_date: str
    reason: str
    stop_hit: bool
    close_rejected: bool
    evidence_path: str
    snippet: str


@dataclass(frozen=True)
class CleanupPatchCandidate:
    candidate_id: str
    title: str
    affected_files: list[str]
    expected_effect: str
    risk: str
    minimal_diff: str
    rollback_plan: str
    verification_commands: list[str]


@dataclass(frozen=True)
class ExecutionCleanupPreview:
    created_at: str
    files_scanned: int
    adapter_mode: str
    adapter_health_ok: bool
    execution_enabled: bool
    kill_switch_enabled: bool
    alpaca_keys_missing: bool
    engine_open_position_count: int
    adapter_position_count: int
    stale_positions: list[StalePosition]
    risk_before: float
    risk_after_simulated: float
    open_risk_fraction_daily_before: float
    open_risk_fraction_daily_after: float
    daily_max_total_risk_cap: float
    signals_eligible_before: int
    signals_eligible_after_simulated: int
    execution_attempts: int
    primary_execution_blocker: str
    candidates: list[CleanupPatchCandidate]
    selected_candidate: str
    patch_preview_diff: str
    tests_to_run: list[str]
    rollback_plan: str
    evidence_paths: list[str]
    report_json: str = ""
    report_markdown: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _likely_files() -> list[str]:
    return [
        str(TRADING_PROJECT_ROOT / "services" / "live_paper_engine.py"),
        str(TRADING_PROJECT_ROOT / "services" / "live_dual_paper_cycle.py"),
        str(TRADING_PROJECT_ROOT / "services" / "execution_adapter.py"),
        str(TRADING_PROJECT_ROOT / "reports" / "live_paper" / "dual" / "state" / "open_positions.json"),
        str(TRADING_PROJECT_ROOT / "reports" / "live_paper" / "dual" / "execution_decision_summary.json"),
        str(TRADING_PROJECT_ROOT / "reports" / "live_paper" / "dual" / "execution_order_events.csv"),
    ]


def _extract_float(text: str, label: str) -> float | None:
    patterns = [
        rf'"{label}"\s*:\s*(-?\d+(?:\.\d+)?)',
        rf"\b{label}\b\s*[=:]\s*(-?\d+(?:\.\d+)?)",
    ]
    for pat in patterns:
        m = re.search(pat, text, re.I)
        if m:
            try:
                return float(m.group(1))
            except ValueError:
                continue
    return None


def _symbols(text: str) -> list[str]:
    found = re.findall(r'"symbol"\s*:\s*"([A-Z][A-Z0-9.\-]{0,7})"', text, re.I)
    if found:
        return found
    raw = re.findall(r"\b[A-Z][A-Z0-9.\-]{0,7}\b", text)
    ignored = {"OPEN", "HIGH", "LOW", "CLOSE", "TRUE", "FALSE", "JSON", "UTC", "CSV", "LONG", "SHORT"}
    return [s for s in raw if s not in ignored]


def _parse_open_positions(files: list[Path], combined: str) -> tuple[list[StalePosition], int]:
    stale: list[StalePosition] = []
    count = 0
    for path in files:
        if "open_positions" not in str(path).lower():
            continue
        text = _read(path, 20000)
        if not text.strip():
            continue
        count = max(count, len(re.findall(r'"symbol"\s*:', text)))
        symbols = _symbols(text)
        for sym in symbols[:30]:
            chunk_pat = rf'"symbol"\s*:\s*"{re.escape(sym)}"[\s\S]{{0,800}}'
            chunk_m = re.search(chunk_pat, text, re.I)
            chunk = chunk_m.group(0) if chunk_m else text[:400]
            stop_hit = bool(re.search(r"stop_loss_hit|stop hit|forced exit", chunk, re.I)) or bool(
                re.search(r"stop_loss_hit", combined, re.I)
            )
            close_rejected = bool(re.search(r"close_order_rejected|close.*rejected|rejected", chunk, re.I)) or bool(
                re.search(rf"{sym}.*rejected", combined, re.I)
            )
            entry_date = "unknown"
            date_m = re.search(r'"entry_date"\s*:\s*"([^"]+)"', chunk)
            if date_m:
                entry_date = date_m.group(1)
            reason = "stale_open_after_stop_rejected"
            if stop_hit and close_rejected:
                reason = "stop_loss_hit_close_order_rejected"
            elif stop_hit:
                reason = "stop_loss_hit_adapter_disabled"
            stale.append(
                StalePosition(
                    symbol=sym,
                    entry_date=entry_date,
                    reason=reason,
                    stop_hit=stop_hit,
                    close_rejected=close_rejected,
                    evidence_path=str(path),
                    snippet=chunk[:260],
                )
            )
        if stale:
            break
    if not stale and count == 0:
        engine_count = _extract_int(combined, "engine_open_position_count") or _extract_int(combined, "n_open_positions_before")
        if engine_count:
            count = engine_count
            for i in range(min(engine_count, 9)):
                stale.append(
                    StalePosition(
                        symbol=f"POS{i+1}",
                        entry_date="unknown",
                        reason="engine_open_without_adapter_positions",
                        stop_hit=True,
                        close_rejected=True,
                        evidence_path="combined evidence",
                        snippet=combined[:260],
                    )
                )
    return stale, count


def _generate_candidates() -> list[CleanupPatchCandidate]:
    files = _likely_files()
    return [
        CleanupPatchCandidate(
            "P1",
            "Paper-local close when adapter disabled and stop/forced exit triggered",
            files[:3],
            "Closes stale paper positions locally when broker adapter is disabled; emits paper_local_close_after_adapter_disabled.",
            "MEDIUM - paper-only state mutation; must never run on real live brokerage path.",
            """```diff
--- a/services/live_paper_engine.py
+++ b/services/live_paper_engine.py
@@
+if paper_mode and adapter_is_disabled and position.forced_exit_due:
+    record_event("close_order_paper_only", reason="paper_local_close_after_adapter_disabled")
+    close_local_open_position(position, broker_close_sent=False)
+    emit_warning("Broker close NOT sent; adapter disabled/missing keys")
+    return
```""",
            "Remove paper-local close branch; restore prior open_positions persistence behavior.",
            [
                "pytest tests/test_execution_cleanup_p1.py -q",
                "show stale open positions",
                "compare risk before after cleanup",
            ],
        ),
        CleanupPatchCandidate(
            "P2",
            "Prefer signal-level blockers over scan-level not_relevant_to_last_bar telemetry",
            files[3:5],
            "reason_if_no_attempt and primary_execution_blocker prefer exposure/risk/signal blockers.",
            "LOW - telemetry only.",
            """```diff
--- a/services/live_dual_paper_cycle.py
+++ b/services/live_dual_paper_cycle.py
@@
-reason_if_no_attempt = "not_relevant_to_last_bar"
+reason_if_no_attempt = primary_signal_blocker or scan_skip_reason
+if primary_signal_blocker:
+    primary_execution_blocker = primary_signal_blocker
```""",
            "Restore previous reason_if_no_attempt assignment order.",
            ["pytest tests/test_execution_cleanup_p2.py -q", "explain top execution blocker"],
        ),
        CleanupPatchCandidate(
            "P3",
            "Separate scan skip count from execution rejection count",
            files[3:5],
            "Adds n_scan_rows_skipped_last_bar distinct from n_execution_rejected.",
            "LOW - reporting only.",
            """```diff
--- a/services/live_dual_paper_cycle.py
+++ b/services/live_dual_paper_cycle.py
@@
+n_scan_rows_skipped_last_bar = count_scan_skipped_last_bar(signals)
 n_execution_rejected = count_execution_rejected(signals)
```""",
            "Remove n_scan_rows_skipped_last_bar field from execution_decision_summary.",
            ["pytest tests/test_execution_cleanup_p3.py -q"],
        ),
        CleanupPatchCandidate(
            "P4",
            "Surface adapter/risk/kill-switch fields in execution_decision_summary",
            files[3:5],
            "Always expose kill_switch_enabled, adapter_health_ok, execution_enabled, primary_execution_blocker, open_risk_fraction_daily, daily_max_total_risk_cap.",
            "LOW - reporting only.",
            """```diff
--- a/services/live_dual_paper_cycle.py
+++ b/services/live_dual_paper_cycle.py
@@
+summary["kill_switch_enabled"] = kill_switch_enabled
+summary["adapter_health_ok"] = adapter_health_ok
+summary["execution_enabled"] = execution_enabled
+summary["primary_execution_blocker"] = primary_execution_blocker
+summary["open_risk_fraction_daily"] = open_risk_fraction_daily
+summary["daily_max_total_risk_cap"] = daily_max_total_risk_cap
```""",
            "Remove added summary telemetry keys.",
            ["pytest tests/test_execution_cleanup_p4.py -q", "inspect execution adapter"],
        ),
    ]


def _primary_blocker(combined: str, stale: list[StalePosition]) -> str:
    for label in (
        "exposure_limit_reached",
        "max_total_risk_engine",
        "primary_execution_blocker",
        "reason_if_no_attempt",
    ):
        value = _extract_str(combined, label)
        if value and value.lower() not in {"none", "null", "not_relevant_to_last_bar"}:
            return value.replace("_", " ")
    if stale and any(s.stop_hit for s in stale):
        return "stale open positions after stop_loss_hit"
    if re.search(r"exposure_limit|max_total_risk", combined, re.I):
        return "exposure_limit_reached"
    return "execution disabled adapter"


def _build_preview() -> ExecutionCleanupPreview:
    files, combined = _collect_evidence()
    adapter, dry_run, disabled = _adapter_state(combined)
    signals, eligible, blocked, attempts, _accepted = _derive_counts(combined, [])
    stale, engine_count = _parse_open_positions(files, combined)
    adapter_count = _extract_int(combined, "adapter_position_count") or 0
    if engine_count == 0:
        engine_count = _extract_int(combined, "n_open_positions_before") or _extract_int(combined, "engine_open_position_count") or len(stale)
    risk_per = _extract_float(combined, "risk_per_trade") or 0.0125
    risk_cap = _extract_float(combined, "daily_max_total_risk_cap") or _extract_float(combined, "max_total_risk") or 0.10
    risk_before = round(min(engine_count * risk_per, 1.0), 4)
    open_risk_before = _extract_float(combined, "open_risk_fraction_daily") or risk_before
    closable = [s for s in stale if s.stop_hit or s.close_rejected or s.reason.startswith("engine_open")]
    closed_count = len(closable) if closable else max(engine_count - adapter_count, 0)
    risk_after = round(max(open_risk_before - closed_count * risk_per, 0.0), 4)
    open_risk_after = round(max(open_risk_before - closed_count * risk_per, 0.0), 4)
    eligible_after = eligible
    if open_risk_after < risk_cap and blocked > 0:
        eligible_after = min(signals, eligible + min(blocked, closed_count))
    elif open_risk_after < open_risk_before and eligible_after == eligible and signals > attempts:
        eligible_after = min(signals, eligible + 1)
    candidates = _generate_candidates()
    selected = "P1"
    primary = _primary_blocker(combined, stale)
    return ExecutionCleanupPreview(
        created_at=datetime.now(timezone.utc).isoformat(),
        files_scanned=len(files),
        adapter_mode=adapter,
        adapter_health_ok=disabled == "no" and dry_run != "true",
        execution_enabled=disabled == "no",
        kill_switch_enabled=bool(re.search(r"kill_switch_enabled\s*[:=]\s*true", combined, re.I)),
        alpaca_keys_missing=bool(re.search(r"ALPACA_API_KEY|ALPACA_SECRET_KEY|missing.*alpaca", combined, re.I)),
        engine_open_position_count=engine_count,
        adapter_position_count=adapter_count,
        stale_positions=stale[:50],
        risk_before=risk_before,
        risk_after_simulated=risk_after,
        open_risk_fraction_daily_before=open_risk_before,
        open_risk_fraction_daily_after=open_risk_after,
        daily_max_total_risk_cap=risk_cap,
        signals_eligible_before=eligible,
        signals_eligible_after_simulated=eligible_after,
        execution_attempts=attempts,
        primary_execution_blocker=primary,
        candidates=candidates,
        selected_candidate=selected,
        patch_preview_diff=candidates[0].minimal_diff,
        tests_to_run=[
            "ExecutionDisabledAdapter + stop hit closes local paper position only",
            "does not mark broker execution accepted",
            "risk fraction drops after local close",
            "telemetry primary blocker prefers exposure_limit_reached over scan noise",
            "execution summary includes kill switch + adapter status",
            "no live order call",
        ],
        rollback_plan=candidates[0].rollback_plan,
        evidence_paths=[str(p) for p in files[:25]],
    )


def _latest_preview() -> ExecutionCleanupPreview:
    global _LAST_PREVIEW
    if _LAST_PREVIEW is None:
        _LAST_PREVIEW = _save_preview(_build_preview())
    return _LAST_PREVIEW


def _save_preview(preview: ExecutionCleanupPreview) -> ExecutionCleanupPreview:
    CLEANUP_REPORT_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    json_path = CLEANUP_REPORT_DIR / f"{ts}_execution_cleanup.json"
    md_path = CLEANUP_REPORT_DIR / f"{ts}_execution_cleanup.md"
    payload = preview.to_dict()
    payload["report_json"] = str(json_path)
    payload["report_markdown"] = str(md_path)
    json_path.write_text(json.dumps(payload, indent=2, ensure_ascii=True), encoding="utf-8")
    md_path.write_text(_format_report_markdown(payload), encoding="utf-8")
    return replace(preview, report_json=str(json_path), report_markdown=str(md_path))


def _format_report_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Execution Cleanup Patch Preview",
        f"Generated: {payload['created_at']}",
        "## Problem",
        "- ExecutionDisabledAdapter + stop_loss_hit close rejections leave stale open_positions.",
        "- Engine open count exceeds adapter positions; risk cap blocks new signals.",
        "## State",
        f"- adapter: {payload['adapter_mode']} health_ok={payload['adapter_health_ok']}",
        f"- kill_switch_enabled: {payload['kill_switch_enabled']}",
        f"- alpaca keys missing: {payload['alpaca_keys_missing']}",
        f"- engine_open_positions: {payload['engine_open_position_count']}",
        f"- adapter_positions: {payload['adapter_position_count']}",
        f"- primary blocker: {payload['primary_execution_blocker']}",
        "## Risk Simulation",
        f"- risk before: {payload['risk_before']}",
        f"- risk after (simulated P1): {payload['risk_after_simulated']}",
        f"- open_risk_fraction_daily before/after: {payload['open_risk_fraction_daily_before']} -> {payload['open_risk_fraction_daily_after']}",
        f"- eligible signals before/after: {payload['signals_eligible_before']} -> {payload['signals_eligible_after_simulated']}",
        "## Stale Positions",
    ]
    for pos in payload.get("stale_positions", [])[:20]:
        lines.append(
            f"- {pos['symbol']} {pos['entry_date']} reason={pos['reason']} stop_hit={pos['stop_hit']} evidence={pos['evidence_path']}"
        )
    lines.extend(["## Patch Preview", payload.get("patch_preview_diff", ""), "## Tests", ""])
    lines.extend(f"- {t}" for t in payload.get("tests_to_run", []))
    lines.extend(["## Rollback", payload.get("rollback_plan", ""), "## Safety", "- Preview only; no production apply without explicit approval."])
    return "\n".join(lines)


def simulate_execution_cleanup_patch() -> str:
    global _LAST_PREVIEW
    preview = _save_preview(_build_preview())
    _LAST_PREVIEW = preview
    lines = [
        "Execution cleanup patch simulation (preview-only, no production writes):",
        f"  selected candidate: {preview.selected_candidate} - {preview.candidates[0].title}",
        f"  stale positions: {len(preview.stale_positions)}",
        f"  engine/adapters: {preview.engine_open_position_count}/{preview.adapter_position_count}",
        f"  risk before: {preview.risk_before}",
        f"  risk after (simulated): {preview.risk_after_simulated}",
        f"  eligible signals before/after: {preview.signals_eligible_before} -> {preview.signals_eligible_after_simulated}",
        f"  execution attempts (unchanged): {preview.execution_attempts}",
        "  simulated events:",
        "    - close_order_paper_only (NOT broker accepted)",
        "    - paper_local_close_after_adapter_disabled",
        "  warning preserved: adapter failure / missing Alpaca keys still surfaced",
        f"  report json: {preview.report_json}",
    ]
    return "\n".join(lines)


def compare_risk_before_after_cleanup() -> str:
    preview = _latest_preview()
    return "\n".join(
        [
            "Risk before/after simulated cleanup:",
            f"  open_risk_fraction_daily: {preview.open_risk_fraction_daily_before} -> {preview.open_risk_fraction_daily_after}",
            f"  aggregate risk estimate: {preview.risk_before} -> {preview.risk_after_simulated}",
            f"  daily_max_total_risk_cap: {preview.daily_max_total_risk_cap}",
            f"  engine open positions: {preview.engine_open_position_count}",
            f"  adapter positions: {preview.adapter_position_count}",
            f"  primary blocker: {preview.primary_execution_blocker}",
            f"  signals eligible before: {preview.signals_eligible_before}",
            f"  signals eligible after simulated cleanup: {preview.signals_eligible_after_simulated}",
            "  note: simulation only; open_positions.json not modified.",
        ]
    )


def show_stale_open_positions() -> str:
    preview = _latest_preview()
    lines = [
        "Stale open positions (read-only scan):",
        f"  engine_open_position_count={preview.engine_open_position_count}",
        f"  adapter_position_count={preview.adapter_position_count}",
        f"  adapter={preview.adapter_mode} disabled={not preview.execution_enabled}",
    ]
    if not preview.stale_positions:
        lines.append("- No stale positions parsed from local evidence.")
    for pos in preview.stale_positions[:25]:
        lines.append(f"- {pos.symbol} entry={pos.entry_date} reason={pos.reason}")
        lines.append(f"  stop_hit={pos.stop_hit} close_rejected={pos.close_rejected}")
        lines.append(f"  evidence: {pos.evidence_path}")
        lines.append(f"  snippet: {pos.snippet}")
    return "\n".join(lines)


def propose_execution_cleanup_patch() -> str:
    preview = _latest_preview()
    lines = [
        "Execution cleanup patch proposal (preview-only):",
        f"  problem: {preview.primary_execution_blocker}",
        f"  root evidence: ExecutionDisabledAdapter / missing ALPACA keys + stop_loss_hit close rejections",
        f"  stale positions: {len(preview.stale_positions)}",
        "  candidates:",
    ]
    for cand in preview.candidates:
        lines.append(f"    - {cand.candidate_id}: {cand.title} (risk={cand.risk})")
    lines.extend(
        [
            f"  recommended bundle: {preview.selected_candidate} + P2 + P4 telemetry",
            "  patch preview diff:",
            preview.patch_preview_diff,
            "  tests to run:",
        ]
    )
    lines.extend(f"    - {t}" for t in preview.tests_to_run)
    lines.append(f"  rollback: {preview.rollback_plan}")
    lines.append("  approval required before any production apply.")
    return "\n".join(lines)


def generate_execution_cleanup_report() -> str:
    global _LAST_PREVIEW
    preview = _save_preview(_build_preview())
    _LAST_PREVIEW = preview
    return (
        "Execution cleanup report saved:\n"
        f"  JSON: {preview.report_json}\n"
        f"  Markdown: {preview.report_markdown}\n\n"
        f"Stale positions: {len(preview.stale_positions)}\n"
        f"Risk: {preview.risk_before} -> {preview.risk_after_simulated}\n"
        f"Eligible signals: {preview.signals_eligible_before} -> {preview.signals_eligible_after_simulated}"
    )
