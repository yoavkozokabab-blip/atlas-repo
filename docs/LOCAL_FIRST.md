# Security and Local-First Design

Atlas runs on your machine. The scanning engine, the dependency/symbol graph, context
packs, and the MCP server all execute locally. **Your source code is not uploaded to
Atlas servers to provide the core product.** (Verified by source inspection of the desktop
and MCP server, commit `69556ceeb`.)

## What stays on your machine

- Source code, file contents, scans, indexes, and generated context packs.
- The MCP server — it speaks JSON-RPC over local stdio, launched by your agent; traffic
  stays between your agent and the local Atlas process.
- Desktop logs and usage analytics — written to your local Atlas data directory; not
  transmitted. (Verified: `analytics.py` is local-file only, no remote endpoint.)
- The desktop's local web UI runs on `127.0.0.1` (your machine only).

## What may be sent to Atlas servers

- If you create an account: your email and an authentication token, to log in and manage
  your subscription. **Never your source code.** (Verified: the desktop auth client
  excludes source code, file paths, and prompt text from request payloads —
  `accounts_client.py`.)
- Website usage produces standard server request logs (via Vercel).
- Payments: **not enabled** in this beta. If enabled later, Stripe would handle them and
  we would never see card numbers.

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

## Known beta limitations

- **Windows only** — macOS/Linux are not supported yet.
- The installer is **unsigned** — Windows SmartScreen may warn ("unknown publisher").
- First scan of a very large repository can take up to a minute; results are cached after.
- **No third-party security certification** yet.
- The full web → desktop → MCP path has not been independently verified on a clean
  machine at the time of writing.
