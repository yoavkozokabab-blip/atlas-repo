"""Persistent browser memory for research loop (Phase 62)."""

from __future__ import annotations

import json
import time

from config import DATA_DIR

_PATH = DATA_DIR / "browser_memory.json"


def _empty() -> dict:
    return {"user_goal": "", "search_queries": [], "visited_pages": [], "page_summaries": [], "facts": []}


def _load() -> dict:
    if not _PATH.is_file():
        return _empty()
    try:
        return json.loads(_PATH.read_text(encoding="utf-8"))
    except Exception:
        return _empty()


def _save(payload: dict) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    _PATH.write_text(json.dumps(payload, indent=2, ensure_ascii=True), encoding="utf-8")


def snapshot() -> dict:
    return _load()


def set_user_goal(goal: str) -> None:
    payload = _load()
    payload["user_goal"] = (goal or "").strip()[:300]
    _save(payload)


def add_search_query(query: str) -> None:
    payload = _load()
    row = {"ts": int(time.time() * 1000), "query": (query or "").strip()[:300]}
    payload.setdefault("search_queries", []).append(row)
    payload["search_queries"] = payload["search_queries"][-100:]
    _save(payload)


def add_visited_page(url: str, title: str, screenshot: str = "") -> None:
    payload = _load()
    row = {
        "ts": int(time.time() * 1000),
        "url": (url or "").strip()[:500],
        "title": (title or "").strip()[:300],
        "screenshot": (screenshot or "").strip()[:500],
    }
    payload.setdefault("visited_pages", []).append(row)
    payload["visited_pages"] = payload["visited_pages"][-150:]
    _save(payload)


def add_page_summary(url: str, summary: str) -> None:
    payload = _load()
    row = {"ts": int(time.time() * 1000), "url": (url or "").strip()[:500], "summary": (summary or "").strip()[:2000]}
    payload.setdefault("page_summaries", []).append(row)
    payload["page_summaries"] = payload["page_summaries"][-120:]
    _save(payload)


def add_fact(fact: str, source_url: str) -> None:
    payload = _load()
    row = {"ts": int(time.time() * 1000), "fact": (fact or "").strip()[:500], "source_url": (source_url or "").strip()[:500]}
    payload.setdefault("facts", []).append(row)
    payload["facts"] = payload["facts"][-300:]
    _save(payload)

