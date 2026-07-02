# 07 — Shortest Path to First External User

**Date:** 2026-06-20 · Code frozen · no new features/retrieval/benchmarks. Goal: one real external user through Download → Install → Connect Claude → Scan → Use.

## The key insight (why this is short)
The journey you specified runs entirely through the **Claude-Desktop MCP path**, and that path is **login-free**:
- The MCP runtime (`jarvis_desktop/mcp_server/runtime.py`) has **no account/auth/license gate** (verified: only secret-redaction code; smoke test scans + builds packs with no login).
- Claude Desktop **spawns `Atlas.exe --mcp` itself** over stdio — the user never needs to open the Atlas GUI, sign in, or reach a backend.

**Therefore Supabase, Vercel, useatlas.dev DNS, website signup/login, `ATLAS_INSTALLER_URL`, code-signing, and billing are ALL off the critical path for the first user.** (They matter for a public self-serve funnel, not for one supervised user using Atlas through Claude.)

## What already exists (no work needed)
- Installer: `packaging/installer/output/Atlas_Setup.exe`, SHA `bc2a3e60113e74400d44d99c3548662e94739ec6074860482a116e6edb30cc6e`, commit `f70a4975e`, contains the auth rewire (irrelevant here) and `--mcp`.
- `run_atlas.py --mcp` rebinds stdio for the frozen windowed build (`_run_mcp_stdio`, lines 122-123).
- `docs/MCP_CLIENT_SETUP.md` — exact `claude_desktop_config.json` snippet + source-mode fallback.
- JSON-RPC-over-real-pipes is **verified** (smoke spawns `python -m jarvis_desktop.mcp_server`, 12/12).

---

## 1. Exact remaining tasks

**T1 — Operator proves the installed `Atlas.exe --mcp` ↔ real Claude Desktop handshake** (on Yoav's own machine). Install the current `Atlas_Setup.exe`; add the MCP entry from `docs/MCP_CLIENT_SETUP.md` (`command: C:\Program Files\Atlas\Atlas.exe`, `args: ["--mcp"]`); restart Claude Desktop; confirm Atlas tools appear and `atlas_scan_repo` + `atlas_build_context_pack` return results. **This is the one never-done verification and the whole plan's pivot.**

**T2 — Make the installer reachable by the user.** Shortest: send `Atlas_Setup.exe` + its `.sha256` directly (Drive/email/private link). Slightly more (reusable): `gh release create v0.1.0-beta packaging/installer/output/Atlas_Setup.exe Atlas_Setup.exe.sha256 --repo yoavkozokabab-blip/atlas-repo --prerelease`.

**T3 — Write the 1-page user note** (reuse `MCP_CLIENT_SETUP.md` + `ATLAS_QUICKSTART.md`): (a) download link; (b) SmartScreen: *More info → Run anyway* (unsigned beta); (c) the exact `claude_desktop_config.json` snippet with the installed path; (d) restart Claude Desktop; (e) first prompt: *"Use Atlas to scan C:\path\to\my\repo, then build a context pack for &lt;a real task&gt;."*; (f) **note: you do not need to open the Atlas window or create an account.**

**T4 — Onboard the one user, supervised.** Send installer + note; screen-share their first run end-to-end; capture anything that breaks.

**Do NOT do (off critical path):** Supabase, Vercel, DNS, website login, `ATLAS_INSTALLER_URL`, signing, Stripe.

## 2. Task order
**T1 → (T2 ∥ T3) → T4.** T1 first — it validates the premise and produces the verified config that T3 documents.

## 3. Estimated time
| Task | Est. | 
|---|---|
| T1 verify installed `--mcp` ↔ Claude Desktop | 30–60 min |
| T2 deliver installer (direct ~5 min / GitHub release ~15 min) | 5–15 min |
| T3 1-page user note (mostly reuse) | 30 min |
| T4 supervised onboarding (incl. user's session) | ~1 hr |
| **Total operator time** | **~2.5–3 hrs**, one afternoon; **zero cloud provisioning** |

## 4. Dependencies
- T1: none (Yoav has the installer + Claude Desktop). **Everything depends on T1 passing.**
- T2: `gh` auth only if using a release (direct send needs nothing).
- T3: depends on T1 (uses the verified config + the working launch command).
- T4: depends on T1 + T2 + T3, and on a willing external user with **Windows + Claude Desktop**.

## 5. Risks (ranked)
1. **Frozen `Atlas.exe --mcp` stdout-rebind misbehaves vs real Claude Desktop (HIGH, unverified).** It's the one unproven link. *Mitigation:* T1 catches it; **fallback = source mode** (`py -3 run_atlas.py --mcp`), which is essentially the verified path — but adds a Python install for the user. Code is frozen, so a broken windowed-exe can only be worked around (fallback), not fixed.
2. **SmartScreen blocks/scares the user (MED).** Unsigned installer. *Mitigation:* explicit "More info → Run anyway" instruction + advance warning + screen-share.
3. **User opens the Atlas GUI, hits the account/login wall (which can't succeed — useatlas.dev isn't live) and gets confused (MED).** *Mitigation:* the note explicitly says don't open the GUI / don't sign in; Atlas works through Claude.
4. **Claude Desktop version/config-path differences (MED).** *Mitigation:* T1 mirrors the user's setup; give exact `%APPDATA%\Claude\claude_desktop_config.json` path; screen-share.
5. **First repo too large → slow scan (LOW–MED).** *Mitigation:* pick a small/medium repo for the first run.
6. **No live support if it breaks (LOW).** *Mitigation:* supervise live; `Download support bundle` exists in-app.

## 6. Definition of success
**One real external user, on their own machine, with no operator file edits on that machine, successfully:**
1. downloaded and installed `Atlas_Setup.exe` (got past SmartScreen),
2. added Atlas to Claude Desktop and **saw the Atlas tools listed**,
3. ran `atlas_scan_repo` on **one of their own repositories**,
4. got a useful result from `atlas_build_context_pack` (or another tool) **inside Claude**.

**Evidence:** a screen recording or the user's confirmation, ideally plus a support bundle showing a successful scan. **Bonus:** their answer to "was this actually useful?"

---

### One-line plan
Yoav verifies installed-exe `--mcp` with Claude Desktop on his machine (T1); if green, send the installer + a 1-page note to one user and screen-share their first scan. No cloud, no login, no signing required for first user.
