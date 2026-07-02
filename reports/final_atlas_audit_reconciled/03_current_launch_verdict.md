# 03 — Current Launch Verdict (CONFIRMED facts only)

**Date:** 2026-06-20. Computed from CONFIRMED current findings only — stale/fixed/unverified-hypothetical findings excluded. UNVERIFIED items are treated as *unmet evidence* (they cannot count as GO), and OWNER_ONLY items are listed as conditions, not code blockers.

| Scenario | Verdict | Rationale + exact blockers |
|---|---|---|
| **1. Private supervised beta** (operator hand-installs for a few known users, guides them) | **CONDITIONAL GO** | Core works (112 tests, MCP smoke 12/12 local, installer current + contains rewire, free-beta billing honest). Conditions: (a) operator runs the accounts backend — either provision Supabase + deploy the site, **or** run desktop in local mode (`ATLAS_AUTH_MODE=local`); (b) accept unsigned-installer SmartScreen and tell users; (c) distribute the known `Atlas_Setup.exe` (SHA `bc2a3e60…`). No code blockers. |
| **2. Free invite beta** (website signup → download → desktop login, invite-gated) | **CONDITIONAL GO** | All CODE is ready: identity unified (desktop→website, PYZ-proven), paid CTAs hidden, pages exist, rate-limit + anti-enumeration fixed, installer current. **Blockers are all OWNER_ONLY ops:** (1) provision Supabase + run migrations `0001`+`0002`; (2) deploy `websites/jarvis-landing` to Vercel with env; (3) point **useatlas.dev → Vercel** (so the frozen desktop's `web_base` default resolves) OR rebuild with the live URL; (4) GitHub release + set `ATLAS_INSTALLER_URL`; (5) accept unsigned installer. Recommend (6) one clean-machine + real-client smoke before inviting. |
| **3. Public free beta** (open, marketed) | **NO-GO** | Confirmed blockers: unsigned installer (mass SmartScreen friction) [OWNER cert]; **UNVERIFIED**: clean-machine install, real Claude/Cursor/Codex calls, live website health, current-build security red-team. Public exposure requires these to be proven, not assumed. |
| **4. Paid beta** | **NO-GO** | Confirmed hard blocker: **no production Stripe** — billing is an intentional stub; `/api/checkout` returns 403; no webhook. Cannot charge. (By design for now.) |
| **5. Paid public launch** | **NO-GO** | All of #3's gaps **plus** #4's billing. Requires real Stripe + webhook + entitlement, code signing, and the full verification matrix. |

## Why not stricter / looser than Codex
- Codex said private supervised beta = CONDITIONAL and public/paid = NO-GO. This reconciliation **agrees**, and adds a distinct **Free invite beta = CONDITIONAL GO** verdict (Codex folded this into "private"): because the identity/billing/page/installer CODE is now confirmed ready, the only thing between Atlas and a free invite beta is **owner ops**, not engineering.
- We do **not** upgrade free-invite-beta to unconditional GO: the frozen desktop points at `useatlas.dev`, which is not yet live, and no clean-machine/real-client run exists. Those are conditions, honestly stated.
- We do **not** call anything NO-GO from stale evidence (404s, MCP "drift" — both debunked).

## One-line gate per scenario
1. Private supervised → **operator can start now** (local mode or after minimal ops).
2. Free invite → **owner completes ops (Supabase+Vercel+DNS+release) → GO**.
3. Public free → **+ signing + clean-machine + real-client + live security**.
4. Paid → **+ real Stripe**.
5. Paid public → **all of the above**.
