"""Phase 137A — billing service adapter (delegates to :mod:`atlas_desktop.usage`)."""

from __future__ import annotations

import os
from typing import Any, Dict, Optional

from atlas_desktop import usage as usage_mod

FEATURE_FLAG = "ATLAS_BILLING_UI_ENABLED"
ADMIN_FLAG = "ATLAS_ADMIN"


def billing_ui_enabled() -> bool:
    return usage_mod.billing_ui_enabled()


def is_admin(user_id: Optional[str] = None, store=None) -> bool:
    if os.environ.get(ADMIN_FLAG, "").strip().lower() in ("1", "true", "yes"):
        return True
    ctx = usage_mod.current_context(store)
    return bool(ctx.get("is_admin"))


def billing_config() -> Dict[str, Any]:
    return {
        "ok": True,
        "ui_enabled": billing_ui_enabled(),
        "feature_flag": FEATURE_FLAG,
        "enforcement": "on" if usage_mod.enforcement_enabled() else "off",
        "payments": "disabled",
        "local_only": True,
        "pages": {"pricing": "/pricing.html", "usage": "/usage.html", "admin": "/billing_admin.html"},
        "note": "Billing UI is gated; core local usage is never blocked unless enforcement flag is on.",
    }


def list_plans() -> Dict[str, Any]:
    payload = usage_mod.plans_api()
    payload["ui_enabled"] = billing_ui_enabled()
    return payload


def user_dashboard(user_id: str = "user_local_owner", store=None) -> Dict[str, Any]:
    return usage_mod.usage_me_summary(store)


def admin_dashboard(requesting_user_id: Optional[str] = None, store=None) -> Dict[str, Any]:
    return usage_mod.usage_admin_summary(store, is_admin=is_admin(requesting_user_id, store))


def record_from_dispatch(path: str, payload: Dict[str, Any], body: Dict[str, Any], store=None) -> None:
    """Legacy hook from server.dispatch — recording is handled in api.py (Phase 137A)."""
    return


def record_usage(action_type: str, **kwargs: Any) -> Dict[str, Any]:
    mapping = {
        "scan": "scan_completed",
        "build": "build_plan_created",
        "investigate": "investigation_created",
        "impact": "impact_created",
        "export": "export_created",
        "prompt": "export_created",
    }
    event_type = mapping.get(action_type, action_type)
    result = usage_mod.record_event(
        event_type,
        repo_path=str(kwargs.get("repo_path") or ""),
        repo_name=str(kwargs.get("repo_name") or ""),
        scan_duration_seconds=float(kwargs.get("duration_sec") or 0),
        meta=dict(kwargs.get("meta") or {}),
    )
    return result.get("event") or result
