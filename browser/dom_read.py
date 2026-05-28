"""Phase 28 — DOM read for allowlisted sites (no pixel clicking)."""

from __future__ import annotations

import re
import urllib.error
import urllib.request

from config import ALLOWED_TRADING_DASHBOARD_URL, BROWSER_DOM_ALLOWLIST, BROWSER_DOM_ENABLED

SITE_URLS: dict[str, str] = {
    "dashboard": ALLOWED_TRADING_DASHBOARD_URL,
    "chatgpt": "https://chatgpt.com",
    "tradingview": "https://www.tradingview.com",
    "yohananof": "https://www.ybitan.co.il",
}

# CSS selectors for read-only scrape (dashboard first)
SITE_SELECTORS: dict[str, list[str]] = {
    "dashboard": ["#health", ".status", "title", "h1"],
    "chatgpt": ["title"],
    "tradingview": ["title"],
    "yohananof": ["title"],
}


def read_dom(site: str, *, timeout: float = 5.0) -> tuple[bool, str]:
    if not BROWSER_DOM_ENABLED:
        return False, "Browser DOM is disabled. Set BROWSER_DOM_ENABLED=true in .env"
    key = (site or "dashboard").strip().lower()
    if key not in BROWSER_DOM_ALLOWLIST:
        return False, f"Site '{key}' not in allowlist: {sorted(BROWSER_DOM_ALLOWLIST)}"
    url = SITE_URLS.get(key)
    if not url:
        return False, f"No URL configured for {key}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "JARVIS-DOM-Read/1.0"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            html = resp.read(50000).decode("utf-8", errors="replace")
    except urllib.error.URLError as exc:
        return False, f"Fetch failed: {exc}"

    snippets: list[str] = [f"URL: {url}", f"Length: {len(html)} bytes", ""]
    for sel in SITE_SELECTORS.get(key, ["title"]):
        if sel == "title":
            m = re.search(r"<title[^>]*>([^<]+)</title>", html, re.I)
            if m:
                snippets.append(f"title: {m.group(1).strip()}")
        else:
            # naive id/class match
            pat = sel.lstrip("#.")
            if f'id="{pat}"' in html or f"class=\"{pat}\"" in html:
                snippets.append(f"selector {sel}: present")
            else:
                snippets.append(f"selector {sel}: not found in HTML snippet")

    snippets.append("")
    snippets.append("_Forms/orders/actions require separate confirmation — not automated._")
    return True, "\n".join(snippets)
