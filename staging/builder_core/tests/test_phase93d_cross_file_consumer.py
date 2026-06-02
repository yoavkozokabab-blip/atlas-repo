"""Phase 93D tests: gated cross-file consumption for inconsistent_return.

The detector reads interproc.cross_file.usage_by_callee ONLY when
CROSS_FILE_CONSUMPTION_ENABLED is True and the facts are present. Default False
== exact Phase 93B. The benchmark (single-file mode) is immune regardless of the
flag because it never produces cross-file facts.
"""

from __future__ import annotations

import os
import textwrap

import pytest

from builder_core.bug_intelligence import engine, engine_benchmark, fact_detectors

QUIXBUGS = r"C:\Repos\QuixBugs"
LEAF = "def helper(x):\n    if x:\n        return x\n"


def _write(path, content):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(textwrap.dedent(content))


def _project(tmp_path, mains: dict, util: str = LEAF):
    """mains: {filename: source}. Builds pkg/util.py + the given pkg/<main>.py files."""
    root = tmp_path / "proj"
    _write(str(root / "pkg" / "__init__.py"), "")
    _write(str(root / "pkg" / "util.py"), util)
    for fname, src in mains.items():
        _write(str(root / "pkg" / fname), src)
    return str(root)


def _helper_kinds(root):
    results = {r.file: r for r in engine.analyze_repository(root)}
    return [f.kind for f in results["pkg/util.py"].findings
            if f.rule == "inconsistent_return" and f.function == "helper"]


DEREF = "from pkg.util import helper\ndef run():\n    return helper(1).attr\n"
NULLCHK = ("from pkg.util import helper\ndef run():\n    r = helper(1)\n"
           "    if r is None:\n        return 0\n    return r.attr\n")
VALUE_ONLY = "from pkg.util import helper\ndef run():\n    return helper(1) + 1\n"
STAR = "from pkg.util import *\ndef run():\n    return helper(1).attr\n"


# ---------------------------------------------------------------------------
# Default + flag-off == 93B
# ---------------------------------------------------------------------------
def test_flag_default_is_false():
    assert fact_detectors.CROSS_FILE_CONSUMPTION_ENABLED is False


def test_flag_off_is_exact_93b(tmp_path):
    # cross-file deref-caller exists, but flag off -> intra-file only -> quarantine
    root = _project(tmp_path, {"main.py": DEREF})
    assert _helper_kinds(root) == ["pattern"]


# ---------------------------------------------------------------------------
# Flag on: cross-file evidence consumed
# ---------------------------------------------------------------------------
def test_flag_on_cross_file_deref_promotes(tmp_path, monkeypatch):
    monkeypatch.setattr(fact_detectors, "CROSS_FILE_CONSUMPTION_ENABLED", True)
    root = _project(tmp_path, {"main.py": DEREF})
    assert _helper_kinds(root) == ["value_flow"]


def test_flag_on_cross_file_null_check_quarantines(tmp_path, monkeypatch):
    monkeypatch.setattr(fact_detectors, "CROSS_FILE_CONSUMPTION_ENABLED", True)
    root = _project(tmp_path, {"main.py": NULLCHK})
    assert _helper_kinds(root) == ["pattern"]


def test_flag_on_mixed_evidence_quarantines(tmp_path, monkeypatch):
    monkeypatch.setattr(fact_detectors, "CROSS_FILE_CONSUMPTION_ENABLED", True)
    # one caller derefs, another null-checks -> any null-check vetoes
    root = _project(tmp_path, {"m1.py": DEREF, "m2.py": NULLCHK})
    assert _helper_kinds(root) == ["pattern"]


def test_flag_on_value_only_quarantines(tmp_path, monkeypatch):
    monkeypatch.setattr(fact_detectors, "CROSS_FILE_CONSUMPTION_ENABLED", True)
    root = _project(tmp_path, {"main.py": VALUE_ONLY})
    assert _helper_kinds(root) == ["pattern"]


def test_flag_on_unresolved_cross_file_ignored(tmp_path, monkeypatch):
    monkeypatch.setattr(fact_detectors, "CROSS_FILE_CONSUMPTION_ENABLED", True)
    # star import -> caller is UNRESOLVED -> contributes no usage -> not promoted
    root = _project(tmp_path, {"main.py": STAR})
    assert _helper_kinds(root) == ["pattern"]


# ---------------------------------------------------------------------------
# analyze_source (single file) unchanged even with the flag on
# ---------------------------------------------------------------------------
def test_analyze_source_unchanged_with_flag_on(monkeypatch):
    monkeypatch.setattr(fact_detectors, "CROSS_FILE_CONSUMPTION_ENABLED", True)
    res = engine.analyze_source(LEAF, "util.py")
    ir = [f for f in res.findings if f.rule == "inconsistent_return"]
    assert ir and all(f.kind == "pattern" for f in ir)  # no cross_file facts in single-file
    assert "cross_file" not in res.facts.get("interproc", {})


# ---------------------------------------------------------------------------
# Benchmark immunity (single-file mode has no cross-file facts)
# ---------------------------------------------------------------------------
@pytest.mark.skipif(not os.path.isdir(QUIXBUGS), reason="QuixBugs absent")
def test_quixbugs_unchanged_flag_off():
    r = engine_benchmark.evaluate_quixbugs_engine(QUIXBUGS)
    assert r["true_positives"] == 12 and r["false_positives"] == 0


@pytest.mark.skipif(not os.path.isdir(QUIXBUGS), reason="QuixBugs absent")
def test_quixbugs_unchanged_even_with_flag_on(monkeypatch):
    monkeypatch.setattr(fact_detectors, "CROSS_FILE_CONSUMPTION_ENABLED", True)
    r = engine_benchmark.evaluate_quixbugs_engine(QUIXBUGS)
    assert r["true_positives"] == 12 and r["false_positives"] == 0  # benchmark is single-file


@pytest.mark.skipif(not engine_benchmark._PAIRS_ROOT.is_dir(), reason="holdout absent")
def test_holdout_unchanged():
    r = engine_benchmark.evaluate_holdout_engine()
    assert r["true_positives"] == 2 and r["false_positives"] == 0


# ---------------------------------------------------------------------------
# engine_benchmark verdict logic is untouched
# ---------------------------------------------------------------------------
def test_benchmark_verdict_kinds_unchanged():
    assert engine_benchmark.BENCHMARK_VERDICT_KINDS == {"semantic", "data_flow", "value_flow"}
