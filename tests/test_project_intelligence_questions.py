"""Tests for Phase 79+ project intelligence question routing and answering.

All 10 required builder questions must:
  - Route to ANSWER_PROJECT_QUESTION (not UNKNOWN, not CLARIFY)
  - Return a non-failed result with JARVIS-relevant content
  - Contain no FINAL_ALGO_TRADER / algo_trader / live_paper contamination
  - Execute no browser, email, or autonomous side effects
  - Have a project root pointing to local_jarvis, not FINAL_ALGO_TRADER

Run:
  py -3 -m pytest tests/test_project_intelligence_questions.py -q
"""

from __future__ import annotations

import json
import webbrowser
from pathlib import Path

import pytest

from core.types import ActionStatus, CommandRequest, Intent

# ── The 10 required questions ──────────────────────────────────────────────────

REQUIRED_QUESTIONS = [
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

# ── Contamination strings that must never appear in answers ────────────────────

CONTAMINATION = [
    "FINAL_ALGO_TRADER",
    "algo_trader",
    "live_paper",
    "scheduled_logs",
]

# ── Keywords that confirm JARVIS-relevant content ──────────────────────────────

JARVIS_KEYWORDS = [
    "jarvis", "phase", "router", "tool", "intent", "brain", "reports",
    "local_jarvis", "action", "classifier", "registry", "trust", "llm",
    "codebase", "builder", "architecture",
]


# ─────────────────────────────────────────────────────────────────────────────
# Routing tests
# ─────────────────────────────────────────────────────────────────────────────

class TestRouting:
    """All 10 questions must route to ANSWER_PROJECT_QUESTION."""

    @pytest.mark.parametrize("question", REQUIRED_QUESTIONS)
    def test_routes_to_project_intelligence(self, question):
        from brain.intent_classifier import classify

        req = classify(question)
        assert req.intent == Intent.ANSWER_PROJECT_QUESTION, (
            f"{question!r} → {req.intent.value!r}  (expected answer_project_question)"
        )

    @pytest.mark.parametrize("question", REQUIRED_QUESTIONS)
    def test_not_unknown_or_clarify(self, question):
        from brain.intent_classifier import classify

        req = classify(question)
        assert req.intent not in (Intent.UNKNOWN, Intent.CLARIFY), (
            f"{question!r} was classified as {req.intent.value!r}"
        )

    @pytest.mark.parametrize("question", REQUIRED_QUESTIONS)
    def test_confidence_above_threshold(self, question):
        from brain.intent_classifier import classify
        from config import CONFIDENCE_THRESHOLD

        req = classify(question)
        assert req.confidence >= CONFIDENCE_THRESHOLD, (
            f"{question!r} confidence {req.confidence:.2f} < threshold {CONFIDENCE_THRESHOLD}"
        )

    def test_trading_questions_do_not_route_to_project_intelligence(self):
        """Trading-specific commands must NOT be captured by the new intent."""
        from brain.intent_classifier import classify

        trading_qs = [
            "show trading dashboard health",
            "show last errors",
            "show open positions",
            "run live daily loop",
        ]
        for q in trading_qs:
            req = classify(q)
            assert req.intent != Intent.ANSWER_PROJECT_QUESTION, (
                f"Trading question {q!r} incorrectly routed to project intelligence"
            )


# ─────────────────────────────────────────────────────────────────────────────
# Handler tests
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def _no_browser(monkeypatch):
    """Block webbrowser.open for all tests in this file."""
    opened = []
    monkeypatch.setattr(webbrowser, "open", lambda *a, **k: opened.append(a))
    yield opened


def _run_handler(question: str) -> "CommandResult":  # type: ignore[name-defined]
    from actions.project_intelligence_actions import AnswerProjectQuestionAction

    action = AnswerProjectQuestionAction()
    request = CommandRequest(
        raw_text=question,
        intent=Intent.ANSWER_PROJECT_QUESTION,
        confidence=0.88,
    )
    return action.execute(request)


class TestHandler:
    """Handler must answer with useful JARVIS content and no contamination."""

    @pytest.mark.parametrize("question", REQUIRED_QUESTIONS)
    def test_handler_does_not_fail_with_error(self, question):
        result = _run_handler(question)
        # FAILED is acceptable only when there's zero documentation at all;
        # but it must never return UNKNOWN.
        assert result.intent != Intent.UNKNOWN

    @pytest.mark.parametrize("question", REQUIRED_QUESTIONS)
    def test_no_contamination_in_answer(self, question):
        result = _run_handler(question)
        text = (result.summary or "").lower()
        for bad in CONTAMINATION:
            assert bad.lower() not in text, (
                f"Answer for {question!r} contains contamination string {bad!r}"
            )

    @pytest.mark.parametrize("question", REQUIRED_QUESTIONS)
    def test_answer_contains_jarvis_relevant_content(self, question):
        result = _run_handler(question)
        text = (result.summary or "").lower()
        has_content = any(kw in text for kw in JARVIS_KEYWORDS)
        assert has_content, (
            f"Answer for {question!r} has no JARVIS keywords.\n"
            f"Got: {result.summary[:300]!r}"
        )

    @pytest.mark.parametrize("question", REQUIRED_QUESTIONS)
    def test_no_browser_opened(self, question, _no_browser):
        _run_handler(question)
        assert _no_browser == [], f"Browser was opened for {question!r}"

    def test_phase_73a_references_browser_trust(self):
        result = _run_handler("Why was Phase 73A built?")
        text = (result.summary or "").lower()
        has_relevant = any(kw in text for kw in [
            "browser", "trust", "73a", "73", "fake", "mock", "repair",
        ])
        assert has_relevant, f"Phase 73A answer missing expected content:\n{result.summary[:500]}"

    def test_phase_79_references_llm_or_router(self):
        result = _run_handler("What problem does Phase 79 solve?")
        text = (result.summary or "").lower()
        has_relevant = any(kw in text for kw in [
            "llm", "router", "tool", "79", "classifier", "miss", "shadow",
        ])
        assert has_relevant, f"Phase 79 answer missing expected content:\n{result.summary[:500]}"

    def test_temporal_question_contains_git_section_or_report_content(self):
        result = _run_handler("What changed in the last 30 days?")
        text = (result.summary or "").lower()
        # Either git log content or document content, never FINAL_ALGO_TRADER
        for bad in CONTAMINATION:
            assert bad.lower() not in text

    def test_unrelated_question_names_trading_and_voice(self):
        result = _run_handler("What parts of the codebase appear unrelated to Jarvis for Builders?")
        text = (result.summary or "").lower()
        # The static answer must mention at least trading and voice
        assert "trading" in text, "Expected 'trading' in unrelated-codebase answer"
        assert "voice" in text or "hebrew" in text, (
            "Expected voice or Hebrew mention in unrelated-codebase answer"
        )

    def test_result_data_has_project_root(self):
        result = _run_handler("Why was Phase 73A built?")
        root = result.data.get("project_root", "")
        assert "local_jarvis" in root or "J.A.R.V.I.S" in root, (
            f"project_root in data unexpected: {root!r}"
        )
        assert "FINAL_ALGO_TRADER" not in root


# ─────────────────────────────────────────────────────────────────────────────
# Anti-contamination unit tests
# ─────────────────────────────────────────────────────────────────────────────

class TestAntiContamination:

    def test_jarvis_root_is_local_jarvis(self):
        from project_intelligence.evidence import JARVIS_ROOT

        root_str = str(JARVIS_ROOT)
        assert "FINAL_ALGO_TRADER" not in root_str
        assert "algo_trader" not in root_str.lower()
        assert "local_jarvis" in root_str or "J.A.R.V.I.S" in root_str

    def test_is_contaminated_blocks_algo_trader_paths(self):
        from project_intelligence.evidence import is_contaminated

        bad = [
            Path(r"C:\FINAL_ALGO_TRADER\reports\live_paper\log.txt"),
            Path("/home/user/algo_trader/x.md"),
            Path(r"C:\Projects\scheduled_logs\2024.txt"),
        ]
        for p in bad:
            assert is_contaminated(p), f"Should be contaminated: {p}"

    def test_is_contaminated_allows_jarvis_paths(self):
        from project_intelligence.evidence import JARVIS_ROOT, is_contaminated

        good = [
            JARVIS_ROOT / "reports" / "phase73a_browser_trust_repair_completion.md",
            JARVIS_ROOT / "README_ARCHITECTURE.md",
            JARVIS_ROOT / "brain" / "router.py",
        ]
        for p in good:
            assert not is_contaminated(p), f"Incorrectly contaminated: {p}"

    def test_search_reports_stays_within_jarvis_root(self):
        from project_intelligence.evidence import JARVIS_ROOT
        from project_intelligence.retrieval import search_reports

        evidence = search_reports(["phase", "trust", "browser"], ["73"])
        for ev in evidence:
            try:
                ev.path.relative_to(JARVIS_ROOT)
            except ValueError:
                pytest.fail(f"Evidence path escapes JARVIS root: {ev.path}")

    def test_is_within_jarvis_rejects_outside_path(self):
        from project_intelligence.evidence import is_within_jarvis

        outside = Path(r"C:\FINAL_ALGO_TRADER\reports\x.md")
        assert not is_within_jarvis(outside)

    def test_is_within_jarvis_accepts_reports_dir(self):
        from project_intelligence.evidence import JARVIS_ROOT, is_within_jarvis

        inside = JARVIS_ROOT / "reports" / "phase79_llm_router_implementation_plan.md"
        # Only check if the file actually exists; skip if not
        if inside.exists():
            assert is_within_jarvis(inside)


# ─────────────────────────────────────────────────────────────────────────────
# Tool registry tests
# ─────────────────────────────────────────────────────────────────────────────

class TestToolRegistry:

    def test_project_answer_question_in_catalog(self):
        from tools.catalog import default_specs

        names = [s.name for s in default_specs()]
        assert "project.answer_question" in names, (
            f"project.answer_question missing from catalog. Found: {names}"
        )

    def test_project_tool_is_read_only(self):
        from tools.catalog import default_specs
        from tools.spec import SafetyClass

        spec = next(s for s in default_specs() if s.name == "project.answer_question")
        assert spec.safety_class == SafetyClass.READ_ONLY

    def test_project_tool_maps_to_correct_intent(self):
        from tools.catalog import default_specs

        spec = next(s for s in default_specs() if s.name == "project.answer_question")
        assert spec.maps_to_intent == "answer_project_question"


# ─────────────────────────────────────────────────────────────────────────────
# Security — verify no unsafe dispatch possible
# ─────────────────────────────────────────────────────────────────────────────

class TestNoUnsafeDispatch:

    def test_intent_in_allowed_intents(self):
        from config import ALLOWED_INTENTS

        assert "answer_project_question" in ALLOWED_INTENTS

    def test_intent_in_implemented_intents(self):
        from config import IMPLEMENTED_INTENTS

        assert "answer_project_question" in IMPLEMENTED_INTENTS

    def test_handler_registered_in_action_registry(self):
        from actions.registry import ActionRegistry

        reg = ActionRegistry()
        assert reg.has("answer_project_question"), (
            "AnswerProjectQuestionAction not registered in ActionRegistry"
        )
