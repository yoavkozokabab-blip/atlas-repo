"""Verification plans for root-cause hypotheses (Phase 55)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from config import DATA_DIR, PROJECT_ROOT
from core.logger import setup_logger
from core.persistent_json import atomic_write_json, load_json

logger = setup_logger("jarvis.assistant.verification_plans")

PLANS_PATH = DATA_DIR / "verification_plans.json"
PLAN_REPORT_DIR = PROJECT_ROOT / "reports" / "verification_plans"

PLAN_TEMPLATES: dict[str, list[dict[str, str]]] = {
    "adapter_disabled": [
        {"step": 1, "action": "inspect execution adapter", "command": "inspect execution adapter"},
        {"step": 2, "action": "compare adapter state over time", "command": "show blocker history"},
        {"step": 3, "action": "compare execution attempts before/after adapter enabled", "command": "compare signal count to order attempts"},
        {"step": 4, "action": "verify execution-disabled events recurrence", "command": "show blocker trends"},
        {"step": 5, "action": "verify no contradictory execution evidence", "command": "reconstruct execution flow"},
    ],
    "overlap_stale_positions": [
        {"step": 1, "action": "show stale open positions", "command": "show stale open positions"},
        {"step": 2, "action": "compare overlap blocks over time", "command": "compare blocker trends"},
        {"step": 3, "action": "verify stale state transitions", "command": "show divergence clusters"},
        {"step": 4, "action": "check execution flow overlap gating", "command": "reconstruct execution flow"},
        {"step": 5, "action": "simulate cleanup impact (read-only)", "command": "simulate execution cleanup patch"},
    ],
    "last_bar_filter": [
        {"step": 1, "action": "reconstruct execution flow", "command": "reconstruct execution flow"},
        {"step": 2, "action": "rank dead signal causes", "command": "rank dead signal causes"},
        {"step": 3, "action": "compare last-bar vs completed-bar logic", "command": "simulate unblock scenario"},
        {"step": 4, "action": "verify signal lifecycle timeline", "command": "show signal lifecycle timeline"},
    ],
    "stale_telemetry_risk": [
        {"step": 1, "action": "show current execution risk", "command": "show current execution risk"},
        {"step": 2, "action": "compare risk before/after cleanup", "command": "compare risk before after cleanup"},
        {"step": 3, "action": "verify stale positions", "command": "show stale open positions"},
    ],
    "cluster_divergence": [
        {"step": 1, "action": "cluster replay divergences", "command": "cluster replay divergences"},
        {"step": 2, "action": "explain largest divergence cluster", "command": "explain largest divergence cluster"},
        {"step": 3, "action": "run replay after patch preview", "command": "replay after patch"},
    ],
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _default_state() -> dict[str, Any]:
    return {"plans": [], "updated_at": ""}


def _load() -> dict[str, Any]:
    def _validate(data: Any) -> dict[str, Any] | None:
        return data if isinstance(data, dict) else None

    state = load_json(PLANS_PATH, default=_default_state(), validator=_validate)
    if not isinstance(state.get("plans"), list):
        state["plans"] = []
    return state


def _save(state: dict[str, Any]) -> None:
    state["updated_at"] = _now()
    atomic_write_json(PLANS_PATH, state)
    try:
        PLAN_REPORT_DIR.mkdir(parents=True, exist_ok=True)
        ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        path = PLAN_REPORT_DIR / f"{ts}_plans.json"
        path.write_text(
            __import__("json").dumps(state, indent=2, ensure_ascii=True),
            encoding="utf-8",
        )
    except OSError as exc:
        logger.debug("Verification plan report skipped: %s", exc)


def generate_verification_plans(*, force: bool = False) -> list[dict[str, Any]]:
    from assistant.hypothesis_engine import refresh_hypotheses

    hypotheses = refresh_hypotheses()
    state = _load()
    existing = {p.get("hypothesis_id"): p for p in state.get("plans", []) if isinstance(p, dict)}
    plans: list[dict[str, Any]] = []
    now = _now()
    for hyp in hypotheses:
        hid = str(hyp.get("id", ""))
        if not hid:
            continue
        steps = PLAN_TEMPLATES.get(hid, [
            {"step": 1, "action": "gather evidence", "command": hyp.get("verify_command", "run investigation cycle")},
            {"step": 2, "action": "verify hypothesis", "command": hyp.get("verify_command", "verify active hypotheses")},
        ])
        prev = existing.get(hid, {})
        plan = {
            "hypothesis_id": hid,
            "hypothesis": hyp.get("title", hid),
            "confidence": float(hyp.get("confidence", 0)),
            "steps": steps,
            "status": prev.get("status", "pending"),
            "completed_steps": list(prev.get("completed_steps") or []),
            "last_run_at": prev.get("last_run_at", ""),
            "updated_at": now,
        }
        plans.append(plan)
    state["plans"] = plans
    _save(state)
    return plans


def show_verification_plans() -> str:
    plans = generate_verification_plans()
    if not plans:
        return "No verification plans generated yet."
    lines = [f"Verification plans ({len(plans)}):"]
    for plan in plans:
        done = len(plan.get("completed_steps") or [])
        total = len(plan.get("steps") or [])
        lines.append(
            f"  - {plan.get('hypothesis_id')}: {plan.get('hypothesis', '')[:70]} "
            f"[{plan.get('status', 'pending')} {done}/{total}]"
        )
    return "\n".join(lines)


def explain_verification_plan(hypothesis_id: str = "") -> str:
    plans = generate_verification_plans()
    if not plans:
        return "No verification plans available."
    plan = plans[0]
    if hypothesis_id:
        for item in plans:
            if item.get("hypothesis_id") == hypothesis_id:
                plan = item
                break
    lines = [
        f"Verification plan: {plan.get('hypothesis', '')}",
        f"  hypothesis_id: {plan.get('hypothesis_id')}",
        f"  status: {plan.get('status', 'pending')}",
        "  steps:",
    ]
    for step in plan.get("steps") or []:
        marker = "x" if step.get("step") in (plan.get("completed_steps") or []) else " "
        lines.append(f"    [{marker}] {step.get('step')}. {step.get('action')} -> {step.get('command')}")
    return "\n".join(lines)


def _evaluate_step(step: dict[str, Any], evidence: dict[str, Any]) -> tuple[bool, str]:
    command = str(step.get("command", "")).lower()
    blockers = str(evidence.get("execution_blockers", "")).lower()
    adapter = str(evidence.get("adapter_state", "")).lower()
    stale = str(evidence.get("stale_positions", "")).lower()
    flow = str(evidence.get("execution_flow", "")).lower()
    risk = str(evidence.get("execution_risk", "")).lower()

    if "adapter" in command:
        ok = "disabled" in adapter or "disabled" in blockers
        return ok, "adapter disabled evidence present" if ok else "adapter not confirmed disabled"
    if "stale" in command:
        ok = "stale" in stale and "none" not in stale
        return ok, "stale positions confirmed" if ok else "no stale positions detected"
    if "risk" in command:
        ok = "cap" in risk or "near" in risk or "stale" in risk
        return ok, "risk telemetry elevated" if ok else "risk telemetry nominal"
    if "flow" in command or "reconstruct" in command:
        ok = bool(flow) and "unavailable" not in flow
        return ok, "execution flow captured" if ok else "execution flow unavailable"
    if "blocker" in command:
        ok = bool(blockers) and "unavailable" not in blockers
        return ok, "blocker evidence captured" if ok else "blockers unavailable"
    return True, "evidence snapshot collected"


def run_verification_plan(hypothesis_id: str = "") -> dict[str, Any]:
    from assistant.evidence_collector import collect_evidence_snapshot

    plans = generate_verification_plans()
    if not plans:
        return {"status": "empty", "message": "No verification plans to run."}
    plan = plans[0]
    if hypothesis_id:
        for item in plans:
            if item.get("hypothesis_id") == hypothesis_id:
                plan = item
                break
    evidence = collect_evidence_snapshot(source=f"verify:{plan.get('hypothesis_id')}")
    completed: list[int] = []
    results: list[dict[str, Any]] = []
    for step in plan.get("steps") or []:
        ok, note = _evaluate_step(step, evidence)
        results.append({"step": step.get("step"), "ok": ok, "note": note, "command": step.get("command")})
        if ok:
            completed.append(int(step.get("step", 0)))
    state = _load()
    for item in state.get("plans", []):
        if item.get("hypothesis_id") == plan.get("hypothesis_id"):
            item["completed_steps"] = sorted(set((item.get("completed_steps") or []) + completed))
            item["last_run_at"] = _now()
            total = len(item.get("steps") or [])
            done = len(item["completed_steps"])
            if done >= total:
                item["status"] = "verified"
            elif done > 0:
                item["status"] = "partial"
            item["results"] = results[-10:]
    _save(state)
    return {
        "hypothesis_id": plan.get("hypothesis_id"),
        "status": "verified" if len(completed) >= len(plan.get("steps") or []) else "partial",
        "completed_steps": completed,
        "results": results,
        "evidence_source": evidence.get("source", ""),
    }


def run_verification_plan_now(hypothesis_id: str = "") -> str:
    payload = run_verification_plan(hypothesis_id)
    if payload.get("status") == "empty":
        return str(payload.get("message", "No plans."))
    lines = [
        f"Verification plan run: {payload.get('hypothesis_id')} -> {payload.get('status')}",
        f"  completed steps: {payload.get('completed_steps')}",
    ]
    for result in payload.get("results") or []:
        mark = "OK" if result.get("ok") else "MISS"
        lines.append(f"  [{mark}] step {result.get('step')}: {result.get('note')}")
    return "\n".join(lines)
