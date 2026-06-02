"""Autonomous Agent Stack v1 — safe lessons memory (non-sensitive).

Stores ONLY abstract operational lessons to data/autonomous_agent_memory.json:
  - useful_domains / failed_domains (host strings + counts)
  - query rewrites that produced results
  - failure-cause counters
  - provider reliability counters

NEVER stores: page content, cookies, credentials, account info, personal data,
URLs with query strings, or any user-private data. Only bare hostnames + counts
+ short cause labels are persisted.
"""

from __future__ import annotations

import json
import re
import threading
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from core.logger import setup_logger

logger = setup_logger("jarvis.autonomy.memory")

_lock = threading.Lock()
_MAX_ENTRIES = 200
_HOST_RE = re.compile(r"^[a-z0-9.\-]{1,253}$")


def _path() -> Path:
    from config import DATA_DIR

    return Path(DATA_DIR) / "autonomous_agent_memory.json"


def _safe_host(url_or_host: str) -> str:
    """Return a bare hostname only (drops scheme/path/query — no sensitive data)."""
    s = (url_or_host or "").strip().lower()
    if "://" in s or "/" in s:
        s = (urlparse(s if "://" in s else "//" + s, scheme="https").hostname or "")
    s = s.split(":")[0]
    return s if _HOST_RE.match(s) else ""


def _load() -> dict[str, Any]:
    p = _path()
    if not p.is_file():
        return {"useful_domains": {}, "failed_domains": {}, "query_rewrites": [],
                "failure_causes": {}, "provider_reliability": {}}
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        for k in ("useful_domains", "failed_domains", "failure_causes", "provider_reliability"):
            data.setdefault(k, {})
        data.setdefault("query_rewrites", [])
        return data
    except Exception:
        return {"useful_domains": {}, "failed_domains": {}, "query_rewrites": [],
                "failure_causes": {}, "provider_reliability": {}}


def _save(data: dict[str, Any]) -> None:
    try:
        p = _path()
        p.parent.mkdir(parents=True, exist_ok=True)
        # bound growth
        for k in ("useful_domains", "failed_domains"):
            if len(data.get(k, {})) > _MAX_ENTRIES:
                items = sorted(data[k].items(), key=lambda kv: kv[1], reverse=True)[:_MAX_ENTRIES]
                data[k] = dict(items)
        data["query_rewrites"] = data.get("query_rewrites", [])[-50:]
        p.write_text(json.dumps(data, ensure_ascii=True, indent=2), encoding="utf-8")
    except Exception as exc:
        logger.warning("autonomy memory save failed: %s", exc)


def note_useful_domain(url_or_host: str) -> None:
    host = _safe_host(url_or_host)
    if not host:
        return
    with _lock:
        d = _load()
        d["useful_domains"][host] = int(d["useful_domains"].get(host, 0)) + 1
        _save(d)


def note_failed_domain(url_or_host: str, cause: str = "") -> None:
    host = _safe_host(url_or_host)
    with _lock:
        d = _load()
        if host:
            d["failed_domains"][host] = int(d["failed_domains"].get(host, 0)) + 1
        if cause:
            label = re.sub(r"[^a-z0-9_ ]", "", cause.lower())[:40] or "unknown"
            d["failure_causes"][label] = int(d["failure_causes"].get(label, 0)) + 1
        _save(d)


def note_query_rewrite(original: str, rewritten: str) -> None:
    if not rewritten or rewritten == original:
        return
    with _lock:
        d = _load()
        d["query_rewrites"].append({"from": (original or "")[:120], "to": rewritten[:120]})
        _save(d)


def note_provider(name: str, ok: bool) -> None:
    name = re.sub(r"[^a-z0-9_]", "", (name or "unknown").lower())[:30] or "unknown"
    with _lock:
        d = _load()
        rec = d["provider_reliability"].setdefault(name, {"ok": 0, "fail": 0})
        rec["ok" if ok else "fail"] += 1
        _save(d)


def is_known_bad_domain(url_or_host: str, *, threshold: int = 3) -> bool:
    host = _safe_host(url_or_host)
    if not host:
        return False
    with _lock:
        d = _load()
        return int(d["failed_domains"].get(host, 0)) >= threshold and \
            int(d["useful_domains"].get(host, 0)) == 0


def snapshot() -> dict[str, Any]:
    with _lock:
        return _load()


def reset_for_tests() -> None:
    with _lock:
        p = _path()
        try:
            if p.is_file():
                p.unlink()
        except Exception:
            pass
