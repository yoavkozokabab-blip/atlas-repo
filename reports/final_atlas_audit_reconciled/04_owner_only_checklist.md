# 04 — Owner-Only Checklist (Yoav)

These require external accounts, credentials, hardware, or human judgment — Claude/Codex cannot do them. Detailed commands: `reports/phase186/owner_setup_guide.md` + `release_prep.md`.

## Required for FREE INVITE BETA (in order)
1. **Provision Supabase** — create project; SQL Editor → run `websites/jarvis-landing/supabase/migrations/0001_init.sql` then `0002_rate_limits.sql`; copy URL + **service_role** key.
2. **Connect useatlas.dev → Vercel** — add the domain in the Vercel project; set registrar DNS; wait for "Valid Configuration". *(Critical: the frozen desktop's `web_base()` default is `https://useatlas.dev`; if you launch on a `*.vercel.app` URL instead, you must rebuild the installer with that URL.)*
3. **Set Vercel env (Production)** — `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `AUTH_SECRET`, `ADMIN_EMAILS`, `NEXT_PUBLIC_SUPPORT_EMAIL`, `NEXT_PUBLIC_ATLAS_VERSION=0.1.0-beta`, optional `BETA_MODE=invite`+`BETA_ALLOWLIST`. **Do NOT set `NEXT_PUBLIC_PAID_PLANS`** (keeps paid hidden).
4. **Deploy** — `vercel deploy --prod`; confirm `https://useatlas.dev/api/health` → `backend: "supabase"`.
5. **Create GitHub release + upload installer** — `gh release create v0.1.0-beta packaging/installer/output/Atlas_Setup.exe Atlas_Setup.exe.sha256 --repo yoavkozokabab-blip/atlas-repo --prerelease` (needs `gh` + auth).
6. **Update ATLAS_INSTALLER_URL** — set it to the release asset URL on Vercel; redeploy; confirm `/download/atlas` → 302 to the asset; downloaded SHA256 == `bc2a3e60…`.
7. **Clean-machine validation** — fresh Windows VM, no Python/Node: install, note SmartScreen, sign up on the live site, log in inside Atlas (run `ATLAS_AUTH_MODE=website ATLAS_WEB_URL=https://useatlas.dev py -3 scripts/desktop_web_auth_smoke.py` to pre-check the live path).
8. **Real Claude / Cursor / Codex validation** — add Atlas (`Atlas.exe --mcp`) to a real client; confirm tools visible + a tool call returns results. Capture evidence (this is the missing "real MCP proof").

## Required additionally for PUBLIC / PAID
9. **Code-signing certificate** (optional but strongly recommended) — sign `Atlas_Setup.exe` to clear SmartScreen for mass download.
10. **Live security red-team** on the deployed build (forged JWT, token replay, support-bundle leak, admin escalation).
11. **Real Stripe** (paid only) — implement checkout + webhook + entitlement (see `billing_architecture.md`); not in scope for free beta.
12. **Run the blind agent A/B** (`scripts/ab_benchmark.py` + ≥2 human graders) to prove answer-quality value.

## Optional hygiene (owner decision, not blockers)
- Decide `.gitignore` for `data/`, `dist/`, `packaging/installer/staging|output/` to clean the working tree (3,000+ churn lines).
- Delete legacy surfaces to remove provenance ambiguity: `C:\Users\babi2\jarvis_landing` (old static site) and `installer/jarvis.iss` (legacy installer).
- Rebuild installer after any source/doc change so staged `docs/ATLAS_QUICKSTART.md` (fixed this turn) and dropped phase-labeled files take effect.
