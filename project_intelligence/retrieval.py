"""Read-only repository evidence retrieval for Project Intelligence."""

from __future__ import annotations

import subprocess
from pathlib import Path

from project_intelligence.evidence import (
    Evidence,
    JARVIS_ROOT,
    is_within_jarvis,
    read_safe,
)
from project_intelligence.ranking import extract_passages, extract_phase_numbers, extract_keywords

MAX_GIT_OUTPUT_CHARS = 2000
MAX_FILES_IN_ANSWER = 5

CODE_SOURCES: tuple[str, ...] = (
    "README_ARCHITECTURE.md",
    "README.md",
    "brain/router.py",
    "brain/intent_classifier.py",
    "brain/llm_tool_router.py",
    "brain/tool_router_prompt.py",
    "tools/flags.py",
    "tools/catalog.py",
    "tools/spec.py",
    "tools/registry.py",
    "actions/registry.py",
    "actions/project_intelligence_actions.py",
    "config.py",
)

DOC_GLOBS: tuple[tuple[str, str], ...] = (
    ("reports", "*.md"),
    ("", "README*.md"),
    ("", "README_ARCHITECTURE.md"),
)

TEST_GLOBS: tuple[str, ...] = (
    "tests/test_phase79_llm_tool_router.py",
    "tests/test_project_intelligence_questions.py",
)


def _git(*args: str) -> str:
    try:
        result = subprocess.run(
            ["git", *args],
            capture_output=True,
            text=True,
            cwd=str(JARVIS_ROOT),
            timeout=10,
            check=False,
        )
        if result.returncode == 0:
            return result.stdout.strip()[:MAX_GIT_OUTPUT_CHARS]
    except (OSError, subprocess.TimeoutExpired):
        pass
    return ""


def git_log_recent(days: int) -> str:
    return _git("log", "--oneline", "--decorate", f"--since={days} days ago")


def git_log_n(n: int = 50) -> str:
    return _git("log", "--oneline", "--decorate", f"-n{n}")


def git_status_short() -> str:
    return _git("status", "--short")


def search_reports(keywords: list[str], phase_numbers: list[str]) -> list[Evidence]:
    reports_dir = JARVIS_ROOT / "reports"
    if not reports_dir.is_dir():
        return []

    results: list[Evidence] = []
    for md_file in sorted(reports_dir.glob("*.md")):
        if not is_within_jarvis(md_file):
            continue
        fname = md_file.name.lower()
        boost = 0.0
        if phase_numbers:
            for pnum in phase_numbers:
                slug = pnum.lower()
                if f"phase{slug}" in fname or f"phase_{slug}" in fname or f"phase-{slug}" in fname:
                    boost = 0.5
                    break
        text = read_safe(md_file)
        for passage, score in extract_passages(text, keywords):
            results.append(Evidence(md_file, passage, score + boost, "report"))
    return results


def search_file(rel_path: str, keywords: list[str], *, source_kind: str = "file") -> list[Evidence]:
    path = JARVIS_ROOT / rel_path
    if not path.exists() or not is_within_jarvis(path):
        return []
    text = read_safe(path)
    return [
        Evidence(path, passage, score, source_kind)
        for passage, score in extract_passages(text, keywords)
    ]


def search_code_modules(keywords: list[str], phase_numbers: list[str]) -> list[Evidence]:
    code_kw = {
        "router",
        "classifier",
        "intent",
        "tool",
        "registry",
        "handler",
        "action",
        "shadow",
        "flag",
        "audit",
        "llm",
        "phase",
        "architecture",
        "risk",
    }
    if not (code_kw.intersection(set(keywords)) or phase_numbers):
        return []
    evidence: list[Evidence] = []
    for rel in CODE_SOURCES:
        evidence.extend(search_file(rel, keywords, source_kind="code"))
    return evidence


def search_tests(keywords: list[str]) -> list[Evidence]:
    if "test" not in keywords and "phase" not in keywords:
        return []
    evidence: list[Evidence] = []
    for rel in TEST_GLOBS:
        evidence.extend(search_file(rel, keywords, source_kind="test"))
    return evidence


def gather_evidence(question: str) -> tuple[list[Evidence], str, str]:
    """Return (ranked evidence, git_section, phase_numbers_csv)."""
    keywords = extract_keywords(question)
    phase_numbers = extract_phase_numbers(question)
    evidence: list[Evidence] = []

    evidence.extend(search_reports(keywords, phase_numbers))
    evidence.extend(search_code_modules(keywords, phase_numbers))
    evidence.extend(search_tests(keywords))

    from project_intelligence.ranking import is_architecture_question, is_temporal, days_requested

    if is_architecture_question(keywords) or not evidence:
        for src in ("README_ARCHITECTURE.md", "README.md", "reports/phase73_100_roadmap.md"):
            evidence.extend(search_file(src, keywords, source_kind="doc"))

    git_section = ""
    if is_temporal(question):
        days = days_requested(question)
        log = git_log_recent(days)
        status = git_status_short()
        if log:
            git_section += f"\nRecent git activity (last {days} days — local_jarvis/):\n{log}"
        if status:
            git_section += f"\n\nWorking tree status (local_jarvis/):\n{status}"

    if not evidence and not git_section:
        log = git_log_n(40)
        if log:
            git_section = f"\nRecent git log (local_jarvis/ — last 40 commits):\n{log}"

    by_path: dict[str, Evidence] = {}
    for item in evidence:
        if not is_within_jarvis(item.path):
            continue
        key = str(item.path)
        current = by_path.get(key)
        if current is None or item.score > current.score:
            by_path[key] = item

    top = sorted(by_path.values(), key=lambda ev: ev.score, reverse=True)[:MAX_FILES_IN_ANSWER]
    return top, git_section, ",".join(phase_numbers)
