# Phase 186D Accounts Red Team Verification

Audit only. No implementation changes.

## Verdict

| Cohort | Verdict |
|---|---|
| 5 supervised beta users | NO-GO |
| 20 supervised beta users | NO-GO |

## Evidence Run

- Read: `reports/phase186b_architecture_review.md`, `reports/phase186c_accounts_beta_safety_fixes.md`, `accounts_service/`, `jarvis_desktop/accounts_client.py`, `jarvis_desktop/accounts_routes.py`.
- Regression suite: `py -3 -B -m pytest accounts_service/tests/test_phase186c_accounts_beta_safety.py jarvis_desktop/tests/test_phase186_accounts.py jarvis_desktop/tests/test_phase186_admin.py jarvis_desktop/tests/test_phase186_privacy.py -q -p no:cacheprovider --tb=short`
- Result: 73 passed, 3 warnings, under vendored-dependency read permission.
- Explicit attack harness: 20 attacks run; 13 passed; 7 blockers remain.
- Full machine-readable results: `reports/phase186d_attack_results.json`.

## What Passed

- Service restart after login: access token remained valid and refresh still worked.
- Forged JWT: rejected with 401.
- Modified role claim: rejected with 401.
- Expired JWT: rejected with 401.
- Refresh replay: replay rejected with 401; session-family invalidation is not implemented.
- Refresh token DB leakage: no raw refresh token stored; `sessions.refresh_hash` values were 64-character hashes.
- Feedback secrets and paths: stored feedback was redacted.
- Support bundle secrets: no raw tested JWT/access/refresh token/API key/bearer/password/auth-header value leaked.
- Regular user admin access: denied with 403.
- Regular admin unban attempt: denied with 403.
- Admin audit log: tested status/license/beta/force-logout/device actions wrote audit logs; tested secrets did not appear in audit rows.
- Rate limit: repeated login/register attempts were throttled; stale rate-limit key pruned.
- Admin dashboard: aggregate-only response; no tested raw feedback/crash/repo/prompt/export content exposed.

## Real Remaining Blockers

### 1. Banned/suspended users are denied by the service but still authenticated by desktop cache

Attack results:

- Banned user: service `/user/me` = 403, service `/user/license` = 403, but desktop `get_account_state()` returned `authenticated=True`.
- Suspended user: service `/user/me` = 403, service `/user/license` = 403, but desktop `get_account_state()` returned `authenticated=True`.

Repository evidence:

- `get_current_user()` rejects banned/suspended/expired users in `accounts_service/dependencies.py:44-55`.
- `accounts_client.get_valid_access_token()` returns the locally cached access token while it is locally unexpired in `jarvis_desktop/accounts_client.py:125-132`.
- If refresh/license calls return an HTTP error, the client can fall through to cached license state in `jarvis_desktop/accounts_client.py:142-144` and `jarvis_desktop/accounts_client.py:173-195`.
- Account state reports `authenticated` from local token plus local user in `jarvis_desktop/accounts_client.py:325-336`.

Impact: banned/suspended transitions do not fully take effect in the desktop client.

### 2. Expired licenses do not block direct local workflow use

Attack result: service license check returned `valid=False`, desktop license state returned `valid=False`, but local protected workflow call returned `protected=200/True`.

Repository evidence:

- `/user/license` correctly returns invalid for expired licenses in `accounts_service/routers/users.py:28-54`.
- Core workflow routes are registered directly in `jarvis_desktop/server.py:80-85` and `jarvis_desktop/server.py:131-138`.
- Account routes are merged separately in `jarvis_desktop/server.py:163-164`.
- UI gating disables `[data-lock="1"]` buttons in `jarvis_desktop/static/atlas_accounts.js:179-188`, but the local route handlers do not enforce account/license state.

Impact: license expiry can be bypassed by direct local API calls.

### 3. Device revocation does not invalidate existing access-token use

Attack result: admin device revoke returned 204 and refresh from that device returned 401, but the old access token still returned `/user/me HTTP 200`; desktop state remained authenticated.

Repository evidence:

- Admin revoke marks device revoked and revokes matching refresh sessions in `accounts_service/routers/admin.py:248-269`.
- Refresh checks refresh-session/device match in `accounts_service/routers/auth.py:179-212`.
- Access-token auth loads the user by token subject and does not check device/session revocation in `accounts_service/dependencies.py:25-55`.

Impact: revoked devices can keep using already-issued access tokens until expiry, and desktop cached state remains usable.

### 4. Cross-account device_id reuse still bypasses device ownership and limits

Attack result: normal second device was denied with 403, but another user registered with an existing foreign `device_id` and got 201; DB contained a bypass session.

Repository evidence:

- Existing devices are looked up only by `Device.device_id == device_id` in `accounts_service/routers/auth.py:71-85`.
- The existing-device branch returns without checking `device.user_id == user.user_id`.

Impact: fake/stolen device ids can create cross-account sessions and bypass device limits.

### 5. Analytics still accepts sensitive data in `event_type`

Attack result:

- Extra fields for source code, prompts, exports, repo paths, and file names were rejected.
- Path-like `app_version` was rejected.
- `event_type=ghp_LEAK` returned 204.
- `event_type=def x(): pass` returned 204.

Repository evidence:

- `event_type` is an allowed string field in `accounts_service/routers/analytics.py:35-55`.
- The secret regex does not cover `ghp_` values in `accounts_service/routers/analytics.py:29-31`.
- Unknown event types are silently accepted in `accounts_service/routers/analytics.py:83-85`.

Impact: hostile authenticated clients can smuggle short secret/code-shaped strings through the analytics boundary.

### 6. Offline grace can still be extended by local cache tampering

Attack result: editing local `license_checked_at` changed the client from `offline_grace_expired` to `authenticated=True` and `valid=True`.

Repository evidence:

- Offline grace trusts local `license_checked_at` in `jarvis_desktop/accounts_client.py:187-195`.
- Local `access_token_expires_at` controls whether a cached access token is treated as valid in `jarvis_desktop/accounts_client.py:125-132`.
- Account state trusts local token plus user for `authenticated` in `jarvis_desktop/accounts_client.py:325-336`.

Impact: this requires local file tampering, but it is still a real offline-grace bypass on the same machine/user profile.
