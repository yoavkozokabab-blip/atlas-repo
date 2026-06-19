# SECURITY VERIFICATION (Phase 186D)

**Date:** 2026-06-20 · Two fixes implemented + verified this session; audit + attack-sim results below.

## 1. User-enumeration leak — **FIXED (PASS)**

- **Before:** `accounts_service/routers/auth.py` returned *"No Atlas account was found for this email."* vs *"Incorrect password…"* — and a test (`test_phase188_signin_error_messages_are_specific`) **enforced** the leak.
- **After:** both unknown-email and wrong-password now return one identical `401 "Invalid email or password."` (`auth.py:234-239`). The dummy-hash verify already kept timing roughly constant; the message is now constant too.
- **Test:** rewrote it to `test_phase188_signin_errors_do_not_leak_account_existence`, asserting both responses are byte-identical.
- **Evidence:** `py -3 -m pytest accounts_service/tests -q` → **73 passed** (after the change).
- The website (`_lib/auth.ts:118`) already returned the generic message — now both surfaces match.

## 2. Website rate limiting — **IMPLEMENTED; code-verified (PASS), distributed behavior BLOCKED**

- **Before:** `_lib/ratelimit.ts` used an in-process `Map` — on Vercel each instance has its own memory, so login/register/forgot/waitlist limits **did not hold** across instances.
- **After:** `rateLimit()` is async and backend-pluggable:
  - **Production:** atomic shared counter in Supabase via Postgres RPC `atlas_rate_limit_hit` (migration `supabase/migrations/0002_rate_limits.sql`) — a single-statement upsert, safe across concurrent serverless invocations. No new npm dependency.
  - **Dev/test:** in-process Map fallback (correct for a single instance).
  - **Fail-open** on backend error (logged) — a limiter outage must not lock out every user.
- All four callers updated to `await` it (`login`, `register`, `forgot`, `waitlist` routes).
- **Evidence:** `npx tsc --noEmit` → exit 0; `npm run build` → success (all routes compiled).
- **BLOCKED:** the *distributed* property cannot be runtime-verified here (no Supabase project). Owner must apply migration `0002` and load-test from two instances.

## 3. Security audit (static)

| Area | Finding |
|---|---|
| **Secrets / `.env`** | `.env`, `.env.local`, `websites/.../.env.local` are **gitignored** (confirmed via `git check-ignore`). No real `sk_live_`/`sk_test_`/service-role keys are committed (grep hits are docs only). `jwt_secret.py` generates/loads a secret, not a stored value. **PASS.** |
| **Exported context packs** | `context_pack.py` `include_snippets` defaults **False**; file bodies only included when explicitly requested. The MCP server always calls with `include_snippets=False` (`mcp_server/runtime.py:463`). **No source bodies leave the machine by default.** PASS. |
| **MCP comms** | stdio-local only; remote `scheme://` paths rejected (`runtime.py:258`); every tool output passes `_sanitize()` which redacts secret-like keys/values (`runtime.py:287`); smoke test asserts `repo_health leaks no secrets`. PASS. |
| **Web sessions** | scrypt + `timingSafeEqual`, HMAC httpOnly cookie, `secure` in prod. **Gap (V3):** self-contained token has **no server-side revocation** — a stolen cookie is valid until exp (7 days). Fixed by the `sessions` table in `identity_architecture.md` §6. |
| **Admin endpoints** | `requireAdmin()` gate returns 403; responses use `toSafe()` (never `passwordHash`). PASS. |

## 4. Attack simulations

| Attack | Result | Notes |
|---|---|---|
| **User enumeration** | **DEFEATED** | Identical 401 + identical message now proven by test (§1). |
| **Brute force (login)** | **MITIGATED in design; not load-verified** | Limits now route through a shared store (§2). Effectiveness across instances is BLOCKED on Supabase. accounts_service also limits 5/15min per IP (tested). |
| **Token replay (web session)** | **PARTIAL** | Signature is HMAC-verified and `exp`-checked, but no revocation list — replay of a live, unexpired cookie succeeds until `exp`. → implement `sessions` table. |
| **Webhook spoofing** | **N/A / BLOCKED** | No webhook exists in the shipping site yet. The reference (`~/jarvis_landing/api/stripe/webhook.js`) verifies signatures via `constructEvent`; idempotency/replay table is specified but unbuilt (see `billing_architecture.md` §4). |

## 5. PASS / FAIL / BLOCKED

| Task | Status |
|---|---|
| Fix enumeration leak | **PASS** (code + test + 73 passing) |
| Rate limiting → shared persistent store | **PASS (code)** / **BLOCKED (distributed runtime proof)** |
| Secrets/.env/exports/MCP audit | **PASS** |
| Brute force sim | **MITIGATED**, not load-verified |
| Token replay sim | **PARTIAL** (V3 open; fix specified) |
| Webhook spoofing sim | **BLOCKED** (no webhook deployed) |

**Files changed this phase:** `accounts_service/routers/auth.py`, `accounts_service/tests/test_phase188_beta_profile_accounts.py`, `websites/jarvis-landing/app/_lib/ratelimit.ts`, `websites/jarvis-landing/app/api/{auth/login,auth/register,auth/forgot,waitlist}/route.ts`, `websites/jarvis-landing/supabase/migrations/0002_rate_limits.sql`.
