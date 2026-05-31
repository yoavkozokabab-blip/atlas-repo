"""RU-3 architectural question understanding regressions."""

from __future__ import annotations

from pathlib import Path

from builder_core import ask, indexer, question_understanding


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _repo(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    _write(root / "README.md", "# Product\n\nLocal assistant runtime.\n")
    _write(
        root / "main.py",
        '"""Application entry point."""\n'
        "from core.app import run\n",
    )
    _write(
        root / "core" / "app.py",
        '"""Shared runtime bootstrap."""\n'
        "def run():\n"
        "    return True\n",
    )
    _write(
        root / "core" / "util.py",
        "def helper():\n"
        "    return 1\n",
    )
    _write(
        root / "voice" / "voice_loop.py",
        '"""Voice loop."""\n'
        "from core.app import run\n\n"
        "def handle_voice_command():\n"
        "    return run()\n",
    )
    _write(
        root / "voice" / "router.py",
        "from core.util import helper\n\n"
        "def dispatch():\n"
        "    return helper()\n",
    )
    _write(
        root / "browser" / "runtime.py",
        "from core.app import run\n\n"
        "def open_page():\n"
        "    return run()\n",
    )
    _write(
        root / "autonomy" / "planner.py",
        "def plan():\n"
        "    return []\n",
    )
    _write(
        root / "tests" / "test_voice.py",
        "def test_voice():\n"
        "    assert True\n",
    )
    _write(root / "pyproject.toml", "[project]\nname = 'sample'\n")
    return root


def test_public_classify_remains_coarse_compatible():
    assert ask.classify("what are the biggest risks in this codebase?") == "risk"
    assert ask.classify("how does login work?") == "retrieval"
    assert ask.classify("What are the most important subsystems?") == "architecture"


def test_classify_question_detail_exposes_ru3_categories():
    detail = question_understanding.classify_question_detail(
        "Which directories contain the highest concentration of production code?"
    )
    assert detail["category"] == "production_layout"
    assert detail["coarse_mode"] == "architecture"

    detail = question_understanding.classify_question_detail(
        "Which modules have the highest number of incoming dependencies?"
    )
    assert detail["category"] == "dependency_centrality"

    detail = question_understanding.classify_question_detail(
        "Which production subsystems are most central according to the dependency graph?"
    )
    assert detail["category"] == "subsystem_centrality"

    detail = question_understanding.classify_question_detail(
        "What are the most critical architectural bottlenecks in this repository?"
    )
    assert detail["category"] == "bottleneck"


def test_ru2_architecture_battery_still_reports_architecture_mode(tmp_path):
    index = indexer.build_index(str(_repo(tmp_path)))
    questions = (
        "What are the most important subsystems?",
        "What happens when a user speaks a voice command?",
        "Which folders contain production code?",
        "List the top directories and explain them.",
    )
    for question in questions:
        result = ask.answer(index, question)
        assert result["mode"] == "architecture", question


def test_production_layout_uses_subsystem_role_counts(tmp_path):
    index = indexer.build_index(str(_repo(tmp_path)))
    result = ask.answer(
        index,
        "Which directories contain the highest concentration of production code?",
    )
    assert result["mode"] == "production_layout"
    assert "density=" in result["answer"]
    assert result["evidence"]
    assert any("subsystem map:" in item for item in result["evidence"])
    assert result["ask_quality"]["benchmark_percent"] == 0.0


def test_dependency_centrality_uses_depgraph_statistics(tmp_path):
    index = indexer.build_index(str(_repo(tmp_path)))
    result = ask.answer(
        index,
        "Which modules have the highest number of incoming dependencies?",
    )
    assert result["mode"] == "dependency"
    assert "incoming import edge" in result["answer"].lower()
    assert result["evidence"]
    assert any("imports" in item for item in result["evidence"])
    assert "core" in result["answer"].lower() or "voice" in result["answer"].lower()


def test_subsystem_centrality_uses_graph_fan_in(tmp_path):
    index = indexer.build_index(str(_repo(tmp_path)))
    result = ask.answer(
        index,
        "Which production subsystems are most central according to the dependency graph?",
    )
    assert result["mode"] == "subsystem"
    assert "fan-in=" in result["answer"]
    assert result["evidence"]
    assert any("imports edge:" in item for item in result["evidence"])


def test_bottlenecks_use_fan_in_cycles_and_components(tmp_path):
    index = indexer.build_index(str(_repo(tmp_path)))
    result = ask.answer(
        index,
        "What are the most critical architectural bottlenecks in this repository?",
    )
    assert result["mode"] == "bottleneck"
    assert "bottleneck" in result["answer"].lower()
    assert result["evidence"]
    assert any("fan-in=" in item or "import-cycle" in item for item in result["evidence"])


def test_ru3_answers_are_deterministic(tmp_path):
    index = indexer.build_index(str(_repo(tmp_path)))
    question = (
        "Which directories contain the highest concentration of production code?"
    )
    first = ask.answer(index, question)
    second = ask.answer(index, question)
    assert first["answer"] == second["answer"]
    assert first["evidence"] == second["evidence"]
