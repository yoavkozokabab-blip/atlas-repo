# Phase 191 — Registration Reliability

**Date:** 2026-06-07

## Root cause of the reported error

When a user clicked **Submit application**, the desktop UI called `POST /api/accounts/register`, which proxies to the accounts service at `http://127.0.0.1:8788`. **The accounts service was not auto-started with Atlas Desktop**, so the proxy returned offline/unavailable.

The frontend then routed that error through `_formatLoginError()`, whose default title is **"Sign-in failed"** — wrong context for registration. The user could not tell whether the account, profile, or application was saved.

| Question | Before fix | After fix |
|----------|------------|-----------|
| Was account created? | Unknown | Clear messaging; duplicate email handled explicitly |
| Was profile stored? | Unknown | Confirmed in DB + admin intake on success |
| Was application submitted? | Appeared failed | `submitted: true/false` in API; dedicated completion/failure screens |

## Fixes (Task A)

### Auto-start accounts service
- New `jarvis_desktop/accounts_service_runner.py` starts `python -m accounts_service.main` when needed.
- Desktop server boot calls `ensure_running_async()`.
- Register/login routes call `ensure_running()` before proxying.

### Registration-specific errors
- `accounts_routes.accounts_register` returns structured codes: `service_unavailable`, `duplicate_email`, `validation_error`.
- Never uses "Sign-in failed" for registration.
- Service down → **Application not submitted** panel with Retry / Save draft / Contact support.

### Partial / duplicate clarity
- Duplicate email → explains account may already exist; suggests sign-in.
- API includes `submitted: false` on all failure paths.

## Fixes (Task B — draft recovery)

- Local draft key: `atlas_beta_application_draft_v1` (localStorage).
- Session passwords: `atlas_beta_application_session_v1` (sessionStorage).
- Auto-save on wizard input/change; restore on page load and when opening register panel.
- Draft preserved on submission failure; cleared only on successful submit.

## Verification tests

| Test | Result |
|------|--------|
| Service offline response shape | PASS |
| Successful submit → account + profile + notification | PASS |
| Duplicate submit | PASS |
| Draft validation contract | PASS |
| Approve / reject application | PASS |

Run: `py -3 -m pytest accounts_service/tests/test_phase191_registration_reliability.py jarvis_desktop/tests/test_phase191_draft_contract.py -q`

## Files changed

- `jarvis_desktop/accounts_service_runner.py` (new)
- `jarvis_desktop/server.py`
- `jarvis_desktop/accounts_routes.py`
- `jarvis_desktop/accounts_client.py`
- `jarvis_desktop/static/atlas_accounts.js`
- `jarvis_desktop/static/index.html`
- `accounts_service/models.py`
- `accounts_service/routers/auth.py`
- `accounts_service/routers/admin.py`
- `accounts_service/schemas.py`
