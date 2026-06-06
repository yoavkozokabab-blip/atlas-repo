"""Phase 176 — first-impression polish (user perception only).

Does not modify trust integrity, graph generation, repository memory core,
or the impact engine. Presentation and demo-quality gates only.
"""

from __future__ import annotations

import copy
from typing import Any, Dict, Iterable, List, Optional

DEMO_WEAK_MESSAGE = "Try a real repository for best results."

_FEATURE_REQUEST_INTENTS = frozenset({
    "add_feature", "new_feature", "implement", "enhancement", "add", "feature",
})
_FEATURE_REQUEST_GOAL_MARKERS = (
    "add ", "implement ", "create ", "introduce ", "build ", "enable ", "new ",
)


def cap_evidence_score(score: Any) -> int:
    try:
        return max(0, min(100, int(round(float(score)))))
    except (TypeError, ValueError):
        return 0


def is_feature_request(*, goal: str = "", intent: str = "") -> bool:
    i = (intent or "").strip().lower().replace("-", "_")
    if i in _FEATURE_REQUEST_INTENTS:
        return True
    g = (goal or "").strip().lower()
    return any(g.startswith(m) or f" {m}" in f" {g}" for m in _FEATURE_REQUEST_GOAL_MARKERS)


def user_facing_implementation_status(
    status: str,
    *,
    goal: str = "",
    intent: str = "",
) -> str:
    """Never show Implemented for feature requests — the user is planning work."""
    if status != "Implemented":
        return status or ""
    if is_feature_request(goal=goal, intent=intent):
        return "Proposed"
    return status


def _confidence_is_low(conf: Any) -> bool:
    s = str(conf or "").lower()
    return s == "low" or s.startswith("low")


def _plan_has_no_files(plan: Dict[str, Any]) -> bool:
    rev = plan.get("repository_evidence") or {}
    files = list(plan.get("files_to_inspect_first") or [])
    if files:
        return False
    if rev.get("file_evidences"):
        return False
    if plan.get("files_likely_to_change") or plan.get("likely_affected_modules"):
        return False
    return True


def is_demo_unanswered(workflow: str, result: Dict[str, Any]) -> bool:
    """True when a demo workflow would show an empty, low-confidence first impression."""
    if workflow == "build":
        plan = result.get("plan") or {}
        order = plan.get("implementation_order") or []
        if _plan_has_no_files(plan) and not order and _confidence_is_low(plan.get("confidence")):
            return True
        if _plan_has_no_files(plan) and not order:
            return True
        return False
    if workflow == "investigate":
        plan = result.get("plan") or {}
        hyps = plan.get("hypotheses") or []
        has_files = any(h.get("files_involved") for h in hyps)
        if not hyps and _confidence_is_low(plan.get("confidence")):
            return True
        if not has_files and not hyps:
            return True
        return False
    if workflow == "impact":
        direct = result.get("direct_impact") or []
        indirect = result.get("indirect_impact") or []
        if not direct and not indirect:
            return True
        return False
    return False


def _polish_repository_evidence(
    rev: Optional[Dict[str, Any]],
    *,
    goal: str = "",
    intent: str = "",
) -> Optional[Dict[str, Any]]:
    if not rev:
        return rev
    out = copy.deepcopy(rev)
    out["status"] = user_facing_implementation_status(
        out.get("status") or "", goal=goal, intent=intent,
    )
    if "confidence_score" in out:
        out["confidence_score"] = cap_evidence_score(out["confidence_score"])
    for fe in out.get("file_evidences") or []:
        if fe.get("evidence_score") is not None:
            fe["evidence_score"] = cap_evidence_score(fe["evidence_score"])
    return out


def polish_plan_display(plan: Dict[str, Any], *, goal: str = "", intent: str = "") -> Dict[str, Any]:
    out = copy.deepcopy(plan)
    intent = intent or str(out.get("intent") or "")
    goal = goal or str(out.get("goal") or out.get("change_goal") or "")

    rev = _polish_repository_evidence(
        out.get("repository_evidence"), goal=goal, intent=intent,
    )
    if rev:
        out["repository_evidence"] = rev

    dk = out.get("domain_knowledge")
    if isinstance(dk, dict):
        dk_rev = _polish_repository_evidence(
            dk.get("repository_evidence"), goal=goal, intent=intent,
        )
        if dk_rev:
            dk["repository_evidence"] = dk_rev
        roles = dk.get("file_roles")
        if isinstance(roles, dict):
            dk["file_roles"] = {
                k: list(v or [])
                for k, v in roles.items()
                if v
            }

    for hyp in out.get("hypotheses") or []:
        if hyp.get("evidence_score") is not None:
            hyp["evidence_score"] = cap_evidence_score(hyp["evidence_score"])
        if hyp.get("evidence_score_100") is not None:
            hyp["evidence_score_100"] = cap_evidence_score(hyp["evidence_score_100"])
    if out.get("root_cause_evidence_score") is not None:
        out["root_cause_evidence_score"] = cap_evidence_score(out["root_cause_evidence_score"])

    return out


def polish_impact_display(result: Dict[str, Any]) -> Dict[str, Any]:
    out = copy.deepcopy(result)
    for key in ("evidence_score", "root_cause_evidence_score"):
        if out.get(key) is not None:
            out[key] = cap_evidence_score(out[key])
    return out


def demo_weak_response(workflow: str, goal: str = "") -> Dict[str, Any]:
    return {
        "ok": False,
        "error": DEMO_WEAK_MESSAGE,
        "code": "demo_limited",
        "demo_notice": DEMO_WEAK_MESSAGE,
        "workflow": workflow,
        "goal": goal,
    }


def polish_workflow_result(
    workflow: str,
    result: Dict[str, Any],
    state: Dict[str, Any],
    *,
    goal: str = "",
) -> Dict[str, Any]:
    if not result.get("ok"):
        return result
    if state.get("demo_mode") and is_demo_unanswered(workflow, result):
        return demo_weak_response(workflow, goal)
    if workflow == "build":
        plan = result.get("plan")
        if plan:
            intent = str(plan.get("intent") or "")
            result["plan"] = polish_plan_display(plan, goal=goal, intent=intent)
    elif workflow == "investigate":
        plan = result.get("plan")
        if plan:
            result["plan"] = polish_plan_display(plan, goal=goal)
    elif workflow == "impact":
        result = polish_impact_display(result)
    return result


def md_optional_section(title: str, items: Iterable[str]) -> List[str]:
    """Omit entire section when there are no items (no '- (none)' placeholders)."""
    rows = [f"- {x}" for x in items if x]
    if not rows:
        return []
    return ["", title + ":", *rows]
