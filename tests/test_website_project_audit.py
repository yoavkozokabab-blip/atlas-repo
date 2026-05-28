"""Website product audit command — read-only."""

from __future__ import annotations

from pathlib import Path

from brain.intent_classifier import classify_rules
from core.types import Intent


def test_classify_inspect_website_project():
    got = classify_rules("inspect website project")
    assert got.intent == Intent.INSPECT_WEBSITE_PROJECT


def test_inspect_website_project_action_read_only(tmp_path):
    site = tmp_path / "site"
    (site / "src" / "app").mkdir(parents=True)
    (site / "src" / "app" / "page.tsx").write_text("export default function Home() {}", encoding="utf-8")
    (site / "src" / "components" / "layout").mkdir(parents=True)
    (site / "src" / "components" / "layout" / "site-header.tsx").write_text(
        'href="/demo"', encoding="utf-8"
    )
    (site / "src" / "components" / "layout" / "site-footer.tsx").write_text(
        'href="/login"', encoding="utf-8"
    )
    (site / "src" / "lib" / "reasoning").mkdir(parents=True)
    (site / "src" / "lib" / "reasoning" / "responses.ts").write_text(
        "seed(command) pick", encoding="utf-8"
    )
    (site / "src" / "lib" / "reasoning" / "memory.ts").write_text(
        "sessionStorage", encoding="utf-8"
    )
    (site / "src" / "lib" / "reasoning" / "compound.ts").write_text(
        "NUTRITION_PATTERNS", encoding="utf-8"
    )
    (site / "src" / "lib" / "reasoning" / "orchestrator.ts").write_text(
        "STAGE_DELAYS", encoding="utf-8"
    )
    (site / "src" / "middleware.ts").write_text("matcher", encoding="utf-8")
    (site / "src" / "components" / "layout" / "route-transition.tsx").write_text(
        "framer-motion", encoding="utf-8"
    )

    from website_audit.inspector import inspect_website_project

    report = inspect_website_project(site)
    assert "Operational Product Audit" in report
    assert "MISSING" in report or "[ok]" in report


def test_registry_executes_audit():
    from actions.registry import ActionRegistry
    from core.types import CommandRequest

    registry = ActionRegistry()
    action = registry._actions.get(Intent.INSPECT_WEBSITE_PROJECT.value)
    assert action is not None
    result = action.execute(CommandRequest(raw_text="inspect website project", intent=Intent.INSPECT_WEBSITE_PROJECT))
    assert result.status.value == "success"
    assert result.data.get("audit_only") is True
    assert "Website" in result.summary or "website" in result.summary.lower()
