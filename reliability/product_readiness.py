"""Phase 65 product readiness aggregator."""

from __future__ import annotations

from reliability.browser_health import run_browser_acceptance
from reliability.coding_health import run_coding_acceptance
from reliability.desktop_health import run_desktop_acceptance
from reliability.hardening_core import TrackScore, reports_dir, write_report
from reliability.integrations_health import run_integrations_acceptance
from reliability.memory_health import run_memory_acceptance
from reliability.performance_health import run_performance_acceptance
from reliability.system_health import run_reliability_acceptance
from reliability.voice_health import run_voice_acceptance


def collect_all_track_scores(*, run_acceptance: bool = True) -> list[TrackScore]:
    if not run_acceptance:
        # T-12 fix: return 0.0 scores rather than invented estimates.
        # Invented numbers (65, 55, 78, …) gave a false impression of measured
        # readiness.  0.0 makes clear that acceptance has not been run.
        _targets = [
            ("Voice", 85.0),
            ("Memory", 85.0),
            ("Browser", 85.0),
            ("Desktop Operator", 80.0),
            ("Coding Assistant", 90.0),
            ("Integrations", 60.0),
            ("Reliability", 85.0),
            ("Performance", 85.0),
        ]
        not_run = [TrackScore(track, 0.0, target) for track, target in _targets]
        for s in not_run:
            s.blockers.append("Acceptance suite was not run (run_acceptance=False).")
        return not_run
    return [
        run_voice_acceptance(),
        run_memory_acceptance(),
        run_browser_acceptance(),
        run_desktop_acceptance(),
        run_coding_acceptance(),
        run_integrations_acceptance(),
        run_reliability_acceptance(),
        run_performance_acceptance(),
    ]


def generate_product_readiness_report() -> str:
    scores = collect_all_track_scores(run_acceptance=True)
    lines = [
        "# Product Readiness Report (Phase 65)",
        "",
        "| Capability | Current % | Target % | Gap | Status |",
        "|------------|-----------|----------|-----|--------|",
    ]
    for s in scores:
        status = "READY" if s.current_pct >= s.target_pct else "HARDENING"
        lines.append(f"| {s.track} | {s.current_pct} | {s.target_pct} | {s.gap} | {status} |")
    lines.extend(["", "## Per-Capability Detail", ""])
    for s in scores:
        blocker_lines = [f"  - {b}" for b in s.blockers] or ["  - none"]
        rec_lines = [f"  - {r}" for r in s.recommendations] or ["  - continue monitoring"]
        lines.extend(
            [
                f"### {s.track}",
                f"- current: {s.current_pct}%",
                f"- target: {s.target_pct}%",
                f"- gap: {s.gap}%",
                f"- pass_rate: {s.pass_rate:.1f}%",
                "- primary blockers:",
                *blocker_lines,
                "- recommended actions:",
                *rec_lines,
                "",
            ]
        )
    body = "\n".join(lines)
    write_report(reports_dir() / "product_readiness_report.md", body.splitlines())
    return body
