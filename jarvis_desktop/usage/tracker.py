"""Phase 137A — usage event recording and dashboard aggregations."""

from __future__ import annotations

import hashlib
import os
import time
from collections import defaultdict
from typing import Any, Dict, List, Optional

from .estimator import estimate_repo_cost
from .limits import check_limit, enforcement_enabled
from .models import EVENT_TYPES, UsageEvent
from .plans import get_plan, list_plans, pricing_payload
from .store import UsageStore, default_store


def billing_ui_enabled() -> bool:
    return os.environ.get("ATLAS_BILLING_UI_ENABLED", "").strip().lower() in ("1", "true", "yes")


def current_context(store: Optional[UsageStore] = None) -> Dict[str, Any]:
    st = store or default_store()
    user = st.ensure_local_user()
    return {
        "user_id": user.id,
        "workspace_id": user.workspace_id,
        "plan": user.plan,
        "is_admin": user.is_admin,
    }


def repo_id_from_path(repo_path: str) -> str:
    norm = os.path.abspath(repo_path or "").replace("\\", "/").lower()
    if not norm:
        return ""
    return hashlib.sha256(norm.encode("utf-8")).hexdigest()[:16]


def record_event(
    event_type: str,
    *,
    user_id: str = "",
    workspace_id: str = "",
    repo_id: str = "",
    repo_path: str = "",
    repo_name: str = "",
    files_count: int = 0,
    modules_count: int = 0,
    edges_count: int = 0,
    symbols_count: int = 0,
    scan_duration_seconds: float = 0.0,
    estimated_token_equivalent: int = 0,
    plan: str = "FREE",
    ok: bool = True,
    meta: Optional[Dict[str, Any]] = None,
    store: Optional[UsageStore] = None,
) -> Dict[str, Any]:
    """Append a usage event; never raises."""
    if event_type not in EVENT_TYPES:
        return {"ok": False, "error": f"unknown event_type: {event_type}"}
    st = store or default_store()
    ctx = current_context(st)
    est = estimate_repo_cost(
        files_count, modules_count, edges_count, symbols_count, scan_duration_seconds
    )
    tok = estimated_token_equivalent or est["token_equivalent_estimate"]
    event = UsageEvent(
        user_id=user_id or ctx["user_id"],
        workspace_id=workspace_id or ctx["workspace_id"],
        event_type=event_type,
        repo_id=repo_id or repo_id_from_path(repo_path),
        repo_path=repo_path,
        repo_name=repo_name,
        files_count=files_count,
        modules_count=modules_count,
        edges_count=edges_count,
        symbols_count=symbols_count,
        scan_duration_seconds=scan_duration_seconds,
        estimated_token_equivalent=tok,
        plan=(plan or ctx["plan"]).upper(),
        ok=ok,
        meta=dict(meta or {}),
    )
    saved = st.record(event)
    return {"ok": saved, "event": event.to_dict(), "estimate": est}


def record_from_scan(
    event_type: str,
    scan: Dict[str, Any],
    *,
    repo_path: str = "",
    symbols_count: int = 0,
    ok: bool = True,
    meta: Optional[Dict[str, Any]] = None,
    store: Optional[UsageStore] = None,
) -> Dict[str, Any]:
    path = repo_path or scan.get("repo_path") or ""
    return record_event(
        event_type,
        repo_path=path,
        repo_name=scan.get("repo_name") or os.path.basename(path) or "",
        files_count=int(scan.get("file_count") or 0),
        modules_count=int(scan.get("module_count") or 0),
        edges_count=int(scan.get("dependency_edges") or 0),
        symbols_count=symbols_count,
        scan_duration_seconds=float(scan.get("scan_duration_seconds") or 0),
        ok=ok,
        meta=meta,
        store=store,
    )


def _atlas_compute_units(events: List[UsageEvent]) -> float:
    total = 0.0
    for ev in events:
        est = estimate_repo_cost(
            ev.files_count,
            ev.modules_count,
            ev.edges_count,
            ev.symbols_count,
            ev.scan_duration_seconds,
        )
        total += float(est.get("scan_units") or 0)
    return round(total, 2)


def _recent_events(events: List[UsageEvent], limit: int = 12) -> List[Dict[str, Any]]:
    rows = sorted(events, key=lambda e: e.created_at, reverse=True)[:limit]
    out: List[Dict[str, Any]] = []
    for ev in rows:
        out.append(
            {
                "id": ev.id,
                "event_type": ev.event_type,
                "repo_name": ev.repo_name,
                "repo_path": ev.repo_path,
                "files_count": ev.files_count,
                "scan_duration_seconds": ev.scan_duration_seconds,
                "estimated_token_equivalent": ev.estimated_token_equivalent,
                "created_at": ev.created_at,
                "ok": ev.ok,
            }
        )
    return out


def _high_usage_users(events: List[UsageEvent], limit: int = 8) -> List[Dict[str, Any]]:
    by_user: Dict[str, Dict[str, Any]] = {}
    for ev in events:
        key = ev.user_id or "unknown"
        row = by_user.setdefault(
            key,
            {
                "user_id": key,
                "workspace_id": ev.workspace_id,
                "plan": ev.plan,
                "events": 0,
                "token_equivalent": 0,
            },
        )
        row["events"] += 1
        row["token_equivalent"] += int(ev.estimated_token_equivalent or 0)
        row["workspace_id"] = ev.workspace_id or row["workspace_id"]
        row["plan"] = ev.plan or row["plan"]
    ranked = sorted(by_user.values(), key=lambda r: (-r["token_equivalent"], -r["events"]))
    return ranked[:limit]


def _month_start_ts() -> float:
    lt = time.localtime()
    return time.mktime((lt.tm_year, lt.tm_mon, 1, 0, 0, 0, 0, 0, -1))


def _events_this_month(events: List[UsageEvent]) -> List[UsageEvent]:
    start = _month_start_ts()
    out: List[UsageEvent] = []
    for ev in events:
        try:
            ts = time.strptime(ev.created_at, "%Y-%m-%dT%H:%M:%S")
            if time.mktime(ts) >= start:
                out.append(ev)
        except ValueError:
            out.append(ev)
    return out


def _aggregate(events: List[UsageEvent]) -> Dict[str, Any]:
    repos: Dict[str, Dict[str, Any]] = {}
    by_type: Dict[str, int] = defaultdict(int)
    total_tokens = 0
    scans_ok = 0
    scans_fail = 0
    slowest: List[Dict[str, Any]] = []

    for ev in events:
        by_type[ev.event_type] += 1
        total_tokens += int(ev.estimated_token_equivalent or 0)
        rid = ev.repo_id or repo_id_from_path(ev.repo_path)
        if rid:
            row = repos.setdefault(
                rid,
                {
                    "repo_id": rid,
                    "repo_name": ev.repo_name,
                    "repo_path": ev.repo_path,
                    "files_count": ev.files_count,
                    "modules_count": ev.modules_count,
                    "edges_count": ev.edges_count,
                    "events": 0,
                    "token_equivalent": 0,
                },
            )
            row["events"] += 1
            row["token_equivalent"] += int(ev.estimated_token_equivalent or 0)
            row["files_count"] = max(row["files_count"], ev.files_count)
            row["modules_count"] = max(row["modules_count"], ev.modules_count)
        if ev.event_type == "scan_completed":
            if ev.ok:
                scans_ok += 1
            else:
                scans_fail += 1
            slowest.append(
                {
                    "repo_name": ev.repo_name,
                    "repo_path": ev.repo_path,
                    "duration_sec": ev.scan_duration_seconds,
                    "files_count": ev.files_count,
                    "ok": ev.ok,
                }
            )

    largest = sorted(repos.values(), key=lambda r: (-r["files_count"], -r["modules_count"]))[:8]
    slowest.sort(key=lambda r: -float(r.get("duration_sec") or 0))
    return {
        "event_counts": dict(by_type),
        "repositories_tracked": len(repos),
        "token_equivalent_total": total_tokens,
        "scans_completed": scans_ok,
        "scans_failed": scans_fail,
        "largest_repos": largest,
        "slowest_scans": slowest[:8],
    }


def usage_me_summary(store: Optional[UsageStore] = None) -> Dict[str, Any]:
    st = store or default_store()
    user = st.ensure_local_user()
    plan = get_plan(user.plan)
    month = _events_this_month(st.all_events())
    mine = [e for e in month if e.user_id == user.id]
    agg = _aggregate(mine)
    scans_used = agg["event_counts"].get("scan_completed", 0)
    exports_used = agg["event_counts"].get("export_created", 0)
    repos_seen = len({e.repo_id for e in mine if e.repo_id})
    atlas_units = _atlas_compute_units(mine)
    token_total = int(agg["token_equivalent_total"] or 0)

    limits = plan.get("limits") or {}
    usage_counts = {
        "scans_used": scans_used,
        "exports_used": exports_used,
        "repositories_used": repos_seen,
        "build_plans": agg["event_counts"].get("build_plan_created", 0),
        "investigations": agg["event_counts"].get("investigation_created", 0),
        "impacts": agg["event_counts"].get("impact_created", 0),
        "repository_map_opens": agg["event_counts"].get("repository_map_opened", 0),
        "token_equivalent_total": token_total,
        "atlas_compute_units": atlas_units,
    }
    has_activity = any(
        int(usage_counts[k] or 0) > 0
        for k in (
            "scans_used",
            "exports_used",
            "repositories_used",
            "build_plans",
            "investigations",
            "impacts",
            "repository_map_opens",
        )
    )
    return {
        "ok": True,
        "billing_ui_enabled": billing_ui_enabled(),
        "enforcement_enabled": enforcement_enabled(),
        "billing_status": "local_preview",
        "payments_active": False,
        "user": user.to_dict(),
        "plan": plan,
        "usage": usage_counts,
        "limits": limits,
        "limit_checks": {
            "scans": check_limit(user.plan, "max_scans_per_month", scans_used),
            "exports": check_limit(user.plan, "max_exports_per_month", exports_used),
            "repositories": check_limit(user.plan, "max_repositories", repos_seen),
        },
        "largest_repos": agg["largest_repos"],
        "recent_events": _recent_events(mine),
        "estimated_token_equivalent": token_total,
        "estimated_atlas_compute_units": atlas_units,
        "has_usage_data": has_activity,
        "empty_state_message": (
            ""
            if has_activity
            else "No usage recorded yet. Run a scan or generate a Build Plan to populate this dashboard."
        ),
        "billing_enabled": False,
        "billing_message": "Billing is not enabled in this beta build. Usage is tracked locally only.",
        "upgrade_note": "Billing is not enabled in beta — join the waitlist for paid plans when they launch.",
    }


def usage_admin_summary(store: Optional[UsageStore] = None, *, is_admin: bool = False) -> Dict[str, Any]:
    if not is_admin:
        return {
            "ok": False,
            "error": "Admin dashboard is disabled. Start Atlas with ATLAS_ADMIN=1 to view local usage analytics.",
            "code": "admin_disabled",
            "admin_enabled": False,
        }
    st = store or default_store()
    month = _events_this_month(st.all_events())
    agg = _aggregate(month)
    users = st.ensure_local_user()
    by_plan: Dict[str, int] = defaultdict(int)
    by_plan[users.plan] += 1
    token_total = int(agg["token_equivalent_total"] or 0)
    atlas_units = _atlas_compute_units(month)
    counts = agg["event_counts"]
    return {
        "ok": True,
        "admin_enabled": True,
        "billing_ui_enabled": billing_ui_enabled(),
        "mock_users": 1,
        "total_events": len(month),
        "total_scans": counts.get("scan_completed", 0),
        "total_repositories": agg["repositories_tracked"],
        "total_build_plans": counts.get("build_plan_created", 0),
        "total_investigations": counts.get("investigation_created", 0),
        "total_impacts": counts.get("impact_created", 0),
        "total_exports": counts.get("export_created", 0),
        "failed_scans": agg["scans_failed"],
        "token_equivalent_total": token_total,
        "estimated_token_equivalent": token_total,
        "estimated_atlas_compute_units": atlas_units,
        "usage_by_plan": dict(by_plan),
        "largest_repositories": agg["largest_repos"],
        "largest_repos": agg["largest_repos"],
        "slowest_scans": agg["slowest_scans"],
        "high_usage_users": _high_usage_users(month),
        "highest_usage_repos": sorted(
            agg["largest_repos"],
            key=lambda r: -int(r.get("token_equivalent") or 0),
        )[:8],
        "recent_events": _recent_events(month, limit=20),
        "event_counts": counts,
    }


def plans_api() -> Dict[str, Any]:
    return {"ok": True, "plans": list_plans(), "enforcement_enabled": enforcement_enabled()}


def pricing_api() -> Dict[str, Any]:
    payload = pricing_payload()
    payload["billing_ui_enabled"] = billing_ui_enabled()
    return payload
