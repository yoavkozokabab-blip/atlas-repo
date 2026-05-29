"""Safe allowlisted website launcher actions (Phase 16)."""

from __future__ import annotations

from actions.base import BaseAction
from core import confirmation
from core.results import (
    result_blocked,
    result_clarification,
    result_confirmation_required,
    result_failed,
    result_success,
)
from core.types import CommandRequest, CommandResult, Intent
from websites.launcher import launch_website
from websites.registry import (
    ApprovedWebsite,
    WebsiteEntry,
    WebsiteRegistry,
    builtin_websites,
    find_website_match,
    get_approval_catalog_entry,
    get_builtin,
    normalize_website_query,
)
from websites.safety import SafetyError, validate_url


def _registry() -> WebsiteRegistry:
    return WebsiteRegistry()


def _website_query(request: CommandRequest) -> str:
    raw = str(
        request.params.get("website")
        or request.params.get("site")
        or request.params.get("query")
        or ""
    ).strip()
    return normalize_website_query(raw) if raw else ""


def _entry_from_params(data: dict) -> WebsiteEntry | None:
    if not data:
        return None
    try:
        site_id = normalize_website_query(str(data.get("site_id", "")))
        url = str(data.get("url", "")).strip()
        if not site_id or not url:
            return None
        return WebsiteEntry(
            site_id=site_id,
            display_name=str(data.get("display_name", site_id)),
            url=validate_url(url),
        )
    except (TypeError, ValueError, SafetyError):
        return None


class ListWebsitesAction(BaseAction):
    intent = Intent.LIST_WEBSITES.value

    def execute(self, request: CommandRequest) -> CommandResult:
        del request
        builtin = builtin_websites()
        approved = _registry().list_approved()
        lines = [f"Built-in websites ({len(builtin)}):"]
        for site in builtin:
            lines.append(f"  • {site.display_name} ({site.site_id})")
        if approved:
            lines.append(f"\nApproved websites ({len(approved)}):")
            for site in approved:
                lines.append(f"  • {site.display_name} ({site.site_id})")
        else:
            lines.append("\nNo additional approved websites yet.")
        return result_success(
            Intent.LIST_WEBSITES,
            "\n".join(lines),
            data={
                "builtin": [s.to_dict() for s in builtin],
                "approved": [s.to_dict() for s in approved],
            },
            next_suggestions=["open chatgpt", "open youtube"],
        )


class OpenWebsiteAction(BaseAction):
    intent = Intent.OPEN_WEBSITE.value

    def execute(self, request: CommandRequest) -> CommandResult:
        from browser.url_parser import extract_first_url, normalize_url

        raw_url = str(request.params.get("url") or "").strip() or extract_first_url(request.raw_text or "")
        if raw_url:
            from browser.runtime import get_browser_runtime_state, navigate_to_url

            target = normalize_url(raw_url)
            body = navigate_to_url(target)
            st = get_browser_runtime_state()
            if not st.last_action_success:
                if st.provider != "playwright":
                    return result_blocked(
                        Intent.OPEN_WEBSITE,
                        body,
                        error="real browser provider unavailable",
                    )
                return result_failed(Intent.OPEN_WEBSITE, body)
            return result_success(Intent.OPEN_WEBSITE, body, data={"url": target, "real_browser": True})

        reg = _registry()

        if request.confirmed:
            entry = _entry_from_params(request.params.get("website_entry", {}))
            if entry is None and request.params.get("site_id"):
                entry = reg.resolve_for_open(str(request.params["site_id"]))
            if entry is None:
                return result_failed(
                    Intent.OPEN_WEBSITE,
                    "Confirmation expired or website data missing. Try again.",
                )
            approved = ApprovedWebsite(
                site_id=entry.site_id,
                display_name=entry.display_name,
                url=entry.url,
            )
            reg.approve(approved)
            try:
                msg = launch_website(entry)
            except SafetyError as exc:
                return result_failed(Intent.OPEN_WEBSITE, str(exc), error=str(exc))
            return result_success(
                Intent.OPEN_WEBSITE,
                msg,
                data={"site_id": entry.site_id, "approved": True},
            )

        query = _website_query(request)
        if not query:
            return result_clarification(
                Intent.OPEN_WEBSITE,
                "Which website should I open? (e.g. open chatgpt)",
            )

        resolved = reg.resolve_for_open(query)
        if resolved is not None and (
            resolved.builtin or resolved.approved or reg.get(query) is not None
        ):
            try:
                msg = launch_website(resolved)
            except SafetyError as exc:
                return result_failed(Intent.OPEN_WEBSITE, str(exc), error=str(exc))
            return result_success(
                Intent.OPEN_WEBSITE,
                msg,
                data={"site_id": resolved.site_id, "url": resolved.url},
            )

        matches, norm = find_website_match(query)
        if not matches:
            return result_failed(
                Intent.OPEN_WEBSITE,
                f"'{query}' is not an allowlisted website. Try: list websites",
            )

        if len(matches) > 1:
            lines = [f"Multiple websites match '{query}':"]
            for site in matches[:8]:
                lines.append(f"  • {site.display_name} ({site.site_id})")
            lines.append("Please be more specific.")
            return result_clarification(
                Intent.OPEN_WEBSITE,
                "\n".join(lines),
                next_suggestions=[f"open {matches[0].site_id}"],
            )

        site = matches[0]
        if site.builtin:
            try:
                msg = launch_website(site)
            except SafetyError as exc:
                return result_failed(Intent.OPEN_WEBSITE, str(exc), error=str(exc))
            return result_success(
                Intent.OPEN_WEBSITE,
                msg,
                data={"site_id": site.site_id},
            )

        if reg.get(site.site_id) is not None:
            try:
                msg = launch_website(site)
            except SafetyError as exc:
                return result_failed(Intent.OPEN_WEBSITE, str(exc), error=str(exc))
            return result_success(Intent.OPEN_WEBSITE, msg, data={"site_id": site.site_id})

        catalog = get_approval_catalog_entry(site.site_id) or site
        cid = confirmation.create_confirmation(
            "open_website",
            {
                "raw_text": request.raw_text,
                "params": {
                    "website": norm,
                    "site_id": catalog.site_id,
                    "approve_and_open": True,
                    "website_entry": catalog.to_dict(),
                },
            },
        )
        return result_confirmation_required(
            Intent.OPEN_WEBSITE,
            f"Approve and open {catalog.display_name}? Reply yes/confirm/כן (id: {cid}) or no/cancel.",
            cid,
            next_suggestions=[f"yes ({cid})", "no"],
        )


class ApproveWebsiteAction(BaseAction):
    intent = Intent.APPROVE_WEBSITE.value

    def execute(self, request: CommandRequest) -> CommandResult:
        query = _website_query(request)
        url_raw = str(request.params.get("url") or "").strip()
        if not query:
            return result_clarification(
                Intent.APPROVE_WEBSITE,
                "Which website should I approve? (site id required)",
            )

        entry = get_builtin(query)
        if entry is not None:
            return result_failed(
                Intent.APPROVE_WEBSITE,
                f"{entry.display_name} is already built-in and does not need approval.",
            )

        if url_raw:
            try:
                safe_url = validate_url(url_raw)
            except SafetyError as exc:
                return result_failed(Intent.APPROVE_WEBSITE, str(exc), error=str(exc))
            display = str(request.params.get("display_name") or query)
            approved = ApprovedWebsite(
                site_id=query,
                display_name=display,
                url=safe_url,
            )
            _registry().approve(approved)
            return result_success(
                Intent.APPROVE_WEBSITE,
                f"Approved {display} for safe browsing.",
                data={"website": approved.to_dict()},
            )

        catalog = get_approval_catalog_entry(query)
        if catalog is None:
            return result_failed(
                Intent.APPROVE_WEBSITE,
                f"No allowlisted catalog entry for '{query}'. Provide a validated https URL.",
            )
        approved = ApprovedWebsite(
            site_id=catalog.site_id,
            display_name=catalog.display_name,
            url=catalog.url,
        )
        _registry().approve(approved)
        return result_success(
            Intent.APPROVE_WEBSITE,
            f"Approved {catalog.display_name}.",
            data={"website": approved.to_dict()},
        )


class ForgetWebsiteAction(BaseAction):
    intent = Intent.FORGET_WEBSITE.value

    def execute(self, request: CommandRequest) -> CommandResult:
        query = _website_query(request)
        if not query:
            return result_clarification(
                Intent.FORGET_WEBSITE,
                "Which website approval should I remove?",
            )
        if get_builtin(query) is not None:
            return result_failed(
                Intent.FORGET_WEBSITE,
                "Built-in websites cannot be removed from the registry.",
            )
        if not _registry().forget(query):
            return result_failed(
                Intent.FORGET_WEBSITE,
                f"'{query}' is not in the approved website list.",
            )
        return result_success(
            Intent.FORGET_WEBSITE,
            f"Removed '{query}' from approved websites.",
        )
