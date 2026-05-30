"""Decision memory: capture and list builder decisions.

A decision is the smallest unit of durable project memory. Each record stores
the raw text, an inferred topic, a UTC timestamp, and the current git commit
(when the project is a repo) so the decision is anchored to a code state.
"""

from __future__ import annotations

import datetime as _dt
import hashlib
from typing import Any, Dict, List

from . import gitutil, store, topics


def _now_iso() -> str:
    return _dt.datetime.now(_dt.timezone.utc).replace(microsecond=0).isoformat()


def _make_id(text: str, timestamp: str) -> str:
    digest = hashlib.sha1(f"{timestamp}|{text}".encode("utf-8")).hexdigest()
    return digest[:12]


def remember(project_root: str, text: str) -> Dict[str, Any]:
    text = text.strip()
    if not text:
        raise ValueError("Decision text must not be empty.")
    timestamp = _now_iso()
    commit = None
    branch = None
    if gitutil.is_repo(project_root):
        commit = gitutil.current_commit(project_root)
        branch = gitutil.current_branch(project_root)
    record = {
        "id": _make_id(text, timestamp),
        "timestamp": timestamp,
        "text": text,
        "topic": topics.infer_topic(text),
        "git_commit": commit,
        "git_branch": branch,
    }
    store.append_decision(project_root, record)
    return record


def list_decisions(project_root: str) -> List[Dict[str, Any]]:
    return store.load_decisions(project_root)
