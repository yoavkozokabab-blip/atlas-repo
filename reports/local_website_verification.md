# Atlas Website — Local Verification (Ops Phase / Step 1)

**Date:** 2026-06-16
**Dir:** `websites/jarvis-landing` (package `atlas-web`, Next.js 15 / React 19)
**Local URL tested:** `http://127.0.0.1:3317` (`next dev -p 3317`)

## Commands run

| Command | Result |
|---|---|
| `npx tsc --noEmit` | ✅ exit 0 (no type errors) |
| `next lint` | ✅ "No ESLint warnings or errors" (+ deprecation + lockfile warning) |
| `next build` | ✅ Compiled successfully; 25/25 static pages generated |
| `next dev -p 3317` | ✅ ready in ~1s, no runtime errors in log |
| `npm install` | not required — `node_modules` already present (260 pkgs) |

No `typecheck` npm script exists; used `tsc --noEmit`. Scripts available: `dev`, `build`,
`start`, `lint`.

## Pages tested (live, HTTP status)

| Route | Status |
|---|---|
| `/` (landing) | 200 |
| `/download` | 200 |
| `/pricing` | 200 |
| `/features` | 200 |
| `/faq` | 200 |
| `/contact` | 200 |
| `/login` | 200 |
| `/api/health` | 200 |

## Functional checks

| Check | Result | Evidence |
|---|---|---|
| Landing renders waitlist form | **PASS** | HTML contains "Get your beta invite" section + "Get beta invite" button |
| Landing primary CTA | **PASS** | "Download for Windows" present |
| `/api/health` responds | **PASS** | `{ok:true, backend:"file", persistence:"ephemeral", hasSupabase:false, paymentsMode:"stub"}` (correct dev state) |
| Waitlist submit (new) | **PASS** | `POST /api/waitlist` → `{ok:true, duplicate:false}` |
| Waitlist dedup (repeat) | **PASS** | same email → `{ok:true, duplicate:true}` |
| Waitlist persistence (dev) | **PASS** | written to `.data/atlas-web.json` (file fallback) |
| Console / server errors | **PASS** | no error/exception lines in dev log (22 compile/request lines) |
| Broken routes | **PASS** | none — all tested routes 200 |

## PASS / FAIL / WARN

| Item | Status |
|---|---|
| Build / typecheck / lint | **PASS** |
| All main pages load | **PASS** |
| Waitlist form + submit + dedup | **PASS** |
| Health endpoint | **PASS** |
| No console errors | **PASS** |
| Workspace-root inference (multiple lockfiles) | **WARN** — see below |
| Download in dev | **WARN** — login-gated; serves local file or 404 until `ATLAS_INSTALLER_URL` set (by design) |

## Issues found

1. **WARN — multiple lockfiles confuse Next's workspace root.** Next detected
   `local_jarvis/package-lock.json` and `websites/jarvis-landing/package-lock.json` and
   inferred the *parent* as the root. Harmless locally, but on Vercel the **Root Directory
   must be set to `websites/jarvis-landing`** (covered in the Vercel guide). Optional: set
   `outputFileTracingRoot` in `next.config.mjs` to silence it.
2. **By design** — `/api/health` reports `backend:"file"` / `persistence:"ephemeral"` locally
   because no Supabase env is set. In production this MUST read `backend:"supabase"` (the
   gating check for go-live).

## Verdict: **PASS** (local website is healthy; production gating is env-only)

Screenshots: none captured (text-based verification via live HTTP + HTML inspection was
sufficient and deterministic).
