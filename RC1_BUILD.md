# RC1_BUILD — Atlas Release Checklist

> Permanent checklist. Run top to bottom. Every box must be checked before Atlas reaches anyone.

## A. Repository
- [ ] `git fetch` and `git pull` latest on `monetization-v1`
- [ ] `git log --oneline -1` includes RC-1 fixes (`211003a22` or later)
- [ ] `git status` reviewed; founder WIP committed or stashed
- [ ] No secrets in tracked files (`git grep -iE "sk-|ghp_|password|jwt_secret ="`)
- [ ] `.env` / `.env.local` NOT tracked
- [ ] Root `README.md` says "Atlas" (not "local_jarvis")
- [ ] `LICENSE` present

## B. Tests
- [ ] `py -m pytest jarvis_desktop/tests/test_rc1_fixes.py` passes
- [ ] `py -m pytest jarvis_desktop/tests/test_context_pack_mvp.py jarvis_desktop/tests/test_root_cause.py jarvis_desktop/tests/test_mcp_server.py jarvis_desktop/tests/test_memory_replacement_mvp.py` passes
- [ ] `py -m pytest jarvis_desktop/tests` reviewed; 0 failures OR every failure triaged as known/non-blocking
- [ ] `py scripts/mcp_smoke_test.py` prints "SMOKE TEST PASSED"

## C. Engine sanity (source mode)
- [ ] `py run_atlas.py --mcp` starts without error
- [ ] `atlas_scan_repo` on a medium repo returns modules > 0
- [ ] `atlas_build_context_pack` returns `token_reduction_pct` as a number (NOT `[REDACTED]`)
- [ ] `atlas_what_breaks` output: no subsystem appears in both `direct_impact` and `what_probably_wont_break`
- [ ] 0 hallucinated/fabricated files in a context pack

## D. Build
- [ ] `powershell -File packaging\installer\installer_build.ps1`
- [ ] `dist/Atlas/Atlas.exe --self-test` reports ready
- [ ] `build_info.json` commit == current `git HEAD`
- [ ] Installer code-signed (SignTool) — cert applied
- [ ] `packaging/installer/output/Atlas_Setup.exe` exists
- [ ] Generate SHA256 of the installer
- [ ] Write `.sha256` sidecar next to the installer
- [ ] Re-read installer file; computed hash == sidecar hash

## E. Clean-machine install (fresh Windows VM)
- [ ] Copy installer to a clean VM (no Python, no prior Atlas)
- [ ] Run installer; SmartScreen behavior recorded (signed = no "unknown publisher")
- [ ] Install completes without error
- [ ] Atlas launches from Start menu
- [ ] `%USERPROFILE%\.jarvis_desktop` data dir created

## F. Agent connection (clean VM)
- [ ] Claude Desktop config written (auto or manual) and valid JSON
- [ ] Restart Claude Desktop; "atlas" appears in tools menu
- [ ] Cursor `.cursor/mcp.json` connects (if shipping Cursor support)
- [ ] Codex / target client connects (if shipping that client)

## G. Core value (clean VM, real client)
- [ ] Scan a real repository via the agent
- [ ] Ask the benchmark question ("where is X / what breaks if I change X")
- [ ] Agent receives a context pack with files + reasons + confidence
- [ ] `atlas_what_breaks` returns impact + tests
- [ ] `atlas_root_cause` returns a result on a sample stack trace
- [ ] MCP returns no secrets and no `[REDACTED]` metrics

## H. Account / auth (if enabled for this build)
- [ ] Create/login an account in the desktop flow
- [ ] Session persists across restart
- [ ] Logout works
- [ ] Paid CTAs hidden OR Stripe live (decision recorded)

## I. Uninstall
- [ ] Uninstall via Windows "Apps & features"
- [ ] `%USERPROFILE%\.jarvis_desktop` cleaned (correct data dir)
- [ ] No leftover processes
- [ ] Reinstall over same machine works

## J. Release
- [ ] Provision Supabase (migrations 0001 + 0002 applied) — if funnel enabled
- [ ] Set required env (`SUPABASE_URL`, service-role key, `SUPPORT_EMAIL`) — verify support email is correct, not personal
- [ ] Deploy website (Vercel) — if funnel enabled
- [ ] Create GitHub Release (tag `v1.0.0`)
- [ ] Upload signed installer + `.sha256` as release assets
- [ ] Set `ATLAS_INSTALLER_URL` to the release asset; redeploy
- [ ] Download installer from the public URL on a separate network
- [ ] Downloaded hash == published `.sha256`

## K. Ship
- [ ] Rotate any previously-exposed secret/JWT
- [ ] Send installer (or download link) to the first external user
- [ ] First user reaches first context pack WITHOUT founder intervention (log every assist)
- [ ] Feedback channel open

## L. Post-send
- [ ] Monitor errors / first-run telemetry (if enabled)
- [ ] Record install → connect → first-value funnel result
- [ ] Triage real-user issues before widening distribution
