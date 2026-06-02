"""Phase 90 tests: the Unified Builder Intelligence Engine.

Covers the unified finding schema, the single analyze_file entry point, logic +
security findings flowing through one pipeline, CLI output consistency, that the
engine never modifies the target repository, and that the legacy commands still
work.
"""

from __future__ import annotations

import hashlib
import os
import textwrap

import pytest

from builder_core.bug_intelligence import engine, finding
from builder_core.bug_intelligence.finding import Finding, CATEGORIES


REQUIRED_FIELDS = (
    "id", "category", "kind", "severity", "confidence", "file", "function",
    "line", "title", "explanation", "evidence", "source_facts",
    "why_might_be_wrong", "next_verification_step", "tags",
)


def _src(code: str) -> str:
    return textwrap.dedent(code)


# ---------------------------------------------------------------------------
# Unified finding schema
# ---------------------------------------------------------------------------
def test_finding_schema_has_all_required_fields():
    f = Finding(
        category=finding.SECURITY_RISK, kind="security", severity="high",
        confidence="high", file="x.py", line=1, title="t",
        explanation="e", why_might_be_wrong="w", next_verification_step="n",
    )
    d = f.to_dict()
    for field_name in REQUIRED_FIELDS:
        assert field_name in d, field_name
    assert f.id  # auto-generated
    assert f.category in CATEGORIES


def test_unknown_category_is_coerced():
    f = Finding(category="not_a_category", kind="x", severity="low", confidence="low",
                file="x.py", line=1, title="t", explanation="e",
                why_might_be_wrong="w", next_verification_step="n")
    assert f.category == finding.UNKNOWN


def test_ranking_orders_by_weight_and_dedupes():
    a = Finding(category=finding.SECURITY_RISK, kind="security", severity="critical",
                confidence="high", file="x.py", line=5, title="a", explanation="",
                why_might_be_wrong="", next_verification_step="", rule="r1")
    b = Finding(category=finding.LOGIC_BUG, kind="pattern", severity="low",
                confidence="low", file="x.py", line=9, title="b", explanation="",
                why_might_be_wrong="", next_verification_step="", rule="r2")
    dup = Finding(category=finding.LOGIC_BUG, kind="semantic", severity="low",
                  confidence="low", file="x.py", line=5, title="a2", explanation="",
                  why_might_be_wrong="", next_verification_step="", rule="r1")
    ranked = finding.rank([b, a, dup])
    assert ranked[0] is a                      # highest weight first
    assert len([f for f in ranked if f.rule == "r1"]) == 1  # dedupe by (file,line,rule)


# ---------------------------------------------------------------------------
# Unified analyze entry point
# ---------------------------------------------------------------------------
def test_analyze_source_returns_full_result():
    res = engine.analyze_source(_src("""
        def f(a, b):
            return a + b
    """), "f.py")
    assert res.file == "f.py"
    assert res.functions == ["f"]
    assert isinstance(res.facts, dict) and "functions" in res.facts
    assert isinstance(res.findings, list)
    assert res.errors == []
    assert "counts" in res.metadata


def test_parse_error_is_captured_not_raised():
    res = engine.analyze_source("def broken(:\n  pass\n", "bad.py")
    assert res.errors
    assert res.findings == []


# ---------------------------------------------------------------------------
# Logic + security findings through one pipeline
# ---------------------------------------------------------------------------
def test_logic_finding_unguarded_container_consumption():
    res = engine.analyze_source(_src("""
        def search(start, goal):
            queue = [start]
            while True:
                node = queue.pop()
                if node is goal:
                    return True
                queue.append(node)
    """), "search.py")
    rules = {f.rule for f in res.findings}
    assert "unguarded_container_consumption" in rules
    f = next(f for f in res.findings if f.rule == "unguarded_container_consumption")
    assert f.category == finding.LOGIC_BUG


def test_security_finding_command_injection():
    res = engine.analyze_source(_src("""
        import subprocess
        def run(cmd):
            subprocess.call(cmd, shell=True)
    """), "run.py")
    sec = [f for f in res.findings if f.category == finding.SECURITY_RISK]
    assert any(f.rule == "command_injection" for f in sec)


def test_categories_present_across_pipeline():
    res = engine.analyze_source(_src("""
        import hashlib
        def breadth_first_search(start, goal):
            queue = [start]
            while True:
                node = queue.pop()
                if node is goal:
                    return True
                queue.append(node)
        def weak(data):
            return hashlib.md5(data).hexdigest()
    """), "breadth_first_search.py")
    cats = {f.category for f in res.findings}
    assert finding.LOGIC_BUG in cats
    assert finding.SECURITY_RISK in cats


# ---------------------------------------------------------------------------
# CLI output consistency
# ---------------------------------------------------------------------------
def _write(path, content):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(textwrap.dedent(content))


@pytest.fixture
def mixed_repo(tmp_path):
    root = tmp_path / "repo"
    _write(str(root / "vuln.py"), """
        import subprocess
        def run(cmd):
            subprocess.call(cmd, shell=True)
    """)
    _write(str(root / "loop.py"), """
        def search(start, goal):
            queue = [start]
            while True:
                node = queue.pop()
                if node is goal:
                    return True
                queue.append(node)
    """)
    _write(str(root / "clean.py"), """
        def add(a, b):
            return a + b
    """)
    return str(root)


SECTIONS = ("SUMMARY", "FINDINGS", "EVIDENCE", "SOURCES", "NEXT VERIFICATION STEPS")


def test_cli_analyze_file_sections(mixed_repo, capsys):
    from builder_core import cli
    assert cli.main(["analyze-file", "--project", mixed_repo, "vuln.py"]) == 0
    out = capsys.readouterr().out
    for s in SECTIONS:
        assert s in out, s
    assert "command_injection" in out


def test_cli_bug_scan_sections(mixed_repo, capsys):
    from builder_core import cli
    assert cli.main(["bug-scan", "--project", mixed_repo, "--top", "10"]) == 0
    out = capsys.readouterr().out
    for s in SECTIONS:
        assert s in out, s
    assert "loop.py" in out
    assert "clean.py" not in out


def test_cli_security_scan_sections(mixed_repo, capsys):
    from builder_core import cli
    assert cli.main(["security-scan", "--project", mixed_repo, "--top", "20"]) == 0
    out = capsys.readouterr().out
    assert "SECURITY SCAN" in out
    for s in SECTIONS:
        assert s in out, s
    assert "command_injection" in out
    assert "clean.py" not in out


# ---------------------------------------------------------------------------
# No target-repo modification
# ---------------------------------------------------------------------------
def _snapshot(root: str):
    snap = {}
    for dirpath, _dirs, files in os.walk(root):
        for fn in files:
            p = os.path.join(dirpath, fn)
            with open(p, "rb") as fh:
                snap[os.path.relpath(p, root)] = hashlib.sha1(fh.read()).hexdigest()
    return snap


def test_engine_does_not_modify_target_repo(mixed_repo, capsys):
    from builder_core import cli
    before = _snapshot(mixed_repo)
    cli.main(["analyze-file", "--project", mixed_repo, "vuln.py"])
    cli.main(["bug-scan", "--project", mixed_repo, "--top", "10"])
    cli.main(["security-scan", "--project", mixed_repo, "--top", "20"])
    capsys.readouterr()
    after = _snapshot(mixed_repo)
    assert before == after  # no files added, removed, or changed


# ---------------------------------------------------------------------------
# Legacy command compatibility
# ---------------------------------------------------------------------------
def test_legacy_commands_still_work(tmp_path, capsys):
    from builder_core import cli
    repo = tmp_path / "proj"
    _write(str(repo / "README.md"), "# Demo\nA small project.\n")
    _write(str(repo / "main.py"), "def main():\n    return 1\n")
    project = str(repo)

    assert cli.main(["init", "--project", project]) == 0
    assert cli.main(["remember", "--project", project, "we chose X because Y"]) == 0
    assert cli.main(["decisions", "--project", project]) == 0
    assert cli.main(["ask", "--project", project, "what is this project?"]) == 0
    out = capsys.readouterr().out
    assert "we chose X because Y" in out
