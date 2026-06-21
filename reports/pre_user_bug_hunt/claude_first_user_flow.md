# Atlas — First User Flow (skeptical user, first 20 minutes)

**Date:** 2026-06-20. Step-by-step journey, with confusion points and time-to-value. Two real paths exist; the MCP path is the one that reaches value.

## Path A — MCP via Claude Desktop (the value path)
| # | Step | What the user does | Friction / confusion |
|---|---|---|---|
| 1 | Get installer | From the site (login-gated) or a direct link / GitHub release | Site download requires creating an account first |
| 2 | SmartScreen | Runs `Atlas_Setup.exe` → "Windows protected your PC" → **More info → Run anyway** | **Unsigned** → scary if not forewarned (download page does warn) |
| 3 | Install | One-click, self-contained (no Python) | None |
| 4 | Configure Claude | Edit `%APPDATA%\Claude\claude_desktop_config.json`, paste the `atlas` `mcpServers` block (`Atlas.exe --mcp`) | **Hand-editing JSON** is the biggest step for a non-technical user |
| 5 | Restart Claude | "atlas" appears in the tools (hammer) menu | Did it connect? — relies on the hammer menu showing it |
| 6 | First value | "Ask Atlas what files matter for &lt;task&gt;" → Atlas scans + returns ranked files/symbols | **Risk:** installed-exe `--mcp` is unverified vs real Claude Desktop; if it misbehaves → source-mode fallback needs Python |

**Time to first value:** ~10–15 min (technical user, happy path). **Steps:** ~7–9. **GUI / login / Supabase NOT required** for this path (MCP runtime is login-free).

## Path B — Website funnel (signup → download → desktop login)
| # | Step | State |
|---|---|---|
| 1 | Land on `/`, click Download | Works |
| 2 | Create account | **BROKEN in prod now** — stale Supabase env → 500 → "Something went wrong." |
| 3 | Download (after login) | gated; needs `ATLAS_INSTALLER_URL` set |
| 4 | Open desktop GUI, sign in | **Dead-end** until `useatlas.dev` is live (desktop auth target) |

Path B is currently NO-GO end-to-end (prod env + domain). It becomes viable once the owner fixes Supabase env, sets `ATLAS_INSTALLER_URL`, and points `useatlas.dev` at Vercel.

## Confusion points (ranked)
1. **Hand-editing `claude_desktop_config.json`** (step A4) — the single biggest self-serve hurdle.
2. **SmartScreen** on the unsigned installer (A2).
3. **"Did Atlas connect?"** — verification for installed users is "check the hammer menu" (the `mcp_smoke_test.py` verify needs Python).
4. **GUI login dead-end** (B4) — a user who opens the app window instead of using Claude hits a failing sign-in.
5. **Production signup currently 500s** (B2) — env drift.

## What would make Path A self-serve (no code change)
- A one-page "Connect Atlas to Claude" note with the exact JSON + the SmartScreen step + "you don't need to open the Atlas window or sign in" (most of this already exists in `docs/MCP_CLIENT_SETUP.md` — just surface it at download time).
- Fix the prod env so the site/download works (owner).
- Verify the installed-exe `--mcp` handshake once (owner) so step A6 is reliable.

## Time-to-value summary
- **Technical user, MCP path, installer in hand, `--mcp` works:** ~10–15 min, unaided.
- **Non-technical user:** likely needs help at the JSON-edit and SmartScreen steps.
- **Website funnel today:** cannot complete (prod env).
