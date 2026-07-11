"""Phase 188 - auth UX and account workflow gating tests."""
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
    assert '<body class="mode-beginner auth-mode auth-loading' in INDEX
    assert 'id="auth-layout"' in INDEX
    assert 'id="app-shell"' in INDEX
    assert "body.auth-mode #app-shell{display:none !important}" in CSS
    assert "body.auth-mode #auth-layout{display:flex}" in CSS
    assert "Sign in" in INDEX
    assert "Create free account" in INDEX
    assert "Continue without an account" in INDEX
    assert "Create your account" in INDEX
    assert "Your code stays on your machine." in INDEX
    assert 'id="acc-login-email-msg"' in INDEX
    assert 'id="acc-reg-email-msg"' in INDEX
    assert ".auth-card" in CSS
    assert ".auth-form-scroll" in CSS


def test_phase188_account_profile_fields_are_present():
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
        "Your Atlas account was created, but we could not confirm it was saved.",
        "This account is suspended. Contact support.",
        "This account is banned and cannot access Atlas.",
        "Your Atlas license is not active.",
        "This device is no longer authorized for this account.",
    ]
    for message in expected:
        assert message in ACCOUNTS_JS

    assert "setFieldError('acc-login-email-msg', 'Enter a valid email address.')" in ACCOUNTS_JS
    assert "setFieldError('acc-reg-email-msg', 'Enter a valid email address.')" in ACCOUNTS_JS


def test_phase188_register_and_login_route_into_app_without_pending_screen():
    register_pos = ACCOUNTS_JS.find("api('POST', '/api/accounts/register'")
    assert register_pos >= 0
    register_success = ACCOUNTS_JS[register_pos : register_pos + 700]
    assert "showAccountScreen('submitted')" in register_success
    assert "refreshState();" in register_success

    login_pos = ACCOUNTS_JS.find("api('POST', '/api/accounts/login'")
    assert login_pos >= 0
    login_success = ACCOUNTS_JS[login_pos : login_pos + 520]
    assert "refreshState()" in login_success

    old_pending_copy = (INDEX + ACCOUNTS_JS).lower()
    assert "waiting for beta approval" not in old_pending_copy
    assert "beta access pending" not in old_pending_copy


def test_phase188_workflow_views_and_actions_require_valid_access():
    assert 'const PROTECTED_VIEWS = new Set(["home", "scan", "hn", "ask", "center", "build", "investigate", "impact", "export"])' in APP_JS
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
    assert "startGuest: startGuest" in ACCOUNTS_JS
    assert "api('POST', '/api/accounts/guest/start'" in ACCOUNTS_JS
    assert "_state && (_state.authenticated || _state.local_access)" in ACCOUNTS_JS
    assert "showAccountScreen('blocked')" in ACCOUNTS_JS
    assert "showAccountScreen('login')" in ACCOUNTS_JS


def test_phase188_license_gating_disables_workflow_buttons():
    assert "btn.disabled = !licenseValid;" in ACCOUNTS_JS
    assert 'btn.title = (!licenseValid)' in ACCOUNTS_JS
    assert 'data-lock="1"' in INDEX

    protected_labels = [
        "Load sample repository",
        "Scan local repository",
        "Create plan",
        "Analyze symptom",
        "Show what breaks",
        "Copy for Claude",
    ]
    for label in protected_labels:
        assert label in INDEX


def test_phase188_admin_review_lists_profile_fields_without_hash_columns():
    assert "Account Requests" in ADMIN_HTML
    assert "/api/accounts/admin/users" in ADMIN_HTML
    assert "Company size" in ADMIN_HTML
    assert "Experience" in ADMIN_HTML
    assert "Primary role" in ADMIN_HTML
    assert "Tools" in ADMIN_HTML
    assert "Notes" in ADMIN_HTML

    forbidden = re.compile(r"password_hash|refresh_hash|refresh_token|access_token", re.IGNORECASE)
    applicant_section = ADMIN_HTML[ADMIN_HTML.find("Account Requests") :]
    assert not forbidden.search(applicant_section)
