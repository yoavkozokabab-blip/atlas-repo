"""Phase 93C tests: cross-file interprocedural infrastructure.

Resolution is import-table-driven and single-candidate only; every star /
ambiguous / third-party / shadowed / symbol-not-found case is UNRESOLVED. Facts
live in the parallel ``interproc.cross_file`` namespace and are consumed by no
detector. The single-file path and the benchmark are unchanged.
"""

from __future__ import annotations

import os
import textwrap

import pytest

from builder_core.bug_intelligence import cross_file, engine, engine_benchmark


def _ctx(files):
    return cross_file.build_project_context([(p, textwrap.dedent(t)) for p, t in files])


def _reasons(ctx, rel):
    return {u["reason"] for u in ctx["per_file"][rel]["unresolved"]}


LEAF = "def helper(x):\n    if x:\n        return x\n"


# ---------------------------------------------------------------------------
# Resolution: resolved forms
# ---------------------------------------------------------------------------
def test_direct_import_resolves():
    ctx = _ctx([
        ("pkg/util.py", LEAF),
        ("pkg/main.py", "from pkg.util import helper\ndef run():\n    return helper(1).attr\n"),
        ("pkg/__init__.py", ""),
    ])
    edges = ctx["resolved_edges"]
    assert any(e["callee_file"] == "pkg/util.py" and e["callee"] == "helper"
               and e["usage"] == "dereferenced" for e in edges)


def test_module_import_resolves():
    ctx = _ctx([
        ("a.py", "def f():\n    if 1:\n        return 1\n"),
        ("b.py", "import a\ndef g():\n    return a.f().x\n"),
    ])
    assert any(e["callee_file"] == "a.py" and e["callee"] == "f" for e in ctx["resolved_edges"])


def test_relative_import_resolves():
    ctx = _ctx([
        ("pkg/__init__.py", ""),
        ("pkg/util.py", LEAF),
        ("pkg/main.py", "from .util import helper\ndef run():\n    return helper(1).attr\n"),
    ])
    assert any(e["callee_file"] == "pkg/util.py" and e["callee"] == "helper"
               for e in ctx["resolved_edges"])


# ---------------------------------------------------------------------------
# Resolution: explicit UNRESOLVED
# ---------------------------------------------------------------------------
def test_star_import_unresolved():
    ctx = _ctx([
        ("a.py", "def f():\n    return 1\n"),
        ("c.py", "from a import *\ndef g():\n    return f().x\n"),
    ])
    assert ctx["resolved_edges"] == []
    assert "star_import" in _reasons(ctx, "c.py")


def test_ambiguous_import_unresolved():
    ctx = _ctx([
        ("a.py", "def f():\n    return 1\n"),
        ("b.py", "def f():\n    return 1\n"),
        ("c.py", "from a import f\nfrom b import f\ndef g():\n    return f().x\n"),
    ])
    assert ctx["resolved_edges"] == []
    assert "ambiguous_import" in _reasons(ctx, "c.py")


def test_third_party_import_unresolved():
    ctx = _ctx([
        ("c.py", "from os import getcwd\ndef g():\n    return getcwd().x\n"),
    ])
    assert ctx["resolved_edges"] == []
    assert "third_party_or_unknown_module" in _reasons(ctx, "c.py")


def test_shadowed_imported_name_unresolved():
    ctx = _ctx([
        ("a.py", "def f():\n    return 1\n"),
        ("c.py", "from a import f\ndef g(f):\n    return f().x\n"),
    ])
    assert ctx["resolved_edges"] == []
    assert "shadowed" in _reasons(ctx, "c.py")


def test_symbol_not_found_unresolved():
    ctx = _ctx([
        ("a.py", "def f():\n    return 1\n"),
        ("c.py", "from a import missing\ndef g():\n    return missing().x\n"),
    ])
    assert ctx["resolved_edges"] == []
    assert "symbol_not_found" in _reasons(ctx, "c.py")


# ---------------------------------------------------------------------------
# Determinism
# ---------------------------------------------------------------------------
def test_resolution_is_deterministic():
    files = [
        ("a.py", "def f():\n    if 1:\n        return 1\n"),
        ("b.py", "from a import f\ndef g():\n    return f().x\n"),
    ]
    assert _ctx(files)["resolved_edges"] == _ctx(files)["resolved_edges"]


def test_cross_file_cycle_terminates():
    # mutual cross-file calls must not hang context construction
    ctx = _ctx([
        ("a.py", "from b import bb\ndef aa():\n    return bb()\n"),
        ("b.py", "from a import aa\ndef bb():\n    return aa()\n"),
    ])
    assert len(ctx["resolved_edges"]) == 2


# ---------------------------------------------------------------------------
# Engine integration: project mode attaches; single file does not
# ---------------------------------------------------------------------------
def _write(path, content):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(textwrap.dedent(content))


@pytest.fixture
def mini_project(tmp_path):
    root = tmp_path / "proj"
    _write(str(root / "pkg" / "__init__.py"), "")
    _write(str(root / "pkg" / "util.py"), LEAF)
    _write(str(root / "pkg" / "main.py"),
           "from pkg.util import helper\ndef run():\n    return helper(1).attr\n")
    return str(root)


def test_single_file_has_no_cross_file_key():
    res = engine.analyze_source(LEAF, "util.py")
    assert "cross_file" not in res.facts.get("interproc", {})


def test_project_mode_attaches_cross_file(mini_project):
    results = {r.file: r for r in engine.analyze_repository(mini_project)}
    util = results["pkg/util.py"]
    cf = util.facts.get("interproc", {}).get("cross_file")
    assert cf and cf["enabled"] is True
    # helper is dereferenced by a cross-file caller (the fact a future consumer needs)
    assert cf["usage_by_callee"].get("helper", {}).get("dereferenced") is True


def test_no_detector_consumes_cross_file(mini_project):
    # helper has the missing-return shape AND a cross-file deref-caller, but the
    # inconsistent_return detector reads INTRA-file usage only -> stays quarantined.
    results = {r.file: r for r in engine.analyze_repository(mini_project)}
    util = results["pkg/util.py"]
    ir = [f for f in util.findings if f.rule == "inconsistent_return" and f.function == "helper"]
    assert ir, "expected the intraprocedural missing-return finding"
    assert all(f.kind == "pattern" for f in ir)  # NOT promoted by cross-file facts


def test_feature_flag_disables_all_cross_file(mini_project, monkeypatch):
    monkeypatch.setattr(cross_file, "CROSS_FILE_ENABLED", False)
    for r in engine.analyze_repository(mini_project):
        assert "cross_file" not in r.facts.get("interproc", {})


# ---------------------------------------------------------------------------
# Benchmark parity
# ---------------------------------------------------------------------------
@pytest.mark.skipif(not os.path.isdir(r"C:\Repos\QuixBugs"), reason="QuixBugs absent")
def test_quixbugs_parity():
    r = engine_benchmark.evaluate_quixbugs_engine(r"C:\Repos\QuixBugs")
    assert r["true_positives"] == 12 and r["false_positives"] == 0


@pytest.mark.skipif(not engine_benchmark._PAIRS_ROOT.is_dir(), reason="holdout absent")
def test_holdout_parity():
    r = engine_benchmark.evaluate_holdout_engine()
    assert r["true_positives"] == 2 and r["false_positives"] == 0
