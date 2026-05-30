"""Repository indexer.

Walks an arbitrary project tree (read-only), classifies files, extracts a
bounded set of text "chunks" for retrieval, and records git metadata. The
result is a plain dict serialised to ``.jarvis_builder/index.json``.
"""

from __future__ import annotations

import datetime as _dt
import os
import re
from typing import Any, Dict, List, Optional

from . import MEMORY_DIRNAME, __version__
from . import gitutil
from . import python_analysis

# ---------------------------------------------------------------------------
# Tunables (kept conservative so index.json stays small on large repos)
# ---------------------------------------------------------------------------
MAX_FILE_BYTES_FOR_CONTENT = 400_000
MAX_CHUNKS_PER_FILE = 25
MAX_TOTAL_CHUNKS = 6000
CHUNK_CHAR_LIMIT = 600
LARGE_FILE_LINES = 600
GIT_LOG_LIMIT = 400

CODE_EXTS = {
    ".py", ".js", ".jsx", ".ts", ".tsx", ".go", ".rs", ".java", ".rb",
    ".c", ".cc", ".cpp", ".h", ".hpp", ".cs", ".kt", ".swift", ".scala",
    ".php", ".sh", ".ps1", ".lua", ".m", ".mm",
}
DOC_EXTS = {".md", ".rst", ".txt", ".adoc"}

SKIP_DIRS = {
    ".git", MEMORY_DIRNAME, "__pycache__", "node_modules", ".venv", "venv",
    "env", ".env", "dist", "build", ".pytest_cache", ".mypy_cache",
    ".idea", ".vscode", "site-packages", ".tox", "target", "vendor",
    ".next", ".cache", "coverage", "htmlcov", ".gradle",
}

_SIG_RE = re.compile(
    r"^\s*(?:export\s+)?(?:public\s+|private\s+|protected\s+|static\s+)*"
    r"(?:async\s+)?(?:def|class|function|func|fn|interface|struct|trait|impl|type)\b.*"
)
_TODO_RE = re.compile(r"\b(TODO|FIXME|HACK|XXX)\b")
_HEADING_RE = re.compile(r"^\s{0,3}#{1,6}\s+\S")


def _now_iso() -> str:
    return _dt.datetime.now(_dt.timezone.utc).replace(microsecond=0).isoformat()


def _categorize(rel_path: str, ext: str) -> Optional[str]:
    name = os.path.basename(rel_path)
    lower = name.lower()
    parts = rel_path.replace("\\", "/").lower().split("/")

    if lower.startswith("readme"):
        return "readme"

    is_test = (
        lower.startswith("test_")
        or lower.endswith("_test.py")
        or lower.endswith(".test.js")
        or lower.endswith(".test.ts")
        or lower.endswith(".spec.js")
        or lower.endswith(".spec.ts")
        or any(p in ("test", "tests", "__tests__", "spec") for p in parts[:-1])
    )
    if is_test and ext in CODE_EXTS:
        return "test"
    if ext in CODE_EXTS:
        return "src"
    if ext in DOC_EXTS or "docs" in parts[:-1] or "doc" in parts[:-1]:
        return "docs"
    return None


def _read_text(path: str) -> Optional[str]:
    try:
        if os.path.getsize(path) > MAX_FILE_BYTES_FOR_CONTENT:
            return None
        with open(path, "r", encoding="utf-8-sig", errors="ignore") as fh:
            return fh.read()
    except OSError:
        return None


def _detect_project_type(project_root: str, files: List[Dict[str, Any]]) -> Dict[str, Any]:
    extensions = {entry.get("ext", "") for entry in files}
    detected: List[str] = []
    signals: List[str] = []
    if ".py" in extensions or any(
        os.path.exists(os.path.join(project_root, name))
        for name in ("pyproject.toml", "requirements.txt", "setup.py", "setup.cfg")
    ):
        detected.append("python")
        signals.append("python_files_or_manifest")
    if any(ext in extensions for ext in (".js", ".jsx", ".ts", ".tsx")) or os.path.exists(
        os.path.join(project_root, "package.json")
    ):
        detected.append("javascript")
        signals.append("javascript_files_or_manifest")
    if not detected:
        detected.append("unknown")
    return {
        "primary": detected[0] if len(detected) == 1 else "mixed",
        "detected": detected,
        "signals": signals,
    }


def _doc_chunks(text: str) -> List[str]:
    """Split markdown/text into heading- and blank-line-delimited blocks."""
    chunks: List[str] = []
    buf: List[str] = []

    def flush() -> None:
        if buf:
            block = " ".join(s.strip() for s in buf if s.strip())
            block = block.strip()
            if block:
                chunks.append(block[:CHUNK_CHAR_LIMIT])
            buf.clear()

    for line in text.splitlines():
        if _HEADING_RE.match(line):
            flush()
            buf.append(line)
            flush()
            continue
        if not line.strip():
            flush()
            continue
        buf.append(line)
    flush()
    return chunks[:MAX_CHUNKS_PER_FILE]


def _code_chunks(text: str) -> List[str]:
    """Extract signatures, leading docstring, and TODO markers."""
    chunks: List[str] = []
    lines = text.splitlines()

    # Module / leading docstring or top comment block.
    head: List[str] = []
    for line in lines[:40]:
        stripped = line.strip()
        if stripped.startswith(("#", "//", "/*", "*", '"""', "'''")):
            cleaned = stripped.strip("#/*\"' ").strip()
            if cleaned:
                head.append(cleaned)
        elif stripped:
            break
    if head:
        chunks.append(" ".join(head)[:CHUNK_CHAR_LIMIT])

    for line in lines:
        if _SIG_RE.match(line):
            sig = line.strip()[:CHUNK_CHAR_LIMIT]
            chunks.append(sig)
        elif _TODO_RE.search(line):
            chunks.append(line.strip()[:CHUNK_CHAR_LIMIT])
        if len(chunks) >= MAX_CHUNKS_PER_FILE:
            break
    return chunks


def build_index(project_root: str) -> Dict[str, Any]:
    """Scan ``project_root`` and return the index dict (does not write it)."""
    project_root = os.path.abspath(project_root)
    files: List[Dict[str, Any]] = []
    chunks: List[Dict[str, str]] = []
    python_sources: List[Dict[str, str]] = []
    python_tests: List[Dict[str, str]] = []
    total_chunks = 0
    counts = {"readme": 0, "docs": 0, "src": 0, "test": 0}

    for dirpath, dirnames, filenames in os.walk(project_root):
        # prune skip dirs in-place for efficiency
        dirnames[:] = [
            d for d in dirnames
            if d not in SKIP_DIRS and not d.startswith(".jarvis_builder")
        ]
        for fname in filenames:
            abs_path = os.path.join(dirpath, fname)
            rel_path = os.path.relpath(abs_path, project_root).replace("\\", "/")
            ext = os.path.splitext(fname)[1].lower()
            category = _categorize(rel_path, ext)
            if category is None:
                continue
            try:
                size = os.path.getsize(abs_path)
            except OSError:
                continue

            text = _read_text(abs_path)
            line_count = text.count("\n") + 1 if text else 0
            todo_count = len(_TODO_RE.findall(text)) if text else 0

            files.append(
                {
                    "path": rel_path,
                    "category": category,
                    "ext": ext,
                    "size": size,
                    "lines": line_count,
                    "todos": todo_count,
                }
            )
            counts[category] += 1
            if text and ext == ".py":
                python_document = {"path": rel_path, "text": text}
                if category == "test":
                    python_tests.append(python_document)
                elif category == "src":
                    python_sources.append(python_document)

            if text and total_chunks < MAX_TOTAL_CHUNKS:
                if category in ("readme", "docs"):
                    file_chunks = _doc_chunks(text)
                else:
                    file_chunks = _code_chunks(text)
                for ch in file_chunks:
                    if total_chunks >= MAX_TOTAL_CHUNKS:
                        break
                    chunks.append(
                        {"path": rel_path, "category": category, "text": ch}
                    )
                    total_chunks += 1

    git_info: Dict[str, Any] = {"is_repo": False}
    git_log: List[Dict[str, str]] = []
    churn: Dict[str, int] = {}
    if gitutil.is_repo(project_root):
        git_info = {
            "is_repo": True,
            "commit": gitutil.current_commit(project_root),
            "branch": gitutil.current_branch(project_root),
        }
        git_log = gitutil.recent_log(project_root, GIT_LOG_LIMIT)
        churn = gitutil.churn_counts(project_root, GIT_LOG_LIMIT)

    python_files = [
        python_analysis.analyze_python(
            document["path"],
            document["text"],
            test_documents=python_tests,
        )
        for document in python_sources
    ]
    index: Dict[str, Any] = {
        "schema_version": 1,
        "builder_core_version": __version__,
        "project_root": project_root,
        "indexed_at": _now_iso(),
        "git": git_info,
        "stats": {
            "files": len(files),
            "chunks": len(chunks),
            **counts,
        },
        "project_type": _detect_project_type(project_root, files),
        "files": files,
        "chunks": chunks,
        "python_analysis": python_files,
        "git_log": git_log,
        "churn": churn,
    }
    return index
