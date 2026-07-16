"""Contracts for the product-wide engineering-investigation language."""
from __future__ import annotations

from pathlib import Path


STATIC = Path(__file__).resolve().parents[1] / "static"
INDEX = (STATIC / "index.html").read_text(encoding="utf-8")
APP = (STATIC / "app.js").read_text(encoding="utf-8")
CSS = (STATIC / "investigation.css").read_text(encoding="utf-8")
ASK_REPORT = (STATIC / "ask_report.js").read_text(encoding="utf-8")
LAUNCH = (STATIC / "atlas_launch_ux.js").read_text(encoding="utf-8")
WORKFLOWS = (STATIC / "atlas_workflows.js").read_text(encoding="utf-8")
HANDOFF = (STATIC / "atlas_zero_friction.js").read_text(encoding="utf-8")


def _view(view_id: str) -> str:
    start = INDEX.index(f'id="view-{view_id}"')
    end = INDEX.find('<section class="view', start + 1)
    return INDEX[start : end if end >= 0 else len(INDEX)]


def test_primary_navigation_stays_short() -> None:
    # Vocabulary rule: navigation labels are short (Ask / Debug / Impact / Plan /
    # Map); the descriptive names (Repository Analysis, Failure Investigation…)
    # belong to page titles, not the nav.
    nav = INDEX[INDEX.index('<nav class="nav"') : INDEX.index("</nav>")]
    assert 'data-view="ask"' in nav
    assert ">Ask</button>" in nav
    assert ">Debug</button>" in nav
    assert "Ask Atlas" not in nav
    for verbose in ("Repository Analysis", "Failure Investigation", "Implementation Plan", "Change Impact"):
        assert verbose not in nav


def test_repository_analysis_is_an_investigation_workspace() -> None:
    view = _view("ask")
    for text in (
        "Repository Analysis",
        "Investigation brief",
        "Run analysis",
        "Investigation templates",
        "Copy report",
    ):
        assert text in view
    for chat_text in (">Send<", "Suggested questions", "Ask your first question"):
        assert chat_text not in view
    assert 'onclick="sendCopilotQuestion()"' in view


def test_engineering_workspaces_keep_real_handlers() -> None:
    expected = {
        "build": ("Implementation Plan", "Change brief", "runChangePlan()"),
        "investigate": ("Failure Investigation", "Observed failure", "runInvestigationPlan()"),
        "impact": ("Change Impact", "Change target", "runImpact()"),
    }
    for view_id, markers in expected.items():
        view = _view(view_id)
        for marker in markers:
            assert marker in view, (view_id, marker)


def test_home_and_map_route_into_analysis_without_chat_ctas() -> None:
    home = _view("home")
    map_view = _view("center")
    assert "Start an engineering investigation." in home
    assert "Engineering question" in home
    assert "Run analysis" in home
    assert "Repository Analysis" in map_view
    assert "Analyze selection" in map_view
    assert 'onclick="focusCopilot()"' in map_view


def test_loading_and_empty_state_describe_repository_work() -> None:
    for stage in (
        "Scoping investigation",
        "Resolving repository evidence",
        "Assembling analysis report",
    ):
        assert stage in ASK_REPORT
    assert "Define an engineering investigation" in ASK_REPORT
    assert "Ask Atlas anything" not in ASK_REPORT


def test_agent_outputs_are_handoffs_not_new_chats() -> None:
    assert "Agent handoff" in HANDOFF
    assert "engineering handoff" in HANDOFF
    assert "new chat" not in HANDOFF
    export = _view("export")
    assert "Agent Handoff" in export
    assert "Evidence package" in export
    # Regression: the handoff surface keeps its real handlers — the rename must
    # never detach a primary action from its implementation.
    for handler in (
        'onclick="generateAgentExport()"',
        'onclick="copyExport()"',
        'onclick="saveExport()"',
        'onclick="copyForTarget(',
    ):
        assert handler in export, handler


def test_command_palette_and_tour_use_investigation_names() -> None:
    for label in (
        "Repository Analysis",
        "Change Impact",
        "Failure Investigation",
        "Implementation Plan",
        "Architecture Map",
    ):
        assert label in LAUNCH
    assert "Repository Analysis" in WORKFLOWS
    assert "Run analysis" in LAUNCH


def test_shared_workspace_css_is_flat_evidence_first_and_responsive() -> None:
    assert 'href="investigation.css"' in INDEX
    assert INDEX.index('href="investigation.css"') > INDEX.index('href="ask_report.css"')
    for selector in (
        ".analysis-workspace",
        ".workspace-head",
        ".investigation-input",
        ".ask-suggestions",
        ".map-ask-cta",
    ):
        assert selector in CSS
    assert "box-shadow: none" in CSS
    assert "@media (max-width: 860px)" in CSS
    assert "prefers-reduced-motion" in CSS


def test_dynamic_analysis_copy_is_not_conversational() -> None:
    assert "Repository analysis started" in APP
    assert "Refine analysis" in APP
    assert "Analysis report copied" in APP
    assert "Ask a follow-up" not in APP
    assert "Press Send" not in APP


def test_loaded_repository_replaces_stale_workflow_gate_with_evidence_state() -> None:
    assert "function renderWorkflowReadyState(view)" in APP
    assert "renderWorkflowReadyState(view);" in APP
    for marker in (
        "workflow-context-line",
        "workflow-empty-state",
        "renderWorkflowContextLine",
        "STATE.summary.file_count",
        "STATE.summary.dependency_edges",
    ):
        assert marker in APP or marker in (STATIC / "ui-polish-v104.css").read_text(encoding="utf-8")


# NOTE: the secondary-surface vocabulary rewrite (about/docs/demo/gallery/admin/
# billing) was deliberately excluded from the engineering-analyst checkpoint to
# keep the changeset reviewable. When those surfaces are migrated in their own
# change, restore a contract test here that pins their vocabulary.
