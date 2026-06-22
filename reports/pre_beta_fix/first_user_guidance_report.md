# TASK 4 — Download / First-User Guidance

**Date:** 2026-06-20. Copy/docs only (no installer logic changed).

## What the download page now tells the user
Already present: beta framing ("unsigned beta build"), the **SmartScreen** warning with **More info → Run anyway**, "code never leaves your machine", and a GUI quick-start (load sample → Change Plan → Copy for Claude/Cursor/Codex).

**Added this pass** (`app/download/page.tsx`) — an "Or connect your AI agent directly (MCP)" block covering the points that were missing:
1. Add Atlas to Claude Desktop / Cursor / Codex via the setup guide (`Atlas.exe --mcp`, **no account needed**).
2. Restart your AI tool — **atlas** appears in its tools menu.
3. **Verify** by asking: *"What Atlas tools are available?"* or *"Use atlas_health."*
4. Not visible? Re-check the config in the setup guide.

This maps the 7 requested points: (1) beta — eyebrow + warn; (2) SmartScreen — warn; (3) More info → Run anyway — warn; (4) open/connect — new MCP block; (5) connect Claude/Cursor/Codex — new block links the setup guide; (6) verify via "use atlas_health" — new block; (7) if not visible → setup guide — new block.

## Quickstart (`docs/ATLAS_QUICKSTART.md`)
Already fixed earlier this program to be installed-first (no "install Python"/`cd path/to/local_jarvis` for installed users). It points to the MCP client setup for connecting agents.

## MCP client setup (`docs/MCP_CLIENT_SETUP.md`)
Already complete: per-client config (Claude Desktop/Code, Cursor, Codex), a **Verify** step, and **example prompts** ("Ask Atlas what files matter for…", "what breaks if I change…"). No change needed.

## Verified
`tsc` clean + `next build` compiled the updated `/download` route. The added copy is plain JSX (links to `/docs`, which exists and returns 200).

## Residual friction (not code-fixable here)
- Hand-editing `claude_desktop_config.json` remains the main step for non-technical users (documented, can't be automated without a new onboarding feature — out of scope).
- SmartScreen persists until the installer is code-signed (owner cert).
