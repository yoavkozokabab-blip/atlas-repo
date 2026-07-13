from __future__ import annotations

from builder_core import repository_understanding as ru
from builder_core.bug_intelligence import depgraph, engine, jsdepgraph


def _write(path, text=""):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_generated_runtime_and_staged_payload_paths_are_classified_generated():
    paths = (
        ".phase152_packaging_lib/PyInstaller/__init__.py",
        ".home_checkpoint_stale_repo/api/handlers.py",
        ".pytest_home_persistence_escalated/repo/app.py",
        "AtlasPytestTemp/run/pkg/main.py",
        "packaging/installer/staging/accounts/_internal/starlette/app.py",
        "packaging/installer/output/unpacked/app.js",
    )
    assert all(ru.is_generated_runtime_path(path) for path in paths)
    assert all(ru.classify_file_role(path) == "generated" for path in paths)


def test_python_graph_excludes_generated_copies_without_losing_real_edges(tmp_path):
    _write(tmp_path / "app" / "__init__.py")
    _write(tmp_path / "app" / "core.py", "VALUE = 1\n")
    _write(tmp_path / "app" / "main.py", "from app.core import VALUE\n")
    _write(
        tmp_path / ".home_checkpoint_stale_repo" / "app" / "main.py",
        "from app.missing import VALUE\n",
    )
    _write(
        tmp_path / "packaging" / "installer" / "staging" / "app" / "main.py",
        "from app.missing import VALUE\n",
    )
    collected = [rel for _abs, rel in engine._collect_python_files(str(tmp_path))]
    assert collected == ["app/__init__.py", "app/core.py", "app/main.py"]
    graph = depgraph.build_graph(str(tmp_path), detail=depgraph.DETAIL_IMPORTS)
    modules = {n.get("path") for n in graph["nodes"] if n.get("type") == "module"}
    assert modules == {"app/__init__.py", "app/core.py", "app/main.py"}
    assert len([e for e in graph["edges"] if e.get("type") == "imports"]) == 1
    assert graph["unresolved"]["imports_external"] == []


def test_js_graph_excludes_generated_copies_without_losing_real_edge(tmp_path):
    _write(tmp_path / "src" / "core.ts", "export const value = 1;\n")
    _write(tmp_path / "src" / "main.ts", "import { value } from './core';\n")
    _write(
        tmp_path / ".redesign_runtime" / "src" / "bad.ts",
        "import value from './missing';\n",
    )
    files = [rel for _abs, rel in jsdepgraph.collect_js_ts_files(str(tmp_path))]
    assert files == ["src/core.ts", "src/main.ts"]
    graph = jsdepgraph.build_graph(str(tmp_path))
    assert len([e for e in graph["edges"] if e.get("type") == "imports"]) == 1
    assert graph["unresolved"]["imports_external"] == []


def test_relative_package_attribute_resolves_to_known_package_without_fake_module(tmp_path):
    _write(tmp_path / "pkg" / "__init__.py", "VERSION = '1'\n")
    _write(tmp_path / "pkg" / "cli.py", "from . import VERSION\n")
    graph = depgraph.build_graph(str(tmp_path), detail=depgraph.DETAIL_IMPORTS)
    imports = [edge for edge in graph["edges"] if edge.get("type") == "imports"]
    assert len(imports) == 1
    assert imports[0]["to"] == "module:pkg/__init__.py"
    assert imports[0]["target_module"] == "pkg"
    assert imports[0]["target_symbol"] == "VERSION"
    assert graph["unresolved"]["imports_external"] == []


def test_non_code_asset_import_is_expected_unresolved_not_internal_defect(tmp_path):
    _write(tmp_path / "src" / "layout.tsx", "import './globals.css';\n")
    graph = jsdepgraph.build_graph(str(tmp_path))
    assert graph["unresolved"]["imports_external"] == [
        {
            "from_module": "src/layout.tsx",
            "target": "./globals.css",
            "reason": "asset_import",
        }
    ]
