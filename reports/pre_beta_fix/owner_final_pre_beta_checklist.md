# TASK 7 — Owner-Only Final Pre-Beta Checklist (Yoav)

**Date:** 2026-06-20. Everything Claude/Codex cannot do (external accounts/creds/hardware). Each is independently testable.

1. **Fix Vercel env** (project root = `websites/jarvis-landing`):
   - `SUPABASE_URL = https://wggjguqcxmskhjznexum.supabase.co`
   - `SUPABASE_SERVICE_ROLE_KEY = <service_role key from the SAME project>`
   - `AUTH_SECRET = <stable 64-hex>` · `ADMIN_EMAILS = <you>` · `NEXT_PUBLIC_SUPPORT_EMAIL = support@useatlas.dev` (or a confirmed monitored inbox — **verify the current personal Gmail isn't a typo**)
   - (optional/cosmetic) `NEXT_PUBLIC_SUPABASE_URL = https://wggjguqcxmskhjznexum.supabase.co` — not consumed by code, set only for consistency.
   - Do NOT set `NEXT_PUBLIC_PAID_PLANS` / `STRIPE_SECRET_KEY` (free beta).
2. **Redeploy** production (`vercel deploy --prod`).
3. **Verify `/api/health`** → `persistence:"ok"`, `supabase.hostname:"wggjguqcxmskhjznexum.supabase.co"`, `validation_passed:true`, `service_role_present:true`.
4. **Run the website smoke** → `BASE_URL=https://useatlas.dev py -3 scripts/website_smoke_test.py` → WEBSITE SMOKE PASSED.
5. **Connect `useatlas.dev` → Vercel** (add domain + DNS). **Required for desktop auth** — the installed app's `web_base()` default is `https://useatlas.dev`.
6. **Upload the rebuilt installer to a GitHub Release** (`gh release create v0.1.0-beta packaging/installer/output/Atlas_Setup.exe Atlas_Setup.exe.sha256 --repo yoavkozokabab-blip/atlas-repo --prerelease`). *(Optional: rebuild first so the installer includes `atlas_root_cause` — current shipped exe has 17 tools, built before it; functionally fine without.)*
7. **Set `ATLAS_INSTALLER_URL`** = the release asset URL; redeploy; confirm `/download/atlas` → 302.
8. **Download the installer from the live site** (through the login-gated flow).
9. **Verify SHA256** of the download == `bc2a3e60113e74400d44d99c3548662e94739ec6074860482a116e6edb30cc6e` (or the new hash if rebuilt).
10. **Clean-machine test** (fresh Windows, no Python/Node):
    - install (note SmartScreen → More info → Run anyway)
    - sign up on the live site → log in inside Atlas (now reaches useatlas.dev)
    - connect Claude Desktop (`Atlas.exe --mcp`); run `py -3 scripts/mcp_install_proof.py "C:\Program Files\Atlas\Atlas.exe"` → PASSED
    - in Claude: **call `atlas_health`** and **`atlas_repo_summary`** → both return.

When 1–10 pass, free invite beta is GO.
