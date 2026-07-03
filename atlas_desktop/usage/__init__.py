"""Phase 137A — Usage tracking and billing-ready infrastructure (local/mock only).

No Stripe, no real payments, no hard paywalls unless ``ATLAS_USAGE_ENFORCEMENT`` is set.
"""

from __future__ import annotations

from .estimator import estimate_repo_cost
from .limits import check_limit, enforcement_enabled
from .models import UsageEvent, EVENT_TYPES
from .plans import PLANS, get_plan, list_plans, pricing_payload
from .store import UsageStore, default_store, usage_data_dir
from .tracker import (
    billing_ui_enabled,
    record_event,
    usage_admin_summary,
    usage_me_summary,
    record_from_scan,
    current_context,
    plans_api,
    pricing_api,
)

__all__ = [
    "UsageEvent",
    "EVENT_TYPES",
    "UsageStore",
    "default_store",
    "usage_data_dir",
    "PLANS",
    "get_plan",
    "list_plans",
    "pricing_payload",
    "estimate_repo_cost",
    "check_limit",
    "enforcement_enabled",
    "billing_ui_enabled",
    "record_event",
    "record_from_scan",
    "usage_me_summary",
    "usage_admin_summary",
    "current_context",
]
