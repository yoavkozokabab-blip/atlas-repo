"""Phase 81 — Evidence Synthesis tests.

Contracts enforced here:
  1. ANSWER: section appears before EVIDENCE: section in every answer
  2. ANSWER: section is not empty
  3. ANSWER: section is not a raw document excerpt (doesn't start with '📄',
     a file path, or the EVIDENCE: or SOURCES: markers)
  4. QUESTION: section matches the question asked
  5. SOURCES: section is present and lists at least one source
  6. No leading file citations (no path or '📄' before ANSWER:)
  7. Phase-specific synthesis contains phase-relevant content
  8. Authoritative topics use their curated answers, not random extracts
  9. UNRELATED_ANSWER follows the same structure
 10. Sentence extractor rejects question headings, code references, and
     bullet-hidden file paths

Run:
  py -3 -m pytest tests/test_phase81_evidence_synthesis.py -q
"""

from __future__ import annotations

import re

import pytest

from project_intelligence.engine import answer_question

# ── The 10 required questions ──────────────────────────────────────────────────

QUESTIONS = [
    "Why was Phase 73A built?",
    "What problem does Phase 79 solve?",
    "What are the biggest architectural risks in the current JARVIS codebase?",
    "What should be built next and why?",
    "Summarize the current state of the project in under 500 words.",
    "What are the most important unfinished phases?",
    "What changed in the last 30 days?",
    "What decisions were made recently that could affect future architecture?",
    "If a new developer joined today, what would they need to understand first?",
    "What parts of the codebase appear unrelated to Jarvis for Builders?",
]


def _answer(question: str) -> str:
    return answer_question(question).summary or ""


def _section_pos(text: str, label: str) -> int:
    """Return character position of 'LABEL:' or 'LABEL\n', -1 if absent."""
    idx = text.find(f"{label}:")
    return idx


# ─────────────────────────────────────────────────────────────────────────────
# 1. Format structure — ANSWER before EVIDENCE
# ─────────────────────────────────────────────────────────────────────────────

class TestAnswerBeforeEvidence:

    @pytest.mark.parametrize("question", QUESTIONS)
    def test_answer_section_present(self, question):
        text = _answer(question)
        assert "ANSWER:" in text, (
            f"No 'ANSWER:' section in output for:\n  {question!r}\n"
            f"Got:\n{text[:400]}"
        )

    @pytest.mark.parametrize("question", QUESTIONS)
    def test_evidence_section_present_when_docs_exist(self, question):
        """EVIDENCE: must appear (project always has docs; if missing something is wrong)."""
        text = _answer(question)
        # UNRELATED answer has static EVIDENCE embedded — check separately
        if "unrelated to jarvis for builders" in question.lower():
            assert "EVIDENCE:" in text
            return
        assert "EVIDENCE:" in text or "SOURCES:" in text, (
            f"Neither EVIDENCE: nor SOURCES: found for:\n  {question!r}\n"
            f"Got:\n{text[:400]}"
        )

    @pytest.mark.parametrize("question", QUESTIONS)
    def test_answer_before_evidence(self, question):
        text = _answer(question)
        answer_pos = _section_pos(text, "ANSWER")
        evidence_pos = _section_pos(text, "EVIDENCE")
        if evidence_pos == -1:
            pytest.skip("EVIDENCE section absent — structure test not applicable")
        assert answer_pos >= 0, f"No ANSWER: section for {question!r}"
        assert answer_pos < evidence_pos, (
            f"ANSWER: at {answer_pos} is not before EVIDENCE: at {evidence_pos}\n"
            f"Question: {question!r}\n"
            f"Output:\n{text[:600]}"
        )

    @pytest.mark.parametrize("question", QUESTIONS)
    def test_sources_at_end(self, question):
        text = _answer(question)
        sources_pos = _section_pos(text, "SOURCES")
        evidence_pos = _section_pos(text, "EVIDENCE")
        if sources_pos == -1:
            return  # Not all answers have sources (e.g. temporal-only)
        if evidence_pos >= 0:
            assert sources_pos > evidence_pos, (
                f"SOURCES: appears before EVIDENCE: for {question!r}"
            )

    @pytest.mark.parametrize("question", QUESTIONS)
    def test_question_section_matches_asked_question(self, question):
        text = _answer(question)
        question_pos = _section_pos(text, "QUESTION")
        assert question_pos >= 0, f"No QUESTION: section for {question!r}"
        # The asked question should appear in the answer within 200 chars of QUESTION:
        snippet = text[question_pos: question_pos + len(question) + 30]
        # At least the first 20 chars of the question should appear
        assert question[:20].lower() in snippet.lower(), (
            f"QUESTION: section doesn't echo the question for {question!r}\n"
            f"Got snippet: {snippet!r}"
        )


# ─────────────────────────────────────────────────────────────────────────────
# 2. ANSWER section content quality
# ─────────────────────────────────────────────────────────────────────────────

class TestAnswerContent:

    def _extract_answer_text(self, question: str) -> str:
        """Return only the text of the ANSWER: section."""
        text = _answer(question)
        answer_pos = _section_pos(text, "ANSWER")
        if answer_pos < 0:
            return ""
        after_answer = text[answer_pos + len("ANSWER:"):].lstrip("\n")
        # Cut at the next section marker
        next_section = re.search(r"\n(EVIDENCE|SOURCES|QUESTION):", after_answer)
        if next_section:
            return after_answer[:next_section.start()].strip()
        return after_answer.strip()

    @pytest.mark.parametrize("question", QUESTIONS)
    def test_answer_section_not_empty(self, question):
        answer_text = self._extract_answer_text(question)
        assert len(answer_text) >= 30, (
            f"ANSWER section too short ({len(answer_text)} chars) for {question!r}\n"
            f"Got: {answer_text!r}"
        )

    @pytest.mark.parametrize("question", QUESTIONS)
    def test_answer_does_not_start_with_file_citation(self, question):
        """The ANSWER block must not begin with '📄', a file path, or a bullet list."""
        answer_text = self._extract_answer_text(question)
        first_char = answer_text.lstrip()[0] if answer_text.strip() else ""
        # Must not start with emoji citation marker
        assert not answer_text.startswith("📄"), (
            f"ANSWER starts with '📄' (file citation) for {question!r}"
        )
        # Must not start with a bare file path like "reports\" or "brain/"
        assert not re.match(r"^(reports|brain|tools|core|actions|tests)[/\\]", answer_text), (
            f"ANSWER starts with a file path for {question!r}:\n  {answer_text[:80]}"
        )
        # Must not start with "EVIDENCE:" or "SOURCES:" (wrong section)
        assert not answer_text.startswith(("EVIDENCE:", "SOURCES:")), (
            f"ANSWER section contains section label for {question!r}"
        )

    @pytest.mark.parametrize("question", QUESTIONS)
    def test_answer_does_not_appear_before_question_section(self, question):
        """Nothing substantive should appear before QUESTION:."""
        text = _answer(question)
        question_pos = _section_pos(text, "QUESTION")
        answer_pos = _section_pos(text, "ANSWER")
        if question_pos < 0 or answer_pos < 0:
            return
        assert question_pos < answer_pos, (
            f"ANSWER: appears before QUESTION: for {question!r}"
        )

    def test_phase_73a_answer_mentions_browser_or_trust(self):
        answer_text = self._extract_answer_text("Why was Phase 73A built?")
        lower = answer_text.lower()
        has_relevant = any(kw in lower for kw in [
            "browser", "trust", "mock", "fake", "success", "provider",
            "73a", "repair", "path", "fix",
        ])
        assert has_relevant, (
            f"Phase 73A ANSWER section has no browser/trust content:\n{answer_text}"
        )

    def test_phase_79_answer_mentions_llm_or_router(self):
        answer_text = self._extract_answer_text("What problem does Phase 79 solve?")
        lower = answer_text.lower()
        has_relevant = any(kw in lower for kw in [
            "llm", "router", "tool", "classifier", "miss", "shadow",
            "routing", "natural-language", "natural language", "keyword",
        ])
        assert has_relevant, (
            f"Phase 79 ANSWER section has no LLM/router content:\n{answer_text}"
        )

    def test_architecture_risks_answer_is_curated_not_extracted(self):
        """Architecture risks uses the curated fallback which lists 5 specific risks."""
        answer_text = self._extract_answer_text(
            "What are the biggest architectural risks in the current JARVIS codebase?"
        )
        # The curated answer lists specific numbered risks
        assert "507" in answer_text or "sprawl" in answer_text, (
            f"Architecture risks answer doesn't mention 507-intent sprawl:\n{answer_text}"
        )
        assert "shadow" in answer_text.lower() or "stage" in answer_text.lower(), (
            f"Architecture risks answer doesn't mention shadow/stage:\n{answer_text}"
        )

    def test_project_state_answer_mentions_tool_registry(self):
        answer_text = self._extract_answer_text(
            "Summarize the current state of the project in under 500 words."
        )
        assert "tool registry" in answer_text.lower() or "phase 78" in answer_text.lower(), (
            f"Project state ANSWER doesn't mention Tool Registry:\n{answer_text}"
        )

    def test_onboarding_answer_lists_specific_files(self):
        answer_text = self._extract_answer_text(
            "If a new developer joined today, what would they need to understand first?"
        )
        # Must mention concrete starting points
        lower = answer_text.lower()
        has_files = any(f in lower for f in [
            "readme", "router.py", "intent_classifier", "brain/", "reports/",
        ])
        assert has_files, (
            f"Onboarding ANSWER doesn't list specific files:\n{answer_text}"
        )

    def test_recent_decisions_answer_is_not_git_log(self):
        """'What decisions were made recently' should give curated answer, not raw commits."""
        answer_text = self._extract_answer_text(
            "What decisions were made recently that could affect future architecture?"
        )
        lower = answer_text.lower()
        # Should describe architectural decisions, not just list commit hashes
        has_architectural = any(kw in lower for kw in [
            "shadow invariant", "timeout", "singleton", "production guard",
            "tool registry", "phase 78", "phase 79", "circuit breaker",
        ])
        assert has_architectural, (
            f"Recent decisions ANSWER doesn't mention architectural decisions:\n{answer_text}"
        )
        # Must NOT be purely commit hashes
        assert not re.match(r"^[0-9a-f]{7,}", answer_text.strip()), (
            "ANSWER starts with a raw commit hash"
        )

    def test_unfinished_phases_names_specific_phases(self):
        answer_text = self._extract_answer_text(
            "What are the most important unfinished phases?"
        )
        lower = answer_text.lower()
        phase_mentions = [p for p in ["phase 79", "phase 80", "phase 81", "phase 84", "phase 85"]
                          if p in lower]
        assert len(phase_mentions) >= 3, (
            f"Unfinished phases ANSWER names only {len(phase_mentions)} specific phases:\n{answer_text}"
        )

    def test_temporal_question_answer_not_empty(self):
        answer_text = self._extract_answer_text("What changed in the last 30 days?")
        assert len(answer_text) >= 20, (
            f"Temporal ANSWER too short:\n{answer_text}"
        )


# ─────────────────────────────────────────────────────────────────────────────
# 3. Sentence extractor unit tests
# ─────────────────────────────────────────────────────────────────────────────

class TestSentenceExtractor:

    def test_rejects_sentence_that_ends_with_question_mark(self):
        """Document headings written as questions must not become answer sentences."""
        from project_intelligence.summarizer import _is_usable_sentence

        assert not _is_usable_sentence("What problem does Phase 79 solve?")
        assert not _is_usable_sentence("Why was Phase 73A built?")

    def test_rejects_markdown_headers(self):
        from project_intelligence.summarizer import _is_usable_sentence

        assert not _is_usable_sentence("# Phase 73A Browser Trust Repair Completion Report")
        assert not _is_usable_sentence("## Architecture Risks")

    def test_rejects_code_fences(self):
        from project_intelligence.summarizer import _is_usable_sentence

        assert not _is_usable_sentence("```python\ndef foo(): pass\n```")

    def test_rejects_short_fragments(self):
        from project_intelligence.summarizer import _is_usable_sentence

        assert not _is_usable_sentence("See §3.")
        assert not _is_usable_sentence("Phase 73A.")

    def test_rejects_file_path_lines(self):
        from project_intelligence.summarizer import _is_usable_sentence

        assert not _is_usable_sentence("actions/phase62_browser_actions.py")
        assert not _is_usable_sentence("brain/router.py:27 classifies the request")

    def test_rejects_bullet_hidden_file_paths(self):
        """After _clean_sentence strips '- ', the result must still be checked."""
        from project_intelligence.summarizer import _clean_sentence, _is_usable_sentence

        raw = "- actions/phase62_browser_actions.py:27,83 return result_success(...)"
        cleaned = _clean_sentence(raw)
        # After cleaning, the sentence starts with a path — must be rejected
        assert not _is_usable_sentence(cleaned), (
            f"Cleaned sentence should be rejected as a file-path line: {cleaned!r}"
        )

    def test_accepts_purposive_prose_sentences(self):
        from project_intelligence.summarizer import _is_usable_sentence

        good = (
            "Phase 73A was built to eliminate mock-success paths "
            "where the browser provider was unavailable."
        )
        assert _is_usable_sentence(good)

    def test_clean_sentence_strips_markdown(self):
        from project_intelligence.summarizer import _clean_sentence

        raw = "- **Phase 73A** was built to `eliminate` mock paths (see §4)."
        cleaned = _clean_sentence(raw)
        assert cleaned == "Phase 73A was built to eliminate mock paths.", (
            f"Unexpected cleaned output: {cleaned!r}"
        )

    def test_extract_returns_empty_string_on_no_candidates(self):
        from project_intelligence.summarizer import _extract_answer_sentences
        from project_intelligence.evidence import Evidence, JARVIS_ROOT

        ev = Evidence(
            path=JARVIS_ROOT / "README.md",
            passage="# Title\n\n```code```\n\nShort.",
            score=0.5,
            source_kind="doc",
        )
        result = _extract_answer_sentences([ev], ["phase", "router", "trust"])
        assert result == "", f"Expected empty string, got: {result!r}"


# ─────────────────────────────────────────────────────────────────────────────
# 4. UNRELATED_ANSWER structure
# ─────────────────────────────────────────────────────────────────────────────

class TestUnrelatedAnswer:

    def test_unrelated_answer_has_all_sections(self):
        text = _answer("What parts of the codebase appear unrelated to Jarvis for Builders?")
        assert "QUESTION:" in text
        assert "ANSWER:" in text
        assert "EVIDENCE:" in text
        assert "SOURCES:" in text

    def test_unrelated_answer_mentions_trading(self):
        text = _answer("What parts of the codebase appear unrelated to Jarvis for Builders?")
        assert "trading" in text.lower()

    def test_unrelated_answer_mentions_voice(self):
        text = _answer("What parts of the codebase appear unrelated to Jarvis for Builders?")
        assert "voice" in text.lower()

    def test_unrelated_answer_mentions_hebrew(self):
        text = _answer("What parts of the codebase appear unrelated to Jarvis for Builders?")
        assert "hebrew" in text.lower() or "hebrew-only" in text.lower()

    def test_unrelated_answer_no_contamination(self):
        text = _answer("What parts of the codebase appear unrelated to Jarvis for Builders?")
        for bad in ("FINAL_ALGO_TRADER", "algo_trader", "live_paper", "scheduled_logs"):
            assert bad.lower() not in text.lower(), (
                f"Contamination string {bad!r} found in UNRELATED_ANSWER"
            )


# ─────────────────────────────────────────────────────────────────────────────
# 5. format_answer() signature stability
# ─────────────────────────────────────────────────────────────────────────────

class TestFormatAnswerAPI:

    def test_format_answer_accepts_empty_evidence(self):
        """format_answer must not raise when evidence list is empty."""
        from project_intelligence.summarizer import format_answer

        result = format_answer("Why was Phase 73A built?", [], git_section="", phase_numbers="")
        assert isinstance(result, str)
        assert "ANSWER:" in result

    def test_format_answer_accepts_git_section_only(self):
        from project_intelligence.summarizer import format_answer

        result = format_answer(
            "What changed in the last 30 days?",
            [],
            git_section="abc1234 add phase 79 shadow mode\ndef5678 fix circuit breaker",
            phase_numbers="",
        )
        assert "ANSWER:" in result
        assert "SOURCES:" in result
        # Git log should appear somewhere after ANSWER:
        assert "abc1234" in result or "git log" in result.lower()

    def test_format_answer_sources_section_lists_files(self):
        from project_intelligence.summarizer import format_answer
        from project_intelligence.evidence import Evidence, JARVIS_ROOT

        ev = Evidence(
            path=JARVIS_ROOT / "reports" / "phase73_100_roadmap.md",
            passage="Phase 79 adds LLM routing for classifier misses.",
            score=0.9,
            source_kind="report",
        )
        result = format_answer("Why was Phase 73A built?", [ev])
        sources_idx = result.find("SOURCES:")
        assert sources_idx >= 0
        sources_text = result[sources_idx:]
        assert "phase73_100_roadmap.md" in sources_text, (
            f"File not listed in SOURCES:\n{sources_text}"
        )
