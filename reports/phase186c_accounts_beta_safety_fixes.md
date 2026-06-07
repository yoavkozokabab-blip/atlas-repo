# Phase 186C — Accounts Beta Safety Fixes

**Date:** 2026-06-05  
**Scope:** P0/P1 account-system blockers only. No Stripe, teams, enterprise, Atlas intelligence, graph, impact, persistence, UX, or packaging changes.

---

## Summary

| ID | Issue | Status |
|----|-------|--------|
| P0-1 | JWT secret regenerated on every restart | **Fixed** |
| P1-1 | Feedback stored raw in `message_redacted` | **Fixed** |
| P1-2 | Refresh token plaintext on disk / in bundles | **Fixed** |
| P1-3 | Unverified JWT claim trust | **Fixed** |
| P1-4 | Admin action validation gaps | **Fixed** |
| P1-5 | Rate limiter memory growth | **Fixed** |

---

## P0-1 — Stable JWT Secret

**Problem:** `config.py` generated a new random secret on each process start, invalidating all access tokens and forcing re-login after every restart.

**Fix:**
- New module `accounts_service/jwt_secret.py` loads secret in priority order:
  1. `ATLAS_AUTH_JWT_SECRET` env var
  2. `ATLAS_JWT_SECRET` env var (legacy/test)
  3. Persisted file `{data_dir}/auth/jwt_secret` (created once with mode `0600`)
- `config.py` calls `load_jwt_secret()` at import time.
- Secret is never logged, returned by `/health`, included in support bundles, or exposed via admin APIs.

**Data directory resolution:** `ATLAS_ACCOUNTS_DATA_DIR` if set, else parent of SQLite DB path.

---

## P1-1 — Feedback Redaction

**Problem:** `Feedback.message_redacted` stored raw user text despite the column name.

**Fix:**
- New `accounts_service/redaction.py` with `redact_feedback_message()`.
- New `POST /feedback` route applies redaction before insert.
- Redacts: API keys, Bearer/JWT tokens, GitHub/Anthropic/OpenAI-style keys, Windows and Unix paths, incidental emails (preserves explicit `contact_email` field).

---

## P1-2 — Refresh Token Storage

**Problem:** Risk of raw refresh tokens in DB, audit logs, or support bundles.

**Fix (verified existing + hardened):**
- Server stores only SHA-256 hash in `sessions.refresh_hash` (unchanged behavior, now covered by tests).
- Audit log metadata never includes refresh token values.
- `jarvis_desktop/install_support.py` writes `accounts_state_redacted.json` with refresh/access tokens redacted when bundling diagnostics.

---

## P1-3 — Token Claim Trust

**Problem:** Some code paths decoded JWT payload without signature verification.

**Fix:**
- `decode_access_token()` in `security.py` validates signature, expiry, audience, and issuer.
- All auth dependencies use verified decode; forged, expired, and tampered tokens return 401.
- Desktop `accounts_client.py` uses stored `access_token_expires_at` for local validity checks instead of unverified JWT decode.

---

## P1-4 — Admin Action Validation

**Fix:**
- `AdminUserUpdate.status` and `.role` constrained to `Literal` enums (invalid values → 422).
- Banning and **unbanning** require `superadmin` role.
- Role changes require `superadmin`.
- Every `PATCH /admin/users/{id}` writes an audit log entry with before/after metadata.

---

## P1-5 — Rate Limiter Cleanup

**Fix:**
- `prune_stale_keys()` removes idle keys from the in-memory store.
- Automatic prune every 32 checks (idle threshold ≥ 1 hour).
- `reset_rate_limit_store()` exported for test isolation.

---

## Additional Fixes

- **bcrypt/passlib:** Direct `bcrypt` usage in `security.py` (passlib 1.7.x incompatible with bcrypt 4.x).
- **Constant-time login:** Precomputed `_DUMMY_HASH` for unknown-email path.
- **Test hygiene:** Rate-limit reset per test; reuse registered `device_id` on login (avoids max-devices=1 failures); valid `@example.com` emails for Pydantic `EmailStr`.

---

## Files Changed

| File | Change |
|------|--------|
| `accounts_service/jwt_secret.py` | **NEW** — persisted JWT secret |
| `accounts_service/redaction.py` | **NEW** — feedback redaction |
| `accounts_service/config.py` | Use `load_jwt_secret()` |
| `accounts_service/security.py` | bcrypt, verified JWT decode |
| `accounts_service/rate_limit.py` | Prune + test reset |
| `accounts_service/schemas.py` | Admin enums, FeedbackCreate |
| `accounts_service/routers/feedback.py` | **NEW** — redacted feedback endpoint |
| `accounts_service/routers/admin.py` | Unban requires superadmin |
| `accounts_service/routers/auth.py` | Dummy hash for login |
| `accounts_service/main.py` | Include feedback router |
| `accounts_service/tests/test_phase186c_accounts_beta_safety.py` | **NEW** — 15 safety tests |
| `jarvis_desktop/accounts_client.py` | No unverified JWT for auth |
| `jarvis_desktop/install_support.py` | Redacted accounts state in bundle |
| `jarvis_desktop/tests/test_phase186_accounts.py` | Email + rate-limit fixes |
| `jarvis_desktop/tests/test_phase186_admin.py` | Device reuse + email fixes |

---

## Test Results

```
py -3 -m pytest accounts_service/tests/ -q
→ 15 passed

py -3 -m pytest jarvis_desktop/tests/test_phase186_accounts.py -q
→ 17 passed

py -3 -m pytest jarvis_desktop/tests/test_phase186_admin.py -q
→ 19 passed

py -3 -m pytest jarvis_desktop/tests/test_phase186_privacy.py -q
→ 22 passed
```

**186C-specific coverage (`test_phase186c_accounts_beta_safety.py`):**
- JWT secret persists across simulated restart; not in `/health`
- Feedback redacts API keys and paths
- DB stores hashed refresh token only; bundle redacts client token
- Forged/expired/tampered JWT rejected
- Invalid admin status → 422; non-superadmin cannot unban; audit log written
- Stale rate-limit keys pruned; active keys retained

---

## Beta Deployment Notes

1. **Production:** Set `ATLAS_AUTH_JWT_SECRET` to a 32+ byte random value in the service environment. Do not rely on auto-generated file in multi-instance deployments.
2. **Single-node beta:** Auto-generated secret file is acceptable; back up `{data_dir}/auth/jwt_secret` with other service data.
3. **Secret rotation:** Changing the secret invalidates all access tokens; users re-login via refresh token (refresh hashes unaffected).

---

## Out of Scope (unchanged)

- Stripe billing integration
- Teams / enterprise features
- Atlas graph, impact, intelligence engines
- Desktop UX beyond accounts client safety
- Packaging / installer
