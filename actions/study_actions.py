"""Phase 40b — study / focus mode (session flags + read-only)."""

from __future__ import annotations

from pathlib import Path

from actions.base import BaseAction
from config import MEMORY_ENABLED, PROJECT_ROOT
from core.results import result_failed, result_success
from core.session import SessionState
from core.types import CommandRequest, CommandResult, Intent
from memory.store import PersonalMemoryStore
from operating.project_io import read_project_file
from workspaces.launcher import workspace_plan


class StartStudyModeAction(BaseAction):
    intent = Intent.START_STUDY_MODE.value

    def execute(self, request: CommandRequest) -> CommandResult:
        del request
        session = SessionState.load()
        session.activity_mode = "studying"
        session.save()
        summary, phrases = workspace_plan("study")
        return result_success(
            Intent.START_STUDY_MODE,
            f"Study mode enabled.\n\n{summary}",
            next_suggestions=phrases[:4],
        )


class FocusModeAction(BaseAction):
    intent = Intent.FOCUS_MODE.value

    def execute(self, request: CommandRequest) -> CommandResult:
        del request
        session = SessionState.load()
        session.activity_mode = "focus"
        session.save()
        return result_success(
            Intent.FOCUS_MODE,
            "Focus mode enabled. Overlay hints favor quiet review; say 'toggle quiet mode' for minimal UI.",
            next_suggestions=["what am i doing", "summarize my notes", "toggle quiet mode"],
        )


class SummarizeMyNotesAction(BaseAction):
    intent = Intent.SUMMARIZE_MY_NOTES.value

    def execute(self, request: CommandRequest) -> CommandResult:
        del request
        if not MEMORY_ENABLED:
            return result_failed(Intent.SUMMARIZE_MY_NOTES, "Memory is disabled.")
        store = PersonalMemoryStore()
        entries = store.list_visible(category="study")
        if not entries:
            return result_success(
                Intent.SUMMARIZE_MY_NOTES,
                "No study notes in memory. Say 'remember this' with study context.",
            )
        lines = ["Study notes (from memory):"]
        for e in entries[:12]:
            lines.append(f"  - {e.text[:200]}")
        return result_success(Intent.SUMMARIZE_MY_NOTES, "\n".join(lines))


class ExplainThisCodeAction(BaseAction):
    intent = Intent.EXPLAIN_THIS_CODE.value

    def execute(self, request: CommandRequest) -> CommandResult:
        session = SessionState.load()
        rel = str(request.params.get("path") or "").strip()
        if not rel and session.last_opened_file:
            try:
                rel = str(
                    Path(session.last_opened_file).relative_to(
                        session.current_project_root or PROJECT_ROOT
                    )
                )
            except ValueError:
                rel = Path(session.last_opened_file).name
        if not rel:
            return result_failed(
                Intent.EXPLAIN_THIS_CODE,
                "No file in context. Specify a path or open a file in the editor first.",
            )
        root = session.current_project_root or str(PROJECT_ROOT)
        text = read_project_file(rel, Path(root), max_chars=2500)
        lines = [ln for ln in text.splitlines() if ln.strip()][:30]
        outline = "\n".join(f"  {i+1}: {ln[:100]}" for i, ln in enumerate(lines))
        summary = (
            f"Code outline (read-only, no LLM):\nFile: {rel}\n"
            f"Non-empty lines (first 30):\n{outline}\n\n"
            "Say 'find function <name>' or 'search code text <term>' for deeper lookup."
        )
        return result_success(Intent.EXPLAIN_THIS_CODE, summary)


class QuizMeAction(BaseAction):
    intent = Intent.QUIZ_ME.value

    def execute(self, request: CommandRequest) -> CommandResult:
        del request
        store = PersonalMemoryStore()
        entries = store.list_visible(category="study")
        if len(entries) < 2:
            return result_success(
                Intent.QUIZ_ME,
                "Add at least two study notes with 'remember this' to enable quiz mode.",
            )
        import random

        pick = random.choice(entries)
        prompt = (
            "Quiz (template):\n"
            f"Topic tag: {', '.join(pick.tags[:3]) or 'general'}\n"
            f"Recall what you stored about: {pick.text[:120]}...\n"
            "Say 'show memory' to check your notes after answering."
        )
        return result_success(Intent.QUIZ_ME, prompt)


class WhatShouldIStudyNextAction(BaseAction):
    intent = Intent.WHAT_SHOULD_I_STUDY_NEXT.value

    def execute(self, request: CommandRequest) -> CommandResult:
        del request
        store = PersonalMemoryStore()
        entries = store.list_visible(category="study")
        if not entries:
            return result_success(
                Intent.WHAT_SHOULD_I_STUDY_NEXT,
                "No study memory yet. Try: start study mode, then remember key topics.",
                next_suggestions=["start study mode", "index project", "open youtube"],
            )
        recent = entries[-1]
        return result_success(
            Intent.WHAT_SHOULD_I_STUDY_NEXT,
            f"Suggested focus: revisit — {recent.text[:200]}\n"
            "Next: summarize my notes, or quiz me.",
            next_suggestions=["quiz me", "summarize my notes", "search project knowledge"],
        )
