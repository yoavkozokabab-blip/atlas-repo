"""Phase 71 — tool providers.

A provider is the only thing that touches the real world.  The ``ToolProvider``
protocol is intentionally tiny: ``is_real``, ``observe``, ``execute``,
``apply_recovery``, ``close``.

``PlaywrightBrowserProvider`` owns its OWN Playwright session (independent of the
legacy ``browser/runtime.py`` global state) so this layer cannot inherit the
mock fallbacks that exist there.  There is no mock branch here: if Playwright or
Chromium is unavailable, ``is_real()`` returns False and the executor reports
BLOCKED_UNAVAILABLE — never success.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Protocol
from urllib.parse import parse_qs, quote_plus, unquote, urlparse

from tooluse.contracts import Observation, PlanStep, StepKind, StepOutcome
from tooluse.recovery import RecoveryDecision, RecoveryKind

# Marginalia is an independent, headless-friendly search engine with stable HTML
# and no aggressive bot-blocking — the most reliable source for a real foundation.
_SEARCH_URL = "https://search.marginalia.nu/search?query={q}"
_SEARCH_ENGINE_HOSTS = (
    "marginalia.nu", "marginalia-search.com",
    "duckduckgo.com", "bing.com", "google.com", "microsoft.com", "msn.com",
)
_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"
)


def _normalize_href(href: str) -> str:
    """Resolve protocol-relative URLs and decode DuckDuckGo /l/?uddg= redirects."""
    href = (href or "").strip()
    if href.startswith("//"):
        href = "https:" + href
    try:
        p = urlparse(href)
        host = (p.hostname or "").lower()
        if "duckduckgo.com" in host and p.path.startswith("/l/"):
            uddg = parse_qs(p.query).get("uddg")
            if uddg:
                return unquote(uddg[0])
    except Exception:
        pass
    return href


class ToolProvider(Protocol):
    def is_real(self) -> bool: ...
    def observe(self) -> Observation: ...
    def execute(self, step: PlanStep) -> StepOutcome: ...
    def apply_recovery(self, decision: RecoveryDecision, step: PlanStep) -> None: ...
    def close(self) -> None: ...


def _query_tokens(text: str) -> set[str]:
    return {t for t in (text or "").lower().split() if len(t) > 2}


class PlaywrightBrowserProvider:
    """Real browser provider backed by an isolated Playwright Chromium session."""

    def __init__(self, *, headless: bool = True, screenshot_dir: Path | None = None) -> None:
        self._headless = headless
        self._pw = None
        self._browser = None
        self._context = None
        self._page = None
        self._results: list[dict[str, str]] = []
        self._cursor = 0
        self._last_query = ""
        self._launch_error = ""
        from config import DATA_DIR

        self._shot_dir = screenshot_dir or (Path(DATA_DIR) / "tooluse_screenshots")

    # -- lifecycle ---------------------------------------------------------

    def _ensure_session(self) -> bool:
        if self._browser is not None and self._page is not None:
            try:
                if self._browser.is_connected():
                    return True
            except Exception:
                pass
        try:
            from playwright.sync_api import sync_playwright

            self._pw = sync_playwright().start()
            self._browser = self._pw.chromium.launch(headless=self._headless)
            self._context = self._browser.new_context(user_agent=_USER_AGENT)
            self._page = self._context.new_page()
            self._launch_error = ""
            return True
        except Exception as exc:  # ImportError, browser binary missing, etc.
            self._launch_error = str(exc)[:300]
            self._browser = None
            self._page = None
            return False

    def is_real(self) -> bool:
        if not self._ensure_session():
            return False
        try:
            return bool(self._browser.is_connected()) and self._page is not None
        except Exception:
            return False

    def close(self) -> None:
        for closer in (
            lambda: self._context and self._context.close(),
            lambda: self._browser and self._browser.close(),
            lambda: self._pw and self._pw.stop(),
        ):
            try:
                closer()
            except Exception:
                pass
        self._pw = self._browser = self._context = self._page = None

    # -- observe -----------------------------------------------------------

    def observe(self) -> Observation:
        if self._page is None:
            return Observation(
                real=False,
                provider="playwright" if self._pw else "unavailable",
                error=self._launch_error or "no active page",
            )
        page = self._page
        url = title = ""
        headings: list[str] = []
        links: list[dict[str, str]] = []
        buttons: list[str] = []
        text = ""
        try:
            url = page.url or ""
        except Exception:
            pass
        try:
            title = (page.title() or "")[:200]
        except Exception:
            pass
        try:
            headings = [h.strip() for h in page.eval_on_selector_all(
                "h1,h2,h3", "els => els.map(e => (e.innerText||'').trim())"
            ) if h.strip()][:20]
        except Exception:
            pass
        try:
            rows = page.eval_on_selector_all(
                "a[href]",
                "els => els.map(e => ({text:(e.innerText||'').trim(), href:e.href||''}))",
            )
            for r in rows[:120]:
                href = _normalize_href(str((r or {}).get("href") or ""))
                txt = str((r or {}).get("text") or "").strip()
                if href.startswith("http"):
                    links.append({"text": txt[:180], "href": href[:500]})
        except Exception:
            pass
        try:
            buttons = [b.strip() for b in page.eval_on_selector_all(
                "button,input[type='submit']", "els => els.map(e => (e.innerText||e.value||'').trim())"
            ) if b.strip()][:30]
        except Exception:
            pass
        try:
            text = (page.inner_text("body") or "").strip()[:5000]
        except Exception:
            pass
        shot = self._screenshot()
        return Observation(
            real=True,
            provider="playwright",
            url=url,
            title=title,
            headings=headings,
            links=links,
            buttons=buttons,
            visible_text=text,
            screenshot_path=shot,
        )

    def _screenshot(self) -> str:
        if self._page is None:
            return ""
        try:
            self._shot_dir.mkdir(parents=True, exist_ok=True)
            path = self._shot_dir / f"shot_{int(time.time()*1000)}.png"
            self._page.screenshot(path=str(path))
            return str(path)
        except Exception:
            return ""

    # -- execute -----------------------------------------------------------

    def execute(self, step: PlanStep) -> StepOutcome:
        if step.kind == StepKind.OPEN_SESSION:
            ok = self._ensure_session()
            return StepOutcome(ok=ok, detail="session launched" if ok else f"launch failed: {self._launch_error}")

        if step.kind == StepKind.SEARCH:
            return self._do_search(step.target)

        if step.kind == StepKind.OPEN_RESULT:
            return self._do_open_result()

        if step.kind in (StepKind.OBSERVE, StepKind.SUMMARIZE):
            # No external fetch — just confirm the page is readable.
            obs = self.observe()
            return StepOutcome(ok=bool(obs.visible_text), detail="observed current page")

        return StepOutcome(ok=False, detail=f"unsupported step kind {step.kind.value}")

    def _do_search(self, query: str) -> StepOutcome:
        if self._page is None:
            return StepOutcome(ok=False, detail="no page")
        self._last_query = (query or "").strip()
        try:
            self._page.goto(_SEARCH_URL.format(q=quote_plus(self._last_query)),
                            wait_until="domcontentloaded", timeout=20000)
        except Exception as exc:
            return StepOutcome(ok=False, detail=f"navigation error: {str(exc)[:120]}")
        self._results = self._extract_results()
        self._cursor = 0
        return StepOutcome(ok=bool(self._results), detail=f"{len(self._results)} organic results",
                           data={"results": self._results[:8]})

    @staticmethod
    def _is_engine_host(host: str) -> bool:
        host = (host or "").lower()
        return any(host == e or host.endswith("." + e) for e in _SEARCH_ENGINE_HOSTS)

    def _extract_results(self) -> list[dict[str, str]]:
        if self._page is None:
            return []
        items: list[dict] = []
        for selector in ("a.result__a", "h2 a[href]", "a[href]"):
            try:
                items = self._page.eval_on_selector_all(
                    selector,
                    "els => els.map(e => ({text:(e.innerText||'').trim(), href:e.href||''}))",
                )
            except Exception:
                items = []
            if items and any(
                not self._is_engine_host(urlparse(_normalize_href(str((i or {}).get("href") or ""))).hostname or "")
                for i in items
            ):
                break
        rows: list[dict[str, str]] = []
        seen: set[str] = set()
        for it in items:
            href = _normalize_href(str((it or {}).get("href") or ""))
            text = str((it or {}).get("text") or "").strip()
            if not href.startswith("http"):
                continue
            host = (urlparse(href).hostname or "").lower()
            if self._is_engine_host(host):   # skip the engine's own nav/links
                continue
            if href in seen:
                continue
            seen.add(href)
            rows.append({"title": text[:180] or href, "url": href[:500]})
            if len(rows) >= 8:
                break
        return self._rank(rows)

    def _rank(self, rows: list[dict[str, str]]) -> list[dict[str, str]]:
        """Most-relevant-first: score by query-token overlap in the title."""
        q = _query_tokens(self._last_query)
        if not q:
            return rows

        def score(row: dict[str, str]) -> int:
            return len(q & _query_tokens(row.get("title", "")))

        return sorted(rows, key=score, reverse=True)

    def _do_open_result(self) -> StepOutcome:
        if self._page is None:
            return StepOutcome(ok=False, detail="no page")
        if self._cursor >= len(self._results):
            return StepOutcome(ok=False, detail="no more candidate results")
        target = self._results[self._cursor].get("url", "")
        try:
            self._page.goto(target, wait_until="domcontentloaded", timeout=20000)
            return StepOutcome(ok=True, detail=f"opened {target}", data={"url": target})
        except Exception as exc:
            return StepOutcome(ok=False, detail=f"open error: {str(exc)[:120]}", data={"url": target})

    # -- recovery ----------------------------------------------------------

    def apply_recovery(self, decision: RecoveryDecision, step: PlanStep) -> None:
        if decision.kind == RecoveryKind.RESTART_SESSION:
            self.close()
            self._ensure_session()
        elif decision.kind == RecoveryKind.NEXT_CANDIDATE:
            self._cursor += 1
            self._do_open_result()
        elif decision.kind == RecoveryKind.RETRY_STEP:
            self.execute(step)
        elif decision.kind == RecoveryKind.REOBSERVE:
            try:
                if self._page is not None:
                    self._page.wait_for_timeout(500)
            except Exception:
                pass
        # NONE: nothing to do.
