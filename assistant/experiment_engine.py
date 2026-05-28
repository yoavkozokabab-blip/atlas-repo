"""Safe experiment suggestions for root-cause verification (Phase 55)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from config import PROJECT_ROOT
from core.logger import setup_logger

logger = setup_logger("jarvis.assistant.experiment_engine")

EXPERIMENT_REPORT_DIR = PROJECT_ROOT / "reports" / "experiments"

SAFE_EXPERIMENTS: list[dict[str, Any]] = [
    {
        "id": "replay_no_overlap_gating",
        "title": "Replay without overlap gating",
        "command": "simulate unblock scenario",
        "impact": "Estimates how many signals would pass if overlap blocks were removed",
        "risk": "read-only simulation",
    },
    {
        "id": "last_bar_vs_completed_bar",
        "title": "Compare last-bar vs completed-bar logic",
        "command": "rank dead signal causes",
        "impact": "Identifies whether last-bar filtering dominates dead signals",
        "risk": "read-only analysis",
    },
    {
        "id": "stale_cleanup_simulation",
        "title": "Simulate stale position cleanup",
        "command": "simulate execution cleanup patch",
        "impact": "Projects risk reduction if stale positions were cleared",
        "risk": "read-only simulation — no patch apply",
    },
    {
        "id": "risk_cap_reset_compare",
        "title": "Compare execution before/after risk cap reset",
        "command": "compare risk before after cleanup",
        "impact": "Shows whether risk caps are suppressing eligible execution",
        "risk": "read-only comparison",
    },
    {
        "id": "adapter_unblock_simulation",
        "title": "Simulate adapter re-enable scenario",
        "command": "simulate unblock scenario",
        "impact": "Estimates execution attempts if adapter gating were lifted",
        "risk": "read-only simulation",
    },
]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def suggest_experiments() -> str:
    lines = [f"Safe experiment suggestions ({len(SAFE_EXPERIMENTS)}):"]
    for idx, exp in enumerate(SAFE_EXPERIMENTS, start=1):
        lines.append(f"  {idx}. {exp.get('title')} [{exp.get('risk')}]")
        lines.append(f"       run: {exp.get('command')}")
    lines.append("All experiments are read-only — no live trading or patch apply.")
    return "\n".join(lines)


def explain_experiment_impact(experiment_id: str = "") -> str:
    exp = SAFE_EXPERIMENTS[0]
    if experiment_id:
        for item in SAFE_EXPERIMENTS:
            if item.get("id") == experiment_id or experiment_id.lower() in str(item.get("title", "")).lower():
                exp = item
                break
    return (
        f"Experiment: {exp.get('title')}\n"
        f"  id: {exp.get('id')}\n"
        f"  impact: {exp.get('impact')}\n"
        f"  risk: {exp.get('risk')}\n"
        f"  command: {exp.get('command')}"
    )


def run_safe_experiment_simulation(experiment_id: str = "") -> str:
    exp = SAFE_EXPERIMENTS[0]
    if experiment_id:
        for item in SAFE_EXPERIMENTS:
            if item.get("id") == experiment_id or experiment_id.lower() in str(item.get("title", "")).lower():
                exp = item
                break
    command = str(exp.get("command", ""))
    result = ""
    try:
        if "simulate unblock" in command:
            from investigation.execution_flow import simulate_unblock_scenario

            result = simulate_unblock_scenario("top")
        elif "cleanup patch" in command:
            from investigation.execution_cleanup import simulate_execution_cleanup_patch

            result = simulate_execution_cleanup_patch()
        elif "risk before after" in command:
            from investigation.execution_cleanup import compare_risk_before_after_cleanup

            result = compare_risk_before_after_cleanup()
        elif "dead signal" in command:
            from investigation.execution_flow import rank_dead_signal_causes

            result = rank_dead_signal_causes()
        else:
            result = f"Experiment command mapped: {command} (preview only)"
    except Exception as exc:
        result = f"Simulation unavailable: {exc}"
    try:
        EXPERIMENT_REPORT_DIR.mkdir(parents=True, exist_ok=True)
        ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        path = EXPERIMENT_REPORT_DIR / f"{ts}_{exp.get('id', 'experiment')}.md"
        path.write_text(
            f"# Safe Experiment: {exp.get('title')}\n\nGenerated: {_now()}\n\n{result[:4000]}\n",
            encoding="utf-8",
        )
    except OSError as exc:
        logger.debug("Experiment report skipped: %s", exc)
    return (
        f"Safe experiment simulation: {exp.get('title')}\n"
        f"  scope: read-only\n"
        f"  output:\n{result[:1200]}"
    )
