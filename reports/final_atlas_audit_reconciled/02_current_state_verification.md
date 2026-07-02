# 02 — Current-State Verification (against today's code)

**Date:** 2026-06-20. Each item re-checked now; commands/paths cited.

## 1. Website pages (old 404 reports)
**Result: STALE — all pages exist.** `app/{privacy,terms,contact,download,pricing}/page.tsx` all present (file check). Earlier this session the served prod build returned 200 for /, /pricing, /privacy, /terms, /contact, /download, /faq, /features, /security, /eula, /refund, /cancellation, /login, /account/* (link crawl). The old "404" findings do not reproduce.

## 2. Broken links / placeholders
**Result: CONFIRMED CLEAN.** `grep -rn 'href="#"' websites/jarvis-landing/app` → **0 matches**. Prior internal link crawl: every internal link 200/redirect; `/download/atlas` → 302 (installer redirect, expected, env-gated).

## 3. Claude MCP
**Classification: ONLY LOCAL DEV PROOF EXISTS.**
- `tools/list` / `tools/call` / `atlas_health` / `atlas_scan_repo` / `atlas_repo_summary` / `atlas_build_context_pack`: exercised by `scripts/mcp_smoke_test.py` (**12/12 PASS**, in-process JSON-RPC) and `test_mcp_server.py` (**5 passed**, schema + read-only + JSON-RPC).
- **Real Claude Desktop proof: NONE.** No clean-machine proof. No screenshots from a real client. The smoke test imports the runtime in-process — it is not a real stdio handshake from an installed `Atlas.exe --mcp`.
- The Codex "schema drift due atlas_root_cause" is **not a bug**: `test_mcp_server.py` asserts `required.issubset(names)`; the 18th tool passes.

## 4. Installer
- **SHA256:** `bc2a3e60113e74400d44d99c3548662e94739ec6074860482a116e6edb30cc6e` (`output/Atlas_Setup.exe.sha256`).
- **build_info commit:** `f70a4975e` (current HEAD ancestor; **not** the stale `ce5f73805`).
- **Contains website-auth rewire:** YES — extracted the embedded `PYZ.pyz` from `Atlas.exe`; compiled `accounts_client` contains `/api/auth/desktop/{login,logout,me,register}` + `auth_mode/web_base/verify_session` (verified earlier this session; engine hashes frozen since, `ab_engine_freeze.sha256` = OK).
- **Auth target:** `web_base()` default = `https://useatlas.dev` (extracted from frozen bytecode). The `127.0.0.1:8788` constant is the dormant local-mode fallback.
- **Signed?** NO — `Atlas.iss` has no `SignTool`. Unsigned → SmartScreen. (OWNER_ONLY.)

## 5. Website auth
- **Supabase adapter + file fallback:** `app/_lib/store.ts` — `getStore()` picks Supabase when `SUPABASE_URL`+`SUPABASE_SERVICE_ROLE_KEY` set, else file store; `persist()` **throws in prod without Supabase** (no silent data loss).
- **Desktop auth endpoints:** `app/api/auth/desktop/{register,login,me,logout}/route.ts` present.
- **register/login/me/logout:** present (cookie for browser; bearer for desktop via `userFromBearer`).
- **Rate limiting:** `app/_lib/ratelimit.ts` — async, Supabase RPC `atlas_rate_limit_hit` (migration `0002`) in prod + in-process fallback dev; awaited in login/register/forgot/waitlist.
- **Anti-enumeration:** `loginUser` returns generic `"Invalid email or password."`; accounts_service login fixed to the same generic message (73 tests).

## 6. Desktop auth
- `jarvis_desktop/accounts_client.py`: `auth_mode()` → **website** when frozen (packaged), **local** for source/dev/tests; override `ATLAS_AUTH_MODE`/`ATLAS_WEB_URL`.
- **Website mode:** `/api/auth/desktop/*`; **local fallback** preserved for dev (152 tests green earlier).
- **Packaged behavior:** never spawns/depends on local accounts service (verified earlier with local URL → dead port, auth still worked).
- **Token storage:** HMAC-signed `accounts_state.json` (integrity-checked; `_state_integrity_valid`).
- **/me verification:** `verify_session()` runs on startup (`accounts_service_runner.ensure_running_async` website branch).

## 7. Billing (free-beta honesty)
- **Paid CTAs hidden:** `PAID_PLANS_ENABLED` default OFF (`_config.ts`); pricing/home show "Join the beta" + "Free in beta".
- **Checkout disabled honestly:** `/api/checkout` → **403** "Atlas is in free beta — there is nothing to purchase yet"; `/checkout/plan/*` → redirect to `/pricing`.
- **No false paid claim:** `/account/billing` (authed) shows "Free beta … nothing will ever be charged"; FAQ/pricing say free-beta, paid later.
- **Billing code untouched** (intentional stub retained behind the flag).

## 8. Benchmarks (claims vs proof)
- **Proven:** retrieval value vs grep baseline — Atlas Hit@1 0.35 / Hit@3 0.65 / Hit@5 0.85 / file-recall@5 0.76 / symbol-recall 0.80 / **0 fabrications** / ~40× fewer tokens; grep scores 0 on Hit@k for langchain + home-assistant. (`atlas_value_validation_benchmark.md`.)
- **NOT proven:** end-to-end agent answer quality (Claude vs Claude+Atlas). The blind A/B is **designed + harness-built but NOT run** (no API key; self-grading forbidden). `build` step ran: Atlas context contains gold 17/20 vs grep 11/20.
- **Overstated?** No — the committed reports explicitly state the narrow claim ("better retrieval, not proven better answers"). Matches Codex finding 3/4 in 12.

**Verification verdict:** the functional product (desktop, MCP, retrieval, website pages, auth, free-beta billing) is **source-complete and locally verified**. Every remaining gap is **runtime/clean-machine/owner** (live site, real client, signing, security red-team, agent A/B) — none are unfixed code bugs.
