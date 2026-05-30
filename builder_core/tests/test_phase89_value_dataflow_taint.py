"""Phase 89 tests: value-aware data flow + taint/security.

Asserts on value-flow FACTS and on security FINDINGS. All synthetic; no target
repo, no network, no execution of analyzed code.
"""

from __future__ import annotations

import textwrap

from builder_core.bug_intelligence import valueflow, security


def _fn(src: str):
    fns = valueflow.analyze_source(textwrap.dedent(src))["functions"]
    assert fns, "expected at least one function"
    return fns[0]


def _sec(src: str, path: str = "x.py"):
    return security.analyze_source(textwrap.dedent(src), path)


def _categories(report) -> set:
    return {f.category for f in report.findings}


# ---------------------------------------------------------------------------
# Value-flow facts
# ---------------------------------------------------------------------------
def test_reaching_defs_through_assignment():
    fn = _fn("""
        def f():
            a = 1
            b = a + 1
            return b
    """)
    rd = fn["reaching_definitions"]
    # the assignment 'a = 1' reaches the use of 'a' in 'b = a + 1' (offset-robust)
    a_def_line = next(d["line"] for d in fn["definitions"]
                      if d["name"] == "a" and d["kind"] == "assign")
    assert any("a" in uses and a_def_line in uses["a"] for uses in rd.values())


def test_minimal_cfg_has_blocks():
    fn = _fn("""
        def f(x):
            if x:
                return 1
            return 2
    """)
    assert len(fn["cfg_blocks"]) >= 2  # entry/branch + at least one successor


def test_branch_condition_facts():
    fn = _fn("""
        def f(x):
            if x > 0:
                return 1
            return -1
    """)
    assert any("x" in bc["vars"] for bc in fn["branch_conditions"])


def test_container_non_empty_after_append():
    fn = _fn("""
        def f():
            items = []
            items.append(1)
            return items
    """)
    cs = fn["container_state"]["items"]
    assert cs["state"] == "non_empty"
    assert cs["grows"] is True


def test_container_maybe_empty_when_only_created():
    fn = _fn("""
        def g():
            items = []
            return items
    """)
    assert fn["container_state"]["items"]["state"] == "maybe_empty"


def test_interval_from_range_len():
    fn = _fn("""
        def f(x):
            for i in range(len(x)):
                print(x[i])
    """)
    iv = fn["intervals"].get("i", {})
    assert iv.get("lower") == 0
    assert "len" in str(iv.get("upper_expr", ""))


# ---------------------------------------------------------------------------
# Nullability
# ---------------------------------------------------------------------------
def test_none_check_before_dereference_not_flagged():
    report = _sec("""
        def f(x=None):
            if x is not None:
                return x.value
            return 0
    """)
    assert "null_dereference" not in {f.category for f in report.value_findings}


def test_missing_none_check_before_dereference_flagged():
    report = _sec("""
        def f(x=None):
            return x.value
    """)
    assert "null_dereference" in {f.category for f in report.value_findings}


# ---------------------------------------------------------------------------
# Taint -> security findings
# ---------------------------------------------------------------------------
def test_tainted_input_into_eval():
    report = _sec("""
        def f():
            data = input()
            eval(data)
    """)
    assert "code_injection" in _categories(report)


def test_tainted_input_into_subprocess_shell_true():
    report = _sec("""
        import subprocess
        def f(cmd):
            subprocess.call(cmd, shell=True)
    """)
    assert "command_injection" in _categories(report)


def test_sql_string_concat_with_tainted_input():
    report = _sec("""
        def f(name, cursor):
            q = "SELECT * FROM users WHERE name = '" + name + "'"
            cursor.execute(q)
    """)
    assert "sql_injection" in _categories(report)


def test_safe_parameterized_sql_not_flagged():
    report = _sec("""
        def f(name, cursor):
            cursor.execute("SELECT * FROM users WHERE name = ?", (name,))
    """)
    assert "sql_injection" not in _categories(report)


def test_path_open_with_tainted_input():
    report = _sec("""
        def f(filename):
            with open(filename) as fh:
                return fh.read()
    """)
    assert "path_traversal" in _categories(report)


def test_sanitized_path_not_flagged():
    report = _sec("""
        import os
        def f(filename):
            safe = os.path.basename(filename)
            with open(safe) as fh:
                return fh.read()
    """)
    assert "path_traversal" not in _categories(report)


def test_pickle_load_on_tainted_file():
    report = _sec("""
        import pickle
        def f(path):
            with open(path, 'rb') as fh:
                return pickle.load(fh)
    """)
    assert "unsafe_deserialization" in _categories(report)


def test_md5_usage_flagged():
    report = _sec("""
        import hashlib
        def f(data):
            return hashlib.md5(data).hexdigest()
    """)
    assert "weak_crypto" in _categories(report)


# ---------------------------------------------------------------------------
# Finding schema completeness
# ---------------------------------------------------------------------------
def test_finding_schema_is_complete():
    report = _sec("""
        def f():
            eval(input())
    """)
    assert report.findings
    f = report.findings[0]
    for fieldname in ("id", "severity", "confidence", "category", "file", "line",
                      "explanation", "evidence", "why_might_be_wrong", "next_verification_step"):
        assert getattr(f, fieldname) not in (None, ""), fieldname


def test_clean_function_has_no_security_findings():
    report = _sec("""
        def add(a, b):
            total = a + b
            return total
    """)
    assert report.findings == []
