"""Browser runtime facade with truthful visible/headless/mock reporting."""

from __future__ import annotations

import json
import threading
import time
from dataclasses import dataclass, field
from urllib.parse import quote_plus

from config import DATA_DIR
from browser.url_parser import normalize_url

_MOCK_BANNER = "MOCK MODE | NO REAL EXTERNAL ACCESS | SIMULATED OUTPUT ONLY"
_REAL_VISIBLE = "REAL VISIBLE BROWSER"
_REAL_HEADLESS = "REAL HEADLESS BROWSER"
_REPLAY_LOG = DATA_DIR / "browser_action_replay.jsonl"
_SCREENSHOT_DIR = DATA_DIR / "browser_screenshots"


@dataclass
class BrowserRuntimeState:
    provider: str = "mock"
    session_active: bool = False
    headed_mode: bool = False
    browser_visible: bool = False
    browser_process_alive: bool = False
    active_tab_title: str = ""
    active_tab_index: int = -1
    tab_count: int = 0
    current_url: str = ""
    last_query: str = ""
    last_page_summary: str = ""
    last_dom_excerpt: str = ""
    last_screenshot_path: str = ""
    last_action_success: bool = False
    last_exception: str = ""
    comparisons: list[str] = field(default_factory=list)
    last_updated_ts: float = field(default_factory=time.time)

    def format_debug(self) -> str:
        mode_line = _MOCK_BANNER
        if self.provider == "playwright":
            mode_line = _REAL_VISIBLE if self.browser_visible else _REAL_HEADLESS
        lines = [
            "Browser debug (Phase 60):",
            f"  {mode_line}",
            f"  provider: {self.provider}",
            f"  session_active: {self.session_active}",
            f"  browser_visible: {self.browser_visible}",
            f"  browser_process_alive: {self.browser_process_alive}",
            f"  active_tab_index: {self.active_tab_index}",
            f"  active_tab_title: {self.active_tab_title or 'n/a'}",
            f"  tab_count: {self.tab_count}",
            f"  current_url: {self.current_url or 'n/a'}",
            f"  last_query: {self.last_query or 'n/a'}",
            f"  last_page_summary: {(self.last_page_summary or 'n/a')[:140]}",
            f"  last_dom_excerpt: {(self.last_dom_excerpt or 'n/a')[:140]}",
            f"  last_screenshot_path: {self.last_screenshot_path or 'n/a'}",
            f"  last_action_success: {self.last_action_success}",
            f"  last_exception: {self.last_exception or 'none'}",
            f"  comparisons: {len(self.comparisons)}",
        ]
        for item in self.comparisons[-3:]:
            lines.append(f"  - {item[:140]}")
        return "\n".join(lines)


_state = BrowserRuntimeState()
_lock = threading.RLock()
_playwright = None
_browser = None
_context = None
_active_page = None
_last_search_results: list[dict[str, str]] = []


def _now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _append_replay(action: str, payload: dict[str, object]) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    row = {"ts": _now_iso(), "action": action, "payload": payload}
    with _REPLAY_LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=True) + "\n")


def _ensure_playwright_session() -> bool:
    global _playwright, _browser, _context, _active_page
    if _context is not None and _browser is not None:
        _refresh_process_health()
        return True
    try:
        from playwright.sync_api import sync_playwright

        _playwright = sync_playwright().start()
        _browser = _playwright.chromium.launch(headless=False)
        _context = _browser.new_context()
        _active_page = _context.new_page()
        _state.provider = "playwright"
        _state.session_active = True
        _state.headed_mode = True
        _state.last_exception = ""
        _state.last_action_success = True
        _refresh_process_health()
        _append_replay("session_start", {"provider": "playwright"})
        return True
    except Exception as exc:
        _state.provider = "mock"
        _state.session_active = False
        _state.browser_visible = False
        _state.browser_process_alive = False
        _state.last_exception = str(exc)[:300]
        _state.last_action_success = False
        _append_replay("session_start_failed", {"error": str(exc)[:300]})
        return False


def _refresh_process_health() -> None:
    _state.browser_process_alive = bool(_browser is not None and getattr(_browser, "is_connected", lambda: False)())
    _state.browser_visible = bool(_state.headed_mode and _state.browser_process_alive)


def _sync_state_from_page() -> None:
    global _active_page
    if _context is None:
        _state.tab_count = 0
        _state.active_tab_index = -1
        _state.active_tab_title = ""
        return
    pages = list(_context.pages)
    _state.tab_count = len(pages)
    if _active_page in pages:
        _state.active_tab_index = pages.index(_active_page)
    elif pages:
        _active_page = pages[-1]
        _state.active_tab_index = len(pages) - 1
    else:
        _state.active_tab_index = -1
        return
    try:
        _state.current_url = _active_page.url or _state.current_url
    except Exception:
        pass
    try:
        _state.active_tab_title = (_active_page.title() or "")[:180]
    except Exception:
        pass
    _refresh_process_health()


def _safe_dom_excerpt(max_chars: int = 3500) -> str:
    if _active_page is None:
        return ""
    try:
        body = _active_page.inner_text("body")
        return (body or "").strip()[:max_chars]
    except Exception:
        return ""


def _capture_screenshot() -> str:
    if _active_page is None:
        return ""
    _SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
    path = _SCREENSHOT_DIR / f"shot_{int(time.time()*1000)}.png"
    try:
        _active_page.screenshot(path=str(path), full_page=True)
        return str(path)
    except Exception:
        return ""


def _extract_page_understanding() -> dict[str, object]:
    if _active_page is None:
        return {
            "title": _state.active_tab_title or "",
            "url": _state.current_url or "",
            "headings": [],
            "links": [],
            "visible_text": "",
            "forms_buttons": [],
            "screenshot_path": _state.last_screenshot_path or "",
        }
    headings: list[str] = []
    links: list[dict[str, str]] = []
    forms_buttons: list[str] = []
    visible_text = ""
    try:
        headings = [x.strip() for x in _active_page.eval_on_selector_all("h1,h2,h3", "els => els.map(e => (e.innerText||'').trim())") if x.strip()][:20]
    except Exception:
        headings = []
    try:
        link_rows = _active_page.eval_on_selector_all(
            "a[href]",
            "els => els.map(e => ({text:(e.innerText||'').trim(), href:e.href||''}))",
        )
        for row in link_rows[:80]:
            href = str((row or {}).get("href") or "").strip()
            text = str((row or {}).get("text") or "").strip()
            if href:
                links.append({"text": text[:180], "href": href[:500]})
    except Exception:
        links = []
    try:
        forms_buttons = [x.strip() for x in _active_page.eval_on_selector_all("form button,button,input[type='submit']", "els => els.map(e => (e.innerText||e.value||'').trim())") if x.strip()][:30]
    except Exception:
        forms_buttons = []
    try:
        visible_text = (_active_page.inner_text("body") or "").strip()[:5000]
    except Exception:
        visible_text = ""
    shot = _capture_screenshot()
    return {
        "title": _state.active_tab_title or "",
        "url": _state.current_url or "",
        "headings": headings,
        "links": links,
        "visible_text": visible_text,
        "forms_buttons": forms_buttons,
        "screenshot_path": shot,
    }


def _needs_approval(action: str, target: str = "") -> bool:
    tokens = ("login", "submit", "buy", "download", "delete", "send", "credential", "password")
    text = f"{action} {target}".lower()
    return any(tok in text for tok in tokens)


def _approval_message(action: str, target: str = "") -> str:
    return (
        "Approval required before risky browser action.\n"
        f"  action: {action}\n"
        f"  target: {target or 'n/a'}\n"
        "  reason: login/submit/buy/download/delete/send/credentials gate triggered."
    )


def get_browser_runtime_state() -> BrowserRuntimeState:
    with _lock:
        return BrowserRuntimeState(**_state.__dict__)


def _truth_success() -> bool:
    return bool(_state.browser_process_alive and _active_page is not None and _context is not None)


def _mode_banner() -> str:
    if _state.provider != "playwright":
        return _MOCK_BANNER
    return _REAL_VISIBLE if _state.browser_visible else _REAL_HEADLESS


def open_browser(url: str = "about:blank") -> str:
    with _lock:
        ok = _ensure_playwright_session()
        if not ok:
            _state.last_updated_ts = time.time()
            _state.last_action_success = False
            return f"Browser open requested.\n{_MOCK_BANNER}"
        global _active_page
        if _active_page is None and _context is not None:
            _active_page = _context.new_page()
        target = (url or "about:blank").strip()
        try:
            _active_page.goto(target, wait_until="domcontentloaded", timeout=15000)
            _state.last_exception = ""
        except Exception as exc:
            _state.last_exception = str(exc)[:300]
        _sync_state_from_page()
        _state.last_dom_excerpt = _safe_dom_excerpt()
        _state.last_screenshot_path = _capture_screenshot()
        _state.last_updated_ts = time.time()
        _state.last_action_success = _truth_success()
        _append_replay("open_browser", {"url": target, "tab_count": _state.tab_count})
        if not _state.last_action_success:
            return (
                "Browser launch failed truth check.\n"
                f"  mode: {_mode_banner()}\n"
                f"  browser_process_alive: {_state.browser_process_alive}\n"
                f"  page_object_exists: {bool(_active_page)}\n"
                f"  last_exception: {_state.last_exception or 'none'}"
            )
        return (
            f"{_mode_banner()}\n"
            f"Browser session active.\n"
            f"  browser_visible: {_state.browser_visible}\n"
            f"  url: {_state.current_url or target}\n"
            f"  tab: {_state.active_tab_index + 1}/{_state.tab_count}"
        )


def navigate_to_url(url: str) -> str:
    target = normalize_url(url)
    if not target:
        return "Navigation failed: empty URL."
    if not (target.startswith("https://") or target.startswith("http://")):
        return f"Navigation failed: URL must start with http:// or https:// (got {target!r})."
    body = open_browser(target)
    with _lock:
        # Truth check: process alive + page exists + non-empty title + host match.
        if not _truth_success():
            _state.last_action_success = False
            return body
        host_ok = False
        try:
            from urllib.parse import urlparse

            target_host = (urlparse(target).hostname or "").lower()
            got_host = (urlparse(_state.current_url or "").hostname or "").lower()
            host_ok = bool(target_host and got_host and (target_host == got_host or got_host.endswith("." + target_host)))
        except Exception:
            host_ok = False
        title_ok = bool((_state.active_tab_title or "").strip())
        if not host_ok or not title_ok:
            _state.last_action_success = False
            return (
                "Navigation truth check failed.\n"
                f"  mode: {_mode_banner()}\n"
                f"  expected_url: {target}\n"
                f"  active_url: {_state.current_url or 'n/a'}\n"
                f"  active_title: {_state.active_tab_title or 'n/a'}\n"
                f"  browser_process_alive: {_state.browser_process_alive}"
            )
        _state.last_action_success = True
    return body


def search_web(query: str) -> str:
    with _lock:
        q = (query or "").strip()
        _state.last_query = q
        ok = _ensure_playwright_session()
        if not ok:
            _state.current_url = f"https://www.google.com/search?q={q.replace(' ', '+')}" if q else _state.current_url
            _state.last_updated_ts = time.time()
            _state.last_action_success = False
            return (
                f"Search results (mock):\n  {_MOCK_BANNER}\n"
                f"  query: {q or 'n/a'}\n"
                "  top_result_1: Official source appears first.\n"
                "  top_result_2: News analysis with contrasting sentiment.\n"
                "  top_result_3: Community discussion (lower reliability)."
            )
        global _active_page
        if _active_page is None and _context is not None:
            _active_page = _context.new_page()
        url = f"https://duckduckgo.com/?q={quote_plus(q)}"
        _active_page.goto(url, wait_until="domcontentloaded", timeout=15000)
        _sync_state_from_page()
        _state.last_dom_excerpt = _safe_dom_excerpt()
        _state.last_screenshot_path = _capture_screenshot()
        _state.last_updated_ts = time.time()
        _state.last_action_success = _truth_success()
        _append_replay("search_web", {"query": q, "url": _state.current_url})
        global _last_search_results
        _last_search_results = _extract_search_results()
        from browser.memory import add_search_query, add_visited_page
        add_search_query(q)
        add_visited_page(_state.current_url, _state.active_tab_title, _state.last_screenshot_path)
        from memory.store import get_personal_memory

        get_personal_memory().remember(
            f"browser_search: query={q} url={_state.current_url}",
            category="session",
            tags=["browser", "search"],
            source="browser_runtime",
            importance=0.4,
            confidence=0.9,
            ttl_seconds=3600,
        )
        return (
            f"Search results ({_mode_banner()}):\n"
            f"  query: {q or 'n/a'}\n"
            f"  active_url: {_state.current_url}\n"
            f"  dom_excerpt: {(_state.last_dom_excerpt or 'n/a')[:220]}\n"
            f"  extracted_results: {len(_last_search_results)}"
        )


def _extract_search_results() -> list[dict[str, str]]:
    if _active_page is None:
        return []
    rows: list[dict[str, str]] = []
    try:
        items = _active_page.eval_on_selector_all(
            "a[href]",
            "els => els.map(e => ({text:(e.innerText||'').trim(), href:e.href||''}))",
        )
        for item in items:
            href = str((item or {}).get("href") or "").strip()
            text = str((item or {}).get("text") or "").strip()
            if not href.startswith("http"):
                continue
            if "duckduckgo.com" in href and ("y.js" in href or "/?" in href):
                continue
            rows.append({"title": text[:180] or href, "url": href[:500]})
            if len(rows) >= 8:
                break
    except Exception:
        return []
    return rows


def summarize_current_page() -> str:
    with _lock:
        ok = _ensure_playwright_session()
        if not ok:
            url = _state.current_url or "current tab"
            _state.last_page_summary = (
                f"{_MOCK_BANNER}\nSummary for {url}: headline context is clear, but verify publication date and source credibility."
            )
            _state.last_updated_ts = time.time()
            _state.last_action_success = False
            return _state.last_page_summary
        _sync_state_from_page()
        excerpt = _safe_dom_excerpt()
        _state.last_dom_excerpt = excerpt
        _state.last_screenshot_path = _capture_screenshot()
        url = _state.current_url or "current tab"
        _state.last_page_summary = (
            f"Summary for {url}\n"
            f"  title: {_state.active_tab_title or 'n/a'}\n"
            f"  key_points: {(excerpt or 'n/a')[:420]}"
        )
        _state.last_updated_ts = time.time()
        _state.last_action_success = _truth_success()
        _append_replay("summarize_page", {"url": url})
        from browser.memory import add_page_summary, add_visited_page
        add_page_summary(url, _state.last_page_summary)
        add_visited_page(url, _state.active_tab_title, _state.last_screenshot_path)
        return f"{_mode_banner()}\n{_state.last_page_summary}"


def compare_latest_results() -> str:
    with _lock:
        if _context is None or len(_context.pages) < 2:
            comparison = (
                f"Comparison (mock): {_MOCK_BANNER}\nNeed at least two tabs/pages for real comparison."
            )
            _state.comparisons.append(comparison)
            _state.last_updated_ts = time.time()
            _state.last_action_success = False
            return comparison
        pages = list(_context.pages)[-2:]
        rows: list[str] = []
        for idx, page in enumerate(pages, 1):
            try:
                title = (page.title() or "")[:120]
            except Exception:
                title = "n/a"
            try:
                url = page.url
            except Exception:
                url = "n/a"
            rows.append(f"  page_{idx}: title={title} url={url}")
        comparison = "Comparison (real browser session):\n" + "\n".join(rows)
        _state.comparisons.append(comparison)
        _state.last_updated_ts = time.time()
        _state.last_action_success = _truth_success()
        _append_replay("compare_pages", {"count": len(pages)})
        return f"{_mode_banner()}\n{comparison}"


def active_tab_status() -> str:
    with _lock:
        _ensure_playwright_session()
        _sync_state_from_page()
        if _state.tab_count <= 0:
            return "No active tab."
        return (
            "Active tab:\n"
            f"  index: {_state.active_tab_index + 1}/{_state.tab_count}\n"
            f"  title: {_state.active_tab_title or 'n/a'}\n"
            f"  url: {_state.current_url or 'n/a'}"
        )


def test_real_browser() -> tuple[bool, str]:
    with _lock:
        out = navigate_to_url("https://example.com")
        _append_replay("test_real_browser_start", {"target": "https://example.com"})
        if _state.provider != "playwright":
            return False, f"{_MOCK_BANNER}\n{out}"
        if not _state.browser_visible:
            return False, (
                f"{_REAL_HEADLESS}\n"
                "test real browser failed: window not visible.\n"
                f"  browser_process_alive: {_state.browser_process_alive}\n"
                f"  last_exception: {_state.last_exception or 'none'}"
            )
        _sync_state_from_page()
        shot = _capture_screenshot()
        _state.last_screenshot_path = shot
        _state.last_action_success = _truth_success()
        ok = bool(_state.last_action_success and _state.browser_visible and _state.current_url)
        msg = (
            f"{_REAL_VISIBLE}\n"
            f"test real browser {'passed' if ok else 'failed'}\n"
            f"  title: {_state.active_tab_title or 'n/a'}\n"
            f"  url: {_state.current_url or 'n/a'}\n"
            f"  screenshot: {shot or 'n/a'}"
        )
        _append_replay("test_real_browser_done", {"ok": ok, "url": _state.current_url, "screenshot": shot})
        return ok, msg


def find_information_about(query: str) -> str:
    return search_web(query)


def open_best_result() -> str:
    with _lock:
        if not _last_search_results:
            _state.last_action_success = False
            return "No recent search results found. Run: find information about <query>"
        best = _last_search_results[0]
        target = best.get("url") or ""
        if _needs_approval("open_best_result", target):
            _state.last_action_success = False
            return _approval_message("open_best_result", target)
    return navigate_to_url(target)


def summarize_top_results() -> str:
    with _lock:
        if not _last_search_results:
            _state.last_action_success = False
            return "No top results available yet. Run: find information about <query>"
        lines = [f"Top results ({_mode_banner()}):"]
        for i, row in enumerate(_last_search_results[:5], 1):
            lines.append(f"  {i}. {row.get('title') or 'n/a'}")
            lines.append(f"     {row.get('url') or 'n/a'}")
        _state.last_action_success = True
        return "\n".join(lines)


def compare_search_results() -> str:
    with _lock:
        if len(_last_search_results) < 2:
            _state.last_action_success = False
            return "Need at least two search results to compare."
        r1, r2 = _last_search_results[0], _last_search_results[1]
        _state.last_action_success = True
        return (
            f"Search result comparison ({_mode_banner()}):\n"
            f"  result_1: {r1.get('title')}\n"
            f"    url: {r1.get('url')}\n"
            f"  result_2: {r2.get('title')}\n"
            f"    url: {r2.get('url')}\n"
            "  note: prefer official sources and dated reporting."
        )


def extract_key_facts_from_page() -> str:
    with _lock:
        ok = _ensure_playwright_session()
        if not ok:
            _state.last_action_success = False
            return f"{_MOCK_BANNER}\nCannot extract real facts without real browser session."
        _sync_state_from_page()
        model = _extract_page_understanding()
        text = str(model.get("visible_text") or "")
        facts = [ln.strip() for ln in text.splitlines() if len(ln.strip()) > 40][:5]
        if not facts:
            facts = [text[:220]] if text else []
        from browser.memory import add_fact, add_visited_page
        for fact in facts:
            add_fact(fact, _state.current_url)
        add_visited_page(_state.current_url, _state.active_tab_title, str(model.get("screenshot_path") or ""))
        _state.last_action_success = True
        lines = [
            f"Key facts ({_mode_banner()}):",
            f"  title: {model.get('title') or 'n/a'}",
            f"  url: {model.get('url') or 'n/a'}",
            "  facts:",
            *[f"    - {f[:220]}" for f in facts[:5]],
            f"  screenshot_path: {model.get('screenshot_path') or 'n/a'}",
        ]
        return "\n".join(lines)


def page_understanding() -> dict[str, object]:
    with _lock:
        _ensure_playwright_session()
        _sync_state_from_page()
        model = _extract_page_understanding()
        _state.last_screenshot_path = str(model.get("screenshot_path") or _state.last_screenshot_path)
        return model


def browser_task_plan(goal: str = "") -> str:
    with _lock:
        from browser.memory import set_user_goal
        from browser.task_planner import plan_browser_task

        if goal.strip():
            set_user_goal(goal)
        page = _state.current_url or "about:blank"
        plan = plan_browser_task(goal=goal.strip(), current_page=page, has_search_results=bool(_last_search_results))
        return plan.format()


def save_browser_research_report() -> str:
    with _lock:
        from browser.memory import snapshot

        mem = snapshot()
        model = page_understanding()
        reports_dir = DATA_DIR / "reports"
        reports_dir.mkdir(parents=True, exist_ok=True)
        path = reports_dir / f"browser_research_{int(time.time())}.md"
        lines = [
            "# Browser Research Report",
            "",
            f"- mode: {_mode_banner()}",
            f"- current_title: {model.get('title') or 'n/a'}",
            f"- current_url: {model.get('url') or 'n/a'}",
            f"- screenshot: {model.get('screenshot_path') or 'n/a'}",
            "",
            "## User Goal",
            mem.get("user_goal") or "n/a",
            "",
            "## Recent Search Queries",
            *[f"- {row.get('query')}" for row in mem.get("search_queries", [])[-10:]],
            "",
            "## Visited Pages",
            *[f"- {row.get('title') or 'n/a'} | {row.get('url') or 'n/a'}" for row in mem.get("visited_pages", [])[-10:]],
            "",
            "## Page Summaries",
            *[f"- {row.get('summary') or ''}" for row in mem.get("page_summaries", [])[-5:]],
            "",
            "## Facts",
            *[f"- {row.get('fact') or ''}" for row in mem.get("facts", [])[-10:]],
        ]
        path.write_text("\n".join(lines), encoding="utf-8")
        _state.last_action_success = True
        _append_replay("save_browser_research_report", {"path": str(path)})
        return f"Saved browser research report: {path}"


def recover_browser_session() -> tuple[bool, str]:
    """Tear down and restart Playwright session after crash/disconnect."""
    global _playwright, _browser, _context, _active_page
    with _lock:
        try:
            if _context is not None:
                _context.close()
        except Exception:
            pass
        try:
            if _browser is not None:
                _browser.close()
        except Exception:
            pass
        try:
            if _playwright is not None:
                _playwright.stop()
        except Exception:
            pass
        _playwright = None
        _browser = None
        _context = None
        _active_page = None
        _state.session_active = False
        _state.browser_process_alive = False
        _state.browser_visible = False
        _append_replay("recover_browser_session", {"phase": "reset"})
        ok = _ensure_playwright_session()
        _state.last_action_success = ok
        if ok:
            return True, f"{_mode_banner()}\nBrowser session recovered."
        return False, f"Browser recovery failed: {_state.last_exception or 'unknown'}"


def recover_navigation(url: str) -> tuple[bool, str]:
    """Retry navigation with session recovery on failure."""
    target = normalize_url(url) or "https://example.com"
    body = navigate_to_url(target)
    if _state.last_action_success:
        return True, body[:200]
    ok, msg = recover_browser_session()
    if not ok:
        return False, msg
    body2 = navigate_to_url(target)
    return _state.last_action_success, body2[:200]

