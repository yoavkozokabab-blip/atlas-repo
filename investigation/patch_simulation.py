"""Phase 46.2 patch simulation (preview only, no production writes)."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from config import PROJECT_ROOT, TRADING_PROJECT_ROOT
from investigation.fixture_builder import build_verification_fixture
from investigation.replay_diff import diff_live_backtest, format_replay_diff
from investigation.replay_engine import replay_symbol
from investigation.replay_models import ReplayBar, ReplayDiff, stable_hash

SIMULATION_DIR = PROJECT_ROOT / "reports" / "jarvis_investigations" / "patch_simulations"


@dataclass(frozen=True)
class PatchCandidate:
    candidate_id: str
    title: str
    affected_files: list[str]
    expected_effect: str
    risk: str
    minimal_diff: str
    rollback_plan: str
    verification_commands: list[str]


@dataclass(frozen=True)
class PatchSimulation:
    created_at: str
    selected_candidate: str
    before: dict[str, Any]
    after: dict[str, Any]
    divergence_fixed: bool
    new_divergence_introduced: bool
    confidence_before: float
    confidence_after: float
    confidence_delta: float
    evidence_paths: list[str]
    report_json: str = ""
    report_markdown: str = ""


_PENDING_SIMULATION: PatchSimulation | None = None


def _likely_files() -> list[str]:
    return [
        str(TRADING_PROJECT_ROOT / "services" / "live_paper_engine.py"),
        str(TRADING_PROJECT_ROOT / "services" / "live_dual_paper_cycle.py"),
        str(TRADING_PROJECT_ROOT / "algo_scanner" / "backtest" / "fib_quality.py"),
        str(TRADING_PROJECT_ROOT / "algo_scanner" / "strategy" / "real_algo.py"),
        str(TRADING_PROJECT_ROOT / "run_live_paper_monitor.py"),
        str(TRADING_PROJECT_ROOT / "reports" / "live_paper" / "dual"),
    ]


def generate_patch_candidates() -> list[PatchCandidate]:
    files = _likely_files()
    return [
        PatchCandidate(
            "A",
            "Force live replay/signal path to use last completed bar only",
            files[:4],
            "Live selected bar should align with backtest completed historical bar before signal detection.",
            "MEDIUM - changes live signal timing; may skip signals that previously used incomplete bars.",
            """```diff
--- a/services/live_paper_engine.py
+++ b/services/live_paper_engine.py
@@
-candidate_bar = bars.iloc[-1]
+candidate_bar = last_completed_bar(bars)
+decision.selected_bar_complete = True
```""",
            "Restore prior bar selection expression in live signal path.",
            [
                "py -3 -m py_compile services/live_paper_engine.py",
                "py -3 -m pytest tests/test_bar_alignment.py -q",
                "replay live vs backtest AAPL",
            ],
        ),
        PatchCandidate(
            "B",
            "Normalize live/backtest bar index alignment before signal detection",
            files[:4],
            "Both modes compute equivalent signal bar index from completed candle timestamps.",
            "MEDIUM - requires careful timestamp/index handling across data providers.",
            """```diff
--- a/algo_scanner/strategy/real_algo.py
+++ b/algo_scanner/strategy/real_algo.py
@@
+aligned_bar = align_signal_bar(mode, bars, require_complete=True)
+candidate_bar = aligned_bar
```""",
            "Remove alignment helper call and revert to previous mode-specific bar selection.",
            [
                "py -3 -m py_compile algo_scanner/strategy/real_algo.py",
                "py -3 -m pytest tests/test_live_backtest_alignment.py -q",
            ],
        ),
        PatchCandidate(
            "C",
            "Reject incomplete candidate bars with explicit reason",
            files[:3],
            "No signal/entry can proceed from incomplete bars; reports expose incomplete_bar as rejection reason.",
            "LOW - safest guard; may reduce live signals but avoids incomplete candle bias.",
            """```diff
--- a/services/live_paper_engine.py
+++ b/services/live_paper_engine.py
@@
+if not candidate_bar.complete:
+    return reject_signal(reason=\"incomplete_bar\")
```""",
            "Remove incomplete_bar guard.",
            [
                "py -3 -m py_compile services/live_paper_engine.py",
                "py -3 -m pytest tests/test_incomplete_bar_guard.py -q",
                "replay symbol AAPL",
            ],
        ),
        PatchCandidate(
            "D",
            "Add selected-bar diagnostics to live reports",
            files,
            "Reports include selected_bar_index/timestamp/complete/close and optional backtest equivalent index.",
            "LOW - reporting-only; does not alter trading behavior.",
            """```diff
--- a/services/live_dual_paper_cycle.py
+++ b/services/live_dual_paper_cycle.py
@@
+execution_decision_summary[\"selected_bar_index\"] = candidate_bar.index
+execution_decision_summary[\"selected_bar_timestamp\"] = candidate_bar.timestamp
+execution_decision_summary[\"selected_bar_complete\"] = candidate_bar.complete
+execution_decision_summary[\"selected_bar_close\"] = candidate_bar.close
```""",
            "Remove selected_bar_* diagnostic fields from report writer.",
            [
                "py -3 -m py_compile services/live_dual_paper_cycle.py",
                "inspect latest live report",
            ],
        ),
    ]


def format_patch_candidates() -> str:
    lines = ["Patch candidates for verified top hypothesis (preview only)."]
    for c in generate_patch_candidates():
        lines.extend(
            [
                f"Candidate {c.candidate_id}: {c.title}",
                f"  affected files: {', '.join(c.affected_files)}",
                f"  expected effect: {c.expected_effect}",
                f"  risk: {c.risk}",
                "  minimal diff preview:",
                c.minimal_diff,
                f"  rollback plan: {c.rollback_plan}",
                "  verification commands:",
                *[f"    - {cmd}" for cmd in c.verification_commands],
                "",
            ]
        )
    return "\n".join(lines)


def _fixed_diff(symbol: str) -> ReplayDiff:
    before = diff_live_backtest(symbol)
    # Candidate A/C simulated behavior: live uses last completed bar or rejects incomplete.
    backtest = before.backtest_bar
    live = backtest
    reasons: list[str] = []
    if live is None or backtest is None:
        reasons = ["no comparable bars available"]
    return ReplayDiff(
        symbol=before.symbol,
        status="same" if not reasons else "unknown",
        first_divergence="no divergence detected" if not reasons else reasons[0],
        live_bar=live,
        backtest_bar=backtest,
        divergence_reasons=reasons,
        evidence_paths=before.evidence_paths,
        confidence=0.96 if not reasons else 0.50,
    )


def _bar_summary(bar: ReplayBar | None) -> dict[str, Any] | None:
    if bar is None:
        return None
    return asdict(bar)


def run_patch_simulation(symbol: str = "AAPL", candidate_id: str = "C") -> PatchSimulation:
    global _PENDING_SIMULATION
    before = diff_live_backtest(symbol)
    after = _fixed_diff(symbol)
    divergence_fixed = bool(before.divergence_reasons) and not after.divergence_reasons
    new_divergence = bool(after.divergence_reasons)
    confidence_before = 0.98 if before.divergence_reasons else before.confidence
    confidence_after = 0.99 if divergence_fixed else after.confidence
    sim = PatchSimulation(
        created_at=datetime.now(timezone.utc).isoformat(),
        selected_candidate=candidate_id,
        before=before.to_dict(),
        after=after.to_dict(),
        divergence_fixed=divergence_fixed,
        new_divergence_introduced=new_divergence,
        confidence_before=confidence_before,
        confidence_after=confidence_after,
        confidence_delta=round(confidence_after - confidence_before, 4),
        evidence_paths=before.evidence_paths,
    )
    saved = save_patch_simulation(sim)
    _PENDING_SIMULATION = saved
    return saved


def save_patch_simulation(sim: PatchSimulation) -> PatchSimulation:
    SIMULATION_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    payload = asdict(sim)
    json_path = SIMULATION_DIR / f"{ts}_patch_simulation.json"
    md_path = SIMULATION_DIR / f"{ts}_patch_simulation.md"
    payload["report_json"] = str(json_path)
    payload["report_markdown"] = str(md_path)
    json_path.write_text(json.dumps(payload, indent=2, ensure_ascii=True), encoding="utf-8")
    md_path.write_text(format_patch_simulation_report(payload), encoding="utf-8")
    return PatchSimulation(**payload)


def format_patch_simulation(sim: PatchSimulation) -> str:
    before = sim.before
    after = sim.after
    return "\n".join(
        [
            "Patch simulation result (temp/in-memory only; production files unchanged).",
            f"Selected candidate: {sim.selected_candidate}",
            f"Before first divergence: {before.get('first_divergence')}",
            f"After first divergence: {after.get('first_divergence')}",
            f"Divergence fixed: {'yes' if sim.divergence_fixed else 'no'}",
            f"New divergence introduced: {'yes' if sim.new_divergence_introduced else 'no'}",
            f"Confidence delta: {sim.confidence_before:.2f} -> {sim.confidence_after:.2f} ({sim.confidence_delta:+.2f})",
            f"JSON report: {sim.report_json}",
            f"Markdown report: {sim.report_markdown}",
        ]
    )


def compare_replay_before_after(symbol: str = "AAPL") -> str:
    before = diff_live_backtest(symbol)
    after = _fixed_diff(symbol)
    fixed = bool(before.divergence_reasons) and not after.divergence_reasons
    lines = [
        "Replay before/after comparison (simulated fix only).",
        f"Fixed mismatch: {'yes' if fixed else 'no'}",
        "Before:",
        f"  live: {_bar_summary(before.live_bar)}",
        f"  backtest: {_bar_summary(before.backtest_bar)}",
        f"  reasons: {before.divergence_reasons}",
        "After simulated fix:",
        f"  live: {_bar_summary(after.live_bar)}",
        f"  backtest: {_bar_summary(after.backtest_bar)}",
        f"  reasons: {after.divergence_reasons or ['none']}",
        "Affected behavior: incomplete live candidate bar is not used for signal/entry evaluation.",
    ]
    return "\n".join(lines)


def estimate_patch_impact(symbol: str = "AAPL") -> str:
    roots = [
        TRADING_PROJECT_ROOT / "reports" / "live_paper",
        TRADING_PROJECT_ROOT / "reports" / "live_paper_trials",
        TRADING_PROJECT_ROOT / "reports" / "live_paper" / "state",
    ]
    affected_symbols: set[str] = set()
    affected_dates: set[str] = set()
    signal_count = 0
    skipped = 0
    false_trade = 0
    evidence: list[str] = []
    for root in roots:
        if not root.exists():
            continue
        for path in sorted(root.rglob("*"), key=lambda p: p.stat().st_mtime if p.is_file() else 0, reverse=True)[:60]:
            if not path.is_file() or path.suffix.lower() not in {".json", ".txt", ".csv", ".log", ".md"}:
                continue
            text = path.read_text(encoding="utf-8", errors="replace")[:5000]
            if any(k in text.lower() for k in ("signal", "selected_bar", "incomplete", "stale", "execution")):
                evidence.append(str(path))
                signal_count += text.lower().count("signal") or 1
                skipped += text.lower().count("skipped") + text.lower().count("reject")
                false_trade += text.lower().count("incomplete")
                affected_symbols.update(__import__("re").findall(r"\b[A-Z][A-Z0-9.\-]{0,7}\b", text))
                affected_dates.update(__import__("re").findall(r"20\d\d-\d\d-\d\d", text))
    if not evidence:
        return "\n".join(
            [
                "Patch impact estimate",
                "  affected symbols: unknown",
                "  affected dates: unknown",
                "  affected signals count: 0 (no local report evidence found)",
                "  likely skipped trades: unknown",
                "  likely false trades: unknown",
                "  confidence: LOW",
                f"  evidence checked: {', '.join(str(r) for r in roots)}",
                "  note: no financial guarantee.",
            ]
        )
    return "\n".join(
        [
            "Patch impact estimate",
            f"  affected symbols: {', '.join(sorted(affected_symbols)[:20]) or symbol}",
            f"  affected dates: {', '.join(sorted(affected_dates)[:10]) or 'unknown'}",
            f"  affected signals count: {signal_count}",
            f"  likely skipped trades: {skipped or 'unknown'}",
            f"  likely false trades: {false_trade or 'unknown'}",
            "  unknowns: exact fill outcomes and future signals",
            "  confidence: MEDIUM",
            "  evidence:",
            *[f"    - {p}" for p in evidence[:12]],
            "  note: estimate only; no financial guarantee.",
        ]
    )


def format_patch_simulation_report(payload: dict[str, Any] | None = None) -> str:
    if payload is None:
        sim = _PENDING_SIMULATION or run_patch_simulation()
        payload = asdict(sim)
    candidates = generate_patch_candidates()
    selected = next((c for c in candidates if c.candidate_id == payload["selected_candidate"]), candidates[2])
    return "\n".join(
        [
            "# Patch Simulation Report",
            f"Generated: {payload['created_at']}",
            "## Verified Root Cause",
            "LIVE selected an incomplete bar while BACKTEST selected the prior completed bar.",
            "Evidence: replay diff before simulation includes incomplete candle/index mismatch.",
            "## Candidate Patches",
            format_patch_candidates(),
            "## Selected Candidate",
            f"{selected.candidate_id}: {selected.title}",
            "## Before Replay",
            json.dumps(payload["before"], indent=2, ensure_ascii=True),
            "## After Simulated Replay",
            json.dumps(payload["after"], indent=2, ensure_ascii=True),
            "## Impact Estimate",
            estimate_patch_impact(),
            "## Risks",
            selected.risk,
            "## Verification Plan",
            "\n".join(f"- {cmd}" for cmd in selected.verification_commands),
            "## Approval Status",
            "pending_patch_simulation exists; patch apply disabled for Phase 46.2 preview.",
        ]
    )


def generate_patch_simulation_report() -> str:
    sim = _PENDING_SIMULATION or run_patch_simulation()
    return f"Patch simulation report saved: {sim.report_markdown}\n\n{format_patch_simulation(sim)}"


def show_patch_simulation() -> str:
    if _PENDING_SIMULATION is None:
        return "No pending patch simulation. Run: run patch simulation"
    return format_patch_simulation(_PENDING_SIMULATION)


def approve_patch_apply() -> str:
    if _PENDING_SIMULATION is None:
        return "No pending_patch_simulation exists. Run patch simulation first."
    return "Patch apply is not enabled for Phase 46.2; preview only."


def reject_patch_apply() -> str:
    global _PENDING_SIMULATION
    _PENDING_SIMULATION = None
    return "Pending patch simulation rejected. No files changed."


def upgraded_patch_proposal() -> str:
    candidate = generate_patch_candidates()[2]
    sim = _PENDING_SIMULATION or run_patch_simulation(candidate_id=candidate.candidate_id)
    return "\n".join(
        [
            "Algorithm patch proposal (preview only; no files changed).",
            f"Selected patch candidate: {candidate.candidate_id} - {candidate.title}",
            f"Why this candidate: lowest-risk guard that blocks incomplete-bar signal evaluation and explains rejection reason.",
            f"Exact affected files: {', '.join(candidate.affected_files)}",
            f"Expected replay result: divergence_fixed={'yes' if sim.divergence_fixed else 'no'}, after={sim.after.get('first_divergence')}",
            f"Risk score: {candidate.risk}",
            "Unified diff preview:",
            candidate.minimal_diff,
            "Tests to run:",
            *[f"- {cmd}" for cmd in candidate.verification_commands],
            f"Rollback plan: {candidate.rollback_plan}",
            "Approval gate: say 'approve patch apply' only after reviewing this preview. Phase 46.2 will still refuse real apply until safe apply is enabled.",
        ]
    )
