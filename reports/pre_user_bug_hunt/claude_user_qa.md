# Atlas Pre-User QA — skeptical first-time user

**Date:** 2026-06-20 · Mode: UX/product QA. **No code changed** (no clear tiny-bug blocker found that's code-fixable; the real blockers are env/ops, documented below).
**Method:** ran the deployed code locally (`next dev`), crawled rendered pages, exercised the live auth API, read the client components + desktop UI + MCP docs. **Part 7 (live Vercel URL) is BLOCKED** — there is no working live deployment (production auth is down due to the stale `SUPABASE_URL` env drift; no live URL available). Findings below are against the code Vercel will serve.

## 1. Landing page — PASS
- **Understand in 10s?** Yes. Hero subhead: *"Point Atlas at a repo, describe a change, and it returns the files to touch, what may break, and the verification steps — then exports a clean, compact packet for your AI tool."* Clear.
- **Value prop clear?** Yes (files-to-touch + what-breaks + verification + AI-ready packet).
- **Download CTA honest?** Yes — "Download for Windows", "Download free". No payment implied.
- **Beta/free positioning?** Yes — pricing shows "Free in beta" + "Join the beta".
- **Paid claims hidden?** Yes — no `$29`/checkout/trial button anywhere (`PAID_PLANS_ENABLED` off).
- **Docs/contact/privacy/terms reachable?** Yes — all return 200; present in header + footer.

## 2. Signup / login — PASS (UX), BLOCKED in prod (env)
Auth error copy (verified against the live API, file store):
| Case | Response | Verdict |
|---|---|---|
| weak password (<8) | `"Password must be at least 8 characters."` | clear |
| invalid email | `"Enter a valid email address."` | clear |
| good register | 201 | works |
| duplicate email | `"An account with this email already exists."` | clear |
| wrong password | `"Invalid email or password."` | correct (anti-enumeration) |
| unknown user | `"Invalid email or password."` (same as wrong-pw) | **no enumeration leak** |
| empty fields | `"Invalid email or password."` (401) | acceptable |
- The login/signup form **surfaces these errors** in red (`client.tsx:39,72`) and disables the button while busy (no double-submit).
- **Network/Supabase error:** on a 500 the form falls back to **"Something went wrong."** (`client.tsx:39`) — generic but no crash/blank. *In the current broken prod (stale Supabase), every signup/login returns 500 → user sees "Something went wrong."* (CONFIRMED locally with the stale env: register → 500.)

## 3. Download — PASS with expectations set
- Download button → `/download` → "Create a free account to download" (**login-gated**) → after login, `/download/atlas` → 302 to `ATLAS_INSTALLER_URL`.
- **Missing release case:** if `ATLAS_INSTALLER_URL` unset → "No installer available" (honest, not a crash).
- **SmartScreen expectation:** the download page **explicitly mentions "unsigned" + "SmartScreen"** — good, sets the right expectation.
- **Wrong-SHA case:** the published `.sha256` (`bc2a3e60…`) lets a user verify; no in-app SHA check (manual). Acceptable for beta.

## 4. Desktop first launch — MIXED
- The desktop GUI guides via **Load Sample Repository → Scan Repo** (`static/app.js`) and a sign-in screen (`atlas_accounts.js`).
- **Risk:** the GUI is account-gated and authenticates to `web_base()` = `https://useatlas.dev`. Until that domain is live, **GUI login fails** → a user who opens the window and tries to sign in hits a dead end.
- **Mitigation / intended path:** the first-value path is **MCP, not the GUI** — Claude Desktop spawns `Atlas.exe --mcp` itself; the user need never open the window or sign in. The onboarding should steer users to the MCP path and away from the GUI login until the domain is live.

## 5. MCP setup — PASS (well-documented)
`docs/MCP_CLIENT_SETUP.md` covers **Claude Desktop, Claude Code, Cursor, Codex** with exact `mcpServers` JSON (installed + source), a **Verify** step, and **example prompts** ("Ask Atlas what files matter for…", "what breaks if I change…") — so the user IS told what to ask Claude.
- **Gaps:** (a) the "Verify" step suggests `py scripts/mcp_smoke_test.py`, which an installed-only user (no Python) can't run — for them, verify = "atlas appears in the tools (hammer) menu" (also stated). (b) The installed-exe `--mcp` path is **documented as experimental/unverified**; source-mode is the verified fallback (needs Python). (c) The website does not surface this doc prominently — a self-serve user must be pointed to it.

## 6. First successful value moment
Target: *"Claude used Atlas and found the right files."* Path: install → add MCP config → restart Claude → "Ask Atlas what files matter for X" → Atlas scans + returns ranked files/symbols. **Achievable for a technical user following the doc.** Blockers to speed: the manual `claude_desktop_config.json` edit, SmartScreen, and the unverified installed-exe `--mcp` handshake.

## Measurements (first 20 min, MCP path, technical user)
- **Clicks/steps:** download → (account create if via site) → run installer → SmartScreen "Run anyway" → open config file → paste JSON → restart Claude → type prompt ≈ **7–9 steps**.
- **Time to first value:** ~10–15 min if the installed `--mcp` works first try; +Python install if it doesn't (source fallback).
- **Confusion points:** (1) SmartScreen warning; (2) hand-editing `claude_desktop_config.json`; (3) whether "atlas" actually connected; (4) if they open the GUI, the login dead-end.
- **Dead buttons:** none. **Misleading buttons:** none (no reachable checkout). **Fake UI:** none. **Unclear labels:** none significant.

## 7. Production-specific QA — BLOCKED
No live Vercel URL, and production auth is currently broken (stale `SUPABASE_URL` → `ENOTFOUND` → register/login 500; `/api/health` would report `persistence:"error"` + the wrong `hostname`). Re-run this section after the owner sets the correct Supabase env and `useatlas.dev` → Vercel; verify each of `/ /login /download /pricing /contact /privacy /terms /api/health` returns 200 and `/api/health` shows `persistence:"ok"` + the correct `hostname`.

## Issues found (none are code blockers)
1. **Support email is a personal Gmail** — every contact/footer link is `mailto:yoavkozlovski@gmail.com` (from `NEXT_PUBLIC_SUPPORT_EMAIL`). The spelling **differs from the owner's git address** (`yoavkozokabab@gmail.com`) — verify it's a real, monitored inbox, or first-user support silently goes nowhere. **Config/env, not code.**
2. **Production auth down** — env drift (see `reports/prod_env_audit.md`). Owner-only fix.
3. **GUI login dead-end** until `useatlas.dev` is live — steer users to the MCP path.
4. **Generic "Something went wrong."** on backend errors — acceptable, but once prod is healthy this should rarely fire.
