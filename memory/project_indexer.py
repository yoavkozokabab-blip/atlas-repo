"""Index allowlisted project folders into searchable summaries."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from config import (
    PROJECT_INDEX_MAX_FILE_KB,
    PROJECT_INDEX_PATH,
    PROJECT_INDEXING_ENABLED,
    PROJECT_ROOT,
    TRADING_PROJECT_ROOT,
)
from memory.redaction import extract_keywords, redact_text, validate_safe_text

ALLOWED_EXTENSIONS = frozenset(
    {".py", ".md", ".txt", ".json", ".yaml", ".yml", ".csv"}
)

BLOCKED_DIR_NAMES = frozenset(
    {
        "node_modules",
        "venv",
        ".venv",
        "__pycache__",
        ".git",
        ".pytest_cache",
        "dist",
        "build",
        ".mypy_cache",
    }
)

BLOCKED_FILE_NAMES = frozenset({".env", ".env.local", ".env.example"})

MAX_SUMMARY_CHARS = 400
MAX_SNIPPET_CHARS = 200


def _max_bytes() -> int:
    return max(1, PROJECT_INDEX_MAX_FILE_KB) * 1024


def _allowlisted_roots() -> list[tuple[str, Path]]:
    roots: list[tuple[str, Path]] = []
    if PROJECT_ROOT.is_dir():
        roots.append(("local_jarvis", PROJECT_ROOT.resolve()))
    if TRADING_PROJECT_ROOT.is_dir():
        roots.append(("trading_project", TRADING_PROJECT_ROOT.resolve()))
    return roots


def _should_skip_dir(name: str) -> bool:
    return name.lower() in BLOCKED_DIR_NAMES or name.startswith(".")


def _should_index_file(path: Path) -> bool:
    if path.name.lower() in BLOCKED_FILE_NAMES:
        return False
    if path.suffix.lower() not in ALLOWED_EXTENSIONS:
        return False
    if path.name.startswith("."):
        return False
    return True


def _summarize_file(path: Path, text: str) -> str:
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    summary_parts: list[str] = []
    for ln in lines[:8]:
        if ln.startswith('"""') or ln.startswith("'''") or ln.startswith("#"):
            summary_parts.append(ln[:120])
        elif ln.startswith("def ") or ln.startswith("class "):
            summary_parts.append(ln[:120])
        if len(" ".join(summary_parts)) > MAX_SUMMARY_CHARS:
            break
    summary = " | ".join(summary_parts) or (lines[0][:MAX_SUMMARY_CHARS] if lines else path.name)
    return redact_text(summary[:MAX_SUMMARY_CHARS])


def _safe_snippet(text: str) -> str:
    return redact_text(text[:MAX_SNIPPET_CHARS])


def _index_file(project: str, root: Path, file_path: Path) -> dict[str, Any] | None:
    try:
        size = file_path.stat().st_size
        if size > _max_bytes():
            return None
        raw = file_path.read_text(encoding="utf-8", errors="replace")
        try:
            validate_safe_text(raw[:2000])
        except Exception:
            return None
    except OSError:
        return None

    rel = str(file_path.relative_to(root)).replace("\\", "/")
    summary = _summarize_file(file_path, raw)
    keywords = extract_keywords(f"{rel} {summary}")
    mtime = datetime.fromtimestamp(file_path.stat().st_mtime, tz=timezone.utc).isoformat()
    snippet = summary[:MAX_SNIPPET_CHARS] if summary else _safe_snippet(raw[:MAX_SNIPPET_CHARS])
    return {
        "path": rel,
        "summary": summary,
        "keywords": keywords,
        "modified_at": mtime,
        "snippet": snippet,
        "project": project,
    }


def index_projects(*, max_files_per_root: int = 500) -> tuple[int, str]:
    """Scan allowlisted roots. Returns (file_count, message)."""
    if not PROJECT_INDEXING_ENABLED:
        return 0, "Project indexing is disabled (PROJECT_INDEXING_ENABLED=false)."

    projects: dict[str, Any] = {}
    total = 0
    errors = 0

    for project_name, root in _allowlisted_roots():
        files: list[dict[str, Any]] = []
        try:
            for path in root.rglob("*"):
                if len(files) >= max_files_per_root:
                    break
                if not path.is_file():
                    continue
                if any(p in BLOCKED_DIR_NAMES for p in path.parts):
                    continue
                if not _should_index_file(path):
                    continue
                try:
                    row = _index_file(project_name, root, path)
                    if row:
                        files.append(row)
                        total += 1
                except Exception:
                    errors += 1
        except OSError:
            errors += 1
        projects[project_name] = {
            "root": str(root),
            "indexed_at": datetime.now(timezone.utc).isoformat(),
            "files": files,
        }

    payload = {
        "indexed_at": datetime.now(timezone.utc).isoformat(),
        "projects": projects,
    }
    try:
        PROJECT_INDEX_PATH.parent.mkdir(parents=True, exist_ok=True)
        PROJECT_INDEX_PATH.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
    except OSError as exc:
        return total, f"Index built ({total} files) but save failed: {exc}"

    msg = f"Indexed {total} files across {len(projects)} project(s)."
    if errors:
        msg += f" ({errors} skipped/errors)"
    return total, msg


def load_project_index() -> dict[str, Any]:
    if not PROJECT_INDEX_PATH.is_file():
        return {"projects": {}}
    try:
        data = json.loads(PROJECT_INDEX_PATH.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            return data
    except (OSError, json.JSONDecodeError):
        pass
    return {"projects": {}}


def format_project_search_results(hits: list[dict[str, Any]], query: str) -> str:
    if not hits:
        return f"No project knowledge matches for '{query}'."
    lines = [f"Project knowledge search: '{query}'", ""]
    for i, row in enumerate(hits, 1):
        lines.append(f"{i}. [{row.get('project', '?')}] {row.get('path', '')}")
        lines.append(f"   summary: {row.get('summary', '')[:300]}")
        snip = row.get("snippet", "")
        if snip:
            lines.append(f"   snippet: {snip[:200]}")
    lines.append("")
    lines.append("_Summaries/snippets only — no full file dumps._")
    return "\n".join(lines)
