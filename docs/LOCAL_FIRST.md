# Security and Local-First Design

Atlas runs on your machine. The scanning engine, the dependency/symbol graph, context
packs, and the MCP server all execute locally. **Your source code is never uploaded by
Atlas.** The code is open source, so you can check this yourself.

## What stays on your machine

- Source code, file contents, scans, indexes, and generated context packs.
- The MCP server — it speaks JSON-RPC over local stdio, launched by your agent; traffic
  stays between your agent and the local Atlas process.
- Desktop logs and the full local analytics log — written to your local Atlas data
  directory.
- The desktop's local web UI runs on `127.0.0.1` (your machine only).

## What may be sent to Atlas servers

- **Installed app only:** a small, fixed list of anonymous product events (for example
  `real_repo_scan_completed` or which MCP tool was called) with a random installation ID.
  Never code, names, paths or free text. Opt out in Settings → *Share anonymous usage
  analytics*. Running from source sends nothing. Details: [PRIVACY.md](../PRIVACY.md).
- **Installed app only:** a version check against the Atlas website.
- **Only when you click Report an issue:** the bug report, with paths and credentials
  redacted.
- There are no accounts and no payments in the current release.

> When you connect Atlas to an AI agent (Claude, Cursor, Codex), that agent receives the
> context Atlas returns. From that point the data is governed by **your agent vendor's**
> policy, which Atlas does not control.

## What you should NOT upload or paste

- Do not paste secrets, tokens, or credentials into agent prompts. Atlas redacts
  secret-shaped values from its tool output, but treat agent prompts as potentially
  logged by your agent vendor.

## How secrets are handled

- Atlas tool output passes through a redaction filter that removes secret-shaped keys and
  values before returning results to the agent.

## How MCP works

- Your agent launches Atlas as a local stdio process.
- Tools are **read-only** (Atlas never writes to your repo) and **local-path-only**.
- Every tool is gated behind a successful local scan.

## Current limitations

- **Windows only** for the desktop app and installer. The MCP server runs from source
  on the Python standard library.
- The installer is **unsigned** — Windows SmartScreen may warn ("unknown publisher").
- First scan of a very large repository can take up to a minute; results are cached after.
- **No third-party security certification** yet.
- The full web → desktop → MCP path has not been independently verified on a clean
  machine at the time of writing.
