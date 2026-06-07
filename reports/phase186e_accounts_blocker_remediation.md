# Phase 186E - Accounts Blocker Remediation

Mode: code changes
Source report: `reports/phase186d_accounts_red_team.md` and `reports/phase186d_attack_results.json`

## Final Recommendation

- 5 supervised beta users: GO
- 20 supervised beta users: GO

All confirmed Phase 186D P0/P1 blockers were fixed and covered by regression tests.

## Blockers Fixed

| 186D ID | Area | Severity | Root Cause | Files Changed | Exact Fix | Regression Test | Before | After | Residual Risk |
|---|---|---|---|---|---|---|---|---|---|
| 9 | Licenses | Critical | Desktop treated server 403 responses as offline and fell back to cached license/account state. Local workflow routes were also callable without account enforcement. | `jarvis_desktop/accounts_client.py`, `jarvis_desktop/server.py` | HTTP 401/403 from `/user/license` now clears cached auth and returns invalid account state. Protected workflow routes now require authenticated active license state. | `test_phase186e_desktop_state_denies_banned_and_suspended_users`, `test_phase186e_protected_workflows_require_valid_license` | Banned user: service denied, Desktop still `authenticated=True`, protected route 200. | Banned user: Desktop `authenticated=False`, tokens cleared, protected routes 403. | Local admin can still delete all account state and re-login if the service permits; service status remains authoritative. |
| 10 | Licenses | Critical | Same cache fallback flaw as ID 9 for suspended users. | `jarvis_desktop/accounts_client.py` | Server-denied account/license checks no longer use cached license grace. | `test_phase186e_desktop_state_denies_banned_and_suspended_users` | Suspended user: service denied, Desktop still authenticated from cache. | Suspended user: Desktop unauthenticated and cached credentials removed. | Same as ID 9. |
| 11 | Licenses | Critical | Desktop workflow routes directly invoked local APIs; UI disablement was the only license gate. | `jarvis_desktop/server.py`, `jarvis_desktop/accounts_client.py` | Added server-side account/license gate for Load Sample, Scan, Change Plan, Debug/Investigate, What Breaks/Impact, Copy for Claude/export, and Copilot Ask in both dispatch and FastAPI paths. | `test_phase186e_protected_workflows_require_valid_license` | Expired license: license invalid but protected local route returned 200. | Expired license: protected local route returns 403 `license_required`. | Older unauthenticated desktop demo tests are no longer valid acceptance for account-gated workflows. |
| 12 | Devices | Critical | Access JWTs were not bound to active session/device rows; revoking a device only blocked refresh, not old access tokens. | `accounts_service/routers/auth.py`, `accounts_service/dependencies.py`, `jarvis_desktop/accounts_client.py` | Access tokens now include `session_id` and `device_id`. Protected dependencies verify the session exists, is unrevoked/unexpired, matches the device, and the device is not revoked. Desktop clears cached state on service denial. | `test_phase186e_device_revocation_invalidates_existing_access_token` | Device revoked: refresh denied but old access token `/user/me` returned 200. | Device revoked: old access token rejected; refresh remains rejected. | Pre-186E access tokens without session/device claims are rejected and require re-login. |
| 13 | Devices | Critical | `_ensure_device()` reused existing device IDs without checking ownership. | `accounts_service/routers/auth.py` | Existing `device_id` now must belong to the authenticating user; cross-account reuse returns 403. | `test_phase186e_cross_account_device_id_reuse_rejected` | Cross-account reused `device_id` registered and created a session. | Cross-account reused `device_id` is rejected before session issuance. | Device IDs remain client-generated, but ownership is enforced server-side. |
| 18 | Privacy | High | Analytics allowed arbitrary short `event_type` strings, so secrets/code-shaped strings could pass in whitelisted metadata. | `accounts_service/routers/analytics.py` | `event_type` is now strict allow-list validated; secret regex also covers GitHub, Anthropic-style, and JWT-looking tokens. | `test_phase186e_analytics_rejects_unknown_event_type_secret_and_code` | `event_type=ghp_LEAK` and `event_type=def x(): pass` returned 204. | Secret/code/unknown event types return 422; valid event types still return 204. | New analytics event types must be added deliberately to the allow-list. |
| 19 | Offline Mode | High | Desktop trusted unsigned local `license_checked_at` and `access_token_expires_at`, allowing local edits to extend offline grace. | `jarvis_desktop/accounts_client.py` | Account state now carries an HMAC over device id, tokens, cached user/license, and license timestamp. Tampered sensitive state returns `local_state_tampered` and does not authenticate. | `test_phase186e_offline_grace_cache_tamper_rejected` | Editing local cache changed expired grace into authenticated valid state. | Edited cache fails integrity and returns unauthenticated invalid state. | A user with write access to both the cache and its local signing secret can still replace local state; service checks remain authoritative once online. |

## Phase 186C Protections Preserved

- Stable JWT secret: existing Phase 186C JWT secret tests still pass.
- Verified JWT signature/expiry: existing forged, modified-role, and expired-token tests still pass.
- Hashed refresh tokens: existing DB hash-only refresh storage test still passes.
- Support bundle redaction: existing support bundle token/secret redaction tests still pass.
- Feedback redaction: existing feedback redaction tests still pass.
- Admin enum validation: existing admin validation tests still pass.
- Superadmin-only unban: existing admin escalation test still passes.
- Audit logging: existing admin audit action tests still pass.
- Rate limiter cleanup: existing cleanup test still passes.

## Tests Added

- `accounts_service/tests/test_phase186e_accounts_blocker_remediation.py::test_phase186e_device_revocation_invalidates_existing_access_token`
- `accounts_service/tests/test_phase186e_accounts_blocker_remediation.py::test_phase186e_cross_account_device_id_reuse_rejected`
- `accounts_service/tests/test_phase186e_accounts_blocker_remediation.py::test_phase186e_desktop_state_denies_banned_and_suspended_users`
- `accounts_service/tests/test_phase186e_accounts_blocker_remediation.py::test_phase186e_protected_workflows_require_valid_license`
- `accounts_service/tests/test_phase186e_accounts_blocker_remediation.py::test_phase186e_analytics_rejects_unknown_event_type_secret_and_code`
- `accounts_service/tests/test_phase186e_accounts_blocker_remediation.py::test_phase186e_offline_grace_cache_tamper_rejected`

## Verification Run

- `py -3 -m pytest accounts_service\tests\test_phase186e_accounts_blocker_remediation.py -q -p no:cacheprovider`
  - Result: 7 passed, 3 warnings.
- `py -3 -m pytest accounts_service\tests\test_phase186c_accounts_beta_safety.py jarvis_desktop\tests\test_phase186_accounts.py jarvis_desktop\tests\test_phase186_admin.py jarvis_desktop\tests\test_phase186_privacy.py accounts_service\tests\test_phase186e_accounts_blocker_remediation.py -q -p no:cacheprovider`
  - Result: 80 passed, 3 warnings.
- `py -3 -m pytest accounts_service\tests\test_phase186c_accounts_beta_safety.py::TestFeedbackRedaction accounts_service\tests\test_phase186c_accounts_beta_safety.py::TestRefreshTokenStorage::test_support_bundle_redacts_refresh_token jarvis_desktop\tests\test_phase174d_final_ship_blockers.py::test_support_bundle_does_not_contain_leak_me jarvis_desktop\tests\test_phase174f_final_blockers.py::test_support_bundle_no_secret_leaks jarvis_desktop\tests\test_phase175d_beta_gate_closure.py::test_a10_strict_support_bundle_no_key_patterns jarvis_desktop\tests\test_phase182a_operations_security.py::test_support_bundle_no_analytics_payload_leak jarvis_desktop\tests\test_phase182a_operations_security.py::test_support_bundle_no_crash_secret_leakage jarvis_desktop\tests\test_phase182a_operations_security.py::test_admin_feedback_no_raw_payload jarvis_desktop\tests\test_phase182a_operations_security.py::test_admin_feedback_summary_no_raw_items_in_insights -q -p no:cacheprovider`
  - Result: 11 passed, 3 warnings.

Initial non-escalated pytest collection failed on sandbox file permissions for `accounts_service\.lib`; the same tests passed under the approved vendored-dependency read path.

## Blockers Remaining

None confirmed from Phase 186D.
