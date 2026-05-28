"""Safe installed-app launcher actions (Phase 15)."""

from __future__ import annotations

from pathlib import Path

from actions.base import BaseAction
from apps.app_registry import AppRegistry, ApprovedApp
from apps.discovery import (
    DiscoveredApp,
    discover_installed_apps,
    find_best_match,
    normalize_app_query,
    search_discovered_apps,
)
from apps.launcher import launch_approved, launch_discovered
from apps.safety import SafetyError
from core import confirmation
from core.results import (
    result_clarification,
    result_confirmation_required,
    result_failed,
    result_success,
)
from core.types import CommandRequest, CommandResult, Intent


def _registry() -> AppRegistry:
    return AppRegistry()


def _app_query(request: CommandRequest) -> str:
    raw = str(request.params.get("app") or request.params.get("query") or "").strip()
    return normalize_app_query(raw) if raw else ""


def _discovered_from_params(data: dict) -> DiscoveredApp | None:
    if not data:
        return None
    try:
        shortcut = Path(str(data.get("shortcut_path", "")))
        return DiscoveredApp(
            app_id=str(data.get("app_id", "")),
            display_name=str(data.get("display_name", "")),
            shortcut_path=shortcut,
            target_path=(
                Path(str(data["target_path"])) if data.get("target_path") else None
            ),
            source=str(data.get("source", "start_menu")),
        )
    except (TypeError, ValueError):
        return None


class DiscoverAppsAction(BaseAction):
    intent = Intent.DISCOVER_APPS.value

    def execute(self, request: CommandRequest) -> CommandResult:
        apps = discover_installed_apps()
        return result_success(
            Intent.DISCOVER_APPS,
            f"Discovered {len(apps)} Start Menu application(s).",
            data={"count": len(apps), "apps": [a.to_dict() for a in apps[:40]]},
            next_suggestions=["list apps", "search apps discord"],
        )


class ListAppsAction(BaseAction):
    intent = Intent.LIST_APPS.value

    def execute(self, request: CommandRequest) -> CommandResult:
        approved = _registry().list_approved()
        if not approved:
            discovered = discover_installed_apps()
            lines = [f"Discovered {len(discovered)} app(s) (none approved yet)."]
            for app in discovered[:25]:
                lines.append(f"  • {app.display_name} ({app.app_id})")
            if len(discovered) > 25:
                lines.append(f"  … and {len(discovered) - 25} more")
            return result_success(
                Intent.LIST_APPS,
                "\n".join(lines),
                data={"approved": [], "discovered_count": len(discovered)},
            )
        lines = [f"Approved apps ({len(approved)}):"]
        for app in approved:
            lines.append(f"  • {app.display_name} ({app.app_id})")
        return result_success(
            Intent.LIST_APPS,
            "\n".join(lines),
            data={"approved": [a.to_dict() for a in approved]},
        )


class SearchAppsAction(BaseAction):
    intent = Intent.SEARCH_APPS.value

    def execute(self, request: CommandRequest) -> CommandResult:
        query = str(request.params.get("query") or _app_query(request) or "").strip()
        if not query:
            return result_clarification(
                Intent.SEARCH_APPS,
                "What app should I search for?",
            )
        matches = search_discovered_apps(query)
        if not matches:
            return result_failed(
                Intent.SEARCH_APPS,
                f"No apps matched '{query}'.",
            )
        lines = [f"Found {len(matches)} match(es) for '{query}':"]
        for app in matches[:15]:
            lines.append(f"  • {app.display_name} ({app.app_id})")
        return result_success(
            Intent.SEARCH_APPS,
            "\n".join(lines),
            data={"matches": [a.to_dict() for a in matches]},
        )


class OpenAppAction(BaseAction):
    intent = Intent.OPEN_APP.value

    def execute(self, request: CommandRequest) -> CommandResult:
        reg = _registry()
        from browser.url_parser import is_probable_url

        if request.confirmed:
            discovered = _discovered_from_params(request.params.get("discovered", {}))
            if discovered is None and request.params.get("app_id"):
                matches, _ = find_best_match(str(request.params.get("app_id")))
                if len(matches) == 1:
                    discovered = matches[0]
            if discovered is None:
                return result_failed(
                    Intent.OPEN_APP,
                    "Confirmation expired or app data missing. Try again.",
                )
            approved = ApprovedApp(
                app_id=discovered.app_id,
                display_name=discovered.display_name,
                shortcut_path=discovered.shortcut_path,
                target_path=discovered.target_path,
            )
            reg.approve(approved)
            try:
                msg = launch_discovered(discovered)
            except SafetyError as exc:
                return result_failed(Intent.OPEN_APP, str(exc), error=str(exc))
            return result_success(
                Intent.OPEN_APP,
                msg,
                data={"app_id": discovered.app_id, "approved": True},
            )

        raw_candidate = str(request.params.get("app") or request.params.get("query") or "").strip()
        if raw_candidate and is_probable_url(raw_candidate):
            return result_failed(Intent.OPEN_APP, "detected_url_not_app")
        query = _app_query(request)
        if not query:
            return result_clarification(
                Intent.OPEN_APP,
                "Which application should I open?",
            )
        if is_probable_url(query):
            return result_failed(Intent.OPEN_APP, "detected_url_not_app")

        approved = reg.get(query)
        if approved is not None:
            try:
                msg = launch_approved(approved)
            except SafetyError as exc:
                return result_failed(Intent.OPEN_APP, str(exc), error=str(exc))
            return result_success(
                Intent.OPEN_APP,
                msg,
                data={"app_id": approved.app_id},
            )

        matches, norm = find_best_match(query)
        if not matches:
            return result_failed(
                Intent.OPEN_APP,
                f"No installed app found for '{query}'. Try: discover apps",
            )
        if len(matches) > 1:
            lines = [f"Multiple apps match '{query}':"]
            for app in matches[:8]:
                lines.append(f"  • {app.display_name} ({app.app_id})")
            lines.append("Please be more specific.")
            return result_clarification(
                Intent.OPEN_APP,
                "\n".join(lines),
                next_suggestions=[f"open {matches[0].app_id}"],
            )

        app = matches[0]
        cid = confirmation.create_confirmation(
            "open_app",
            {
                "raw_text": request.raw_text,
                "params": {
                    "app": norm,
                    "app_id": app.app_id,
                    "approve_and_open": True,
                    "discovered": app.to_dict(),
                },
            },
        )
        return result_confirmation_required(
            Intent.OPEN_APP,
            f"Approve and open {app.display_name}? Reply yes/confirm/כן (id: {cid}) or no/cancel.",
            cid,
            next_suggestions=[f"yes ({cid})", "no"],
        )


class ApproveAppAction(BaseAction):
    intent = Intent.APPROVE_APP.value

    def execute(self, request: CommandRequest) -> CommandResult:
        query = _app_query(request)
        if not query:
            return result_clarification(Intent.APPROVE_APP, "Which app should I approve?")
        matches, _ = find_best_match(query)
        if not matches:
            return result_failed(Intent.APPROVE_APP, f"No app found for '{query}'.")
        if len(matches) > 1:
            return result_clarification(
                Intent.APPROVE_APP,
                f"Multiple apps match '{query}'. Specify one.",
            )
        app = matches[0]
        approved = ApprovedApp(
            app_id=app.app_id,
            display_name=app.display_name,
            shortcut_path=app.shortcut_path,
            target_path=app.target_path,
        )
        _registry().approve(approved)
        return result_success(
            Intent.APPROVE_APP,
            f"Approved {app.display_name} for safe launch.",
            data={"app": approved.to_dict()},
        )


class ForgetAppAction(BaseAction):
    intent = Intent.FORGET_APP.value

    def execute(self, request: CommandRequest) -> CommandResult:
        query = _app_query(request)
        if not query:
            return result_clarification(Intent.FORGET_APP, "Which app should I remove?")
        if not _registry().forget(query):
            return result_failed(
                Intent.FORGET_APP,
                f"'{query}' is not in the approved app list.",
            )
        return result_success(
            Intent.FORGET_APP,
            f"Removed '{query}' from approved apps.",
        )
