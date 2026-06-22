# 03 — Auth Flow User QA

**Date:** 2026-06-20. Tested against the live API (local file-store run; logic identical to prod-Supabase).

| Scenario | Result | Clarity |
|---|---|---|
| Create account | 201 → redirect to `/account` | clear |
| Duplicate account | 400 `"An account with this email already exists."` | clear + actionable |
| Wrong password | 401 `"Invalid email or password."` | clear; **anti-enumeration** |
| Unknown email | 401 `"Invalid email or password."` (identical to wrong-pw) | correct — no enumeration leak |
| Weak password (<8) | 400 `"Password must be at least 8 characters."` | clear |
| Invalid email | 400 `"Enter a valid email address."` | clear |
| Empty fields | 401 generic | acceptable |
| Logout | `POST /api/auth/logout` → `/` | clear |
| Login again | 200 → `/account` | clear |
| Close tab, reopen `/account` | session persists (httpOnly cookie, 7-day) → stays signed in; anon → 307 `/login` | correct |
| Forgot password | always returns generic "if an account exists, a reset link has been sent" | correct (no leak); **but** email delivery is stub (logs link) — see note |
| Delete account | requires typing `DELETE`; then `/api/account/delete` → `/` | safe (guarded) |

## Assessment
- **Error clarity:** strong. Messages are specific where safe (dup/weak/invalid) and generic where required (login). The form renders errors in red and disables the button while busy.
- **Success/redirect clarity:** register/login both redirect to `/account`; logout to `/`. Clear.
- **Session persistence:** httpOnly signed cookie, 7-day, `secure` in prod — feels correct. **No server-side revocation** (a stolen cookie is valid until exp) — acceptable for beta, flagged for later.
- **Note — password reset:** the reset link is **logged, not emailed** (no transactional email provider wired). A real user clicking "forgot password" gets the generic "check your email" message but **no email arrives**. This is a real first-user dead-end for password recovery. Not fixable without an email provider (owner) → P1.

## Fixes this pass
None to auth code (out of scope + already clean). Password-reset email delivery flagged as P1 owner item.
