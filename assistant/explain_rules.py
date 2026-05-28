"""Rules-based explain output (no LLM)."""

from __future__ import annotations

from pathlib import Path

from config import PROJECT_ROOT
from core.session import SessionState
from diagnostics import explain_last_failure
from diagnostics.engine import get_last_report
from operating.project_io import read_project_file
from operating.workspace_context import build_activity_snapshot, get_cached_mode


def build_explain_report(*, focus: str = "general", topic: str = "") -> str:
    session = SessionState.load()
    sections: list[str] = []

    if focus in ("error", "general"):
        try:
            report = explain_last_failure()
            sections.append("## Last failure\n" + (report.summary or "No failure recorded."))
        except Exception as exc:
            sections.append(f"## Last failure\n(unavailable: {exc})")

    last = get_last_report()
    if last and last.findings:
        sections.append("## Diagnostic findings")
        for f in last.findings[:3]:
            sections.append(f"- {f.issue}: {f.likely_cause}")
            for step in f.suggested_steps[:2]:
                sections.append(f"  → {step}")

    snap = build_activity_snapshot(session)
    sections.append(
        f"## Workspace\nMode: {snap.mode}\n{snap.summary}\n"
        f"Project: {Path(snap.project_root).name if snap.project_root else 'n/a'}"
    )

    if topic or session.last_opened_file:
        rel = topic or session.last_opened_file
        try:
            rel_path = str(Path(rel).relative_to(session.current_project_root or PROJECT_ROOT))
        except ValueError:
            rel_path = Path(rel).name
        excerpt = read_project_file(rel_path, Path(session.current_project_root or PROJECT_ROOT), max_chars=800)
        if excerpt and not excerpt.startswith("File not") and not excerpt.startswith("Path"):
            sections.append(f"## Related file ({rel_path})\n{excerpt[:800]}")

    sections.append(
        "## Suggested spoken commands (you must say each)\n"
        "- run diagnostics\n"
        "- suggest next steps\n"
        "- show recent commands"
    )
    sections.append(
        "\n_No automatic execution. Phase 40b may add LLM narrative; this report is rules-only._"
    )
    return "\n".join(sections)
