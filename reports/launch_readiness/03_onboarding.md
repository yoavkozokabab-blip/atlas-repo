# 03 — Onboarding Optimization

**Date:** 2026-06-20. Cold user, Windows, already uses an AI coding agent.

## The clock
**First 30 seconds (landing):** must answer "what is this + why do I care." Atlas's hero already does ("files to touch / what breaks / verification / a compact packet for your AI tool"). Add one line that name-drops the tools: *"Works with Claude, Cursor, and Codex via MCP."* Success signal: user clicks Download.

**First 2 minutes (download + install):** create account → download → run installer → SmartScreen → **More info → Run anyway**. The single biggest 2-minute risk is **SmartScreen panic** and the **login-gated download**. The download page already warns about SmartScreen. Success signal: Atlas installed.

**First 10 minutes (connect + first value):** add `Atlas.exe --mcp` to `claude_desktop_config.json` → restart Claude → ask *"Use Atlas to scan C:\my\repo, then tell me where authentication is implemented."* → see the tool call → get ranked files. Success signal: **"Claude used Atlas and found the right files."** (Proven achievable: MCP cold-start → correct answer in ~2s.)

## What confuses them (ranked)
1. **Hand-editing `claude_desktop_config.json`** — the #1 wall. Many devs have never touched it.
2. **GUI vs MCP** — they open the Atlas window, hit the sign-in/beta form, and get lost. **They don't need the window.** Onboarding must say so.
3. **SmartScreen** — looks like malware to a cautious user.
4. **"Did it connect?"** — no obvious confirmation besides the tools/hammer menu.
5. **Which repo / path format** — Windows paths in the prompt.

## What causes abandonment
- The config-file step with no copy-paste-exact snippet for *their* OS path.
- Opening the GUI and hitting the stale beta-application form (fix: hide it in website mode).
- No "it worked!" moment — they don't know what success looks like.

## Docs to rewrite / create
- **One page: "Connect Atlas to Claude in 3 steps"** — exact `claude_desktop_config.json` path + block, restart, verify prompt, "you don't need to open the Atlas window." (Most of this exists in `docs/MCP_CLIENT_SETUP.md` + the download page; consolidate into ONE linked page.)
- Trim `docs/MCP_CLIENT_SETUP.md` to put the installed-app path first and the verify step front-and-center.

## Screenshots that should exist
1. SmartScreen "More info → Run anyway".
2. The exact `claude_desktop_config.json` with the `atlas` block highlighted.
3. Claude Desktop tools (hammer) menu showing **atlas**.
4. A real Claude answer that used `atlas_build_context_pack` (the auth.py result).

## Videos that should exist
- **One 90-second screen recording**: download → SmartScreen → install → paste config → restart Claude → ask the auth question → Atlas answers. This single asset removes most abandonment and is your HN/Reddit/landing demo.

## Examples that should exist
- The bundled sample repo + 3 canned prompts ("where is auth implemented?", "what breaks if I change X?", "what files matter for adding Y?"). The first is already proven (auth.py #1).
