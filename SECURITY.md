# Security Policy

## Reporting a vulnerability

If you believe you have found a security issue in Atlas, please report it privately to
_[security/support email — owner to set before publishing]_. Do **not** open a public
issue for security reports. We aim to acknowledge reports within _[X business days]_.
_[NEEDS OWNER CONFIRMATION: contact + response SLA.]_

## Scope

- Atlas desktop application and local MCP server.
- Atlas website (account/auth).

## Design (summary)

Atlas is local-first: the scanning engine and MCP server run on your machine, and your
source code is not uploaded to Atlas servers to provide the product. See
[`docs/LOCAL_FIRST.md`](docs/LOCAL_FIRST.md) for what runs locally, what is sent, and what
not to upload.

- Passwords are scrypt-hashed and compared in constant time (`app/_lib/auth.ts`).
- MCP tool output passes through a secret-redaction filter before returning to the agent.
- MCP tools are read-only and local-path-only.

## Current limitations (honest)

- Windows only; macOS/Linux not supported yet.
- The app is not currently code-signed — Windows SmartScreen may warn.
- **No third-party security certification** (e.g., SOC 2) exists yet.
- The full web → desktop → MCP path has not been independently verified on a clean
  machine at the time of writing.

## Supported versions

Atlas `1.0.0`. Security fixes target the latest build only.
