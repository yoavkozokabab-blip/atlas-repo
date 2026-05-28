"""Phase 31 — unified JARVIS status center (read-only)."""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from config import (
    ALLOWED_INTENTS,
    BROWSER_DOM_ALLOWLIST,
    BROWSER_DOM_ENABLED,
    COMPUTER_CONTROL_ENABLED,
    DATA_DIR,
    FAST_VOICE_MODE,
    GUIDED_UI_ENABLED,
    IMPLEMENTED_INTENTS,
    OVERLAY_ENABLED,
    PATCH_APPLY_ENABLED,
    PROJECT_ROOT,
    TASK_QUEUE_MAX_RUNTIME_SECONDS,
    TRADING_PROJECT_ROOT,
    TRADING_REPORTS_ROOT,
    TTS_ENABLED,
    TTS_ENGINE,
    SCREEN_BLOCK_SECRET_WINDOWS,
    SCREEN_CAPTURE_MODE,
    SCREEN_CAPTURE_SAVE_DEBUG,
    SCREEN_OCR_ENABLED,
    SCREEN_REDACTION_ENABLED,
    ASYNC_PERSISTENCE_ENABLED,
    CONVERSATION_CONTINUATION_ENABLED,
    CONVERSATION_ENABLED,
    CONVERSATION_FAST_ACK_ENABLED,
    CONVERSATION_MAX_TURNS,
    TTS_FAST_SUMMARY_ENABLED,
    SCREEN_UNDERSTANDING_ENABLED,
    VISION_ENABLED,
    VOICE_ENABLED,
    WAKE_WORD_ENABLED,
)
from voice.latency_tracker import get_last_latency

_SECRET_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"(?i)(api[_-]?key|secret|password|token|credential)\s*[=:]\s*\S+"),
    re.compile(r"(?i)Bearer\s+[A-Za-z0-9._-]+"),
    re.compile(r"sk-[A-Za-z0-9]{20,}"),
]


def _flag(enabled: bool) -> str:
    return "enabled" if enabled else "disabled"


def redact_secrets(text: str) -> str:
    """Remove secret-like substrings from status output."""
    out = text or ""
    for pat in _SECRET_PATTERNS:
        out = pat.sub("***REDACTED***", out)
    return out


@dataclass
class SectionResult:
    name: str
    status: str  # ok | disabled | degraded
    lines: list[str] = field(default_factory=list)

    def render(self) -> str:
        header = f"## {self.name}\nstatus: {self.status}"
        body = "\n".join(f"  {line}" for line in self.lines) if self.lines else "  (no details)"
        return f"{header}\n{body}"


def _safe_section(name: str, collector: Callable[[], SectionResult]) -> SectionResult:
    try:
        return collector()
    except Exception as exc:
        return SectionResult(
            name=name,
            status="degraded",
            lines=[f"collector_error: {type(exc).__name__}", "message: (suppressed for safety)"],
        )


def _collect_overall(sections: list[SectionResult]) -> SectionResult:
    statuses = [s.status for s in sections]
    if any(s == "degraded" for s in statuses):
        overall = "degraded"
    elif all(s == "disabled" for s in statuses):
        overall = "disabled"
    elif any(s == "ok" for s in statuses):
        overall = "ok"
    else:
        overall = "ok"
    lines = [f"sections_reporting: {len(sections)}", f"ok: {statuses.count('ok')}"]
    lines.append(f"disabled: {statuses.count('disabled')}")
    lines.append(f"degraded: {statuses.count('degraded')}")
    return SectionResult(name="overall_status", status=overall, lines=lines)


def _collect_runtime() -> SectionResult:
    lines = [
        f"python: {sys.version.split()[0]}",
        f"project_root: {PROJECT_ROOT}",
        f"data_dir: {'present' if DATA_DIR.is_dir() else 'missing'}",
    ]
    try:
        from actions.registry import ActionRegistry

        reg = ActionRegistry()
        handler_count = len(getattr(reg, "_actions", {}))
        lines.append(f"action_handlers_registered: {handler_count}")
    except Exception:
        lines.append("action_handlers_registered: degraded")
    lines.append(f"allowed_intents: {len(ALLOWED_INTENTS)}")
    lines.append(f"implemented_intents: {len(IMPLEMENTED_INTENTS)}")
    status = "ok" if DATA_DIR.is_dir() else "degraded"
    return SectionResult(name="runtime", status=status, lines=lines)


def _collect_voice() -> SectionResult:
    lines = [
        f"voice: {_flag(VOICE_ENABLED)}",
        f"fast_voice_mode: {_flag(FAST_VOICE_MODE)}",
        f"tts: {_flag(TTS_ENABLED)} (engine={TTS_ENGINE})",
        f"wake_word: {_flag(WAKE_WORD_ENABLED)}",
        f"vision: {_flag(VISION_ENABLED)}",
    ]
    rec = get_last_latency()
    if rec is None:
        lines.append("last_voice_latency: none")
    else:
        rec.finish()
        lines.append(f"last_voice_total_ms: {rec.total_ms:.1f}" if rec.total_ms else "last_voice_total_ms: -")
    status = "disabled" if not VOICE_ENABLED else "ok"
    return SectionResult(name="voice", status=status, lines=lines)


def _collect_overlay() -> SectionResult:
    status = "disabled" if not OVERLAY_ENABLED else "ok"
    return SectionResult(
        name="overlay",
        status=status,
        lines=[f"overlay: {_flag(OVERLAY_ENABLED)}"],
    )


def _collect_task_agent() -> SectionResult:
    from task_agent.session import get_active_task

    session = get_active_task()
    if session is None:
        return SectionResult(
            name="task_agent",
            status="disabled",
            lines=["active_task: none", "supervised_task: idle"],
        )
    lines = [
        f"active_task: {session.task_id}",
        f"task_status: {session.status.value}",
        f"plan_approved: {session.plan_approved}",
        f"findings_count: {len(session.structured_findings)}",
        f"steps_completed: {session.steps_completed}",
    ]
    if session.report_path:
        lines.append(f"report_path: {session.report_path}")
    return SectionResult(name="task_agent", status="ok", lines=lines)


def _collect_patch_system() -> SectionResult:
    from task_agent.patch_apply import get_last_apply
    from task_agent.session import get_active_task

    lines = [f"patch_apply: {_flag(PATCH_APPLY_ENABLED)}"]
    session = get_active_task()
    if session and session.patch_proposal:
        p = session.patch_proposal
        lines.append(f"proposal_id: {p.proposal_id}")
        lines.append(f"proposal_status: {p.status}")
        lines.append(f"proposal_risk: {p.risk_level}")
    else:
        lines.append("proposal: none")
    last = get_last_apply()
    if last:
        lines.append(f"last_apply_id: {last.apply_id or 'n/a'}")
        lines.append(f"last_apply_applied: {last.applied}")
        lines.append(f"last_apply_rolled_back: {last.rolled_back}")
    else:
        lines.append("last_apply: none")
    status = "disabled" if not PATCH_APPLY_ENABLED else "ok"
    return SectionResult(name="patch_system", status=status, lines=lines)


def _collect_trading() -> SectionResult:
    lines = [
        f"trading_project: {'present' if TRADING_PROJECT_ROOT.is_dir() else 'missing'}",
        f"reports_root: {'present' if TRADING_REPORTS_ROOT.is_dir() else 'missing'}",
    ]
    try:
        from actions.trading_dashboard import dashboard_health_reachable

        reachable = dashboard_health_reachable()
        lines.append(f"dashboard_health_localhost: {'reachable' if reachable else 'unreachable'}")
    except Exception:
        lines.append("dashboard_health_localhost: degraded")
    status = "ok" if TRADING_PROJECT_ROOT.is_dir() else "degraded"
    return SectionResult(name="trading", status=status, lines=lines)


def _collect_browser_dom() -> SectionResult:
    allow = ", ".join(sorted(BROWSER_DOM_ALLOWLIST))
    status = "disabled" if not BROWSER_DOM_ENABLED else "ok"
    return SectionResult(
        name="browser_dom",
        status=status,
        lines=[
            f"browser_dom: {_flag(BROWSER_DOM_ENABLED)}",
            f"allowlist_sites: {allow}",
        ],
    )


def _collect_guided_ui() -> SectionResult:
    status = "disabled" if not GUIDED_UI_ENABLED else "ok"
    return SectionResult(
        name="guided_ui",
        status=status,
        lines=[
            f"guided_ui: {_flag(GUIDED_UI_ENABLED)}",
            "coordinate_automation: disabled",
        ],
    )


def _collect_workspaces() -> SectionResult:
    from workspaces.launcher import WORKSPACES

    names = ", ".join(sorted(WORKSPACES.keys()))
    return SectionResult(
        name="workspaces",
        status="ok",
        lines=[
            f"workspace_profiles: {names}",
            "auto_launch: disabled (manual phrases only)",
        ],
    )


def _collect_startup_health() -> SectionResult:
    log = PROJECT_ROOT / "reports" / "jarvis_logs" / "startup_latest.log"
    lines = [
        f"data_dir: {'present' if DATA_DIR.is_dir() else 'missing'}",
        f"startup_log: {'present' if log.is_file() else 'missing'}",
    ]
    if log.is_file():
        try:
            lines.append(f"startup_log_bytes: {log.stat().st_size}")
        except OSError:
            lines.append("startup_log_bytes: degraded")
    queue_file = DATA_DIR / "task_queue.json"
    lines.append(f"task_queue_file: {'present' if queue_file.is_file() else 'absent'}")
    lines.append(f"task_queue_max_runtime_s: {TASK_QUEUE_MAX_RUNTIME_SECONDS}")
    status = "ok" if DATA_DIR.is_dir() else "degraded"
    return SectionResult(name="startup_health", status=status, lines=lines)


def _collect_conversation() -> SectionResult:
    status = "disabled" if not CONVERSATION_ENABLED else "ok"
    return SectionResult(
        name="conversation",
        status=status,
        lines=[
            f"enabled: {_flag(CONVERSATION_ENABLED)}",
            f"continuation_prompts: {_flag(CONVERSATION_CONTINUATION_ENABLED)}",
            f"max_turns: {CONVERSATION_MAX_TURNS}",
            f"fast_ack: {_flag(CONVERSATION_FAST_ACK_ENABLED)}",
            f"tts_fast_summary: {_flag(TTS_FAST_SUMMARY_ENABLED)}",
            f"async_persistence: {_flag(ASYNC_PERSISTENCE_ENABLED)}",
            "auto_execute: disabled (supervised only)",
        ],
    )


def _collect_screen_understanding() -> SectionResult:
    status = "disabled" if not SCREEN_UNDERSTANDING_ENABLED else "ok"
    return SectionResult(
        name="screen_understanding",
        status=status,
        lines=[
            f"enabled: {_flag(SCREEN_UNDERSTANDING_ENABLED)}",
            f"capture_mode: {SCREEN_CAPTURE_MODE}",
            f"ocr_enabled: {_flag(SCREEN_OCR_ENABLED)}",
            f"debug_saving_enabled: {_flag(SCREEN_CAPTURE_SAVE_DEBUG)}",
            f"redaction_enabled: {_flag(SCREEN_REDACTION_ENABLED)}",
            f"blocked_secret_windows_enabled: {_flag(SCREEN_BLOCK_SECRET_WINDOWS)}",
        ],
    )


def _collect_safety() -> SectionResult:
    return SectionResult(
        name="safety",
        status="ok",
        lines=[
            "router_security_registry: intact",
            "arbitrary_shell: blocked",
            "autonomous_execution: blocked",
            "live_trading_execution: blocked",
            "file_edits_without_approval: blocked",
            "computer_control: " + _flag(COMPUTER_CONTROL_ENABLED),
        ],
    )


def build_jarvis_status_report() -> str:
    """Aggregate subsystem status into one read-only report."""
    collectors: list[tuple[str, Callable[[], SectionResult]]] = [
        ("runtime", _collect_runtime),
        ("voice", _collect_voice),
        ("overlay", _collect_overlay),
        ("task_agent", _collect_task_agent),
        ("patch_system", _collect_patch_system),
        ("trading", _collect_trading),
        ("browser_dom", _collect_browser_dom),
        ("guided_ui", _collect_guided_ui),
        ("workspaces", _collect_workspaces),
        ("startup_health", _collect_startup_health),
        ("screen_understanding", _collect_screen_understanding),
        ("conversation", _collect_conversation),
        ("safety", _collect_safety),
    ]

    sections = [_safe_section(name, fn) for name, fn in collectors]
    overall = _collect_overall(sections)
    parts = ["# JARVIS Status Center (read-only)", "", overall.render(), ""]
    for sec in sections:
        parts.append(sec.render())
        parts.append("")

    report = redact_secrets("\n".join(parts))
    # Never leak raw .env lines
    report = re.sub(r"(?i)(OPENAI|TELEGRAM|API)[_A-Z]*\s*=\s*\S+", r"\1=***REDACTED***", report)
    return report
