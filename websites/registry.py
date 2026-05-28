"""Built-in and user-approved website registry."""

from __future__ import annotations

import json
import re
import shutil
import unicodedata
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from config import APPROVED_WEBSITES_PATH, BACKUPS_DIR, DATA_DIR
from core.logger import setup_logger
from websites.safety import SafetyError, validate_url

logger = setup_logger("jarvis.websites.registry")

_BUILTIN_WEBSITES: dict[str, dict[str, str]] = {
    "chatgpt": {
        "display_name": "ChatGPT",
        "url": "https://chatgpt.com",
    },
    "tradingview": {
        "display_name": "TradingView",
        "url": "https://www.tradingview.com",
    },
    "youtube": {
        "display_name": "YouTube",
        "url": "https://www.youtube.com",
    },
    "gmail": {
        "display_name": "Gmail",
        "url": "https://mail.google.com",
    },
    "google": {
        "display_name": "Google",
        "url": "https://www.google.com",
    },
    "github": {
        "display_name": "GitHub",
        "url": "https://github.com",
    },
    "yohananof": {
        "display_name": "Yohananof",
        "url": "https://www.ybitan.co.il",
    },
    "openai": {
        "display_name": "OpenAI",
        "url": "https://platform.openai.com",
    },
}

# Sites that may be opened after one-time user approval (not built-in immediate).
_APPROVAL_CATALOG: dict[str, dict[str, str]] = {}

_WEBSITE_ALIASES: dict[str, str] = {
    "chat gpt": "chatgpt",
    "gpt": "chatgpt",
    "צאט גיפיטי": "chatgpt",
    "צאטגיפיטי": "chatgpt",
    "טריידינגויו": "tradingview",
    "trading view": "tradingview",
    "יוטיוב": "youtube",
    "גימייל": "gmail",
    "גיטהאב": "github",
    "יוחננוף": "yohananof",
    "ybitan": "yohananof",
}


@dataclass(frozen=True)
class WebsiteEntry:
    site_id: str
    display_name: str
    url: str
    builtin: bool = False
    approved: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "site_id": self.site_id,
            "display_name": self.display_name,
            "url": self.url,
            "builtin": self.builtin,
            "approved": self.approved,
        }


@dataclass(frozen=True)
class ApprovedWebsite:
    site_id: str
    display_name: str
    url: str
    approved_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "site_id": self.site_id,
            "display_name": self.display_name,
            "url": self.url,
            "approved_at": self.approved_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ApprovedWebsite | None:
        try:
            sid = website_slug_key(str(data.get("site_id", "")))
            url = str(data.get("url", "")).strip()
            if not sid or not url:
                return None
            safe_url = validate_url(url)
            return cls(
                site_id=sid,
                display_name=str(data.get("display_name", sid)),
                url=safe_url,
                approved_at=str(data.get("approved_at", "")),
            )
        except (TypeError, ValueError, SafetyError):
            return None


def website_slug_key(site_id: str) -> str:
    return website_slug(site_id)


def website_slug(name: str) -> str:
    text = unicodedata.normalize("NFKC", name).strip().lower()
    text = re.sub(r"[^\w\s-]", "", text, flags=re.UNICODE)
    text = re.sub(r"[\s_]+", "", text)
    return text


def normalize_website_query(query: str) -> str:
    raw = unicodedata.normalize("NFKC", query).strip().lower()
    raw = re.sub(r"\s+", " ", raw)
    if raw in _WEBSITE_ALIASES:
        return _WEBSITE_ALIASES[raw]
    slug = website_slug(raw)
    if slug in _WEBSITE_ALIASES:
        return _WEBSITE_ALIASES[slug]
    return slug


def builtin_websites() -> list[WebsiteEntry]:
    out: list[WebsiteEntry] = []
    for site_id, meta in sorted(_BUILTIN_WEBSITES.items()):
        out.append(
            WebsiteEntry(
                site_id=site_id,
                display_name=meta["display_name"],
                url=validate_url(meta["url"]),
                builtin=True,
                approved=False,
            )
        )
    return out


def get_builtin(site_id: str) -> WebsiteEntry | None:
    key = website_slug_key(site_id)
    meta = _BUILTIN_WEBSITES.get(key)
    if meta is None:
        return None
    return WebsiteEntry(
        site_id=key,
        display_name=meta["display_name"],
        url=validate_url(meta["url"]),
        builtin=True,
    )


def get_approval_catalog_entry(site_id: str) -> WebsiteEntry | None:
    key = website_slug_key(site_id)
    meta = _APPROVAL_CATALOG.get(key)
    if meta is None:
        return None
    return WebsiteEntry(
        site_id=key,
        display_name=meta["display_name"],
        url=validate_url(meta["url"]),
        builtin=False,
    )


def is_builtin_website_slug(slug: str) -> bool:
    return website_slug_key(slug) in _BUILTIN_WEBSITES


def all_website_slugs() -> frozenset[str]:
    return frozenset(_BUILTIN_WEBSITES.keys()) | frozenset(_APPROVAL_CATALOG.keys())


def find_website_match(query: str) -> tuple[list[WebsiteEntry], str]:
    norm = normalize_website_query(query)
    if not norm:
        return [], ""

    matches: list[WebsiteEntry] = []
    builtin = get_builtin(norm)
    if builtin is not None:
        matches.append(builtin)

    catalog = get_approval_catalog_entry(norm)
    if catalog is not None and catalog.site_id not in {m.site_id for m in matches}:
        matches.append(catalog)

    if len(matches) == 1:
        return matches, norm

    # Fuzzy alias scan
    for alias, target in _WEBSITE_ALIASES.items():
        if norm == target or norm in alias.replace(" ", ""):
            entry = get_builtin(target) or get_approval_catalog_entry(target)
            if entry and entry.site_id not in {m.site_id for m in matches}:
                matches.append(entry)

    # Partial id match (unique only)
    partial: list[WebsiteEntry] = []
    for site_id in _BUILTIN_WEBSITES:
        if norm in site_id or site_id.startswith(norm):
            entry = get_builtin(site_id)
            if entry:
                partial.append(entry)
    for site_id in _APPROVAL_CATALOG:
        if norm in site_id or site_id.startswith(norm):
            entry = get_approval_catalog_entry(site_id)
            if entry:
                partial.append(entry)

    if len(partial) == 1 and not matches:
        return partial, norm
    if len(partial) > 1:
        return partial, norm

    return matches, norm


class WebsiteRegistry:
    """Persist user-approved websites."""

    def __init__(self, path: Any | None = None) -> None:
        from pathlib import Path

        self.path = Path(path) if path is not None else APPROVED_WEBSITES_PATH
        self.path.parent.mkdir(parents=True, exist_ok=True)
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        BACKUPS_DIR.mkdir(parents=True, exist_ok=True)

    def _load(self) -> dict[str, dict[str, Any]]:
        if not self.path.is_file():
            return {}
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            sites = data.get("websites") if isinstance(data, dict) else data
            if isinstance(sites, dict):
                return sites
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning("Could not load approved websites: %s", exc)
        return {}

    def _save(self, sites: dict[str, dict[str, Any]]) -> None:
        if self.path.is_file():
            stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup = BACKUPS_DIR / f"approved_websites_{stamp}.json"
            try:
                shutil.copy2(self.path, backup)
            except OSError as exc:
                logger.debug("Approved websites backup skipped: %s", exc)
        payload = {
            "websites": sites,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        self.path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def list_approved(self) -> list[ApprovedWebsite]:
        out: list[ApprovedWebsite] = []
        for raw in self._load().values():
            site = ApprovedWebsite.from_dict(raw)
            if site is not None:
                out.append(site)
        return sorted(out, key=lambda s: s.display_name.lower())

    def get(self, site_id: str) -> ApprovedWebsite | None:
        raw = self._load().get(website_slug_key(site_id))
        if raw is None:
            return None
        return ApprovedWebsite.from_dict(raw)

    def approve(self, site: ApprovedWebsite) -> ApprovedWebsite:
        safe_url = validate_url(site.url)
        apps = self._load()
        entry = site.to_dict()
        entry["url"] = safe_url
        entry["approved_at"] = datetime.now(timezone.utc).isoformat()
        apps[site.site_id] = entry
        self._save(apps)
        return ApprovedWebsite.from_dict(entry) or site

    def forget(self, site_id: str) -> bool:
        apps = self._load()
        key = website_slug_key(site_id)
        if key not in apps:
            return False
        del apps[key]
        self._save(apps)
        return True

    def resolve_for_open(self, site_id: str) -> WebsiteEntry | None:
        """Built-in, then user-approved."""
        builtin = get_builtin(site_id)
        if builtin is not None:
            return builtin
        approved = self.get(site_id)
        if approved is not None:
            return WebsiteEntry(
                site_id=approved.site_id,
                display_name=approved.display_name,
                url=approved.url,
                approved=True,
            )
        catalog = get_approval_catalog_entry(site_id)
        if catalog is not None:
            return catalog
        return None
