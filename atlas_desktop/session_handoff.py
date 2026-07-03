"""Minimal Atlas session handoff memory.

This does not create a task manager. It only renders explicit session events into
managed SESSION.md / CHECKPOINT.md blocks so an agent can resume without guessing.
"""
from __future__ import annotations

import hashlib
import os
import time
from typing import Any, Dict, Iterable, List

from . import agent_files as af


SESSION_FILENAME = "SESSION.md"
CHECKPOINT_FILENAME = "CHECKPOINT.md"
SESSION_KIND = "session"
CHECKPOINT_KIND = "checkpoint"

_LIST_FIELDS = (
    "completed_work",
    "changed_files",
    "commands_run",
    "tests_run",
    "failures",
    "blockers",
    "next_actions",
    "do_not_repeat",
)


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _clean_text(value: Any) -> str:
    return str(value or "").strip()


def _clean_list(values: Any) -> List[str]:
    if values is None:
        return []
    if isinstance(values, str):
        values = [values]
    if not isinstance(values, Iterable):
        values = [str(values)]
    out: List[str] = []
    seen: set = set()
    for raw in values:
        item = _clean_text(raw)
        if item and item not in seen:
            seen.add(item)
            out.append(item)
    return out[:25]


def _has_active_session(events: Dict[str, Any]) -> bool:
    if _clean_text(events.get("current_task")):
        return True
    return any(_clean_list(events.get(field)) for field in _LIST_FIELDS)


def build_session_memory(repository_memory: Dict[str, Any], events: Dict[str, Any] | None = None) -> Dict[str, Any]:
    """Build a handoff summary from explicit session events only."""
    repo_mem = repository_memory or {}
    events = events or {}
    freshness = str(repo_mem.get("freshness_status") or "unknown")
    session = {
        "kind": "ATLAS_SESSION_HANDOFF v1",
        "timestamp": _clean_text(events.get("timestamp")) or _now(),
        "active": _has_active_session(events),
        "current_task": _clean_text(events.get("current_task")),
        "completed_work": _clean_list(events.get("completed_work")),
        "changed_files": _clean_list(events.get("changed_files")),
        "commands_run": _clean_list(events.get("commands_run")),
        "tests_run": _clean_list(events.get("tests_run")),
        "failures": _clean_list(events.get("failures")),
        "blockers": _clean_list(events.get("blockers")),
        "next_actions": _clean_list(events.get("next_actions")),
        "do_not_repeat": _clean_list(events.get("do_not_repeat")),
        "repository_memory": {
            "version": repo_mem.get("version", "unknown"),
            "repo_name": repo_mem.get("repo_name", "repository"),
            "scan_signature": repo_mem.get("scan_signature", ""),
            "memory_hash": repo_mem.get("memory_hash", ""),
            "freshness_status": freshness,
            "fresh": freshness == "fresh",
        },
    }
    core = repr(sorted(session.items())).encode("utf-8", errors="ignore")
    session["session_hash"] = hashlib.sha256(core).hexdigest()[:12]
    return session


def _bullet_section(out: List[str], title: str, values: List[str]) -> None:
    if not values:
        return
    out.append(f"\n## {title}")
    out.extend(f"- {v}" for v in values)


def generate_session_md(session: Dict[str, Any]) -> str:
    repo = session.get("repository_memory") or {}
    out: List[str] = [
        "# SESSION.md - Atlas handoff summary",
        "",
        "This is an Atlas-generated handoff summary from explicit session events.",
        "Do not treat missing items as completed work.",
        f"Timestamp: {session.get('timestamp', '')}",
        f"Repository memory: {repo.get('version', 'unknown')} / scan `{repo.get('scan_signature', '') or 'unknown'}`",
    ]
    freshness = repo.get("freshness_status", "unknown")
    if repo.get("fresh"):
        out.append("Repository memory freshness: fresh.")
    else:
        out.append(f"Repository memory freshness: {freshness}. Atlas does not claim this handoff is current until repository memory is refreshed.")

    if not session.get("active"):
        out.append("\n## Current task")
        out.append("No active session events were provided. Do not infer completed work, changed files, tests, or blockers.")
        return "\n".join(out).strip()

    out.append("\n## Current task")
    out.append(session.get("current_task") or "UNKNOWN")
    _bullet_section(out, "Completed work", session.get("completed_work") or [])
    _bullet_section(out, "Changed files", session.get("changed_files") or [])
    _bullet_section(out, "Commands run", session.get("commands_run") or [])
    _bullet_section(out, "Tests run", session.get("tests_run") or [])
    _bullet_section(out, "Failures", session.get("failures") or [])
    _bullet_section(out, "Blockers", session.get("blockers") or [])
    _bullet_section(out, "Next actions", session.get("next_actions") or [])
    _bullet_section(out, "Do not repeat", session.get("do_not_repeat") or [])
    return "\n".join(out).strip()


def generate_checkpoint_md(session: Dict[str, Any]) -> str:
    repo = session.get("repository_memory") or {}
    out: List[str] = [
        "# CHECKPOINT.md - Atlas resume checkpoint",
        "",
        "This checkpoint is generated from explicit Atlas session events.",
        f"Timestamp: {session.get('timestamp', '')}",
        f"Repository memory freshness: {repo.get('freshness_status', 'unknown')}.",
    ]
    if not repo.get("fresh"):
        out.append("Atlas does not claim freshness until repository memory is refreshed.")

    if not session.get("active"):
        out.append("\nNo active session events were provided.")
        return "\n".join(out).strip()

    out.append(f"\nCurrent task: {session.get('current_task') or 'UNKNOWN'}")
    _bullet_section(out, "Next actions", session.get("next_actions") or [])
    _bullet_section(out, "Blockers", session.get("blockers") or [])
    _bullet_section(out, "Tests run", session.get("tests_run") or [])
    _bullet_section(out, "Changed files", session.get("changed_files") or [])
    _bullet_section(out, "Do not repeat", session.get("do_not_repeat") or [])
    return "\n".join(out).strip()


def _norm(text: str) -> str:
    return "\n".join(line.rstrip() for line in (text or "").splitlines()).strip()


class AtlasSessionMemoryGenerator:
    """Write SESSION.md / CHECKPOINT.md managed blocks without touching human text."""

    def __init__(self, session_memory: Dict[str, Any]):
        self.session_memory = session_memory or {}

    def body(self, kind: str = SESSION_KIND) -> str:
        if kind == SESSION_KIND:
            return generate_session_md(self.session_memory)
        if kind == CHECKPOINT_KIND:
            return generate_checkpoint_md(self.session_memory)
        raise ValueError(f"unknown session memory kind: {kind}")

    def expected_block(self, kind: str = SESSION_KIND) -> str:
        return af.wrap_block(self.body(kind))

    def write(self, repo_path: str, kind: str = SESSION_KIND) -> Dict[str, Any]:
        filename = SESSION_FILENAME if kind == SESSION_KIND else CHECKPOINT_FILENAME
        path = os.path.join(repo_path, filename)
        body = self.body(kind)
        existing = ""
        if os.path.isfile(path):
            try:
                with open(path, encoding="utf-8") as fh:
                    existing = fh.read()
            except OSError:
                existing = ""
        updated = af.apply_managed_block(existing, body)
        action = "unchanged"
        if _norm(updated) != _norm(existing):
            tmp = path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as fh:
                fh.write(updated)
            os.replace(tmp, path)
            action = "created" if not existing else "updated"
        return {
            "path": path,
            "kind": kind,
            "action": action,
            "signature": af.block_signature(self.expected_block(kind)),
            "tokens": af.estimate_tokens(body),
        }

    def write_all(self, repo_path: str, *, checkpoint: bool = True) -> List[Dict[str, Any]]:
        results = [self.write(repo_path, SESSION_KIND)]
        if checkpoint:
            results.append(self.write(repo_path, CHECKPOINT_KIND))
        return results
