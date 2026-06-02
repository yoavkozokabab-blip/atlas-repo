"""Tests for the standalone Builder Core CLI MVP.

All tests operate on a synthetic repo created under pytest's tmp_path, so they
never touch the real JARVIS tree and never require network or an LLM.
"""

from __future__ import annotations

import json
import os
import subprocess

import pytest

from builder_core import (
    ask as ask_mod,
    decisions as dec_mod,
    indexer,
    retrieval,
    risk,
    store,
    topics,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
def _write(path, content):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(content)


@pytest.fixture
def fake_repo(tmp_path):
    """A minimal but realistic project: README, src, tests, docs."""
    root = tmp_path / "sample_project"
    _write(
        str(root / "README.md"),
        "# Sample Project\n\n"
        "This service handles user authentication using JWT tokens.\n\n"
        "## Architecture\n\n"
        "The API layer talks to a Postgres database via a repository layer.\n",
    )
    _write(
        str(root / "src" / "auth.py"),
        '"""Authentication module using JWT."""\n\n'
        "def login(user, password):\n"
        "    # TODO: add rate limiting\n"
        "    return True\n\n"
        "def issue_token(user):\n"
        "    return 'jwt-token'\n",
    )
    _write(
        str(root / "src" / "payments.py"),
        '"""Payment processing — handles charges."""\n\n'
        "def charge(amount):\n"
        "    return amount\n" + ("# filler line\n" * 200),
    )
    _write(
        str(root / "tests" / "test_auth.py"),
        "from src.auth import login\n\n"
        "def test_login():\n"
        "    assert login('u', 'p') is True\n",
    )
    _write(
        str(root / "docs" / "design.md"),
        "# Design\n\nWe use a layered architecture to keep coupling low.\n",
    )
    return str(root)


@pytest.fixture
def git_repo(fake_repo):
    """Turn the fake repo into a git repo with one commit (skips if no git)."""
    env = dict(os.environ, GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@t",
               GIT_COMMITTER_NAME="t", GIT_COMMITTER_EMAIL="t@t")

    def run(*args):
        return subprocess.run(["git", *args], cwd=fake_repo, env=env,
                              capture_output=True, text=True)

    init = run("init")
    if init.returncode != 0:
        pytest.skip("git not available")
    run("add", "-A")
    commit = run("commit", "-m", "initial commit")
    if commit.returncode != 0:
        pytest.skip("git commit failed in sandbox")
    return fake_repo


# ---------------------------------------------------------------------------
# Indexer
# ---------------------------------------------------------------------------
def test_index_categorizes_files(fake_repo):
    index = indexer.build_index(fake_repo)
    stats = index["stats"]
    assert stats["readme"] == 1
    assert stats["src"] == 2
    assert stats["test"] == 1
    assert stats["docs"] == 1
    paths = {f["path"] for f in index["files"]}
    assert "src/auth.py" in paths
    assert "tests/test_auth.py" in paths


def test_index_is_written_under_jarvis_builder(fake_repo):
    index = indexer.build_index(fake_repo)
    path = store.save_index(fake_repo, index)
    assert os.path.basename(path) == "index.json"
    assert ".jarvis_builder" in path
    assert os.path.exists(path)
    # round-trips as valid JSON
    with open(path, encoding="utf-8") as fh:
        loaded = json.load(fh)
    assert loaded["stats"]["files"] == index["stats"]["files"]


def test_index_only_writes_inside_memory_dir(fake_repo):
    before = set(os.listdir(fake_repo))
    index = indexer.build_index(fake_repo)
    store.save_index(fake_repo, index)
    after = set(os.listdir(fake_repo))
    # the only new top-level entry is the memory dir
    assert after - before == {".jarvis_builder"}


# ---------------------------------------------------------------------------
# Retrieval + ask
# ---------------------------------------------------------------------------
def test_retrieval_finds_auth(fake_repo):
    index = indexer.build_index(fake_repo)
    hits = retrieval.search(index, "how does authentication work?")
    assert hits, "expected at least one hit"
    top_paths = {h[0]["path"] for h in hits}
    assert any("auth" in p or "README" in p for p in top_paths)


def test_ask_retrieval_returns_answer_evidence_sources(fake_repo):
    index = indexer.build_index(fake_repo)
    result = ask_mod.answer(index, "how does authentication work?")
    assert result["mode"] == "retrieval"
    assert result["answer"]
    assert result["evidence"]
    assert result["sources"]


def test_ask_risk_mode_is_classified(fake_repo):
    assert ask_mod.classify("what are the biggest risks in this codebase?") == "risk"
    assert ask_mod.classify("how does login work?") == "retrieval"


def test_ask_risk_surfaces_untested_or_large_files(fake_repo):
    index = indexer.build_index(fake_repo)
    result = ask_mod.answer(index, "what are the biggest risks in this codebase?")
    assert result["mode"] == "risk"
    assert result["answer"]
    # payments.py is large and untested -> must appear somewhere
    joined = " ".join(result["evidence"]) + " ".join(result["sources"])
    assert "payments.py" in joined


# ---------------------------------------------------------------------------
# Risk signals
# ---------------------------------------------------------------------------
def test_risk_flags_untested_large_file(fake_repo):
    index = indexer.build_index(fake_repo)
    signals = risk.compute_risks(index)
    types = {s["type"] for s in signals}
    # payments.py has 200+ lines and no test referencing 'payments'
    assert "large_file" in types or "coverage_gap" in types


def test_risk_no_tests_signal(tmp_path):
    root = tmp_path / "untested"
    _write(str(root / "src" / "main.py"), "def run():\n    return 1\n")
    index = indexer.build_index(str(root))
    signals = risk.compute_risks(index)
    assert any(s["type"] == "no_tests" for s in signals)


# ---------------------------------------------------------------------------
# Topics
# ---------------------------------------------------------------------------
def test_topic_inference():
    assert topics.infer_topic("we chose Postgres over MySQL for the database") == "database"
    assert topics.infer_topic("switched auth to JWT tokens") == "authentication"
    assert topics.infer_topic("the weather is nice today") == "general"


# ---------------------------------------------------------------------------
# Decisions
# ---------------------------------------------------------------------------
def test_remember_and_list_without_git(fake_repo):
    rec = dec_mod.remember(fake_repo, "we chose Postgres because of PostGIS")
    assert rec["topic"] == "database"
    assert rec["text"].startswith("we chose Postgres")
    assert rec["timestamp"]
    listed = dec_mod.list_decisions(fake_repo)
    assert len(listed) == 1
    assert listed[0]["id"] == rec["id"]


def test_remember_appends(fake_repo):
    dec_mod.remember(fake_repo, "decision one about the api")
    dec_mod.remember(fake_repo, "decision two about testing")
    listed = dec_mod.list_decisions(fake_repo)
    assert len(listed) == 2
    assert listed[0]["text"] != listed[1]["text"]


def test_remember_rejects_empty(fake_repo):
    with pytest.raises(ValueError):
        dec_mod.remember(fake_repo, "   ")


# ---------------------------------------------------------------------------
# Git-aware behaviour (skips cleanly if git is unavailable)
# ---------------------------------------------------------------------------
def test_index_captures_git_metadata(git_repo):
    index = indexer.build_index(git_repo)
    assert index["git"]["is_repo"] is True
    assert index["git"]["commit"]
    assert index["git_log"], "expected at least one commit in the log"


def test_remember_captures_commit(git_repo):
    rec = dec_mod.remember(git_repo, "we chose a layered architecture")
    assert rec["git_commit"], "expected a commit hash to be captured"
    assert rec["topic"] == "architecture"


# ---------------------------------------------------------------------------
# CLI end-to-end (in-process)
# ---------------------------------------------------------------------------
def test_cli_init_ask_remember_decisions(fake_repo, capsys):
    from builder_core import cli

    assert cli.main(["init", "--project", fake_repo]) == 0
    out = capsys.readouterr().out
    assert "Indexed project" in out

    assert cli.main(["ask", "--project", fake_repo, "what are the biggest risks?"]) == 0
    out = capsys.readouterr().out
    assert "ANSWER" in out and "EVIDENCE" in out and "SOURCES" in out

    assert cli.main(["remember", "--project", fake_repo, "we chose X because Y"]) == 0
    out = capsys.readouterr().out
    assert "Decision stored" in out

    assert cli.main(["decisions", "--project", fake_repo]) == 0
    out = capsys.readouterr().out
    assert "we chose X because Y" in out


def test_cli_ask_without_index_errors(fake_repo):
    from builder_core import cli

    # no init performed -> ask should return non-zero
    rc = cli.main(["ask", "--project", fake_repo, "anything"])
    assert rc == 2
