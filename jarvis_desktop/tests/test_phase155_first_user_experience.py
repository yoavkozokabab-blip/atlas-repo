"""Phase 155 — zero-friction first user experience.

These tests assert the *user-facing* surface only (static UI, launcher wording,
and the broad-folder warning helper). They do not touch the semantic resolver,
knowledge / evidence / impact engines, billing, benchmarks, or the website.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from jarvis_desktop import api

ROOT = Path(__file__).resolve().parents[2]
STATIC = ROOT / "jarvis_desktop" / "static"
INDEX = STATIC / "index.html"
ZERO_FRICTION = STATIC / "atlas_zero_friction.js"
APP_JS = STATIC / "app.js"
SUPPORT = STATIC / "support.html"
FEEDBACK = STATIC / "feedback.js"
QUICKSTART = STATIC / "quickstart.html"
RUN_ATLAS = ROOT / "run_atlas.py"
ENTRY = ROOT / "packaging" / "pyinstaller" / "atlas_entry.py"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


# --------------------------------------------------------------------------- #
# 1. First launch shows only the three main actions
# --------------------------------------------------------------------------- #
def test_first_launch_shows_three_main_actions():
    html = _read(INDEX)
    home = html.split('class="home-actions"', 1)[1].split("</div>", 1)[0]
    assert "Load Sample Repository" in home
    assert "Scan My Repository" in home
    assert "Learn more" in home
    # Long tours are de-emphasized: not a primary action button.
    assert "Guided Walkthrough" not in home


def test_advanced_surfaces_are_deemphasized():
    html = _read(INDEX)
    # Diagnostics / support / report are tucked into the user menu, not the main bar.
    # (Phase 194 consolidated the separate "Help & more" menu into the user menu.)
    assert "help-menu" in html
    assert 'id="userMenu"' in html
    assert "Copy diagnostics" in html and "Report an issue" in html
    # Quickstart is available from the top bar (now inside the user menu).
    assert 'href="quickstart.html"' in html
    # Advanced scan options are collapsed.
    assert "scope-advanced" in html
    assert "Scan options" in html


# --------------------------------------------------------------------------- #
# 2. Sample repository path
# --------------------------------------------------------------------------- #
def test_sample_repo_cta_exists():
    html = _read(INDEX)
    assert "Create your first Change Plan" in html
    assert 'id="scanSuccessTitle"' in html


def test_sample_success_recognition_message():
    app = _read(APP_JS)
    assert "Atlas understood the sample repository." in app


def test_sample_does_not_auto_jump_too_quickly():
    # The old behavior force-navigated to Build Plan ~900ms after demo load.
    polish = _read(STATIC / "atlas_polish.js")
    assert "goToFirstBuildPlan()" not in polish.split("promptFirstBuildPlanAfterScan", 1)[1][:400]


# --------------------------------------------------------------------------- #
# 3. Scan success CTA
# --------------------------------------------------------------------------- #
def test_scan_success_cta_exists():
    html = _read(INDEX)
    block = html.split('id="scanSuccess"', 1)[1].split("</section>", 1)[0]
    assert "Create your first Change Plan" in block
    assert "Explore Codebase Map" in block


# --------------------------------------------------------------------------- #
# 4. Send-to-AI export workflow
# --------------------------------------------------------------------------- #
def test_export_to_ai_buttons_exist():
    js = _read(ZERO_FRICTION)
    assert "Copy for Claude" in js
    assert "Copy for Cursor" in js
    assert "Copy for Codex" in js
    assert "Download Markdown" in js
    assert "Paste into Claude, Cursor, or Codex and ask it to implement" in js


def test_send_to_ai_panel_wired_into_workflows():
    app = _read(APP_JS)
    assert app.count('sendToAiPanel("') >= 3  # build, investigate, impact
    assert 'sendToAiPanel("build")' in app
    assert 'sendToAiPanel("investigate")' in app
    assert 'sendToAiPanel("impact")' in app


def test_ai_prompt_includes_safe_modification_instruction():
    js = _read(ZERO_FRICTION)
    assert "How to work safely" in js
    assert "rollback" in js.lower()
    assert "tests" in js.lower()


# --------------------------------------------------------------------------- #
# 5. No raw traceback in the user UI
# --------------------------------------------------------------------------- #
def test_no_raw_traceback_in_user_ui():
    for path in (INDEX, SUPPORT, QUICKSTART):
        text = _read(path)
        assert "Traceback (most recent call last)" not in text


def test_frozen_launch_routes_failures_to_support_not_traceback():
    entry = _read(ENTRY)
    assert "excepthook" in entry
    assert "startup-error.html" in entry
    assert "_open_support_fallback" in entry
    launcher = _read(RUN_ATLAS)
    # Frozen launches log instead of printing tracebacks, and fall back to Support.
    assert "_frozen_launch" in launcher
    assert "support.html" in launcher


# --------------------------------------------------------------------------- #
# 6. Jargon is reduced / hidden
# --------------------------------------------------------------------------- #
def test_nav_uses_plain_language_labels():
    html = _read(INDEX)
    assert ">Codebase Map<" in html
    assert ">Change Plan<" in html
    assert ">What breaks?<" in html
    assert ">Repository Context<" in html


def test_old_jargon_removed_from_nav():
    html = _read(INDEX)
    assert 'onclick="go(\'center\')">Repository Map<' not in html
    assert 'onclick="go(\'build\')">Build Plan<' not in html
    assert 'onclick="go(\'export\')">Export<' not in html


# --------------------------------------------------------------------------- #
# 7. Support wording says saved locally
# --------------------------------------------------------------------------- #
def test_report_issue_wording_is_saved_locally():
    fb = _read(FEEDBACK)
    assert "Save feedback locally" in fb
    assert "Saved on this device only" in fb
    assert "Saved locally" in fb
    support = _read(SUPPORT)
    assert "saved locally" in support.lower()
    assert "Copy diagnostics" in support
    assert "Open support bundle" in support


# --------------------------------------------------------------------------- #
# 8. Broad-folder warning logic
# --------------------------------------------------------------------------- #
def test_broad_folder_warning_node_modules():
    warnings = api.broad_folder_warnings(
        "/projects/app", child_names=["node_modules", "src"], nested_git_count=0
    )
    assert any("node_modules" in w for w in warnings)


def test_broad_folder_warning_multiple_projects():
    warnings = api.broad_folder_warnings(
        "/work/all-repos", child_names=[".git"], nested_git_count=3
    )
    assert any("sub-project" in w for w in warnings)


def test_broad_folder_warning_large_file_count():
    warnings = api.broad_folder_warnings(
        "/projects/huge", total_files=50000, child_names=[], nested_git_count=0
    )
    assert any("file count" in w.lower() for w in warnings)


def test_broad_folder_warning_desktop_and_external_repos():
    desktop = api.broad_folder_warnings(
        "/home/dev/Desktop", child_names=[], nested_git_count=0
    )
    assert any("desktop" in w.lower() for w in desktop)
    external = api.broad_folder_warnings(
        "/work/external_repos", child_names=[], nested_git_count=0
    )
    assert any("external_repos" in w for w in external)


def test_broad_folder_warning_clean_folder_is_silent():
    warnings = api.broad_folder_warnings(
        "/projects/my-app", child_names=["src", "README.md"], total_files=120, nested_git_count=0
    )
    assert warnings == []


def test_validation_surfaces_broad_warnings_field(tmp_path):
    (tmp_path / "main.py").write_text("print('hi')\n", encoding="utf-8")
    (tmp_path / "node_modules").mkdir()
    res = api.validate_repository_path(str(tmp_path))
    assert res.get("ok") is True
    assert "broad_warnings" in res
    assert any("node_modules" in w for w in res["broad_warnings"])


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(pytest.main([__file__, "-v"]))
