# Atlas Privacy

Atlas is **local-first**: the engine that scans your code runs on your machine, and
**your source code is never uploaded by Atlas**. The code is open, so every statement
below can be checked against the source.

## What stays on your machine

- Your source code, file contents, file names and paths.
- Scans, indexes, dependency graphs and generated context packs.
- MCP traffic between Atlas and your agent (local stdio).
- Desktop logs and the full local analytics log.

## What the installed app sends

The installed app (not source mode) sends a **small, fixed list of anonymous product
events** to the Atlas website, for example `desktop_launched`,
`real_repo_scan_completed`, `mcp_connected` or which of the 18 MCP tools was called.

- Each event carries only closed-enum values (e.g. agent = `claude` / `cursor` /
  `codex` / `other`, repository size bucket = `small` / `medium` / …), the app version
  and a random installation ID.
- It never includes code, file or repository names, paths, prompts or free text. Values
  outside that fixed list are dropped before sending
  (see [`atlas_desktop/analytics_remote.py`](atlas_desktop/analytics_remote.py)).
- **Opt out** any time: Settings → *Share anonymous usage analytics*. Opting out is
  stored locally and is never silently re-enabled.
- **Running from source sends nothing** unless you set `ATLAS_ANALYTICS_ENDPOINT`.

## Update check

The installed app can ask the Atlas website whether a newer version exists. It is a
plain request for the latest version number; nothing about you or your code is sent.

## Bug reports

Only when you click **Report an issue**. Paths and credentials are redacted before
sending, and a copy is kept on your machine.

## Your AI agent

When you connect Atlas to Claude, Cursor or Codex, that agent receives the context
Atlas returns and sends it to its own model provider under **that provider's** privacy
policy. Atlas does not control your agent vendor.

## Accounts and payments

There are none. Atlas has no sign-up, no account system in the current release, and no
paid plans.

## Contact

yoavkozokabab@gmail.com
