# Atlas — Final Limited Beta Checklist (Ops Phase / Step 9)

**Date:** 2026-06-16

## FINAL VERDICT: `READY_AFTER_HUMAN_OPS`

All engineering is complete and verified locally. Atlas **cannot reach beta users yet** only
because the remaining steps are human-only ops Claude cannot perform: install Inno Setup +
rebuild, provision Supabase, deploy to Vercel, publish the GitHub Release, and run the
clean-machine test. None require code changes. Estimated total: **~1–1.5 hours**.

---

## ✅ Claude-completed (verified this session)

- Website: `tsc`/`lint`/`build` clean; live dev server — all pages 200, **waitlist submit +
  dedup work**, `/api/health` correct, no console errors (`reports/local_website_verification.md`).
- Desktop: app boots, UI serves, `/api/health` 200, `--self-test` READY, `--mcp` verified,
  scan/context/what-breaks proven via MCP (`reports/local_desktop_verification.md`).
- MCP protocol fully conformant; smoke test 12/12 (`reports/mcp_client_compatibility.md`).
- **Production safety guard added**: file store refuses writes in prod without Supabase
  (no silent data loss); `/api/health` flags misconfig (`reports/vercel_readiness_audit.md`).
- Persistence (Supabase adapter + migration + dedup + admin CSV), serverless download
  redirect, uninstall fix, all committed.
- Click-by-click guides: Supabase, Vercel, GitHub Release; clean-install plan; MCP real-client
  test; release process.

## 🔴 Must do before the FIRST user (human-only)

1. **Install Inno Setup 6** and **rebuild the installer** (`installer_build.ps1`) — the shipped
   06-15 build predates this session's fixes. Regenerate SHA256.
   → `reports/installer_rebuild_report.md`
2. **Provision Supabase** + run `0001_init.sql` + set env (`SUPABASE_*`, `AUTH_SECRET`,
   `ADMIN_EMAILS`). → `docs/SUPABASE_CLICK_BY_CLICK.md`
3. **Deploy to Vercel** (Root Directory = `websites/jarvis-landing`) + env vars; verify
   `/api/health` → `backend:"supabase"`. → `docs/VERCEL_DEPLOYMENT_CLICK_BY_CLICK.md`
4. **Publish GitHub Release** (rebuilt exe + .sha256); set `ATLAS_INSTALLER_URL` in Vercel +
   redeploy; confirm Download 302s to the asset. → `docs/GITHUB_RELEASE_CLICK_BY_CLICK.md`
5. **Run the clean-machine install test** once. → `docs/CLEAN_INSTALL_TEST_PLAN.md`
6. **Verify a waitlist round-trip persists** in Supabase after a redeploy.

## 🟡 Should do before ~10 users

7. **Real-client MCP test** in Claude Desktop / Cursor (both installed). Promote MCP off
   "experimental" if green; else keep the experimental label. → `docs/MCP_REAL_CLIENT_TEST.md`
8. Add 1–2 **real product screenshots** to landing + download (top trust lever).
9. Align **positioning** to the "persistent memory" spine; fix `MyAppURL` placeholder.
10. Confirm admin export (`/api/admin/waitlist?format=csv`) for sending invites.

## 🟢 Can wait until after feedback

11. **Code-signing certificate** (removes SmartScreen) — required for *public* download, not
    invited beta.
12. Real Stripe (payments are stub today — fine for a free beta).
13. macOS / Linux builds (waitlist already captures this demand).
14. Conversion polish from `reports/website_conversion_audit.md`.

## Human-only steps (summary — Claude cannot do these)
Install Inno Setup; create Supabase/Vercel accounts + paste secrets; push to GitHub + publish
release; run a clean-machine install; drive the Claude Desktop/Cursor GUIs; buy a signing cert.

## Gate
Open the invited beta the moment **Must-do 1–6** are green. Start with ~10 invitees (not 25),
each told: unsigned build (SmartScreen) + MCP experimental. Do **not** open a public/un-gated
download until the installer is code-signed and the clean-machine + real-client-MCP checks pass.
