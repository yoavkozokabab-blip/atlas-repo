"""Phase 82 Builder Core CLI MVP tests."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from builder_core import cli, store


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _fake_repo(tmp_path: Path) -> Path:
    root = tmp_path / "fake_repo"
    _write(root / "README.md", "# Fake Repo\n\nA small Python graph algorithms project.\n")
    _write(
        root / "python_programs" / "breadth_first_search.py",
        "def breadth_first_search(startnode, goalnode):\n"
        "    queue = [startnode]\n"
        "    nodesseen = {startnode}\n"
        "    while queue:\n"
        "        node = queue.pop(0)\n"
        "        if node is goalnode:\n"
        "            return True\n"
        "        queue.extend(node.successors)\n"
        "        nodesseen.update(node.successors)\n"
        "    return False\n",
    )
    _write(
        root / "python_programs" / "off_by_one.py",
        "def last_item(items):\n"
        "    for index in range(len(items) + 1):\n"
        "        return items[index]\n",
    )
    _write(
        root / "tests" / "test_graph.py",
        "def test_placeholder():\n"
        "    assert True\n",
    )
    return root


def test_cli_init_creates_memory_and_preserves_sources(tmp_path, capsys):
    root = _fake_repo(tmp_path)
    source = root / "python_programs" / "breadth_first_search.py"
    before_hash = _sha256(source)
    before_paths = {
        path.relative_to(root).as_posix()
        for path in root.rglob("*")
        if path.is_file()
    }

    assert cli.main(["init", "--project", str(root)]) == 0
    output = capsys.readouterr().out

    assert "project type: python" in output
    assert (root / ".jarvis_builder" / "index.json").is_file()
    assert _sha256(source) == before_hash
    after_paths = {
        path.relative_to(root).as_posix()
        for path in root.rglob("*")
        if path.is_file() and ".jarvis_builder" not in path.parts
    }
    assert after_paths == before_paths


def test_cli_ask_returns_bug_findings_with_required_sections(tmp_path, capsys):
    root = _fake_repo(tmp_path)
    assert cli.main(["init", "--project", str(root)]) == 0
    capsys.readouterr()

    question = (
        "Analyze python_programs/breadth_first_search.py "
        "for likely bugs and logic errors."
    )
    assert cli.main(["ask", "--project", str(root), question]) == 0
    output = capsys.readouterr().out

    assert "ANSWER" in output
    assert "FINDINGS" in output
    assert "EVIDENCE" in output
    assert "SOURCES" in output
    assert "algorithmic_mismatch" in output
    assert "visited-membership filter" in output
    assert "python_programs/breadth_first_search.py" in output


def test_risk_report_ranks_suspicious_python_files(tmp_path, capsys):
    root = _fake_repo(tmp_path)
    assert cli.main(["init", "--project", str(root)]) == 0
    capsys.readouterr()

    assert cli.main(["risk-report", "--project", str(root), "--top", "10"]) == 0
    output = capsys.readouterr().out

    assert "RISK REPORT" in output
    assert "python_programs/breadth_first_search.py" in output
    assert "python_programs/off_by_one.py" in output
    assert "off_by_one_risk" in output


def test_index_contains_python_ast_metadata(tmp_path):
    root = _fake_repo(tmp_path)
    assert cli.main(["init", "--project", str(root)]) == 0
    index = store.load_index(str(root))

    assert index is not None
    assert index["project_type"]["primary"] == "python"
    analyses = {item["path"]: item for item in index["python_analysis"]}
    bfs = analyses["python_programs/breadth_first_search.py"]
    assert bfs["functions"][0]["name"] == "breadth_first_search"
    assert any(item["rule"] == "algorithmic_mismatch" for item in bfs["findings"])


def test_index_json_is_the_only_init_write(tmp_path):
    root = _fake_repo(tmp_path)
    assert cli.main(["init", "--project", str(root)]) == 0

    memory_files = {
        path.relative_to(root / ".jarvis_builder").as_posix()
        for path in (root / ".jarvis_builder").rglob("*")
        if path.is_file()
    }
    assert memory_files == {"index.json"}
    json.loads((root / ".jarvis_builder" / "index.json").read_text(encoding="utf-8"))
