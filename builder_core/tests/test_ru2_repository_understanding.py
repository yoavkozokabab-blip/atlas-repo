"""RU-2 repository-understanding regressions."""

from __future__ import annotations

from pathlib import Path

from builder_core import ask, cli, indexer, repository_understanding, retrieval


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _repo(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    _write(root / "README.md", "# Product\n\nLocal assistant runtime.\n")
    _write(
        root / "README_ARCHITECTURE.md",
        "# Architecture\n\nVoice commands enter the runtime and route through core services.\n",
    )
    _write(
        root / "main.py",
        '"""Application entry point for the local assistant."""\n'
        "from core.app import run\n",
    )
    _write(
        root / "core" / "app.py",
        '"""Shared runtime bootstrap and command dispatch."""\n'
        "def run():\n"
        "    return True\n",
    )
    _write(
        root / "voice" / "voice_loop.py",
        '"""Wake listener and voice command loop."""\n'
        "from core.app import run\n\n"
        "def handle_voice_command():\n"
        "    return run()\n",
    )
    _write(
        root / "browser" / "runtime.py",
        '"""Browser runtime facade."""\n'
        "from core.app import run\n\n"
        "def open_page():\n"
        "    return run()\n",
    )
    _write(
        root / "autonomy" / "planner.py",
        '"""Bounded autonomy planner."""\n'
        "def plan():\n"
        "    return []\n",
    )
    _write(
        root / "reports" / "phase_old.md",
        "# Benchmark History\n\n"
        "BugsInPy pandas thefuck voice command architecture subsystem benchmark report.\n",
    )
    _write(
        root / "data" / "external_benchmarks" / "bugsinpy_pandas" / "buggy.py",
        '"""BugsInPy pandas thefuck voice command architecture subsystem."""\n'
        "def broken():\n"
        "    return False\n",
    )
    _write(
        root / "tests" / "test_voice.py",
        "def test_voice_command():\n"
        "    assert True\n",
    )
    _write(root / "pyproject.toml", "[project]\nname = 'sample'\n")
    return root


def test_role_classifier_covers_ru2_roles():
    classify = repository_understanding.classify_file_role
    assert classify("voice/voice_loop.py") == "production_code"
    assert classify("tests/test_voice.py") == "test"
    assert classify("builder_core/benchmarks/holdout/pairs/x/buggy.py") == "benchmark"
    assert classify("python_programs/search.py") == "production_code"
    assert classify("python_programs/search.py", project_root="C:/Repos/QuixBugs") == "benchmark"
    assert classify("data/sample.json") == "dataset"
    assert classify("generated/client.py") == "generated"
    assert classify("reports/phase95.md") == "report_history"
    assert classify("README_ARCHITECTURE.md") == "architecture_doc"
    assert classify("README.md") == "general_doc"
    assert classify("pyproject.toml") == "config"
    assert classify("image.png") == "unknown"


def test_index_stores_roles_and_deterministic_subsystem_map(tmp_path):
    root = _repo(tmp_path)
    first = indexer.build_index(str(root))
    second = indexer.build_index(str(root))
    files = {item["path"]: item for item in first["files"]}
    assert files["voice/voice_loop.py"]["role"] == "production_code"
    assert files["reports/phase_old.md"]["role"] == "report_history"
    assert files["data/external_benchmarks/bugsinpy_pandas/buggy.py"]["role"] == "benchmark"
    assert files["pyproject.toml"]["role"] == "config"
    assert first["subsystems"] == second["subsystems"]
    subsystems = {item["name"]: item for item in first["subsystems"]}
    assert subsystems["voice"]["entry_files"] == ["voice/voice_loop.py"]
    assert subsystems["voice"]["dependencies"] == ["core"]


def test_architecture_retrieval_enforces_source_caps(tmp_path):
    index = indexer.build_index(str(_repo(tmp_path)))
    hits = retrieval.search(index, "What happens when a user speaks a voice command?", limit=6)
    assert hits
    metrics = retrieval.source_distribution_for_chunks([item[0] for item in hits])
    assert metrics["reports_percent"] <= 20.0
    assert metrics["benchmark_percent"] == 0.0
    assert metrics["production_percent"] + metrics["architecture_percent"] >= 50.0
    assert not any("bugsinpy" in item[0]["path"].lower() for item in hits)


def test_architecture_questions_answer_from_real_subsystems(tmp_path):
    index = indexer.build_index(str(_repo(tmp_path)))
    questions = (
        "What are the most important subsystems?",
        "What happens when a user speaks a voice command?",
        "Which folders contain production code?",
        "List the top directories and explain them.",
    )
    answers = [ask.answer(index, question) for question in questions]
    for result in answers:
        text = " ".join([result["answer"], *result["evidence"], *result["sources"]]).lower()
        assert result["mode"] == "architecture"
        assert result["sources"]
        assert "bugsinpy" not in text
        assert "pandas" not in text
        assert "thefuck" not in text
        assert result["ask_quality"]["benchmark_percent"] == 0.0
        assert (
            result["ask_quality"]["production_percent"]
            + result["ask_quality"]["architecture_percent"]
            >= 50.0
        )
    assert "voice" in answers[1]["answer"].lower()
    assert any(source.startswith("voice/") for source in answers[1]["sources"])


def test_cli_ask_prints_quality_report(tmp_path, capsys):
    root = _repo(tmp_path)
    assert cli.main(["init", "--project", str(root)]) == 0
    capsys.readouterr()
    assert cli.main([
        "ask",
        "--project",
        str(root),
        "What are the most important subsystems?",
    ]) == 0
    output = capsys.readouterr().out
    assert "ASK QUALITY" in output
    assert "- production:" in output
    assert "- architecture:" in output
    assert "- reports:" in output
    assert "- benchmarks:" in output
