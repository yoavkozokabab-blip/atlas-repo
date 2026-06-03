"""Phase 137A — plan limit checks (advisory unless enforcement flag is on)."""

from __future__ import annotations

import os
from typing import Any, Dict

from .plans import get_plan


def enforcement_enabled() -> bool:
    return os.environ.get("ATLAS_USAGE_ENFORCEMENT", "").strip().lower() in ("1", "true", "yes")


def check_limit(
    plan_id: str,
    metric: str,
    used: int,
    *,
    repo_files: int = 0,
) -> Dict[str, Any]:
    """Return whether an action is within plan limits (never blocks unless enforced)."""
    plan = get_plan(plan_id)
    limits = plan.get("limits") or {}
    cap = limits.get(metric)
    allowed = True
    reason = ""

    if metric == "large_repo" and repo_files:
        max_files = int(limits.get("max_repo_files", 0))
        large_ok = bool(limits.get("large_repo_allowed"))
        if max_files > 0 and repo_files > max_files and not large_ok:
            allowed = False
            reason = f"Repository has {repo_files} files; {plan_id} allows up to {max_files} without large-repo access."
        elif max_files > 0 and repo_files > max_files * 2:
            allowed = False
            reason = f"Repository exceeds {plan_id} file cap ({max_files})."

    elif isinstance(cap, int) and cap >= 0 and used >= cap:
        allowed = False
        reason = f"{plan_id} limit for {metric}: {used}/{cap} this month."

    enforced = enforcement_enabled() and not allowed
    return {
        "metric": metric,
        "used": used,
        "limit": cap,
        "allowed": allowed,
        "enforced": enforced,
        "would_block": enforced,
        "reason": reason,
        "enforcement_enabled": enforcement_enabled(),
    }
