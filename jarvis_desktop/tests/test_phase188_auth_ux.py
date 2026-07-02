"""Phase 188 - auth UX and pre-access workflow gating tests."""
from __future__ import annotations

import re
from pathlib import Path


STATIC = Path(__file__).resolve().parents[1] / "static"
INDEX = (STATIC / "index.html").read_text(encoding="utf-8")
CSS = (STATIC / "styles.css").read_text(encoding="utf-8")
APP_JS = (STATIC / "app.js").read_text(encoding="utf-8")
ACCOUNTS_JS = (STATIC / "atlas_accounts.js").read_text(encoding="utf-8")
ADMIN_HTML = (STATIC / "admin.html").read_text(encoding="utf-8")


def _snippet_after(marker: str, length: int = 420) -> str:
    pos = APP_JS.find(marker)
    assert pos >= 0, f"missing marker {marker}"
    return APP_JS[pos : pos + length]


def test_phase188_auth_layout_is_dedicated_and_polished():
    assert '<body class="mode-beginner auth-mode auth-loading">' in INDEX
    assert 'id="auth-layout"' in INDEX
    assert 'id="app-shell"' in INDEX
    assert "body.auth-mode #app-shell{display:none !important}" in CSS
    assert "body.auth-mode #auth-layout{display:flex}" in CSS
    assert "Sign in" in INDEX
    assert "Apply for beta access" in INDEX
    assert "Atlas beta access is manually approved. Your code stays local." in INDEX
    assert 'id="acc-login-email-msg"' in INDEX
    assert 'id="acc-reg-email-msg"' in INDEX
    assert ".auth-card" in CSS
    assert ".auth-form-scroll" in CSS


def test_phase188_beta_application_fields_are_present():
    for field_id in (
        "acc-current-dev-yes",
        "acc-current-dev-no",
        "acc-project-use",
        "acc-company-name",
        "acc-company-size",
        "acc-dev-exp",
        "acc-primary-role",
        "acc-repo-size",
        "acc-languages",
        "acc-notes",
    ):
        assert f'id="{field_id}"' in INDEX

    for name in ('name="acc-tools"', 'name="acc-help"'):
        assert name in INDEX

    for value in (
        "claude",
        "cursor",
        "codex",
        "github_copilot",
        "windsurf",
        "understand_codebases",
        "planning_changes",
        "what_breaks",
    ):
        assert f'value="{value}"' in INDEX


def test_phase188_signin_and_blocked_state_messages_are_human_readable():
    expected = [
        "Enter a valid email address.",
        "No Atlas account was found for this email.",
        "Incorrect password. Try again or reset it.",
        "Your account was created and is waiting for beta approval.",
        "This account is suspended. Contact the Atlas operator.",
        "This account is banned and cannot access Atlas.",
        "Your Atlas access is not currently active.",
        "This device is no longer authorized for this account.",
    ]
    for message in expected:
        assert message in ACCOUNTS_JS

    assert "setFieldError('acc-login-email-msg', 'Enter a valid email address.')" in ACCOUNTS_JS
    assert "setFieldError('acc-reg-email-msg', 'Enter a valid email address.')" in ACCOUNTS_JS


def test_phase188_workflow_views_and_actions_require_valid_access():
    assert 'const PROTECTED_VIEWS = new Set(["home", "scan", "center", "build", "investigate", "impact", "export"])' in APP_JS
    assert 'PROTECTED_VIEWS.has(view) && !requireAtlasAccess("Atlas")' in APP_JS

    for marker in (
        "function onboardingLoadSample()",
        "async function validateRepoPath(showToast)",
        "async function browseRepoFolder()",
        "async function loadDemoMode(pack)",
        "async function scanFlow()",
        "async function executeScanFlow(validation)",
        "async function startProductTour()",
        "async function copyContext(target)",
        "async function runChangePlan()",
        "async function runInvestigationPlan()",
        "async function runImpact()",
        "async function refreshExport()",
        "async function copyExport()",
    ):
        assert "requireAtlasAccess" in _snippet_after(marker), marker

    assert "requireAccess: () => {" in ACCOUNTS_JS
    assert "showAccountScreen('blocked')" in ACCOUNTS_JS
    assert "showAccountScreen('login')" in ACCOUNTS_JS


def test_phase188_license_gating_disables_workflow_buttons():
    assert "btn.disabled = !licenseValid;" in ACCOUNTS_JS
    assert 'btn.title = (!licenseValid)' in ACCOUNTS_JS
    assert 'data-lock="1"' in INDEX

    protected_labels = [
        "Load Sample Repository",
        "Scan Repository",
        "Create Change Plan",
        "Analyze symptom",
        "Show what breaks",
        "Copy for Claude",
    ]
    for label in protected_labels:
        assert label in INDEX


def test_phase188_admin_review_lists_profile_fields_without_hash_columns():
    # The applicants section was renamed "Beta applicants" -> "Pending Applications".
    heading = "Pending Applications" if "Pending Applications" in ADMIN_HTML else "Beta applicants"
    assert heading in ADMIN_HTML
    assert "/api/accounts/admin/users" in ADMIN_HTML
    assert "Company size" in ADMIN_HTML
    assert "Experience" in ADMIN_HTML
    assert "Primary role" in ADMIN_HTML
    assert "Tools" in ADMIN_HTML
    assert "Notes" in ADMIN_HTML

    forbidden = re.compile(r"password_hash|refresh_hash|refresh_token|access_token", re.IGNORECASE)
    applicant_section = ADMIN_HTML[ADMIN_HTML.find(heading):]
    assert not forbidden.search(applicant_section)
