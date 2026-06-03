"""Phase 137A — draft plan catalogue (configurable, NOT enforced aggressively yet).

Plans describe intended limits/features so usage can be measured against them.
Nothing here blocks local usage; limits are surfaced in dashboards only.
"""

from __future__ import annotations

from typing import Dict, List

from .models import Plan, PlanLimit

PLANS: Dict[str, Plan] = {
    "free": Plan(
        id="free",
        name="Free",
        price_display="$0",
        tagline="Understand one or two repositories locally.",
        availability="Available (local) — private beta",
        cta="Get started",
        features=[
            "1 workspace",
            "Up to 3 repositories",
            "Small / medium repositories",
            "Limited scans per month",
            "Limited exports",
            "Repository map",
            "No team / admin features",
        ],
        limits=PlanLimit(
            workspaces=1, repositories=3, max_repo_size="medium",
            scans_per_month=30, exports_per_month=10,
            team_features=False, admin_dashboard=False,
            repository_map=True, evidence_engine=False, knowledge_engine=False,
            export_prompts=False, sso=False, audit_logs=False,
        ),
    ),
    "pro": Plan(
        id="pro",
        name="Pro",
        price_display="Coming soon",
        tagline="Serious repository intelligence for an individual engineer.",
        availability="Private beta — join waitlist",
        cta="Join waitlist",
        features=[
            "More repositories",
            "Larger repositories",
            "More scans",
            "Unlimited local reports (fair use)",
            "Export prompts",
            "Repository map",
            "Knowledge / evidence engine",
        ],
        limits=PlanLimit(
            workspaces=3, repositories=25, max_repo_size="large",
            scans_per_month=400, exports_per_month=-1,
            team_features=False, admin_dashboard=False,
            repository_map=True, evidence_engine=True, knowledge_engine=True,
            export_prompts=True, sso=False, audit_logs=False,
        ),
    ),
    "team": Plan(
        id="team",
        name="Team",
        price_display="Coming soon",
        tagline="Shared repository intelligence for a whole team.",
        availability="Private beta — contact us",
        cta="Contact us",
        features=[
            "Multiple users",
            "Shared workspaces",
            "Admin usage dashboard",
            "Higher limits",
            "Team repository history",
            "Knowledge / evidence engine",
        ],
        limits=PlanLimit(
            workspaces=10, repositories=200, max_repo_size="xlarge",
            scans_per_month=4000, exports_per_month=-1,
            team_features=True, admin_dashboard=True,
            repository_map=True, evidence_engine=True, knowledge_engine=True,
            export_prompts=True, sso=False, audit_logs=False,
        ),
    ),
    "enterprise": Plan(
        id="enterprise",
        name="Enterprise",
        price_display="Custom",
        tagline="Custom limits, private deployment, and governance.",
        availability="Private beta — contact us",
        cta="Contact us",
        features=[
            "Custom limits",
            "SSO-ready (placeholder)",
            "Audit logs",
            "Priority large-repo support",
            "Private deployment (note)",
        ],
        limits=PlanLimit(
            workspaces=-1, repositories=-1, max_repo_size="unlimited",
            scans_per_month=-1, exports_per_month=-1,
            team_features=True, admin_dashboard=True,
            repository_map=True, evidence_engine=True, knowledge_engine=True,
            export_prompts=True, sso=True, audit_logs=True,
            private_deployment=True,
        ),
    ),
}


def plan_ids() -> List[str]:
    return list(PLANS.keys())


def get_plan(plan_id: str) -> Plan:
    return PLANS.get((plan_id or "free").lower(), PLANS["free"])
