# Phase 188 - Auth UX and Beta Profile Onboarding

## Summary

Phase 188 replaced the small pre-existing sign-in surface with a dedicated Atlas auth layout, added a beta application profile, and moved workflow access checks ahead of repository/workflow execution paths.

Final recommendation for first 3-5 supervised beta users: **GO**. The three prior blockers (account-service tests, after screenshots, commit lock) are all resolved. Account-service, admin, and privacy tests now execute and pass, the auth UX screenshots were captured from the live app, and the stale `.git/index.lock` was removed so the work can commit cleanly.

## UI/UX Changes

- Dedicated centered auth layout for sign-in, beta application, and blocked account states.
- App shell, repository chips, workflow navigation, scan controls, dashboards, sample controls, and workflow panels are hidden while `body.auth-mode` is active.
- Inline email validation now shows: `Enter a valid email address.`
- Sign-in error copy maps unknown email, wrong password, pending approval, suspended, banned, inactive license, and device revoked states to human-readable messages.
- Create account is now a beta application form with the copy: `Atlas beta access is manually approved. Your code stays local.`
- Beta application collects developer status, intended use, optional company name, company size, developer experience, primary role, coding tools, optional languages/frameworks, repo size, help categories, and optional notes.
- Workflow actions now check account access before validation, folder selection, sample loading, scan execution, Change Plan, Debug, What Breaks, context refresh, and copy/export.

## Screenshots

Captured from the live Atlas desktop app (`127.0.0.1:8802`) via Playwright/Chromium, driving the real auth state machine. Saved under `reports/phase188_auth_ux/`:

- `00_auth_before.png` — pre-Phase-188 baseline: the old login box floated over the full app shell (repository chips and demo packs leaked through).
- `01_login_signed_out.png` — dedicated signed-out sign-in screen.
- `02_create_account_beta_profile.png` — create-account beta application form with the BETA PROFILE section.
- `03_pending_approval.png` — "Beta access pending / waiting for beta approval" state.
- `04_access_denied_no_beta.png` — "Account suspended / Contact the Atlas operator" denied state.
- `05_admin_profile_review.png` — admin Beta-applicants table showing profile columns (Use, Company size, Experience, Primary role, Tools, Notes) and **no** password/hash/token columns.

The earlier `file://` / `127.0.0.1:8765` browser-policy block was avoided by serving the app on `127.0.0.1:8802` and driving it with a scripted Chromium session (`scripts/capture_phase188_screens.py`). The admin screenshot uses representative sample applicants rendered through the page's own row template, because no live accounts service runs in the verification environment; the privacy assertion (no hash/token columns) is enforced by the schema and by `test_phase188_admin_can_view_profile_without_password_or_token_hashes`.

## Files Changed

- `accounts_service/models.py`
- `accounts_service/schemas.py`
- `accounts_service/routers/auth.py`
- `accounts_service/routers/users.py`
- `accounts_service/tests/test_phase186f_beta_smoke.py`
- `accounts_service/tests/test_phase188_beta_profile_accounts.py`
- `jarvis_desktop/accounts_client.py`
- `jarvis_desktop/accounts_routes.py`
- `jarvis_desktop/static/index.html`
- `jarvis_desktop/static/styles.css`
- `jarvis_desktop/static/atlas_accounts.js`
- `jarvis_desktop/static/app.js`
- `jarvis_desktop/static/admin.html`
- `jarvis_desktop/tests/test_phase188_auth_ux.py`
- `reports/phase188_auth_ux/` (6 screenshots: before + login + beta profile + pending + denied + admin review)
- `scripts/capture_phase188_screens.py` (screenshot capture harness; no product code)
- `reports/phase188_auth_ux_beta_profile.md`
- `reports/phase188_results.json`

## Data Storage

- Account database: `accounts_service/config.py` reads `ATLAS_ACCOUNTS_DB`; default is `sqlite:///./atlas_accounts.db`.
- Database initialization: `accounts_service/database.py:init_db()` calls `Base.metadata.create_all(bind=engine)`, so the new table is created with the existing init path.
- Users and password hashes: `users.password_hash` in `accounts_service/models.py`.
- Refresh/session hashes: `sessions.refresh_hash` in `accounts_service/models.py`; raw refresh tokens are not stored.
- Device IDs and revocation state: `devices.device_id`, `devices.status`, and `devices.revoked_by`.
- Licenses: `licenses.plan`, `licenses.status`, `licenses.expires_at`, `licenses.max_devices`.
- Beta profile metadata: new `beta_profiles` table with only non-sensitive beta application metadata.
- Admin audit logs: `admin_audit_log`.
- Accounts-service feedback: `feedback.message_redacted`.
- Desktop feedback: `desktop_data_dir()/feedback/feedback.jsonl` from `jarvis_desktop/api.py`; text is redacted before persistence.
- Desktop account cache: `desktop_data_dir()/accounts_state.json`; this is protected by existing cache signing/HMAC logic.
- Desktop data directory resolution: `ATLAS_DESKTOP_DATA` or `JARVIS_DESKTOP_DATA` override, otherwise `~/.jarvis_desktop`, then `%LOCALAPPDATA%/Atlas/desktop_data`, then temp fallback.
- Support bundle generation: `jarvis_desktop/install_support.py:export_support_bundle()` builds `atlas_support_bundle_*.zip` in memory and returns base64 content.

## Security/Privacy Review

- Password hashes are not exposed by `AdminUserOut` or the admin applicant UI.
- Refresh/session hashes are not exposed by `AdminUserOut` or the admin applicant UI.
- Access and refresh tokens are not exposed by the admin applicant UI.
- Beta profile optional text rejects common secret, bearer token, GitHub token, OpenAI/Anthropic key, code-like, and local path patterns.
- Beta profile does not collect source code, repository contents, repository paths, prompts, exports, or overly personal information.
- Support bundles continue to redact account state and support text through `_redact_support_text()` and `accounts_state_redacted.json`.
- Feedback continues to store redacted message text in the account service.

## Tests Added

- `accounts_service/tests/test_phase188_beta_profile_accounts.py::test_phase188_register_stores_beta_profile_and_keeps_account_pending`
- `accounts_service/tests/test_phase188_beta_profile_accounts.py::test_phase188_optional_company_name_may_be_empty`
- `accounts_service/tests/test_phase188_beta_profile_accounts.py::test_phase188_profile_rejects_secrets_code_and_paths`
- `accounts_service/tests/test_phase188_beta_profile_accounts.py::test_phase188_admin_can_view_profile_without_password_or_token_hashes`
- `accounts_service/tests/test_phase188_beta_profile_accounts.py::test_phase188_desktop_register_validates_email_password_and_required_profile`
- `accounts_service/tests/test_phase188_beta_profile_accounts.py::test_phase188_signin_error_messages_are_specific`
- `jarvis_desktop/tests/test_phase188_auth_ux.py::test_phase188_auth_layout_is_dedicated_and_polished`
- `jarvis_desktop/tests/test_phase188_auth_ux.py::test_phase188_beta_application_fields_are_present`
- `jarvis_desktop/tests/test_phase188_auth_ux.py::test_phase188_signin_and_blocked_state_messages_are_human_readable`
- `jarvis_desktop/tests/test_phase188_auth_ux.py::test_phase188_workflow_views_and_actions_require_valid_access`
- `jarvis_desktop/tests/test_phase188_auth_ux.py::test_phase188_license_gating_disables_workflow_buttons`
- `jarvis_desktop/tests/test_phase188_auth_ux.py::test_phase188_admin_review_lists_profile_fields_without_hash_columns`

## Tests Run

All executed from a normal local terminal with full filesystem access (the prior `.lib` permission block is gone):

- `py -3 -m pytest accounts_service/tests/test_phase188_beta_profile_accounts.py jarvis_desktop/tests/test_phase188_auth_ux.py -p no:cacheprovider` — **PASS, 12 passed** (6 account-service + 6 auth-UX). This is the suite that was BLOCKED before.
- `py -3 -m pytest accounts_service/tests/test_phase186f_beta_smoke.py accounts_service/tests/test_phase186e_accounts_blocker_remediation.py accounts_service/tests/test_phase186c_accounts_beta_safety.py jarvis_desktop/tests/test_phase186_accounts.py jarvis_desktop/tests/test_phase186_admin.py jarvis_desktop/tests/test_phase186_privacy.py -p no:cacheprovider` — **PASS, 104 passed** (Phase 186/186E/186F account/admin/privacy regression).
- `py -3 -m pytest jarvis_desktop/tests/test_phase143_installer_and_support.py jarvis_desktop/tests/test_phase182a_operations_security.py jarvis_desktop/tests/test_phase181g_persistence_signing.py -p no:cacheprovider` — **50 passed, 1 failed**. The single failure (`test_clear_cache_and_rebuild`) is **pre-existing and unrelated to Phase 188**: it fails identically on clean HEAD with all working-tree changes stashed, because demo mode has no on-disk repository path to rescan after a cache clear. The privacy-relevant `test_support_bundle_no_source_code` in the same file passes.

Total relevant: **166 passed, 1 pre-existing unrelated failure**.

## Remaining Issues

- `test_phase143_installer_and_support.py::test_clear_cache_and_rebuild` fails in demo mode (no repository path to rescan). Confirmed pre-existing (reproduces on clean HEAD), not a Phase 188 regression, and outside the Phase 188 surface (auth/beta-profile). No action taken under the "no behavior changes unless a real Phase 188 regression" rule.

## Final Verdict

Ready for first 3-5 supervised beta users: **GO**.
