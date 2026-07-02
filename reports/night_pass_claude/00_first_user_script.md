# 00 — Ideal First-User Script

**Date:** 2026-06-20. The fastest real path to value is **MCP via Claude** (login-free; Claude spawns `Atlas.exe --mcp`). The website signup is optional unless downloading through the gated funnel.

| # | Step | Expected screen | User action | Success signal | Likely confusion | Help/copy needed |
|---|---|---|---|---|---|---|
| 1 | Land | `/` hero | read | "files to touch / what breaks / verification / packet for your AI tool" | none | — |
| 2 | Understand (10s) | hero subhead | read | "this feeds my AI coding agent the right context" | "is it another chatbot?" | hero already clarifies it augments Claude/Cursor/Codex |
| 3 | Create account | `/login` (signup) | email + password (≥8) | redirect to `/account` | weak-pw rule learned only on submit | inline errors are clear |
| 4 | Download | `/download` → `/download/atlas` | click Download | installer downloads | login-gated (must sign up first) | "create a free account to download" stated |
| 5 | Install (SmartScreen) | Windows warning | More info → Run anyway | app installs | scary unsigned warning | download page **warns** about this |
| 6 | Open Atlas (optional) | desktop window | — | app loads | **GUI sign-in may dead-end** if domain not live | steer to MCP (step 7); GUI not required |
| 7 | Connect Claude | `claude_desktop_config.json` | paste the `atlas` MCP block | "atlas" in the tools (hammer) menu | hand-editing JSON | `docs/MCP_CLIENT_SETUP.md` + download-page MCP block |
| 8 | Scan repo | Claude chat | "Use atlas_scan_repo on C:\my\repo" | scan summary returned | path format | example prompts in docs |
| 9 | Ask | Claude chat | "where is authentication implemented?" | Claude calls Atlas | did it use Atlas? | tell them to watch the tool call |
| 10 | See tool call | Claude chat | observe | `atlas_build_context_pack` runs | none | — |
| 11 | Get value | Claude chat | read | ranked files/symbols + plan, fewer tokens | none | "Use atlas_health" to verify connection |

**Critical dependencies:** prod env correct (signup/download), `useatlas.dev` live (only if using GUI login), installer reachable (`ATLAS_INSTALLER_URL`). The MCP path itself needs none of these.
