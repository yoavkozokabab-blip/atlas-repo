"""Phase 137A — configurable plan catalogue (not enforced unless flagged)."""

from __future__ import annotations

from typing import Any, Dict, List

PLANS: Dict[str, Dict[str, Any]] = {
    "FREE": {
        "id": "FREE",
        "name": "Free",
        "price_display": "$0",
        "billing_period": "month",
        "tagline": "Explore Atlas on a few repositories locally.",
        "cta": "Start local",
        "availability": "Available during private beta",
        "features": [
            "1 workspace",
            "Up to 3 repositories",
            "Small / medium repos",
            "30 scans / month",
            "10 exports / month",
            "Repository map",
        ],
        "limits": {
            "max_repositories": 3,
            "max_scans_per_month": 30,
            "max_repo_files": 3000,
            "max_exports_per_month": 10,
            "max_team_members": 1,
            "large_repo_allowed": False,
            "admin_dashboard_allowed": False,
        },
    },
    "PRO": {
        "id": "PRO",
        "name": "Pro",
        "price_display": "Coming soon",
        "billing_period": "month",
        "tagline": "Deeper intelligence for individual engineers.",
        "cta": "Join beta",
        "availability": "Private beta — no checkout yet",
        "features": [
            "25 repositories",
            "Large repositories",
            "400 scans / month",
            "Unlimited exports (fair use)",
            "Export prompts + evidence engine",
        ],
        "limits": {
            "max_repositories": 25,
            "max_scans_per_month": 400,
            "max_repo_files": 20000,
            "max_exports_per_month": -1,
            "max_team_members": 1,
            "large_repo_allowed": True,
            "admin_dashboard_allowed": False,
        },
    },
    "TEAM": {
        "id": "TEAM",
        "name": "Team",
        "price_display": "Coming soon",
        "billing_period": "month",
        "tagline": "Shared workspaces and admin visibility.",
        "cta": "Request access",
        "availability": "Private beta — contact us",
        "features": [
            "200 repositories",
            "Huge repositories",
            "4,000 scans / month",
            "Admin usage dashboard",
            "Up to 25 team members",
        ],
        "limits": {
            "max_repositories": 200,
            "max_scans_per_month": 4000,
            "max_repo_files": 50000,
            "max_exports_per_month": -1,
            "max_team_members": 25,
            "large_repo_allowed": True,
            "admin_dashboard_allowed": True,
        },
    },
    "ENTERPRISE": {
        "id": "ENTERPRISE",
        "name": "Enterprise",
        "price_display": "Custom",
        "billing_period": "year",
        "tagline": "Custom limits, governance, and deployment options.",
        "cta": "Contact us",
        "availability": "Private beta — no payment collection",
        "features": [
            "Unlimited repositories (contract)",
            "Unlimited scans (contract)",
            "SSO-ready placeholder",
            "Audit logs placeholder",
            "Private deployment note",
        ],
        "limits": {
            "max_repositories": -1,
            "max_scans_per_month": -1,
            "max_repo_files": -1,
            "max_exports_per_month": -1,
            "max_team_members": -1,
            "large_repo_allowed": True,
            "admin_dashboard_allowed": True,
        },
    },
}


def get_plan(plan_id: str) -> Dict[str, Any]:
    key = (plan_id or "FREE").upper()
    return dict(PLANS.get(key, PLANS["FREE"]))


def list_plans() -> List[Dict[str, Any]]:
    return [dict(PLANS[k]) for k in ("FREE", "PRO", "TEAM", "ENTERPRISE")]


def pricing_payload() -> Dict[str, Any]:
    return {
        "ok": True,
        "currency": "USD",
        "payment_provider": None,
        "checkout_enabled": False,
        "billing_enabled": False,
        "billing_message": "Billing is not enabled in this beta build. Plans are preview-only.",
        "note": (
            "Atlas compute is priced in token-equivalent units for planning only. "
            "Billing is not enabled in beta — no checkout, no payment collection."
        ),
        "plans": list_plans(),
    }
