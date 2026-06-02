"""Phase 96A tests: contract fact extraction infrastructure (no findings)."""

from __future__ import annotations

import ast
import os
import textwrap

import pytest

from builder_core.bug_intelligence import (
    contract_facts,
    engine,
    engine_benchmark,
    facts,
)


def _contracts(src: str, file: str = "m.py"):
    s = textwrap.dedent(src)
    tree = ast.parse(s)
    mf = facts.extract_module_facts(s, file)
    from builder_core.bug_intelligence import callgraph, summaries
    cg = callgraph.build_call_graph(tree, file)
    mf["interproc"] = {"call_graph": cg, "summaries": summaries.compute_summaries(mf, cg)}
    return contract_facts.extract_module_contracts(mf, tree, file)


def _obligations(records, obligation=None):
    if obligation is None:
        return [r["obligation"] for r in records]
    return [r for r in records if r["obligation"] == obligation]


def test_return_type_hint_non_optional():
    c = _contracts("""
        def fetch() -> str:
            return "ok"
    """)
    ret = c["return_contracts"]
    assert _obligations(ret, "return.non_none")
    assert ret[0]["confidence"] == contract_facts.CONFIDENCE_EXPLICIT
    assert contract_facts.SOURCE_TYPE_HINT in ret[0]["sources"]


def test_return_type_hint_optional():
    c = _contracts("""
        def fetch() -> str | None:
            return None
    """)
    ret = c["return_contracts"]
    assert _obligations(ret, "return.optional")
    null = _obligations(c["nullability_contracts"], "null.allowed")
    assert null


def test_argument_type_hint_non_none():
    c = _contracts("""
        def run(name: str) -> None:
            print(name)
    """)
    args = c["argument_contracts"]
    assert any(
        r["subject"]["slot"] == "param:name" and r["obligation"] == "arg.non_none"
        for r in args
    )
    assert args[0]["confidence"] == contract_facts.CONFIDENCE_EXPLICIT


def test_docstring_raises_exception_contract():
    c = _contracts("""
        def run(x):
            '''Do work.

            Raises:
                ValueError: when x is bad.
            '''
            raise ValueError(x)
    """)
    exc = c["exception_contracts"]
    assert exc and exc[0]["obligation"] == "raises.documented"
    assert "ValueError" in exc[0]["exceptions"]


def test_assert_non_none_param():
    c = _contracts("""
        def run(x):
            assert x is not None
            return x.upper()
    """)
    args = _obligations(c["argument_contracts"], "arg.non_none")
    assert args and args[0]["sources"] == [contract_facts.SOURCE_ASSERT]


def test_caller_behavior_inferred_strong():
    c = _contracts("""
        def helper():
            return 1
        def caller():
            return helper().real
    """)
    ret = _obligations(c["return_contracts"], "return.non_none")
    caller_facts = [r for r in ret if r["sources"] == [contract_facts.SOURCE_CALLER_BEHAVIOR]]
    assert caller_facts
    assert caller_facts[0]["confidence"] == contract_facts.CONFIDENCE_INFERRED_STRONG
    assert caller_facts[0]["subject"]["qualname"] == "helper"


def test_caller_null_check_inferred_weak():
    c = _contracts("""
        def helper():
            return 1
        def caller():
            v = helper()
            if v is None:
                return 0
            return v
    """)
    ret = [r for r in c["return_contracts"] if contract_facts.SOURCE_CALLER_BEHAVIOR in r["sources"]]
    assert ret
    assert ret[0]["confidence"] == contract_facts.CONFIDENCE_INFERRED_WEAK
    assert ret[0]["obligation"] == "return.optional"


def test_callee_param_deref_contract():
    c = _contracts("""
        def run(name):
            return name.upper()
    """)
    args = [r for r in c["argument_contracts"] if contract_facts.SOURCE_CALLEE_BEHAVIOR in r["sources"]]
    assert args and args[0]["obligation"] == "arg.non_none"


def test_guard_is_not_none_narrows():
    c = _contracts("""
        def run(x):
            if x is not None:
                return x.upper()
            return ""
    """)
    guards = _obligations(c["nullability_contracts"], "null.narrowed_by_guard")
    assert guards


def test_state_init_field_read():
    c = _contracts("""
        class Worker:
            def __init__(self):
                self.name = "a"
            def run(self):
                return self.name
    """)
    state = c["state_mutation_contracts"]
    assert any(r["obligation"] == "state.initialized_before_read" for r in state)


def test_statistics_bucketed():
    c = _contracts("""
        def run(name: str) -> str:
            assert name is not None
            return name
    """)
    stats = c["statistics"]
    assert stats["total"] > 0
    assert stats["by_kind"][contract_facts.RETURN_CONTRACT] >= 1
    assert contract_facts.CONFIDENCE_EXPLICIT in stats["by_confidence"]


def test_engine_attaches_contract_facts():
    res = engine.analyze_source(textwrap.dedent("""
        def fetch() -> str:
            return "x"
    """), "m.py")
    assert "contracts" in res.facts
    assert res.facts["contracts"]["statistics"]["total"] >= 1


def test_engine_finding_count_unchanged_by_contract_layer():
    src = textwrap.dedent("""
        def find(xs, t):
            for i, x in enumerate(xs):
                if x == t:
                    return i
    """)
    before = len(engine.analyze_source(src, "x.py").findings)
    assert "contracts" in engine.analyze_source(src, "x.py").facts
    assert len(engine.analyze_source(src, "x.py").findings) == before


def test_no_confirmed_bug_category_in_findings():
    res = engine.analyze_source(textwrap.dedent("""
        def run(x):
            assert x is not None
            return x.real
    """), "m.py")
    for f in res.findings:
        assert "confirmed" not in (f.category or "").lower()
        assert "confirmed" not in (f.kind or "").lower()
        assert "confirmed" not in (f.rule or "").lower()


def test_disable_contract_facts_flag(monkeypatch):
    monkeypatch.setattr(contract_facts, "CONTRACT_FACTS_ENABLED", False)
    res = engine.analyze_source("def f() -> int:\n    return 1\n", "m.py")
    assert "contracts" not in res.facts


def test_formatter_shows_contract_summary():
    res = engine.analyze_source("def f() -> int:\n    return 1\n", "m.py")
    text = engine.format_result(res)
    assert "CONTRACT FACTS" in text
    assert "total=" in text


def test_mini_quixbugs_benchmark_unchanged(tmp_path):
    root = tmp_path / "MiniQuixBugs"
    buggy = root / "python_programs"
    correct = root / "correct_python_programs"
    buggy.mkdir(parents=True)
    correct.mkdir()
    bfs = textwrap.dedent("""
        from collections import deque as Queue
        def breadth_first_search(startnode, goalnode):
            queue = Queue()
            queue.append(startnode)
            nodesseen = set()
            nodesseen.add(startnode)
            while True:
                node = queue.popleft()
                if node is goalnode:
                    return True
                queue.extend(n for n in node.successors if n not in nodesseen)
                nodesseen.update(node.successors)
            return False
    """)
    (buggy / "breadth_first_search.py").write_text(bfs, encoding="utf-8")
    (correct / "breadth_first_search.py").write_text(
        bfs.replace("while True:", "while queue:"), encoding="utf-8")
    report = engine_benchmark.evaluate_quixbugs_engine(str(root))
    assert report["true_positives"] == 1
    assert report["false_positives"] == 0

    holdout = engine_benchmark.evaluate_holdout_engine(pairs_root=tmp_path / "nope")
    assert holdout["available"] is False


@pytest.mark.skipif(not os.path.isdir(r"C:\Repos\QuixBugs"), reason="QuixBugs absent")
def test_quixbugs_unchanged():
    report = engine_benchmark.evaluate_quixbugs_engine(r"C:\Repos\QuixBugs")
    assert report["true_positives"] == 12
    assert report["false_positives"] == 0


@pytest.mark.skipif(not engine_benchmark._PAIRS_ROOT.is_dir(), reason="holdout absent")
def test_holdout_unchanged():
    report = engine_benchmark.evaluate_holdout_engine()
    assert report["true_positives"] == 2
    assert report["false_positives"] == 0
