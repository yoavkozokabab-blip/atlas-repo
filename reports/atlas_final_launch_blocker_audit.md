# Atlas — Final Launch-Blocker Audit (Phase 1)

**Date:** 2026-06-16
**Auditor:** Claude (Atlas end-to-end completion mission)
**Canonical repo:** `C:\J.A.R.V.I.S\local_jarvis` (own `.git`, branch `monetization-v1`, HEAD `2846b2d57`, 2026-06-13)
**Scope:** Beta launch readiness only. Classify every issue; fix only beta blockers.

> Note on repo topology: `C:\Users\babi2` is *also* a git repo (the whole home dir was `git init`'d) but that is incidental noise. **All product code, the website, installers, and reports live in `C:\J.A.R.V.I.S\local_jarvis`.** This audit treats that as the source of truth.

---

## Executive summary

| Area | Verdict | Blocking issues |
|------|---------|-----------------|
| Desktop app | LIKELY OK (not clean-install verified this session) | version metadata mismatch (P0), untracked source (P0) |
| Installer | **REBUILT & CURRENT** (06-15 from HEAD) | version string `1.0.0` vs `0.1.0-beta` (P0) |
| Website / funnel | **NO-GO** | ephemeral file storage for accounts+waitlist (P0), prod download broken on serverless (P0) |
| MCP | **EXPERIMENTAL — not real-client compatible** | writes Content-Length framing, real clients need newline-delimited (P0) |
| Retrieval / context quality | PASS (per prior audit; not re-run this session) | none |
| Security / privacy | LIKELY OK | secrets-in-bundle + tracked-creds not re-verified this session (P1) |

**Correction to prior (06-15) state:** the installer is **no longer stale**. `installer/output/Atlas_Setup.exe` was rebuilt **2026-06-15 20:47** from commit `2846b2d57` (== HEAD), `build_info.json` version `0.1.0-beta`. The "stale 06-08 installer" P0 from the previous audit is **resolved**. The remaining installer P0 is purely the version-string mismatch.

---

## P0 — BETA BLOCKERS (must fix before any beta user)

### P0-1 — Website accounts + waitlist persist to the local filesystem (ephemeral on serverless)
- **Evidence:**
  - `websites/jarvis-landing/app/_lib/store.ts` — `getStore()` returns `fileStore` unconditionally; Supabase is a `// TODO(live)` comment (line 129). All users/auth/billing/admin/audit write to `process.cwd()/<dataDir>/atlas-web.json` via `fs.writeFileSync`.
  - `websites/jarvis-landing/app/api/waitlist/route.ts` — appends to `.waitlist/submissions.jsonl` via `fs.appendFile`.
- **Impact:** On Vercel/serverless, the filesystem is read-only/ephemeral and per-instance. **Every signup, account, and waitlist entry is lost or inconsistent.** Directly violates mission rules "No fake waitlist" and "Signups must persist reliably."
- **Fix options (mission-sanctioned):** (A) wire Supabase behind the existing `Store` interface (call-site-free swap — the code is already structured for it); (B) drop accounts and use a reliable external beta form; (C) make the site download-first and host waitlist externally. **Recommended: A** (the seam already exists). Requires Supabase creds/decision from user.

### P0-2 — Production download cannot serve the installer
- **Evidence:** `app/download/atlas/route.ts` streams a local file resolved from `../../packaging/installer/output/Atlas_Setup.exe` or `../../installer/output/Atlas_Setup.exe`. On Vercel these paths don't exist and a 42 MB binary is not deployable to serverless functions.
- **Secondary:** the route is **login-gated** (anonymous → `/login?next=/download`), so download also depends on the broken account store (P0-1).
- **Impact:** Download button 404s in production. Violates "No stale download" / "Beta user can get installer."
- **Fix:** host the verified installer on a GitHub Release (or CDN/Supabase Storage) and have the route `302` redirect there (env `ATLAS_INSTALLER_PATH`/release URL). Decide whether download stays login-gated.

### P0-3 — MCP server is not compatible with real MCP stdio clients
- **Evidence:** `jarvis_desktop/mcp_server/runtime.py`:
  - `_read_messages` (502-531) accepts **both** newline-delimited JSON and Content-Length framing — tolerant.
  - `_write_message` (534-538) **always** emits `Content-Length: …\r\n\r\n` framing.
- **Impact:** Current MCP stdio spec (Claude Desktop, Cursor, Codex) uses **newline-delimited JSON**; Content-Length is the LSP/legacy convention. The 12/12 smoke test passes only because it speaks the server's own framing. **Against a real client the server's responses won't be parsed.** Violates "No false claims" if MCP is presented as working.
- **Fix:** write newline-delimited JSON (`data + b"\n"`, no embedded newlines), keep the tolerant reader, re-run smoke test. Small, low-risk. (Until fixed, MCP must be labeled EXPERIMENTAL.)

### P0-4 — Installer version string mismatch
- **Evidence:** `installer/jarvis.iss` line 3 `#define MyAppVersion "1.0.0"`, but `build_info.json` and the app report `0.1.0-beta`.
- **Impact:** Installed program shows `1.0.0` in Add/Remove Programs while everything else says `0.1.0-beta`. Violates "version is consistent" rule and undermines provenance.
- **Fix:** set `MyAppVersion` to `0.1.0-beta` (Inno allows the string), rebuild installer.

### P0-5 — Critical source files are untracked in git
- **Evidence:** `git ls-files` shows `jarvis_desktop/context_pack.py` and `jarvis_desktop/mcp_server/` (runtime.py, server.py, tools.py, __init__) **untracked**. `build_info.json` claims the installer was built from commit `2846b2d57`, but these files are not in that commit.
- **Impact:** (1) Build-provenance claim is misleading — the shipped retrieval + MCP code is not in the named commit. (2) Loss risk: an untracked file can be wiped by `git clean`/checkout. The PyInstaller build *does* bundle them (it reads the working tree), so the installer itself is fine — this is a version-control/provenance integrity blocker, not a "missing from build" one.
- **Fix:** stage + commit these files. **Requires user authorization to commit** (repo is on `monetization-v1` with 259 dirty files; I will not commit unprompted).

---

## P1 — Important before broader launch (not beta-blocking)

- **P1-1 — Clean-install verification not done this session.** Installer is fresh, but Phase 5's full install→launch→scan→context-pack→MCP→uninstall cycle on a clean path has not been re-verified against the 06-15 build. Required before declaring INSTALLER_GO.
- **P1-2 — Secrets-in-bundle / tracked-credentials not re-scanned this session.** Prior audits passed; needs a fresh `git`-tracked-secrets + client-bundle scan before public exposure.
- **P1-3 — `atlas_what_breaks` input param is `target`, not `changed_files`.** Diverges from the mission's Phase-4 spec wording. Functionally works; reconcile schema/docs so client prompt examples match.
- **P1-4 — Duplicate-signup handling.** Waitlist route has no dedup; accounts store dedups by email only in `create` call sites. Verify once persistence is real (P0-1).
- **P1-5 — Email-verification truthfulness.** Confirm no API/UI claims "verification email sent" when email is not configured (mission rule). Needs a pass over `auth/register` + `auth/forgot`.

## P2 — Polish (after P0/P1)

- Landing copy alignment to the approved positioning ("persistent repo memory for AI coding agents").
- Desktop empty/loading/error states per Phase 3.
- Context-pack and "what breaks" screen completeness (copy-for-Claude/Cursor/JSON, token estimate, evidence).
- MCP setup screen labeled experimental + troubleshooting.
- Beta feedback path ("was this context useful / wrong file / report issue").
- Internal phase labels (`phase###`) must not appear in any shipped surface — spot-check before release.

## Ignore (not launch-relevant)

- `C:\Users\babi2` home-dir git repo noise.
- `.phase150_*` / `.phase152_*` scratch build dirs.

---

## Recommended fix order

1. **P0-3** MCP newline framing (small, self-contained, verifiable now).
2. **P0-4** installer version string (one line + rebuild).
3. **P0-5** commit untracked source (needs user OK to commit).
4. **P0-1 / P0-2** funnel persistence + download hosting (needs Supabase creds / hosting decision — biggest items).
5. **P1** clean-install + secrets re-verification.

**Beta-launch gate:** NOT READY until P0-1 and P0-2 are resolved (no reliable signup/download) and P0-3 is either fixed or MCP is clearly labeled experimental. P0-4/P0-5 are quick. Retrieval and the desktop scan/context flow are the strongest parts of the product today.
