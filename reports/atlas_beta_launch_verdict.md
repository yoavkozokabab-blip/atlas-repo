# Atlas — Beta Launch Verdict (Phase 5 / P7)

**Date:** 2026-06-16
**Branch:** `monetization-v1` (commits `14b1e88e6` → `74ecddd88`)
**Scope:** can Atlas be safely distributed to the first ~25 external beta users?

## FINAL VERDICT: `READY_WITH_LIMITED_BETA`

…**conditional on a short deployment checklist that only the owner can run** (Supabase +
hosting + secrets). The *engineering* blockers are cleared and verified. The *operational*
blockers are not — and **until they are, the live state is NOT_READY** (no durable
persistence, no hosted installer). This is an honest "the code is ready; the deployment
is not" verdict, not "ship it today."

Limited beta = a small set of **invited Windows developers**, told up front that the build
is unsigned (SmartScreen) and that MCP is experimental.

---

## Critical Blockers (must clear before any external user)

All are **operational/ops actions requiring the owner's accounts** — not code. The code is in
place and builds.

1. **Supabase not provisioned in production.** Persistence code is implemented and builds
   (`store.ts` Supabase adapter), but no project/env is wired. Until `SUPABASE_URL` +
   `SUPABASE_SERVICE_ROLE_KEY` are set and `supabase/migrations/0001_init.sql` is applied,
   the site silently uses the **ephemeral file store** → accounts and waitlist are lost on
   Vercel. *Verify via `/api/health` → `backend:"supabase"`.*
2. **No installer is hosted.** `/download/atlas` redirects to `ATLAS_INSTALLER_URL`, which is
   unset → production download 404s. Run `docs/RELEASE_PROCESS.md` steps 5–6 (gh release +
   set env).
3. **`AUTH_SECRET` unset in production** → sessions reset every redeploy. Set it (one env var).

→ All three are covered by `docs/RELEASE_PROCESS.md` + `websites/.../docs/SUPABASE_SETUP.md`.
Estimated time with creds in hand: **~20–30 min**.

## Major Risks (accept-with-disclosure for limited beta; fix before public)

- **Installer is unsigned** → SmartScreen "unknown publisher." Acceptable for *invited* beta
  with a heads-up (already disclosed on the download page); **blocks public download.** Needs
  a code-signing cert (owner's external blocker).
- **Installed-app MCP path unverified.** `Atlas.exe --mcp` is implemented (stdio rebind for
  the windowed exe) but not driven by a real client with a rebuilt exe. MCP ships **labeled
  experimental**; source mode is verified. (`reports/mcp_client_compatibility.md`.)
- **No clean-machine install test performed.** Static audit passed; the live
  install→launch→scan→context→MCP→uninstall cycle must be run once on a fresh VM
  (`reports/atlas_install_verification.md` checklist).
- **Uninstall + serverInfo fixes need a rebuild** to land in the binary (they're in source).
  Re-run `installer_build.ps1` and regenerate the SHA256 before publishing.
- **Payments are stub** (no real Stripe). Fine for a free beta; ensure "Start 7-day trial"
  copy/flows don't imply a charge.

## Minor Issues

- Positioning inconsistent ("repository intelligence" vs the intended "persistent memory")
  across hero/meta. No real product screenshots. `MyAppURL` is a placeholder
  (`github.com/atlas`). (See `reports/website_conversion_audit.md`.)

## Ready Areas (verified this phase)

- **Retrieval / context quality** — context packs return HIGH-confidence, evidence-backed
  files (live MCP drive + 12/12 smoke). Strongest part of the product.
- **MCP protocol** — initialize / notifications / tools/list / tools/call / error handling
  all conformant, newline-framed (real-client compatible). Source mode verified.
- **Funnel code** — async store + Supabase adapter + waitlist (dedup) + admin CSV export +
  `/api/health`; `next build` green (all routes), `tsc` clean.
- **Download pipeline code** — serverless-safe redirect to a hosted asset; checksum
  generated; buttons point at the server route (no local-path assumption).
- **Waitlist now reachable** — UI form added to landing + download (was previously
  backend-only and unreachable).
- **Installer artifact** — current (06-15, from HEAD), version-consistent (0.1.0-beta),
  accounts service + frozen MCP/retrieval included, SHA256
  `b98ca5e5edbdd2aa6a64930211ce867dcb442e0cf1f5a994dabd756491d6cbc6`.
- **Security/privacy** — scrypt password hashing; Supabase RLS-locked (service-role only);
  `/api/health` and MCP output leak no secrets; local-first scanning.

## Status by area

| Area | Verdict |
|---|---|
| Retrieval | ✅ PASS |
| MCP (source) | ✅ READY · (installed app) ⚠️ EXPERIMENTAL |
| Funnel persistence | 🟡 CODE READY, deploy pending |
| Download pipeline | 🟡 CODE READY, hosting pending |
| Installer | 🟡 CONDITIONAL_GO (rebuild + clean-machine test) |
| Website conversion | 🟡 improved (waitlist live); screenshots/positioning pending |
| Security/privacy | ✅ adequate for beta |

## Recommended Next Action

**Run the deployment checklist, then invite a first cohort of ~10 (not 25) Windows devs.**

1. Provision Supabase, apply the migration, set `SUPABASE_*` + `AUTH_SECRET` + `ADMIN_EMAILS`
   in Vercel; verify `/api/health` → `persistence:"ok"`.
2. `installer_build.ps1` → regenerate SHA256 → `gh release create`; set `ATLAS_INSTALLER_URL`
   + `NEXT_PUBLIC_ATLAS_VERSION`; redeploy; verify `/download/atlas` 302 + checksum.
3. Run the clean-machine install checklist once; wire Claude Desktop to `Atlas.exe --mcp` and
   confirm one `tools/call` (promote MCP if green).
4. Invite a small cohort with explicit notes: unsigned build (SmartScreen), MCP experimental.

**Do not** open a public/un-gated download until the installer is code-signed and the
clean-machine + real-client-MCP checks pass.

### Marketing
Soft-launch messaging to an invite list is fine now (the waitlist captures demand durably
once Supabase is live). Hold broad public marketing until signing + public download are ready.
