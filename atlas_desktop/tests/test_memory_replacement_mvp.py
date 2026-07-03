"""Verification suite for the Memory Replacement MVP.

Proves Atlas can generate and maintain AGENTS.md / CLAUDE.md from the canonical
repository memory, without manual maintenance and without destroying user content.
"""
from __future__ import annotations

import json
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from atlas_desktop import repository_memory as rm
from atlas_desktop import agent_files as af
from atlas_desktop import agent_context as ac


def _make_repo(tmp_path):
    (tmp_path / "package.json").write_text(json.dumps({
        "name": "demo-app",
        "description": "A demo app.",
        "scripts": {"build": "tsc", "test": "vitest", "lint": "eslint ."},
        "dependencies": {"react": "^19", "next": "^15"},
    }), encoding="utf-8")
    (tmp_path / "README.md").write_text("# demo-app\n\nA tiny demo application used for tests.\n", encoding="utf-8")
    (tmp_path / "tsconfig.json").write_text('{"compilerOptions": {"strict": true}}', encoding="utf-8")
    (tmp_path / ".eslintrc.json").write_text("{}", encoding="utf-8")
    (tmp_path / "Makefile").write_text("deploy:\n\techo deploy\n", encoding="utf-8")
    src = tmp_path / "src"
    src.mkdir()
    (src / "index.ts").write_text("export const x = 1;\n", encoding="utf-8")
    return tmp_path


def _state(repo, modules=12):
    return {
        "path": str(repo),
        "scan": {
            "repo_name": "demo-app",
            "module_count": modules, "dependency_edges": 20, "file_count": 30,
            "import_cycle_count": 1, "degraded": False,
            "graph_health": {"label": "healthy"},
            "top_hubs": [{"module": "src/core", "fan_in": 8}, {"module": "src/api", "fan_in": 5}],
            "top_risks": [{"module": "src/core"}],
            "signature_v2": {"signature": "sig-abc"},
        },
        "index": {"subsystems": [
            {"name": "core", "role_counts": {"production_code": 10}},
            {"name": "api", "role_counts": {"production_code": 6}},
        ]},
    }


def _memory(repo, modules=12):
    return rm.build_memory(_state(repo, modules), generated_by_version="test")


# --- P0: derivation ---
def test_derivation_extracts_commands_deps_conventions(tmp_path):
    repo = _make_repo(tmp_path)
    ctx = ac.derive_agent_context(str(repo), _state(repo)["scan"], _state(repo)["index"])
    assert ctx["commands"].get("build") == "npm run build"
    assert ctx["commands"].get("test") == "npm run test"
    assert ctx["commands"].get("deploy") == "make deploy"
    assert "react" in ctx["important_dependencies"]
    assert any("TypeScript" in c for c in ctx["conventions"])
    assert "ESLint" in ctx["conventions"]
    assert "src/" in ctx["structure"]
    assert ctx["project_summary"]
    assert ctx["derivation_confidence"] in ("medium", "high")


def test_python_primary_ignores_auxiliary_package_json_for_commands(tmp_path):
    (tmp_path / "README.md").write_text("# demo\n\nPython framework.\n", encoding="utf-8")
    (tmp_path / "pyproject.toml").write_text(
        "\n".join([
            "[build-system]",
            'requires = ["setuptools>=77"]',
            "[project]",
            'name = "demo"',
            'dependencies = ["Django>=5", "tzdata; sys_platform == \'win32\'"]',
            "[tool.black]",
            'target-version = ["py312"]',
        ]),
        encoding="utf-8",
    )
    (tmp_path / "package.json").write_text(
        json.dumps({"scripts": {"test": "grunt test --verbose"}, "devDependencies": {"grunt": "^1"}}),
        encoding="utf-8",
    )
    pkg = tmp_path / "demo"
    tests = tmp_path / "tests"
    pkg.mkdir()
    tests.mkdir()
    for i in range(8):
        (pkg / f"module_{i}.py").write_text("x = 1\n", encoding="utf-8")
    (tests / "runtests.py").write_text("print('run tests')\n", encoding="utf-8")
    (tmp_path / "js_tests").mkdir()
    (tmp_path / "js_tests" / "asset.test.js").write_text("test('asset', () => {})\n", encoding="utf-8")

    ctx = ac.derive_agent_context(str(tmp_path), _state(tmp_path)["scan"], _state(tmp_path)["index"])

    assert ctx["primary_language"] == "Python"
    assert "JavaScript/Node" in ctx["secondary_languages"]
    assert ctx["commands"]["test"] == "python tests/runtests.py"
    assert ctx["commands"]["test"] != "npm run test"
    assert "Django" in ctx["important_dependencies"]
    assert "tzdata" in ctx["important_dependencies"]
    assert all(";" not in dep for dep in ctx["important_dependencies"])


def test_python_dependency_extraction_cleans_multiple_sources(tmp_path):
    (tmp_path / "pyproject.toml").write_text(
        "\n".join([
            "[project]",
            'name = "deps-demo"',
            'dependencies = ["requests>=2; python_version >= \'3.10\'"]',
            "[tool.poetry.dependencies]",
            'python = ">=3.11"',
            'rich = "^13"',
            '"markdown-it-py" = ">=3"',
        ]),
        encoding="utf-8",
    )
    (tmp_path / "setup.cfg").write_text(
        "[options]\ninstall_requires =\n    celery>=5\n    kombu<6\n",
        encoding="utf-8",
    )
    (tmp_path / "requirements-dev.txt").write_text(
        "\n".join([
            "# dev tools",
            "pytest>=8; python_version >= '3.11'",
            "-r requirements.txt",
            "bad fragment >= ;",
        ]),
        encoding="utf-8",
    )
    (tmp_path / "pkg").mkdir()
    (tmp_path / "pkg" / "__init__.py").write_text("", encoding="utf-8")

    deps = ac.detect_dependencies(str(tmp_path))

    assert {"requests", "rich", "markdown-it-py", "celery", "kombu", "pytest"}.issubset(set(deps))
    assert "python" not in {d.lower() for d in deps}
    assert all(";" not in dep and ">=" not in dep and "<" not in dep for dep in deps)


def test_confidence_drops_when_evidence_is_degraded_or_missing(tmp_path):
    (tmp_path / "README.md").write_text("# weak\n\nSparse project.\n", encoding="utf-8")
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "weak"\n', encoding="utf-8")
    (tmp_path / "pkg").mkdir()
    (tmp_path / "pkg" / "__init__.py").write_text("", encoding="utf-8")
    scan = {
        "repo_name": "weak",
        "module_count": 1,
        "dependency_edges": 0,
        "file_count": 3,
        "degraded": True,
        "graph_health": {"label": "degraded"},
        "top_hubs": [],
        "top_risks": [],
    }

    ctx = ac.derive_agent_context(str(tmp_path), scan, {"subsystems": []})

    assert ctx["commands"]["test"] == "UNKNOWN"
    assert ctx["derivation_confidence"] == "low"
    assert "dependencies missing" in ctx["confidence_reasons"]


def test_critical_files_are_resolvable_repository_paths(tmp_path):
    (tmp_path / "README.md").write_text("# path-demo\n\nPath demo.\n", encoding="utf-8")
    (tmp_path / "pyproject.toml").write_text(
        "[project]\nname = 'path-demo'\ndependencies = ['requests>=2']\n[tool.pytest.ini_options]\ntestpaths = ['tests']\n",
        encoding="utf-8",
    )
    src = tmp_path / "src" / "path_demo"
    src.mkdir(parents=True)
    (src / "__init__.py").write_text("", encoding="utf-8")
    (src / "core.py").write_text("def run(): return 1\n", encoding="utf-8")
    (src / "api.py").write_text("from .core import run\n", encoding="utf-8")
    tests = tmp_path / "tests"
    tests.mkdir()
    (tests / "test_core.py").write_text("def test_ok(): assert True\n", encoding="utf-8")
    scan = {
        "repo_name": "path-demo",
        "module_count": 3,
        "dependency_edges": 2,
        "file_count": 6,
        "degraded": False,
        "graph_health": {"label": "healthy"},
        "top_hubs": [{"module": "src.path_demo.core"}, {"module": "src.path_demo.api"}],
        "top_risks": [{"module": "missing.module"}],
    }

    ctx = ac.derive_agent_context(str(tmp_path), scan, {"subsystems": []})

    assert "src/path_demo/core.py" in ctx["critical_files"]
    assert "src/path_demo/api.py" in ctx["critical_files"]
    assert "missing.module" in ctx["unresolved_critical_refs"]
    assert all((tmp_path / rel).is_file() for rel in ctx["critical_files"])
    # Intent: critical files are resolvable, repo-relative paths (is_file() above
    # proves resolvability). The engine legitimately surfaces non-.py repo files
    # such as pyproject.toml / README.md, so do NOT constrain by extension; only
    # ensure none is an absolute path or a bare module dotted-name.
    assert all(
        not (rel.startswith(("/", "\\")) or (len(rel) > 1 and rel[1] == ":"))
        for rel in ctx["critical_files"]
    )


def test_generated_agents_md_uses_openable_critical_files(tmp_path):
    repo = tmp_path
    (repo / "README.md").write_text("# agent-paths\n\nAgent paths demo.\n", encoding="utf-8")
    (repo / "pyproject.toml").write_text(
        "[project]\nname = 'agent-paths'\ndependencies = ['requests']\n[tool.pytest.ini_options]\ntestpaths = ['tests']\n",
        encoding="utf-8",
    )
    pkg = repo / "agent_paths"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("", encoding="utf-8")
    (pkg / "service.py").write_text("x = 1\n", encoding="utf-8")
    scan = {
        "repo_name": "agent-paths",
        "module_count": 2,
        "dependency_edges": 1,
        "file_count": 4,
        "import_cycle_count": 0,
        "degraded": False,
        "graph_health": {"label": "healthy"},
        "top_hubs": [{"module": "agent_paths.service"}],
        "top_risks": [],
        "signature_v2": {"signature": "sig-paths"},
    }
    mem = rm.build_memory({"path": str(repo), "scan": scan, "index": {"subsystems": []}}, generated_by_version="test")
    body = af.generate_agents_md(mem)

    assert "- agent_paths/service.py" in body
    assert (repo / "agent_paths" / "service.py").is_file()


def test_subsystems_group_directories_with_representative_files(tmp_path):
    (tmp_path / "README.md").write_text("# subsystems\n\nSubsystem demo.\n", encoding="utf-8")
    (tmp_path / "pyproject.toml").write_text(
        "[project]\nname = 'subsystems'\ndependencies = ['requests']\n[tool.pytest.ini_options]\ntestpaths = ['tests']\n",
        encoding="utf-8",
    )
    for rel in [
        "pkg/auth/session.py",
        "pkg/auth/tokens.py",
        "pkg/db/models.py",
        "pkg/db/queries.py",
        "pkg/api/routes.py",
        "pkg/api/http.py",
        "tests/test_session.py",
    ]:
        path = tmp_path / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("x = 1\n", encoding="utf-8")

    ctx = ac.derive_agent_context(str(tmp_path), {
        "repo_name": "subsystems",
        "module_count": 7,
        "dependency_edges": 6,
        "file_count": 9,
        "degraded": False,
        "graph_health": {"label": "healthy"},
        "top_hubs": [],
        "top_risks": [],
    }, {"subsystems": []})

    subs = ctx["key_subsystems"]
    names = {s["name"]: s for s in subs}
    assert "pkg/auth" in names
    assert "pkg/db" in names
    assert "pkg/api" in names
    assert names["pkg/auth"]["purpose"] == "authentication and session handling"
    assert names["pkg/db"]["purpose"] == "database layer"
    for sub in subs:
        assert not sub["name"].endswith(".py")
        assert sub["purpose"]
        assert sub["confidence"] in {"high", "medium", "low"}
        assert all((tmp_path / rel).is_file() for rel in sub["representative_files"])


def test_subsystem_purpose_matching_avoids_accidental_substrings():
    assert ac._purpose_for_group("src/requests")[0] == "core package area"
    assert ac._purpose_for_group("tools")[0] == "core package area"
    assert ac._purpose_for_group("rich/_unicode_data")[0] == "core package area"
    assert ac._purpose_for_group("tests")[0] == "test suite"


def test_makefile_multi_target_commands_are_detected(tmp_path):
    (tmp_path / "Makefile").write_text("test tests:\n\tpytest\nlint format:\n\truff check .\n", encoding="utf-8")

    assert {"test", "tests", "lint", "format"}.issubset(set(ac._makefile_targets(str(tmp_path))))


def test_monorepo_packages_include_commands_dependencies_and_owners(tmp_path):
    libs = tmp_path / "libs"
    core = libs / "core"
    classic = libs / "langchain"
    for pkg, name, module in [
        (core, "langchain-core", "langchain_core"),
        (classic, "langchain-classic", "langchain_classic"),
    ]:
        pkg.mkdir(parents=True)
        (pkg / "pyproject.toml").write_text(
            "\n".join([
                "[build-system]",
                'requires = ["hatchling"]',
                "[project]",
                f'name = "{name}"',
                'description = "Package demo"',
                'dependencies = ["requests>=2", "pydantic>=2"]',
            ]),
            encoding="utf-8",
        )
        (pkg / "Makefile").write_text("test tests:\n\tpytest\nlint:\n\truff check .\ntype:\n\tmypy .\n", encoding="utf-8")
        mod = pkg / module
        mod.mkdir()
        (mod / "__init__.py").write_text("", encoding="utf-8")
        (mod / "api.py").write_text("x = 1\n", encoding="utf-8")

    ctx = ac.derive_agent_context(str(tmp_path), {
        "repo_name": "mono",
        "module_count": 4,
        "dependency_edges": 0,
        "file_count": 8,
        "degraded": True,
        "graph_health": {"label": "degraded"},
        "top_hubs": [],
        "top_risks": [],
    }, {"subsystems": []})

    packages = {p["path"]: p for p in ctx["packages"]}
    assert {"libs/core", "libs/langchain"}.issubset(packages)
    assert packages["libs/core"]["commands"]["test"] == "make -C libs/core test"
    assert packages["libs/core"]["commands"]["lint"] == "make -C libs/core lint"
    assert "requests" in packages["libs/core"]["dependencies"]
    assert packages["libs/core"]["owner"] == "langchain_core"

    body = af.generate_agents_md({"repo_name": "mono", "agent_context": ctx})
    assert "## Workspace packages" in body
    assert "make -C libs/core test" in body
    assert "Package sections are higher confidence" in body


def test_degraded_graph_suppresses_ci_script_hubs(tmp_path):
    (tmp_path / "README.md").write_text("# mono\n\nMonorepo.\n", encoding="utf-8")
    core = tmp_path / "libs" / "core"
    core.mkdir(parents=True)
    (core / "pyproject.toml").write_text(
        "[build-system]\nrequires=['hatchling']\n[project]\nname='core'\ndependencies=['requests']\n",
        encoding="utf-8",
    )
    (core / "Makefile").write_text("test:\n\tpytest\nlint:\n\truff check .\n", encoding="utf-8")
    mod = core / "core"
    mod.mkdir()
    (mod / "__init__.py").write_text("", encoding="utf-8")
    (mod / "service.py").write_text("x = 1\n", encoding="utf-8")
    (tmp_path / ".github" / "scripts").mkdir(parents=True)
    (tmp_path / ".github" / "scripts" / "check_diff.py").write_text("x = 1\n", encoding="utf-8")
    extra = tmp_path / "libs" / "extra"
    extra.mkdir(parents=True)
    (extra / "pyproject.toml").write_text("[project]\nname='extra'\ndependencies=['pydantic']\n", encoding="utf-8")
    (extra / "extra").mkdir()
    (extra / "extra" / "__init__.py").write_text("", encoding="utf-8")

    ctx = ac.derive_agent_context(str(tmp_path), {
        "repo_name": "mono",
        "module_count": 4,
        "dependency_edges": 0,
        "file_count": 8,
        "degraded": True,
        "graph_health": {"label": "degraded"},
        "top_hubs": [{"module": ".github/scripts/check_diff.py"}],
        "top_risks": [],
    }, {"subsystems": []})

    assert ".github/scripts/check_diff.py" not in ctx["critical_files"]
    assert ".github/scripts/check_diff.py" in ctx["suppressed_graph_refs"]
    assert any(path.startswith("libs/core/") for path in ctx["critical_files"])


def test_memory_includes_agent_context_and_is_signed(tmp_path):
    repo = _make_repo(tmp_path)
    mem = _memory(repo)
    assert "agent_context" in mem and mem["agent_context"]["commands"]
    assert rm.verify_memory_record(mem, str(repo))  # hash covers agent_context


# --- P4.1: initial scan generates AGENTS.md ---
def test_initial_scan_generates_agents_md(tmp_path):
    repo = _make_repo(tmp_path)
    res = af.AtlasManagedAgentsGenerator(_memory(repo)).write(str(repo), "agents")
    assert res["action"] == "created"
    text = (repo / "AGENTS.md").read_text(encoding="utf-8")
    assert af.MANAGED_BEGIN in text and af.MANAGED_END in text
    assert "## Architecture" in text and "## Commands" in text and "demo-app" in text


# --- P4.2 + P4.3: repo change updates memory and AGENTS.md ---
def test_repo_change_updates_memory_and_file(tmp_path):
    repo = _make_repo(tmp_path)
    mem1 = _memory(repo, modules=12)
    af.AtlasManagedAgentsGenerator(mem1).write(str(repo), "agents")
    mem2 = _memory(repo, modules=99)
    assert mem1["memory_hash"] != mem2["memory_hash"]
    assert af.generate_agents_md(mem1) != af.generate_agents_md(mem2)
    res = af.AtlasManagedAgentsGenerator(mem2).write(str(repo), "agents")
    assert res["action"] == "updated"
    assert "99 modules" in (repo / "AGENTS.md").read_text(encoding="utf-8")


# --- P4.4 + P4.8: user content preserved / no catastrophic overwrite ---
def test_user_content_preserved_block_in_middle(tmp_path):
    repo = _make_repo(tmp_path)
    before = "# My project\n\nHuman intro the agent should keep.\n\n"
    after = "\n## Human notes\n\nDo not delete me.\n"
    old_block = af.wrap_block("OLD ATLAS CONTENT")
    (repo / "AGENTS.md").write_text(before + old_block + after, encoding="utf-8")

    af.AtlasManagedAgentsGenerator(_memory(repo)).write(str(repo), "agents")
    text = (repo / "AGENTS.md").read_text(encoding="utf-8")

    assert "Human intro the agent should keep." in text
    assert "Do not delete me." in text
    assert text.startswith(before)          # human content before block byte-identical
    assert text.rstrip().endswith(after.rstrip())
    assert "OLD ATLAS CONTENT" not in text  # managed block was replaced
    assert text.count(af.MANAGED_BEGIN) == 1 and text.count(af.MANAGED_END) == 1


# --- P4.6: managed blocks valid + idempotent ---
def test_managed_block_idempotent(tmp_path):
    repo = _make_repo(tmp_path)
    mem = _memory(repo)
    gen = af.AtlasManagedAgentsGenerator(mem)
    gen.write(str(repo), "agents")
    second = gen.write(str(repo), "agents")  # same memory object → no change
    assert second["action"] == "unchanged"
    text = (repo / "AGENTS.md").read_text(encoding="utf-8")
    assert af.extract_block(text) is not None
    assert text.count(af.MANAGED_BEGIN) == 1


# --- P1.5: CLAUDE.md from the same store ---
def test_claude_md_generated_same_store(tmp_path):
    repo = _make_repo(tmp_path)
    res = af.AtlasManagedAgentsGenerator(_memory(repo)).write(str(repo), "claude")
    assert res["action"] == "created"
    text = (repo / "CLAUDE.md").read_text(encoding="utf-8")
    assert "CLAUDE.md" in text and af.MANAGED_BEGIN in text
    assert "See AGENTS.md for repository facts" in text
    assert "## Commands" not in af.generate_claude_md(_memory(repo))


# --- P4.7: generated context is concise (token budget) ---
@pytest.mark.parametrize("kind", ["agents", "claude"])
def test_generated_context_concise(tmp_path, kind):
    repo = _make_repo(tmp_path)
    body = af.AtlasManagedAgentsGenerator(_memory(repo)).body(kind)
    assert af.estimate_tokens(body) < 900  # fits a reasonable budget


# --- P4.5 + P3: drift / stale detection ---
def test_drift_in_sync_after_write(tmp_path):
    repo = _make_repo(tmp_path)
    mem = _memory(repo)
    mem["freshness_status"] = "fresh"
    af.AtlasManagedAgentsGenerator(mem).write_all(str(repo))
    drift = af.detect_drift(mem, str(repo))
    assert drift["is_current"] is True
    assert drift["files_in_sync"] is True


def test_drift_detects_stale_memory(tmp_path):
    repo = _make_repo(tmp_path)
    mem = _memory(repo)
    af.AtlasManagedAgentsGenerator(mem).write_all(str(repo))
    mem["freshness_status"] = "stale"
    drift = af.detect_drift(mem, str(repo))
    assert drift["is_current"] is False
    assert drift["memory_fresh"] is False
    assert any("freshness" in r for r in drift["reasons"])


def test_drift_detects_human_edited_block(tmp_path):
    repo = _make_repo(tmp_path)
    mem = _memory(repo)
    mem["freshness_status"] = "fresh"
    af.AtlasManagedAgentsGenerator(mem).write(str(repo), "agents")
    # Human tampers inside the managed block.
    p = repo / "AGENTS.md"
    text = p.read_text(encoding="utf-8").replace("## Architecture", "## Architecture (edited)")
    p.write_text(text, encoding="utf-8")
    drift = af.detect_drift(mem, str(repo))
    assert drift["is_current"] is False
    assert any("AGENTS.md" in r for r in drift["reasons"])
