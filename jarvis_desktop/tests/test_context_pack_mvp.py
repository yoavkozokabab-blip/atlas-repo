"""Context Pack MVP tests."""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from jarvis_desktop import context_pack as cp
from jarvis_desktop.evidence_engine import build_evidence_store


def _repo(tmp_path):
    (tmp_path / "app").mkdir()
    (tmp_path / "tests").mkdir()
    (tmp_path / "vendor").mkdir()
    (tmp_path / "app" / "__init__.py").write_text("", encoding="utf-8")
    (tmp_path / "app" / "auth.py").write_text(
        "\n".join([
            "class AuthStore:",
            "    def login(self, token):",
            "        return token",
            "",
            "def refresh_token(token):",
            "    return token",
        ]),
        encoding="utf-8",
    )
    (tmp_path / "app" / "routes.py").write_text(
        "from app.auth import AuthStore\n\nhandler = AuthStore()\n",
        encoding="utf-8",
    )
    (tmp_path / "tests" / "test_auth.py").write_text(
        "from app.auth import AuthStore\n\ndef test_login():\n    assert AuthStore()\n",
        encoding="utf-8",
    )
    (tmp_path / "vendor" / "generated_auth.py").write_text("def auth(): pass\n", encoding="utf-8")
    return tmp_path


def _state(repo):
    paths = ["app/auth.py", "app/routes.py", "tests/test_auth.py", "vendor/generated_auth.py"]
    graph = {
        "nodes": [
            {"id": "module:app/auth.py", "type": "module", "path": "app/auth.py"},
            {"id": "module:app/routes.py", "type": "module", "path": "app/routes.py"},
            {"id": "module:tests/test_auth.py", "type": "module", "path": "tests/test_auth.py"},
            {"id": "module:vendor/generated_auth.py", "type": "module", "path": "vendor/generated_auth.py"},
        ],
        "edges": [
            {"type": "imports", "resolved": True, "from": "module:app/routes.py", "to": "module:app/auth.py"},
            {"type": "imports", "resolved": True, "from": "module:tests/test_auth.py", "to": "module:app/auth.py"},
        ],
    }
    index = {
        "files": [
            {"path": p, "role": "test_code" if p.startswith("tests/") else "production_code", "size": 200}
            for p in paths
        ],
        "subsystems": [
            {"name": "app", "role_counts": {"production_code": 2}},
            {"name": "tests", "role_counts": {"test_code": 1}},
        ],
    }
    store = build_evidence_store(str(repo), graph, index).to_dict()
    return {
        "path": str(repo),
        "scan": {
            "repo_name": "demo",
            "module_count": 4,
            "dependency_edges": 2,
            "file_count": 4,
            "degraded": False,
            "graph_health": {"label": "healthy"},
            "top_hubs": [{"path": "app/auth.py", "module": "app.auth", "fan_in": 2}],
            "top_risks": [{"path": "app/auth.py", "score": 12}],
        },
        "graph": graph,
        "index": index,
        "evidence_store": store,
    }


def _memory(repo):
    return {
        "repo_path": str(repo),
        "repo_name": "demo",
        "graph_health": "healthy",
        "agent_context": {
            "commands": {"test": "pytest", "lint": "ruff check .", "build": "python -m build"},
            "conventions": ["Ruff"],
            "pitfalls": ["Change auth flows with tests."],
            "derivation_confidence": "high",
            "critical_files": ["app/auth.py"],
            "key_subsystems": [
                {
                    "name": "app",
                    "purpose": "application code",
                    "representative_files": ["app/auth.py", "app/routes.py"],
                }
            ],
        },
    }


def _framework_state(repo, paths):
    graph = {
        "nodes": [{"id": f"module:{p}", "type": "module", "path": p} for p in paths],
        "edges": [],
    }
    index = {
        "files": [
            {"path": p, "role": "production_code", "size": 200}
            for p in paths
        ],
        "subsystems": [{"name": "homeassistant", "role_counts": {"production_code": len(paths)}}],
    }
    store = build_evidence_store(str(repo), graph, index).to_dict()
    return {
        "path": str(repo),
        "scan": {
            "repo_name": "framework",
            "module_count": len(paths),
            "dependency_edges": 0,
            "file_count": len(paths),
            "degraded": False,
            "graph_health": {"label": "healthy"},
            "top_hubs": [],
            "top_risks": [],
        },
        "graph": graph,
        "index": index,
        "evidence_store": store,
    }


def _framework_memory(repo):
    return {
        "repo_path": str(repo),
        "repo_name": "framework",
        "graph_health": "healthy",
        "agent_context": {
            "commands": {"test": "pytest"},
            "critical_files": [],
            "key_subsystems": [],
        },
    }


def test_context_pack_prefers_framework_roots_over_keyword_leaf_swarm(tmp_path):
    paths = [
        "homeassistant/components/sensor/__init__.py",
        "homeassistant/components/binary_sensor/__init__.py",
        "homeassistant/config_entries.py",
        "homeassistant/config.py",
        "homeassistant/setup.py",
        "django/db/models/query.py",
        "django/db/models/sql/query.py",
        "django/db/models/fields/related.py",
        "django/template/defaulttags.py",
        "django/template/library.py",
        "django/template/__init__.py",
        "django/core/management/templates.py",
    ]
    paths.extend(f"homeassistant/components/integration_{idx}/sensor.py" for idx in range(30))
    for rel in paths:
        target = tmp_path / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("sensor platform config entry setup flow\n", encoding="utf-8")

    sensor_pack = cp.build_context_pack_from_state(
        str(tmp_path),
        "Add a new sensor platform",
        _framework_state(tmp_path, paths),
        memory=_framework_memory(tmp_path),
        max_files=8,
    )
    sensor_selected = [item["path"] for item in sensor_pack["recommended_files"]]
    assert sensor_selected[0] == "homeassistant/components/sensor/__init__.py"

    config_pack = cp.build_context_pack_from_state(
        str(tmp_path),
        "Improve the config entry setup flow",
        _framework_state(tmp_path, paths),
        memory=_framework_memory(tmp_path),
        max_files=8,
    )
    config_selected = [item["path"] for item in config_pack["recommended_files"]]
    assert "homeassistant/config_entries.py" in config_selected[:3]

    queryset_pack = cp.build_context_pack_from_state(
        str(tmp_path),
        "Fix queryset filtering across related fields",
        _framework_state(tmp_path, paths),
        memory=_framework_memory(tmp_path),
        max_files=8,
    )
    queryset_selected = [item["path"] for item in queryset_pack["recommended_files"]]
    assert "django/db/models/query.py" in queryset_selected[:3]

    template_pack = cp.build_context_pack_from_state(
        str(tmp_path),
        "Add a new template tag",
        _framework_state(tmp_path, paths),
        memory=_framework_memory(tmp_path),
        max_files=8,
    )
    template_selected = [item["path"] for item in template_pack["recommended_files"]]
    assert "django/template/defaulttags.py" in template_selected[:3]


def test_parse_task_extracts_files_actions_modules_and_concepts():
    signals = cp.parse_task("Fix app/auth.py token replay in app.auth.AuthStore tests")
    assert "fix" in signals.actions
    assert "app/auth.py" in signals.files
    assert "app.auth.AuthStore" in signals.modules
    assert "token" in signals.concepts
    assert "auth" in signals.domain_keywords


def test_context_pack_selects_direct_symbol_dependency_and_tests(tmp_path):
    repo = _repo(tmp_path)
    pack = cp.build_context_pack_from_state(
        str(repo),
        "Fix app/auth.py AuthStore token replay and update tests.",
        _state(repo),
        memory=_memory(repo),
    )

    selected = [item["path"] for item in pack["recommended_files"]]
    tests = [item["path"] for item in pack["related_tests"]]

    assert selected[0] == "app/auth.py"
    assert "app/routes.py" in selected
    assert "tests/test_auth.py" in tests or "tests/test_auth.py" in selected
    assert pack["confidence"] in {"MEDIUM", "HIGH"}
    assert any("AuthStore" in reason for item in pack["recommended_files"] for reason in item["reasons"])
    assert any("app/routes.py" in note or "app/auth.py" in note for note in pack["dependency_notes"])
    assert "pytest" in "\n".join(pack["relevant_commands"])
    assert "ATLAS_CONTEXT_PACK" in pack["markdown"]


def test_context_pack_is_evidence_centric_every_file_explains_why(tmp_path):
    """Excellence #1: every recommended file carries structured evidence —
    relevance score + selection/dependency/impact reasons — and the markdown
    surfaces it. No file may appear without a stated WHY."""
    repo = _repo(tmp_path)
    pack = cp.build_context_pack_from_state(
        str(repo),
        "Fix app/auth.py AuthStore token replay and update tests.",
        _state(repo),
        memory=_memory(repo),
    )
    recs = pack["recommended_files"]
    assert recs, "expected at least one recommended file"
    for item in recs:
        assert isinstance(item.get("relevance_score"), (int, float))
        assert item.get("selection_reason"), f"{item['path']} missing selection_reason"
        assert item.get("dependency_reason"), f"{item['path']} missing dependency_reason"
        assert item.get("impact_reason"), f"{item['path']} missing impact_reason"
    md = pack["markdown"]
    assert "why selected:" in md
    assert "dependencies:" in md
    assert "impact:" in md


def test_context_pack_excludes_generated_vendor_noise(tmp_path):
    repo = _repo(tmp_path)
    pack = cp.build_context_pack_from_state(
        str(repo),
        "Fix generated auth helper behavior",
        _state(repo),
        memory=_memory(repo),
    )

    selected = [item["path"] for item in pack["recommended_files"]]
    excluded = [item["path"] for item in pack["excluded_files"]]
    assert "vendor/generated_auth.py" not in selected
    assert "vendor/generated_auth.py" in excluded


def test_context_pack_low_confidence_when_no_relevant_context(tmp_path):
    repo = _repo(tmp_path)
    pack = cp.build_context_pack_from_state(
        str(repo),
        "Change billing checkout invoice emails",
        _state(repo),
        memory=_memory(repo),
    )

    assert pack["confidence"] == "LOW"
    assert pack["recommended_files"] == []
    assert "No relevant files identified" in pack["markdown"]
