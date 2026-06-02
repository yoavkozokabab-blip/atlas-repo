"""Phase 94D tests: proven intra-file method call resolution."""

from __future__ import annotations

import ast
import textwrap

import pytest

from builder_core.bug_intelligence import callgraph, depgraph, engine_benchmark, impact


def _cg(src: str, file: str = "m.py"):
    return callgraph.build_call_graph(ast.parse(textwrap.dedent(src)), file)


def _graph(root: str, files):
    return depgraph.build_graph_from_files(root, [(p, textwrap.dedent(t)) for p, t in files])


def test_self_method_call_resolved():
    cg = _cg("""
        class Worker:
            def run(self):
                return self.helper()
            def helper(self):
                return 1
    """)
    assert cg["edges"].get("Worker.run") == ["Worker.helper"]
    assert cg["unresolved_count"] == 0


def test_cls_classmethod_resolved():
    cg = _cg("""
        class Worker:
            @classmethod
            def build(cls):
                return cls.factory()
            @classmethod
            def factory(cls):
                return 1
    """)
    assert cg["edges"].get("Worker.build") == ["Worker.factory"]


def test_local_instance_method_resolved():
    cg = _cg("""
        class Worker:
            def helper(self):
                return 1
        def run():
            obj = Worker()
            return obj.helper()
    """)
    assert cg["edges"].get("run") == ["Worker.helper"]


def test_class_name_method_resolved():
    cg = _cg("""
        class Worker:
            @classmethod
            def factory(cls):
                return 1
        def run():
            return Worker.factory()
    """)
    assert cg["edges"].get("run") == ["Worker.factory"]


def test_parameter_receiver_stays_unresolved():
    cg = _cg("""
        class Worker:
            def helper(self):
                return 1
        def run(o):
            return o.helper()
    """)
    assert cg["edges"].get("run") is None
    assert cg["unresolved_count"] == 1


def test_reassigned_instance_stays_unresolved():
    cg = _cg("""
        class A:
            def f(self):
                return 1
        class B:
            def f(self):
                return 2
        def run():
            obj = A()
            obj = B()
            return obj.f()
    """)
    assert cg["edges"].get("run") is None
    assert cg["unresolved_count"] >= 1


def test_super_call_stays_unresolved():
    cg = _cg("""
        class Base:
            def f(self):
                return 1
        class Sub(Base):
            def g(self):
                return super().f()
    """)
    assert cg["edges"].get("Sub.g") is None
    assert cg["unresolved_count"] >= 1


def test_depgraph_intra_file_method_edge():
    graph = _graph("/repo", [
        ("svc.py", """
            class Service:
                def run(self):
                    return self.compute()
                def compute(self):
                    return 1
        """),
    ])
    calls = [e for e in graph["edges"] if e["type"] == "calls"]
    assert any(
        e["from"] == "function:svc.py::Service.run"
        and e["to"] == "function:svc.py::Service.compute"
        and e.get("scope") == "intra_file"
        for e in calls
    )


def test_execution_path_reaches_method_via_self(monkeypatch, tmp_path):
    root = tmp_path / "proj"
    root.mkdir()
    (root / "main.py").write_text(textwrap.dedent("""
        class App:
            def start(self):
                return self.run()
            def run(self):
                return 1
    """), encoding="utf-8")
    result = impact.build_and_analyze(
        str(root),
        kind="function",
        function="main.py::App.run",
    )
    paths = result["questions"]["execution_paths"]
    assert paths
    assert paths[0][-1] == "function:main.py::App.run"


def test_method_resolution_disable_restores_conservatism(monkeypatch):
    monkeypatch.setattr(callgraph, "METHOD_RESOLUTION_ENABLED", False)
    cg = _cg("""
        class Worker:
            def run(self):
                return self.helper()
            def helper(self):
                return 1
    """)
    assert cg["edges"].get("Worker.run") is None
    assert cg["unresolved_count"] == 1


def test_benchmark_unchanged(tmp_path):
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


def test_nested_closure_self_method_resolved():
    cg = _cg("""
        class Worker:
            def run(self):
                def inner():
                    return self.helper()
                return inner()
            def helper(self):
                return 1
    """)
    assert cg["edges"].get("Worker.run.inner") == ["Worker.helper"]


def test_nested_class_classname_method_resolved():
    cg = _cg("""
        class Outer:
            class Inner:
                @classmethod
                def build(cls):
                    return 1
            def run(self):
                return Inner.build()
    """)
    assert cg["edges"].get("Outer.run") == ["Outer.Inner.build"]


def test_nested_class_instance_binding_resolved():
    cg = _cg("""
        class Outer:
            class Inner:
                def ping(self):
                    return 1
            def run(self):
                obj = Inner()
                return obj.ping()
    """)
    assert cg["edges"].get("Outer.run") == ["Outer.Inner.ping"]


def test_ambiguous_nested_class_name_stays_unresolved():
    cg = _cg("""
        class Outer:
            class Inner:
                def ping(self):
                    return 1
            class Mid:
                class Inner:
                    def ping(self):
                        return 2
            def run(self):
                obj = Inner()
                return obj.ping()
    """)
    assert cg["edges"].get("Outer.run") is None
    assert cg["unresolved_count"] >= 1


def test_inherited_method_stays_unresolved():
    cg = _cg("""
        class Base:
            def helper(self):
                return 1
        class Sub(Base):
            def run(self):
                return self.helper()
    """)
    assert cg["edges"].get("Sub.run") is None
    assert cg["unresolved_count"] >= 1


def test_nested_class_not_visible_at_module_level():
    cg = _cg("""
        class Outer:
            class Inner:
                @classmethod
                def build(cls):
                    return 1
        def run():
            return Inner.build()
    """)
    assert cg["edges"].get("run") is None
    assert cg["unresolved_count"] >= 1


def test_walrus_instance_binding_resolved():
    cg = _cg("""
        class Worker:
            def helper(self):
                return 1
        def run():
            if (obj := Worker()):
                return obj.helper()
            return 0
    """)
    assert cg["edges"].get("run") == ["Worker.helper"]
