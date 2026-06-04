"""Phase 137 — regression tests for framework-agnostic semantic generalization.

Phase 136 proved the HA-tuned resolver returned 0% coverage for these
cross-cutting concepts on every repo: logging, events, background jobs,
scheduling, state management, plugins, api layer. These tests lock in the
generic resolver (impact_engine/concept_lexicon.py + resolve_generic_concept):

  1. each zero-coverage concept resolves from a repo's OWN structure,
  2. a repo that genuinely lacks a concept honestly resolves to nothing,
  3. the curated Home-Assistant map still wins (no HA regression),
  4. resolution is framework-agnostic (Python, Django, TS/VS Code layouts).
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from jarvis_desktop.impact_engine import concept_lexicon as lex  # noqa: E402
from jarvis_desktop.impact_engine.target_resolver import (  # noqa: E402
    resolve_generic_concept,
    resolve_semantic_target,
)


def _nodes(paths):
    return {f"n{i}": {"path": p, "dotted": p.replace("/", ".")} for i, p in enumerate(paths)}


# --------------------------------------------------------------------------
# 1 — concept phrase matching
# --------------------------------------------------------------------------
@pytest.mark.parametrize("query,concept", [
    ("what breaks if I remove the logging layer", "logging"),
    ("remove the event system", "events"),
    ("background jobs", "background_jobs"),
    ("scheduling", "scheduling"),
    ("state management", "state_management"),
    ("the plugin system", "plugins"),
    ("the api layer", "api_layer"),
    ("dependency injection", "dependency_injection"),
    ("routing", "routing"),
    ("authentication", "authentication"),
])
def test_match_concept(query, concept):
    assert lex.match_concept(query) == concept


def test_match_concept_unknown():
    assert lex.match_concept("the flux capacitor subsystem") is None
    assert lex.match_concept("") is None


# --------------------------------------------------------------------------
# 2 — the seven zero-coverage concepts resolve from real structure
# --------------------------------------------------------------------------
def test_zero_coverage_concepts_resolve():
    nodes = _nodes([
        "app/core/logging.py",
        "app/events/dispatcher.py",
        "app/workers/tasks.py",
        "app/scheduler/cron.py",
        "app/state/store.py",
        "app/plugins/manager.py",
        "app/api/routes.py",
        "app/util/helpers.py",
    ])
    expected = {
        "the logging layer": "app/core/logging.py",
        "the event system": "app/events/dispatcher.py",
        "background jobs": "app/workers/tasks.py",
        "scheduling": "app/scheduler/cron.py",
        "state management": "app/state/store.py",
        "the plugin system": "app/plugins/manager.py",
        "the api layer": "app/api/routes.py",
    }
    for query, want in expected.items():
        payload = resolve_generic_concept(nodes, query)
        assert payload is not None, query
        assert want in payload["module_paths"], (query, payload["module_paths"])
        assert payload["primary_path"] == want, (query, payload["primary_path"])


# --------------------------------------------------------------------------
# 3 — honest miss: a repo without a concept resolves to nothing
# --------------------------------------------------------------------------
def test_repo_without_concept_resolves_to_none():
    # algorithms corpus (QuixBugs-like): no cross-cutting infrastructure
    nodes = _nodes([
        "breadth_first_search.py", "knapsack.py", "quicksort.py",
        "levenshtein.py", "shortest_path_length.py",
    ])
    for query in ["the logging layer", "caching", "the api layer", "websocket support",
                  "background jobs", "state management"]:
        assert resolve_generic_concept(nodes, query) is None, query


# --------------------------------------------------------------------------
# 4 — framework-agnostic: Django + VS Code style layouts
# --------------------------------------------------------------------------
def test_django_layout_resolution():
    nodes = _nodes([
        "django/utils/log.py", "django/core/cache/__init__.py", "django/conf/__init__.py",
        "django/db/models/base.py", "django/middleware/common.py", "django/template/engine.py",
        "django/contrib/auth/__init__.py", "django/dispatch/dispatcher.py",
    ])
    cases = {
        "the logging layer": "django/utils/log.py",
        "caching": "django/core/cache/__init__.py",
        "configuration": "django/conf/__init__.py",
        "the database layer": "django/db/models/base.py",
        "middleware": "django/middleware/common.py",
        "the template engine": "django/template/engine.py",
        "authentication": "django/contrib/auth/__init__.py",
        "the event system": "django/dispatch/dispatcher.py",
    }
    for query, want in cases.items():
        payload = resolve_generic_concept(nodes, query)
        assert payload is not None and want in payload["module_paths"], (query, payload)


def test_typescript_vscode_layout_resolution():
    nodes = _nodes([
        "src/vs/platform/log/common/log.ts",
        "src/vs/platform/configuration/common/configurationService.ts",
        "src/vs/platform/commands/common/commands.ts",
        "src/vs/editor/editorBrowser.ts",
        "src/vs/workbench/workbench.main.ts",
        "src/vs/workbench/services/extensions/common/extensionHostManager.ts",
    ])
    cases = {
        "the logging layer": "src/vs/platform/log/common/log.ts",
        "configuration": "src/vs/platform/configuration/common/configurationService.ts",
        "the command registry": "src/vs/platform/commands/common/commands.ts",
        "the editor": "src/vs/editor/editorBrowser.ts",
        "workbench": "src/vs/workbench/workbench.main.ts",
    }
    for query, want in cases.items():
        payload = resolve_generic_concept(nodes, query)
        assert payload is not None and want in payload["module_paths"], (query, payload)


# --------------------------------------------------------------------------
# 5 — no Home Assistant regression: curated map still wins
# --------------------------------------------------------------------------
def test_curated_ha_concepts_still_win():
    ha_nodes = _nodes([
        "homeassistant/components/websocket_api/__init__.py",
        "homeassistant/core.py",
        "homeassistant/helpers/event.py",
        "homeassistant/auth/__init__.py",
        "homeassistant/config_entries.py",
    ])
    # "event bus" / "websocket support" are curated → must keep their curated label,
    # not be overridden by the generic lexicon.
    eb = resolve_semantic_target(ha_nodes, "event bus")
    assert eb is not None and eb["concept"] == "event bus" and not eb.get("generic")
    ws = resolve_semantic_target(ha_nodes, "websocket support")
    assert ws is not None and ws["concept"] in ("websocket support", "websocket")
    assert not ws.get("generic")


def test_generic_fallback_engages_for_noncurated_concept():
    nodes = _nodes([
        "homeassistant/util/logging.py", "homeassistant/core.py",
        "homeassistant/components/automation/__init__.py",
    ])
    # "the logging layer" is NOT in the curated HA map → generic path resolves it.
    payload = resolve_semantic_target(nodes, "the logging layer")
    assert payload is not None and payload.get("generic") is True
    assert payload["concept"] == "logging"
    assert "homeassistant/util/logging.py" in payload["module_paths"]


# --------------------------------------------------------------------------
# 6 — benchmark coverage is wired
# --------------------------------------------------------------------------
def test_benchmark_covers_zero_coverage_concepts():
    from benchmarks.generalization import scenarios
    assert len(scenarios.PHASE137_ZERO_COVERAGE_CONCEPTS) == 7
    for c in scenarios.PHASE137_ZERO_COVERAGE_CONCEPTS:
        assert lex.match_concept(c) is not None, c
