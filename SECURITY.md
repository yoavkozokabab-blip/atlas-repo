# Security Policy

## Reporting a vulnerability

Please report security issues privately by email to **yoavkozokabab@gmail.com**
rather than in a public issue. Atlas is maintained by one person, so replies may take
a few days.

## Scope

- The Atlas desktop application and its local MCP server.
- The installer published on GitHub Releases.

## Design (summary)

Atlas is local-first: the scanning engine and the MCP server run on your machine, and
your source code is not uploaded anywhere by Atlas. See
[`docs/LOCAL_FIRST.md`](docs/LOCAL_FIRST.md) for what runs locally and
[`PRIVACY.md`](PRIVACY.md) for exactly what leaves your machine.

- MCP tools are read-only and only accept local paths; Atlas never writes to your
  repository.
- MCP tool output passes through a secret-redaction filter before it is returned to
  the agent.
- The MCP server runs on the Python standard library — no third-party packages.

## Current limitations

- Windows only; macOS and Linux are not supported yet.
- The installer is not code-signed, so Windows SmartScreen will warn. You can verify
  the SHA-256 published with each release, or run Atlas from source instead.
- No third-party security audit or certification.

## Supported versions

Security fixes target the latest release only.
