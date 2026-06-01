"""Phase 101A — architectural-risk routing regressions.

Architectural-risk questions ("architectural risk", "risk modules", "blast
radius", "fan-in", "import cycles", "structural fragility", "coupled") must route
to the deterministic architectural **bottleneck** mode (dependency-graph fan-in +
cycles + central modules), not to keyword retrieval.
"""

from __future__ import annotations

from pathlib import Path

from builder_core import ask, indexer, question_understanding

ARCH_RISK_QUESTIONS = [
    "Rank the top architectural risk modules in this repository using dependency "
    "graph fan-in, module size, import cycles, and test coverage.",
    "Which modules have the highest architectural risk and why?",
    "What are the riskiest modules?",
    "Which modules have the biggest blast radius?",
    "Rank modules by import fan-in.",
    "Are there any import cycles?",
    "Which parts have the most structural fragility?",
    "What are the most coupled modules?",
    "Show me the critical architectural bottlenecks.",
]


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _repo(tmp_path: Path) -> Path:
    """A repo with a clear fan-in hub and an import cycle."""
    root = tmp_path / "repo"
    # fan-in hub: core/util.py imported by three modules
    _write(root / "core" / "util.py", '"""Shared helper."""\n\n\ndef helper():\n    return 1\n')
    for name in ("a", "b", "c"):
        _write(root / f"{name}.py", f"from core.util import helper\n\n\ndef run_{name}():\n    return helper()\n")
    # import cycle: ring.x <-> ring.y
    _write(root / "ring" / "x.py", "from ring.y import gy\n\n\ndef gx():\n    return gy()\n")
    _write(root / "ring" / "y.py", "from ring.x import gx\n\n\ndef gy():\n    return 1\n")
    _write(root / "README.md", "# sample repo\n")
    return root


def test_architectural_risk_questions_classify_as_bottleneck():
    for question in ARCH_RISK_QUESTIONS:
        detail = question_understanding.classify_question_detail(question)
        assert detail["category"] == "bottleneck", question
        assert detail["fired_rule"].startswith("anchor:"), question


def test_architectural_risk_routes_to_bottleneck_not_retrieval(tmp_path):
    index = indexer.build_index(str(_repo(tmp_path)))
    result = ask.answer(
        index,
        "Rank the top architectural risk modules using dependency graph fan-in, "
        "import cycles, and test coverage.",
    )
    assert result["mode"] == "bottleneck"
    # must NOT be the retrieval fallback prose
    assert "based on the indexed project" not in result["answer"].lower()


def test_bottleneck_answer_cites_fanin_and_cycles(tmp_path):
    index = indexer.build_index(str(_repo(tmp_path)))
    result = ask.answer(index, "What are the most critical architectural bottlenecks?")
    assert result["mode"] == "bottleneck"
    joined = " ".join([result["answer"], *result["evidence"]]).lower()
    assert "fan-in" in joined          # fan-in signal surfaced
    assert "cycle" in joined           # the ring.x <-> ring.y cycle surfaced
    assert "core" in joined            # the fan-in hub (core.util) is ranked


def test_generic_risk_question_still_routes_to_risk(tmp_path):
    # "biggest risks" without architectural vocabulary stays on the risk path
    assert ask.classify("what are the biggest risks in this codebase?") == "risk"
    index = indexer.build_index(str(_repo(tmp_path)))
    result = ask.answer(index, "what are the biggest risks in this codebase?")
    assert result["mode"] == "risk"


def test_architecture_overview_still_routes_to_architecture(tmp_path):
    # "architectural"/"architecture" overview must not be hijacked by bottleneck
    detail = question_understanding.classify_question_detail(
        "Give me an overview of the system architecture."
    )
    assert detail["category"] == "architecture"


def test_classification_is_deterministic():
    for question in ARCH_RISK_QUESTIONS:
        first = question_understanding.classify_question_detail(question)
        second = question_understanding.classify_question_detail(question)
        assert first == second
