"""Cross-source diagnostic analysis (read-only, no fixes)."""

from __future__ import annotations

from diagnostics.collectors import (
    collect_dashboard,
    collect_log_errors,
    collect_loop_signals,
    collect_rejections,
    collect_runtime,
    collect_screen_errors,
)
from diagnostics.models import DiagnosticFinding, DiagnosticReport

_last_report: DiagnosticReport | None = None

_SAFE_STEPS = {
    "dashboard_down": [
        "Run: show dashboard health",
        "Run: open trading dashboard (allowlisted script only)",
        "Check if port 8077 is listening locally",
    ],
    "log_errors": [
        "Run: show last errors",
        "Run: summarize latest log",
        "Run: search trading logs <keyword>",
    ],
    "rejections": [
        "Run: show rejection reasons",
        "Run: show blocked trades",
        "Review risk/position limits in dashboard summary",
    ],
    "screen": [
        "Run: describe screen",
        "Run: detect screen errors",
        "Run: read screen text",
    ],
    "runtime": [
        "Re-run the last command with more detail",
        "Run: show last errors",
        "Run: run diagnostics",
    ],
    "loop": [
        "Run: show dashboard health",
        "Run: diagnose trading loop",
        "Confirm loop status in dashboard before any confirmed run command",
    ],
}


def _store(report: DiagnosticReport) -> DiagnosticReport:
    global _last_report
    _last_report = report
    return report


def get_last_report() -> DiagnosticReport | None:
    return _last_report


def _finding_dashboard(data: dict) -> list[DiagnosticFinding]:
    findings: list[DiagnosticFinding] = []
    if not data.get("reachable"):
        findings.append(
            DiagnosticFinding(
                source="dashboard",
                issue="Trading dashboard is not reachable",
                evidence=[
                    f"port_open={data.get('port_open')}",
                    "Health endpoint returned no usable JSON",
                ],
                severity="critical",
                likely_cause="Dashboard process may be stopped or bound to another port.",
                suggested_steps=_SAFE_STEPS["dashboard_down"],
            )
        )
        return findings

    ks = data.get("kill_switch")
    if ks is True or str(ks).lower() in {"true", "on", "1", "enabled"}:
        findings.append(
            DiagnosticFinding(
                source="dashboard",
                issue="Kill switch appears enabled",
                evidence=[f"kill_switch={ks}"],
                severity="high",
                likely_cause="Trading execution may be halted by kill switch.",
                suggested_steps=[
                    "Run: show dashboard health",
                    "Review dashboard summary before any confirmed trading action",
                ],
            )
        )

    mode = data.get("execution_mode")
    if mode:
        findings.append(
            DiagnosticFinding(
                source="dashboard",
                issue=f"Dashboard execution mode: {mode}",
                evidence=[f"execution_mode={mode}"],
                severity="info",
                likely_cause="Informational state from dashboard API.",
                suggested_steps=["Run: show dashboard health"],
            )
        )
    return findings


def _finding_logs(data: dict) -> list[DiagnosticFinding]:
    count = data.get("line_count", 0)
    lines = data.get("lines") or []
    if count == 0:
        return []
    severity = "high" if count >= 10 else "medium"
    return [
        DiagnosticFinding(
            source="logs",
            issue=f"Recent log errors detected ({count} lines)",
            evidence=lines[:5],
            severity=severity,
            likely_cause="Failures or exceptions in recent trading log files.",
            suggested_steps=_SAFE_STEPS["log_errors"],
        )
    ]


def _finding_rejections(data: dict) -> list[DiagnosticFinding]:
    total = data.get("total_hits", 0)
    top = data.get("top_reasons") or []
    if total == 0:
        return []
    top_reason = top[0][0] if top else "unknown"
    evidence = [f"{r}: {c}" for r, c in top[:5]]
    samples = data.get("samples") or []
    if samples:
        evidence.append(samples[0])
    severity = "high" if total >= 20 else "medium"
    return [
        DiagnosticFinding(
            source="rejections",
            issue=f"Frequent trade rejections/blocks (top: {top_reason})",
            evidence=evidence,
            severity=severity,
            likely_cause="Risk limits, entry confirmation, or position caps may be blocking trades.",
            suggested_steps=_SAFE_STEPS["rejections"],
        )
    ]


def _finding_screen(data: dict) -> list[DiagnosticFinding]:
    if not data.get("enabled"):
        return []
    count = data.get("match_count", 0)
    if count == 0:
        if data.get("ocr_error") or data.get("error"):
            return [
                DiagnosticFinding(
                    source="screen",
                    issue="Screen OCR unavailable for error scan",
                    evidence=[str(data.get("ocr_error") or data.get("error"))],
                    severity="low",
                    likely_cause="Tesseract missing or vision capture failed.",
                    suggested_steps=["Enable VISION_ENABLED and install Tesseract if needed"],
                )
            ]
        return []
    matches = data.get("matches") or []
    evidence = [m.get("line", "")[:120] for m in matches[:5] if m.get("line")]
    return [
        DiagnosticFinding(
            source="screen",
            issue=f"On-screen error-like text detected ({count} lines)",
            evidence=evidence or [f"match_count={count}"],
            severity="medium",
            likely_cause="Visible UI or console may show an active error state.",
            suggested_steps=_SAFE_STEPS["screen"],
        )
    ]


def _finding_runtime(data: dict) -> list[DiagnosticFinding]:
    findings: list[DiagnosticFinding] = []
    err = data.get("last_error")
    if err:
        findings.append(
            DiagnosticFinding(
                source="runtime",
                issue="Last JARVIS command reported an error",
                evidence=[err[:200], (data.get("last_result_summary") or "")[:120]],
                severity="medium",
                likely_cause="Previous routed command failed or was blocked.",
                suggested_steps=_SAFE_STEPS["runtime"],
            )
        )
    if not data.get("running"):
        findings.append(
            DiagnosticFinding(
                source="runtime",
                issue="JARVIS runtime marked as not running",
                evidence=["running=false"],
                severity="low",
                likely_cause="Shutdown or tray exit may have been requested.",
                suggested_steps=["Restart JARVIS if you still need the assistant"],
            )
        )
    return findings


def _finding_loop(dashboard: dict, loop_data: dict) -> list[DiagnosticFinding]:
    findings: list[DiagnosticFinding] = []
    lines = loop_data.get("lines") or []
    if not dashboard.get("reachable") and lines:
        findings.append(
            DiagnosticFinding(
                source="trading_loop",
                issue="Loop-related log activity but dashboard unreachable",
                evidence=lines[:4],
                severity="high",
                likely_cause="Loop may be logging while dashboard is down.",
                suggested_steps=_SAFE_STEPS["loop"],
            )
        )
    stopped = [ln for ln in lines if "stopped" in ln.lower() or "kill_switch" in ln.lower()]
    if stopped:
        findings.append(
            DiagnosticFinding(
                source="trading_loop",
                issue="Recent loop stop or kill-switch signals in logs",
                evidence=stopped[:4],
                severity="medium",
                likely_cause="Scheduled loop may have halted or kill switch engaged.",
                suggested_steps=_SAFE_STEPS["loop"],
            )
        )
    elif lines and dashboard.get("reachable"):
        findings.append(
            DiagnosticFinding(
                source="trading_loop",
                issue="Recent loop-related log activity (informational)",
                evidence=lines[:3],
                severity="info",
                likely_cause="Normal loop logging; verify mode in dashboard.",
                suggested_steps=["Run: show dashboard health"],
            )
        )
    return findings


def run_diagnostics() -> DiagnosticReport:
    """Full cross-source read-only diagnostic pass."""
    sources = ["dashboard", "logs", "rejections", "runtime", "screen"]
    dash = collect_dashboard()
    logs = collect_log_errors()
    rej = collect_rejections()
    runtime = collect_runtime()
    screen = collect_screen_errors()
    loop = collect_loop_signals()

    findings: list[DiagnosticFinding] = []
    findings.extend(_finding_dashboard(dash))
    findings.extend(_finding_logs(logs))
    findings.extend(_finding_rejections(rej))
    findings.extend(_finding_runtime(runtime))
    findings.extend(_finding_screen(screen))
    findings.extend(_finding_loop(dash, loop))

    report = DiagnosticReport.from_findings(
        findings,
        sources_checked=sources + ["trading_loop"],
        title="Full diagnostics",
    )
    return _store(report)


def diagnose_dashboard() -> DiagnosticReport:
    dash = collect_dashboard()
    findings = _finding_dashboard(dash)
    if not findings and dash.get("reachable"):
        findings.append(
            DiagnosticFinding(
                source="dashboard",
                issue="Dashboard appears healthy",
                evidence=["reachable=yes"],
                severity="info",
                likely_cause="HTTP health or port check succeeded.",
                suggested_steps=["Run: show dashboard health for details"],
            )
        )
    return _store(
        DiagnosticReport.from_findings(
            findings,
            sources_checked=["dashboard"],
            title="Dashboard diagnostics",
        )
    )


def diagnose_trading_loop() -> DiagnosticReport:
    dash = collect_dashboard()
    loop = collect_loop_signals()
    findings = _finding_loop(dash, loop)
    findings.extend(_finding_dashboard(dash))
    if not findings:
        findings.append(
            DiagnosticFinding(
                source="trading_loop",
                issue="No loop anomalies detected in recent logs",
                evidence=[],
                severity="info",
                likely_cause="No stop/kill-switch patterns in scanned log tail.",
                suggested_steps=_SAFE_STEPS["loop"],
            )
        )
    return _store(
        DiagnosticReport.from_findings(
            findings,
            sources_checked=["dashboard", "trading_loop", "logs"],
            title="Trading loop diagnostics",
        )
    )


def diagnose_recent_errors() -> DiagnosticReport:
    logs = collect_log_errors()
    rej = collect_rejections()
    findings = _finding_logs(logs)
    findings.extend(_finding_rejections(rej))
    if not findings:
        findings.append(
            DiagnosticFinding(
                source="logs",
                issue="No recent error or rejection spikes found",
                evidence=[],
                severity="info",
                likely_cause="Scanned log tails had no error keywords or rejection reasons.",
                suggested_steps=_SAFE_STEPS["log_errors"],
            )
        )
    return _store(
        DiagnosticReport.from_findings(
            findings,
            sources_checked=["logs", "rejections"],
            title="Recent error diagnostics",
        )
    )


def analyze_current_screen() -> DiagnosticReport:
    screen = collect_screen_errors()
    runtime = collect_runtime()
    findings = _finding_screen(screen)
    if screen.get("enabled") is False:
        findings.append(
            DiagnosticFinding(
                source="screen",
                issue="Screen analysis skipped (vision disabled)",
                evidence=[screen.get("note", "")],
                severity="info",
                likely_cause="Set VISION_ENABLED=true for OCR-based screen diagnostics.",
                suggested_steps=["Enable vision, then run: analyze current screen"],
            )
        )
    findings.extend(_finding_runtime(runtime))
    return _store(
        DiagnosticReport.from_findings(
            findings,
            sources_checked=["screen", "runtime"],
            title="Screen diagnostics",
        )
    )


def explain_last_failure() -> DiagnosticReport:
    runtime = collect_runtime()
    logs = collect_log_errors(max_files=3)
    findings = _finding_runtime(runtime)
    if logs.get("line_count"):
        findings.append(
            DiagnosticFinding(
                source="logs",
                issue="Supporting errors in recent logs",
                evidence=(logs.get("lines") or [])[:4],
                severity="medium",
                likely_cause="May explain the last failed JARVIS or trading operation.",
                suggested_steps=_SAFE_STEPS["log_errors"],
            )
        )
    if not findings:
        findings.append(
            DiagnosticFinding(
                source="runtime",
                issue="No recorded last failure",
                evidence=[(runtime.get("last_result_summary") or "none")[:120]],
                severity="info",
                likely_cause="No last_error in runtime state.",
                suggested_steps=["Run a command, then retry if it fails"],
            )
        )
    return _store(
        DiagnosticReport.from_findings(
            findings,
            sources_checked=["runtime", "logs"],
            title="Last failure explanation",
        )
    )


def suggest_next_steps() -> DiagnosticReport:
    report = get_last_report()
    if report is None or not report.findings:
        report = run_diagnostics()
    steps: list[str] = []
    seen: set[str] = set()
    for f in report.findings[:5]:
        for step in f.suggested_steps:
            if step not in seen:
                seen.add(step)
                steps.append(step)
    if not steps:
        steps = [
            "Run: run diagnostics",
            "Run: show dashboard health",
            "Run: show last errors",
        ]
    try:
        from operating.workspace_context import get_cached_mode

        mode = get_cached_mode()
        if mode == "coding":
            steps = ["run diagnostics", "show task queue", "what am i doing"] + steps
        elif mode == "trading":
            steps = ["show dashboard health", "show last errors"] + steps
        elif mode == "studying":
            steps = ["summarize my notes", "what should i study next"] + steps
    except Exception:
        pass
    seen_ws: set[str] = set()
    deduped: list[str] = []
    for s in steps:
        if s not in seen_ws:
            seen_ws.add(s)
            deduped.append(s)
    steps = deduped[:8]
    finding = DiagnosticFinding(
        source="diagnostics",
        issue="Safe suggested next steps (read-only)",
        evidence=[report.top_issue],
        severity="info",
        likely_cause="Derived from latest diagnostic findings; no automatic fixes.",
        suggested_steps=steps[:8],
    )
    summary = "Suggested next steps (read-only):\n" + "\n".join(
        f"  - {s}" for s in steps[:8]
    )
    out = DiagnosticReport(
        top_issue=report.top_issue,
        findings=[finding],
        summary=summary,
        sources_checked=report.sources_checked,
    )
    return _store(out)
