# 04 — Download + Install Expectation QA

**Date:** 2026-06-20. Assessed the download page copy + docs (not just the redirect).

| Question | Answer |
|---|---|
| Does the user understand what file they're downloading? | ✓ "Atlas_Setup.exe · v0.1.0-beta · Windows 10/11 · ~42 MB" |
| Is the unsigned warning visible enough? | ✓ A dedicated `dl-warn` box: "Heads up — this is an unsigned beta build." |
| Does it mention SmartScreen clearly? | ✓ "Windows SmartScreen may show a warning on first run. Click **More info → Run anyway**." |
| Does it explain what to do after install? | ✓ "Get value in under 5 minutes" (GUI) **+** new "Or connect your AI agent directly (MCP)" block |
| Does it explain MCP setup? | ✓ links the setup guide; says point Claude/Cursor/Codex at `Atlas.exe --mcp` ("no account needed") |
| Does it give the exact verification prompt? | ✓ "Verify by asking: *What Atlas tools are available?* or *Use atlas_health.*" |
| Does it explain what success looks like? | ✓ "**atlas** appears in its tools menu" + a tool call returns |

## Findings
- The download experience is **honest and now self-explanatory** for the MCP path (the connect+verify copy was added last pass and builds cleanly).
- **Gaps (not copy-fixable here):**
  - The installer is **unsigned** → SmartScreen friction persists until code-signed (owner cert).
  - `/download/atlas` is **login-gated** and depends on `ATLAS_INSTALLER_URL` being set (owner) — otherwise "No installer available".
  - There is **no in-app SHA256 check**; the published `.sha256` (`bc2a3e60…`) lets a user verify manually. Fine for beta.
- The setup guide referenced from `/docs` should ensure the **installed-app** config (Claude Desktop `Atlas.exe --mcp`) is the first option — it is (`docs/MCP_CLIENT_SETUP.md` step 1 lists installed first).

## Fixes this pass
None needed (the prior pass added the connect/verify copy). Copy is adequate for first-user success on the MCP path.
