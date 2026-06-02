"""Phase 94E tests: explicit, conservative cross-file callable exports."""

from __future__ import annotations

import textwrap

from builder_core.bug_intelligence import cross_file, depgraph


def _ctx(files):
    return cross_file.build_project_context(
        [(path, textwrap.dedent(source)) for path, source in files]
    )


def _resolved(ctx, caller_file: str, callee_file: str, callee: str) -> bool:
    return any(
        edge["caller_file"] == caller_file
        and edge["callee_file"] == callee_file
        and edge["callee"] == callee
        for edge in ctx["resolved_edges"]
    )


def _reasons(ctx, rel: str):
    return {item["reason"] for item in ctx["per_file"][rel]["unresolved"]}


def test_direct_import_explicit_constructor_resolves():
    ctx = _ctx([
        ("models.py", """
            class Widget:
                def __init__(self):
                    self.ready = True
        """),
        ("main.py", """
            from models import Widget
            def build():
                return Widget()
        """),
    ])
    assert _resolved(ctx, "main.py", "models.py", "Widget.__init__")


def test_module_handle_explicit_constructor_resolves():
    ctx = _ctx([
        ("models.py", """
            class Widget:
                def __init__(self):
                    self.ready = True
        """),
        ("main.py", """
            import models
            def build():
                return models.Widget()
        """),
    ])
    assert _resolved(ctx, "main.py", "models.py", "Widget.__init__")


def test_explicit_package_reexport_resolves_direct_import():
    ctx = _ctx([
        ("pkg/__init__.py", "from .util import helper\n"),
        ("pkg/util.py", "def helper():\n    return 1\n"),
        ("main.py", """
            from pkg import helper
            def run():
                return helper()
        """),
    ])
    assert _resolved(ctx, "main.py", "pkg/util.py", "helper")


def test_explicit_package_reexport_resolves_module_handle():
    ctx = _ctx([
        ("pkg/__init__.py", "from .util import helper\n"),
        ("pkg/util.py", "def helper():\n    return 1\n"),
        ("main.py", """
            import pkg
            def run():
                return pkg.helper()
        """),
    ])
    assert _resolved(ctx, "main.py", "pkg/util.py", "helper")


def test_package_reexport_alias_is_explicit_and_resolves():
    ctx = _ctx([
        ("pkg/__init__.py", "from .util import helper as public_helper\n"),
        ("pkg/util.py", "def helper():\n    return 1\n"),
        ("main.py", """
            from pkg import public_helper
            def run():
                return public_helper()
        """),
    ])
    assert _resolved(ctx, "main.py", "pkg/util.py", "helper")


def test_default_or_inherited_constructor_stays_unresolved():
    ctx = _ctx([
        ("models.py", """
            class Widget:
                pass
        """),
        ("main.py", """
            from models import Widget
            def build():
                return Widget()
        """),
    ])
    assert ctx["resolved_edges"] == []
    assert "symbol_not_found" in _reasons(ctx, "main.py")


def test_runtime_assignment_export_stays_unresolved():
    ctx = _ctx([
        ("pkg/__init__.py", "from . import util\nhelper = util.helper\n"),
        ("pkg/util.py", "def helper():\n    return 1\n"),
        ("main.py", """
            from pkg import helper
            def run():
                return helper()
        """),
    ])
    assert ctx["resolved_edges"] == []
    assert "symbol_not_found" in _reasons(ctx, "main.py")


def test_implicit_package_magic_stays_unresolved():
    ctx = _ctx([
        ("pkg/__init__.py", ""),
        ("pkg/helper.py", "def helper():\n    return 1\n"),
        ("main.py", """
            from pkg import helper
            def run():
                return helper()
        """),
    ])
    assert ctx["resolved_edges"] == []
    assert "symbol_not_found" in _reasons(ctx, "main.py")


def test_non_package_reexport_stays_unresolved():
    ctx = _ctx([
        ("impl.py", "def helper():\n    return 1\n"),
        ("api.py", "from impl import helper\n"),
        ("main.py", """
            from api import helper
            def run():
                return helper()
        """),
    ])
    assert ctx["resolved_edges"] == []
    assert "symbol_not_found" in _reasons(ctx, "main.py")


def test_dynamic_import_export_stays_unresolved():
    ctx = _ctx([
        ("pkg/__init__.py", """
            import importlib
            helper = importlib.import_module("pkg.util").helper
        """),
        ("pkg/util.py", "def helper():\n    return 1\n"),
        ("main.py", """
            from pkg import helper
            def run():
                return helper()
        """),
    ])
    assert ctx["resolved_edges"] == []
    assert "symbol_not_found" in _reasons(ctx, "main.py")


def test_ambiguous_package_reexport_stays_unresolved():
    ctx = _ctx([
        ("pkg/__init__.py", "from .a import helper\nfrom .b import helper\n"),
        ("pkg/a.py", "def helper():\n    return 1\n"),
        ("pkg/b.py", "def helper():\n    return 2\n"),
        ("main.py", """
            from pkg import helper
            def run():
                return helper()
        """),
    ])
    assert ctx["resolved_edges"] == []
    assert "symbol_not_found" in _reasons(ctx, "main.py")


def test_star_import_stays_unresolved():
    ctx = _ctx([
        ("pkg/__init__.py", "from .util import *\n"),
        ("pkg/util.py", "def helper():\n    return 1\n"),
        ("main.py", """
            from pkg import helper
            def run():
                return helper()
        """),
    ])
    assert ctx["resolved_edges"] == []
    assert "symbol_not_found" in _reasons(ctx, "main.py")


def test_depgraph_constructor_edge_targets_real_init_function():
    graph = depgraph.build_graph_from_files("/repo", [
        ("models.py", textwrap.dedent("""
            class Widget:
                def __init__(self):
                    self.ready = True
        """)),
        ("main.py", textwrap.dedent("""
            from models import Widget
            def build():
                return Widget()
        """)),
    ])
    calls = [edge for edge in graph["edges"] if edge["type"] == "calls"]
    assert any(
        edge["from"] == "function:main.py::build"
        and edge["to"] == "function:models.py::Widget.__init__"
        and edge["scope"] == "cross_file"
        for edge in calls
    )


def test_export_index_flag_restores_legacy_behavior(monkeypatch):
    monkeypatch.setattr(cross_file, "EXPORT_INDEX_ENABLED", False)
    ctx = _ctx([
        ("models.py", """
            class Widget:
                def __init__(self):
                    self.ready = True
        """),
        ("main.py", """
            from models import Widget
            def build():
                return Widget()
        """),
    ])
    assert ctx["resolved_edges"] == []
    assert "symbol_not_found" in _reasons(ctx, "main.py")
