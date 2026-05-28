"""Code search action tests."""

from pathlib import Path

from actions.code_search import (
    FindClassAction,
    FindFunctionAction,
    SearchProjectFileByNameAction,
    _is_excluded,
)
from core.types import CommandRequest, Intent


def test_excluded_folders():
    p = Path("proj/.git/config")
    assert _is_excluded(p)
    p2 = Path("proj/src/main.py")
    assert not _is_excluded(p2)


def test_find_function_on_temp_project(tmp_path: Path, monkeypatch):
    root = tmp_path / "proj"
    (root / "pkg").mkdir(parents=True)
    (root / "pkg" / "mod.py").write_text("def generate_trades():\n    pass\n", encoding="utf-8")
    monkeypatch.setattr("actions.code_search.TRADING_PROJECT_ROOT", root)

    action = FindFunctionAction()
    req = CommandRequest(
        raw_text="find function generate_trades",
        intent=Intent.FIND_FUNCTION,
        params={"name": "generate_trades"},
    )
    result = action.execute(req)
    assert result.status.value == "success"
    assert "generate_trades" in result.summary


def test_find_class_on_temp_project(tmp_path: Path, monkeypatch):
    root = tmp_path / "proj"
    (root / "pkg").mkdir(parents=True)
    (root / "pkg" / "mod.py").write_text(
        "class PortfolioManager:\n    pass\n",
        encoding="utf-8",
    )
    monkeypatch.setattr("actions.code_search.TRADING_PROJECT_ROOT", root)

    action = FindClassAction()
    req = CommandRequest(
        raw_text="find class PortfolioManager",
        intent=Intent.FIND_CLASS,
        params={"name": "PortfolioManager"},
    )
    result = action.execute(req)
    assert result.status.value == "success"
    assert "PortfolioManager" in result.summary


def test_search_file_ignores_git(tmp_path: Path, monkeypatch):
    root = tmp_path / "proj"
    root.mkdir()
    (root / ".git").mkdir()
    (root / "fib_quality.py").write_text("x=1\n", encoding="utf-8")
    monkeypatch.setattr("actions.code_search.TRADING_PROJECT_ROOT", root)

    action = SearchProjectFileByNameAction()
    req = CommandRequest(
        raw_text="fib_quality",
        intent=Intent.SEARCH_PROJECT_FILE_BY_NAME,
        params={"query": "fib_quality"},
    )
    result = action.execute(req)
    assert result.status.value == "success"
    assert "fib_quality.py" in result.summary
