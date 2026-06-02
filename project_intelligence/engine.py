"""Project Intelligence answer engine — retrieval + extractive synthesis only."""

from __future__ import annotations

from core.results import result_failed, result_success
from core.types import CommandResult, Intent
from project_intelligence.evidence import JARVIS_ROOT
from project_intelligence.ranking import is_unrelated_question
from project_intelligence.retrieval import gather_evidence
from project_intelligence.summarizer import UNRELATED_ANSWER, format_answer


def answer_question(question: str) -> CommandResult:
    """Answer a builder question using read-only repository evidence."""
    text = (question or "").strip()
    if not text:
        return result_failed(
            Intent.ANSWER_PROJECT_QUESTION,
            "No question provided. Ask something like: 'Why was Phase 73A built?'",
        )

    if is_unrelated_question(text):
        return result_success(
            Intent.ANSWER_PROJECT_QUESTION,
            UNRELATED_ANSWER.strip(),
            data={
                "question": text,
                "evidence_files": [],
                "project_root": str(JARVIS_ROOT),
            },
        )

    evidence, git_section, phase_numbers = gather_evidence(text)
    if not evidence and not git_section:
        return result_failed(
            Intent.ANSWER_PROJECT_QUESTION,
            f"No relevant JARVIS documentation found for: {text!r}\n"
            "Tip: browse reports/ or ask about a specific phase number.",
        )

    summary = format_answer(
        text,
        evidence,
        git_section=git_section,
        phase_numbers=phase_numbers,
    )
    files_cited = sorted({str(ev.path.name) for ev in evidence})
    return result_success(
        Intent.ANSWER_PROJECT_QUESTION,
        summary,
        data={
            "question": text,
            "evidence_files": files_cited,
            "phase_numbers": phase_numbers.split(",") if phase_numbers else [],
            "is_temporal": bool(git_section),
            "project_root": str(JARVIS_ROOT),
        },
    )
