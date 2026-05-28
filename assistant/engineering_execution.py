"""Semi-autonomous engineering execution helpers (Phase 56 upgrade)."""

from __future__ import annotations

from typing import Any

from core.logger import setup_logger

logger = setup_logger("jarvis.assistant.engineering_execution")


def propose_engineering_patch(*, target: str = "") -> str:
    """Generate a patch proposal without applying it."""
    lines = [
        "Engineering patch proposal (read-only):",
        "  status: proposal only — not applied",
    ]
    target_hint = (target or "").strip()
    if not target_hint:
        try:
            from assistant.root_cause_engine import get_overlay_snapshot

            snap = get_overlay_snapshot()
            target_hint = str(snap.get("dominant_root_cause") or "")
        except Exception:
            pass
    if target_hint:
        lines.append(f"  target: {target_hint[:160]}")
    try:
        from assistant.experiment_engine import suggest_experiments

        experiments = suggest_experiments()
        if experiments:
            lines.append("")
            lines.append(experiments[:800])
    except Exception:
        lines.append("  suggestion: run suggest experiments or propose algorithm patch")
    lines.append("")
    lines.append("Next: simulate engineering patch → validate engineering patch → explain patch risks")
    return "\n".join(lines)


def simulate_engineering_patch(*, target: str = "") -> str:
    """Simulate patch impact using existing safe simulation paths."""
    lines = ["Engineering patch simulation (read-only):"]
    try:
        from assistant.experiment_engine import run_safe_experiment_simulation

        body = run_safe_experiment_simulation()
        lines.append(body[:1000])
    except Exception as exc:
        lines.append(f"  simulation unavailable: {exc}")
        lines.append("  fallback: simulate patch for top hypothesis")
    return "\n".join(lines)


def validate_engineering_patch(*, target: str = "") -> str:
    lines = ["Engineering patch validation checklist:"]
    checks = [
        ("py_compile", "python -m py_compile local_jarvis"),
        ("smoke", "scripts/smoke_phase56.py"),
        ("watchdog", "no runtime degradation / no queue deadlock"),
        ("audio", "TTS interruption + recovery"),
        ("metrics", "compare before/after latency and failure counts"),
    ]
    for name, cmd in checks:
        lines.append(f"  [ ] {name}: {cmd}")
    try:
        from assistant.verification_plans import show_verification_plans

        plans = show_verification_plans()
        if plans:
            lines.append("")
            lines.append(plans[:600])
    except Exception:
        pass
    return "\n".join(lines)


def explain_patch_risks(*, target: str = "") -> str:
    lines = [
        "Patch risk assessment:",
        "  - May affect runtime stability if applied without smoke tests",
        "  - Audio/voice paths sensitive to threading and COM lifecycle",
        "  - Investigation scheduler and background tasks may interact with changes",
        "  - Trading/execution patches require extra confirmation",
        "  rollback: keep git branch + run recover runtime / reset jarvis runtime",
    ]
    try:
        from assistant.root_cause_summary import explain_dominant_root_cause

        rc = explain_dominant_root_cause()
        if rc:
            lines.append("")
            lines.append(rc[:500])
    except Exception:
        pass
    return "\n".join(lines)


def compare_before_after_metrics() -> str:
    lines = ["Before/after metrics comparison (read-only):"]
    try:
        from assistant.operational_comparison import compare_before_after_cleanup

        lines.append(compare_before_after_cleanup()[:800])
    except Exception as exc:
        lines.append(f"  comparison unavailable: {exc}")
    return "\n".join(lines)
