"""Read-only repo search baseline (no Atlas)."""

from __future__ import annotations

import re
import time
from pathlib import Path
from typing import Any, Dict, List, Tuple

from .schema import TaskDef


def _walk_py_files(repo_path: Path) -> List[Path]:
    skip = {".git", "__pycache__", ".venv", "node_modules", "dist", "build"}
    out: List[Path] = []
    for path in repo_path.rglob("*.py"):
        if any(part in skip for part in path.parts):
            continue
        out.append(path)
    return sorted(out)


def _read_excerpt(path: Path, max_lines: int = 40) -> str:
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return ""
    return "\n".join(lines[:max_lines])


def _keywords_for_task(task: TaskDef) -> List[str]:
    prompt = task.prompt.lower()
    mapping = {
        "authentication": ["auth", "login", "session", "middleware", "jwt"],
        "retry": ["retry", "retries", "max_retries", "urllib3"],
        "lifecycle": ["routes", "middleware", "order", "execution", "auth"],
        "break": ["import", "session", "login", "depend"],
        "attributeerror": ["middleware", "headers", "authorization", "request"],
        "graphql": ["graphql", "gql", "schema", "resolver"],
    }
    keys: List[str] = []
    for needle, kws in mapping.items():
        if needle in prompt:
            keys.extend(kws)
    if not keys:
        keys = [w.strip(".,?") for w in prompt.split() if len(w) > 4][:8]
    return list(dict.fromkeys(keys))


def run_baseline(task: TaskDef, repo_path: Path) -> Dict[str, Any]:
    started = time.perf_counter()
    tool_calls: List[Dict[str, Any]] = []
    files_inspected: List[str] = []
    keywords = _keywords_for_task(task)
    hits: List[Tuple[int, str, str]] = []

    for py_file in _walk_py_files(repo_path):
        rel = py_file.relative_to(repo_path).as_posix()
        try:
            text = py_file.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        files_inspected.append(rel)
        lower = text.lower()
        score = sum(1 for kw in keywords if kw in lower)
        if score:
            excerpt = _read_excerpt(py_file)
            hits.append((score, rel, excerpt))
            tool_calls.append({"tool": "read_file", "path": rel, "keyword_score": score})

    hits.sort(key=lambda item: (-item[0], item[1]))
    top = hits[:8]

    if task.category == "negative_control":
        graphql_hits = [h for h in hits if "graphql" in h[1].lower() or "graphql" in h[2].lower()]
        if graphql_hits:
            answer = (
                "Search found possible GraphQL references:\n"
                + "\n".join(f"- {h[1]}" for h in graphql_hits[:5])
            )
        else:
            answer = (
                "No GraphQL API server implementation found. "
                f"Searched {len(files_inspected)} Python files under {repo_path.name} "
                "for graphql/gql/schema/resolver patterns with no matches."
            )
    elif not top:
        answer = (
            f"Baseline search found no strong keyword matches for {keywords!r} "
            f"across {len(files_inspected)} Python files."
        )
    else:
        lines = [
            f"Baseline read-only search (keywords: {', '.join(keywords)}). Top matches:",
        ]
        for score, rel, excerpt in top:
            lines.append(f"\n### {rel} (score={score})\n```python\n{excerpt}\n```")
        answer = "\n".join(lines)

    latency = time.perf_counter() - started
    return {
        "ok": True,
        "response_text": answer,
        "tool_calls": tool_calls,
        "atlas_tool_calls": [],
        "files_inspected": files_inspected[:200],
        "latency_seconds": latency,
        "error": "",
    }
