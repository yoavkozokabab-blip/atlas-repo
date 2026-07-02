# ATLAS 1.0 — LAUNCH ROADMAP

**Source audit:** `reports/phase186_product_completion_audit.md` (2026-06-20)
**Principle:** This is an *unblock-the-user* list, not a feature list. Do nothing here that does not move Atlas closer to a real user succeeding. Order is dependency-correct: do M0 before M1, etc.

**Two tracks.** Pick one before starting:
- **Track A — Free invite beta** (recommended first): everything up to and including **M2**, skipping the billing milestone. Achievable in days, no signing cert, no Stripe.
- **Track B — Paid public 1.0**: all milestones M0–M5.

---

## M0 — DECISIONS & OPS (owner-only; blocks everything) ⏱ ~1–2h of human steps

These are not code. Until they're done, the live product loses data and has no download.

1. **Decide Track A vs Track B.** This determines whether the billing milestone (M3) is in scope.
2. **Decide the identity model** (this is the single most important architecture call — see M1): does the **website Supabase store** become the one source of truth, or does the **FastAPI accounts_service** become a hosted service the website also uses? Recommendation: **make the website + Supabase canonical**; have the desktop authenticate to the hosted website API instead of spawning a local service.
3. Provision **Supabase** (run `supabase/migrations/0001_init.sql`), set `SUPABASE_URL` + `SUPABASE_SERVICE_ROLE_KEY`, `AUTH_SECRET`, `NEXT_PUBLIC_SUPPORT_EMAIL`, `ADMIN_EMAILS`.
4. Provision **Vercel** (Root Dir = `websites/jarvis-landing`), deploy, confirm `/api/health` reports `backend: "supabase"`.
5. **GitHub Release** the current `Atlas_Setup.exe` (commit `ce5f73805`, sha256 in `output/Atlas_Setup.exe.sha256`); set `ATLAS_INSTALLER_URL` to the asset URL.

**Exit criteria:** `/api/health` green on Supabase; download button serves the installer; a web signup persists across a redeploy.

---

## M1 — UNIFY IDENTITY (Critical C3) ⏱ ~1–2 days

Today: desktop → local `127.0.0.1:8788` accounts_service; website → Supabase; old serverless = third. A web account is not a desktop login. Fix this or the funnel is fiction.

1. Choose canonical store per M0.2 (recommend website+Supabase).
2. Point the desktop at the hosted accounts API: change `ATLAS_ACCOUNTS_URL` default (`jarvis_desktop/accounts_client.py:29`) to the deployed site, and **stop auto-spawning** the local service in production mode (`accounts_service_runner.py`) — keep local spawn only for dev.
3. Either (a) host `accounts_service` as the API the website also calls, **or** (b) add desktop-login endpoints to the Next.js app backed by the same Supabase `users` table. Pick one; do not keep both.
4. Bridge **license/plan** into the desktop session so a web plan unlocks desktop features.
5. Add a tiny integration test: register on web → log in from desktop client against the same backend.

**Exit criteria:** one account works in both web and desktop; one place to revoke/suspend.

---

## M2 — PROVE THE HEADLINE PATH ON A REAL CLIENT + CLEAN MACHINE (Critical C6) ⏱ ~1 day

The "connect Claude, scan, ask" flow has only ever run in-process and on the dev box.

1. On a **clean Windows VM** (no Python/Node): install from the released `Atlas_Setup.exe`; record SmartScreen behavior, clicks, and time (Part 2 metrics).
2. Configure **one real client** (Claude Desktop *or* Cursor) to launch `Atlas.exe --mcp`; verify `initialize` → `tools/list` → `atlas_scan_repo` → `atlas_build_context_pack` over the real stdio handshake.
3. Fix the **stale smoke-test assertion** ("all 7 tools" → assert all 18) so regressions in the new tools are caught (`scripts/mcp_smoke_test.py`).
4. Add a per-tool **timeout** in `runtime.call_tool` so a pathological scan can't wedge the stdio loop.
5. Write the result up; if any step needs manual file editing, fix it so it doesn't.

**Exit criteria:** a screen recording of a clean machine going install → connect → scan → answer, with no source edits by the user.

> **Track A can launch after M2** (free invite beta): hide paid CTAs (M3.0), ship.

---

## M3 — BILLING (Track B only; Critical C1, C2) ⏱ ~3–5 days

0. **(Track A interim)** Hide every paid CTA; set pricing page to "Pro coming soon"; keep Free + waitlist. *This alone unblocks a free launch.*
1. Add the Stripe SDK to the Next.js app; implement a **real** `startCheckout` (Checkout Session) replacing the stub (`_lib/billing.ts:30`), gated by `liveChargesEnabled()` + real keys.
2. Implement the **billing portal** (`_lib/billing.ts:55`) via Stripe Customer Portal.
3. Port/rewrite the **webhook** from `~/jarvis_landing/api/stripe/webhook.js` into a Next.js route; verify `stripe-signature`; handle `checkout.session.completed`, `customer.subscription.updated/deleted`, `invoice.payment_failed`. Sync `plan/planStatus/stripeCustomerId` into the Supabase `users` row (fields already exist in `store.ts`).
4. Wire **cancel/upgrade/downgrade/refund/dunning** to Stripe, not local state mutation.
5. Tie **license activation/revocation** (M1 bridge) to subscription status.
6. Test in **Stripe test mode** end-to-end before any live key.

**Exit criteria:** a test-mode card completes checkout, the webhook flips the user to `active`, and the desktop unlocks Pro.

---

## M4 — SECURITY & ABUSE HARDENING ⏱ ~1–2 days

1. **V1:** replace the in-process rate-limit `Map` (`_lib/ratelimit.ts`) with a shared store (Supabase table or Upstash) so login/register/checkout limits actually hold on serverless. **Do before public exposure.**
2. **V2:** make accounts_service login return a **single generic** error (`routers/auth.py:235,237`) to stop user enumeration (or retire the service per M1).
3. **V3:** add server-side session revocation (a sessions table or short token TTL + refresh) so a stolen cookie can be killed.
4. Verify **password-reset email** actually sends (or disable the "forgot" CTA until it does).
5. Confirm admin allow-list (`ADMIN_EMAILS`) is set in prod and no default admin exists.

**Exit criteria:** brute force is throttled in prod; no enumeration; sessions revocable.

---

## M5 — POLISH & SCALE READINESS ⏱ ~2–3 days (can trail launch)

1. **Code-signing cert (C4):** sign `Atlas_Setup.exe` to clear SmartScreen. *External purchase; start early — EV certs take days.*
2. **Remote error reporting (Part 8):** add lightweight opt-in crash/telemetry so prod issues are diagnosable without asking users for support bundles.
3. **Performance (Part 9):** measure scan time / memory / pack latency on small→huge repos; document limits; cap or stream for huge repos given the single in-memory state model.
4. **Auto-update** mechanism + in-app **changelog**.
5. **SEO:** add `sitemap.xml` + `robots.txt` routes; fix `MyAppURL` placeholder in `Atlas.iss`; rename `public/jarvis-hero.png` and audit branding drift (jarvis→Atlas).
6. **In-app onboarding** for the MCP-config step (the main Part 2 friction point).
7. Multi-repo/workspace, team accounts, cloud sync — **only if demanded by beta users.**

---

## DEPENDENCY ORDER (one line)

**M0 (ops/decisions) → M1 (unify identity) → M2 (prove real client + clean install) → [Track A launches here, free] → M3 (billing) → M4 (security hardening) → [Track B launches here] → M5 (polish/scale).**

## DO-NOT-DO (explicitly out of scope for 1.0)
Architecture refactors, speculative features, beating Cursor at inline editing, team/SSO before a single paying user asks, anything not on this list.
