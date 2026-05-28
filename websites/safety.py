"""URL safety checks for website launcher — https allowlist only."""

from __future__ import annotations

import ipaddress
import re
from urllib.parse import urlparse, urlunparse

from config import ALLOWED_TRADING_DASHBOARD_URL

BLOCKED_SCHEMES: frozenset[str] = frozenset(
    {"file", "javascript", "data", "vbscript", "about", "ftp", "mailto"}
)

SUSPICIOUS_QUERY_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"<script", re.I),
    re.compile(r"javascript\s*:", re.I),
    re.compile(r"on\w+\s*=", re.I),
    re.compile(r"\bexec\b", re.I),
    re.compile(r"\beval\b", re.I),
)


class SafetyError(Exception):
    """URL is not safe to open."""


def _is_ip_host(host: str) -> bool:
    try:
        ipaddress.ip_address(host)
        return True
    except ValueError:
        if host.startswith("[") and host.endswith("]"):
            try:
                ipaddress.ip_address(host[1:-1])
                return True
            except ValueError:
                return False
        return False


def _is_trading_dashboard_url(url: str) -> bool:
    return url.rstrip("/") == ALLOWED_TRADING_DASHBOARD_URL.rstrip("/")


def validate_url(url: str) -> str:
    """
    Validate and normalize an https URL for webbrowser.open().
    Raises SafetyError if blocked.
    """
    raw = (url or "").strip()
    if not raw:
        raise SafetyError("Empty URL.")

    parsed = urlparse(raw)
    scheme = (parsed.scheme or "").lower()
    if scheme in BLOCKED_SCHEMES:
        raise SafetyError(f"Blocked URL scheme: {scheme}")
    if scheme != "https":
        raise SafetyError("Only https:// URLs are allowed.")

    host = (parsed.hostname or "").lower()
    if not host:
        raise SafetyError("URL must include a hostname.")

    if _is_ip_host(host):
        if not _is_trading_dashboard_url(raw):
            raise SafetyError("IP-only URLs are blocked.")

    if host in {"localhost", "127.0.0.1", "::1"}:
        if not _is_trading_dashboard_url(raw):
            raise SafetyError("localhost URLs are blocked (except trading dashboard intent).")

    port = parsed.port
    if port is not None and port != 443:
        if not (host in {"127.0.0.1", "localhost"} and port == 8077 and _is_trading_dashboard_url(raw)):
            raise SafetyError(f"Non-standard port {port} is blocked.")

    query = parsed.query or ""
    for pattern in SUSPICIOUS_QUERY_PATTERNS:
        if pattern.search(query):
            raise SafetyError("Suspicious query string blocked.")

    return normalize_url(raw)


def normalize_url(url: str) -> str:
    """Lowercase host, strip trailing slash on path, preserve punycode host."""
    parsed = urlparse(url.strip())
    host = (parsed.hostname or "").lower()
    path = parsed.path or ""
    if path != "/" and path.endswith("/"):
        path = path.rstrip("/")
    if not path:
        path = ""
    netloc = host
    if parsed.port and parsed.port != 443:
        netloc = f"{host}:{parsed.port}"
    rebuilt = urlunparse(
        (
            "https",
            netloc,
            path,
            "",
            parsed.query,
            "",
        )
    )
    return rebuilt
