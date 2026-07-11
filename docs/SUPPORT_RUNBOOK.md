# Atlas v1.0 — Support Runbook

Contact: **yoavkozokabab@gmail.com**. All paths below are verified against the v1.0.0 build (commit `3f0ce7a0`).

## Where things live

| Thing | Path |
|---|---|
| App install | `%LOCALAPPDATA%\Programs\Atlas` |
| Data (scans, index, memory, analytics, logs) | `%USERPROFILE%\.atlas_desktop` |
| Launcher log | `%USERPROFILE%\.atlas_desktop\launcher.log` |
| Persisted scans + registry | `%USERPROFILE%\.atlas_desktop\scans\` (`registry.json` + per-repo sidecars) |
| MCP config backups | next to each agent config: `*.atlas-backup-<timestamp>` |
| Agent configs | Claude `%APPDATA%\Claude\claude_desktop_config.json` · Cursor `~\.cursor\mcp.json` · Codex `~\.codex\config.toml` |

Secret redaction: MCP responses and analytics pass through a redaction filter (`sk-`, `ghp_`, bearer tokens, `api_key=` patterns → `[REDACTED]`); analytics is local-only aggregate event names.

## Playbooks

**Install fails** — Ask for the last lines of the Inno Setup log (`%TEMP%\Setup Log*.txt`). Most common: previous install directory reused from registry → rerun installer with `/DIR="%LOCALAPPDATA%\Programs\Atlas"`. Verify download integrity against the published SHA256 first.

**SmartScreen warning** — Expected: the installer is unsigned. More info → Run anyway. Tell users to verify the SHA256 from the GitHub release before doing so. Never tell users to disable SmartScreen.

**App won't open** — 1) `%USERPROFILE%\.atlas_desktop\launcher.log`; 2) startup crashes open the support page automatically with "Copy diagnostics"; 3) port conflict: launch `Atlas.exe --port 8790`; 4) last resort: rename `.atlas_desktop` to `.atlas_desktop.bak` (preserves data) and relaunch.

**Scan fails** — The scan-failed panel names the cause (empty path / not found / no code files / permission denied / partial graph). Ask for the exact panel text. Fallback: load the sample repository to separate "Atlas broken" from "this repo/permissions."

**MCP connect fails** — The manual-setup modal shows the exact config path, a paste-ready snippet, the likely cause, and Retry. Config was invalid JSON/TOML? Atlas refused to touch it (by design) — the user fixes their file or pastes the snippet manually. Every successful write leaves a timestamped backup for rollback.

**Agent doesn't see Atlas after connect** — Fully restart the agent (configs load at startup). Then in Atlas press "Test <Agent>" — PASS with 18 tools means the server side is fine.

**Stale repository** — Expected behavior, not a bug: the repo changed since the last scan, so Atlas refuses stale context and asks for a rescan. Rescan fixes it. If it happens with *no* changes, collect `scans/<repo_id>/latest.json` + the live signature from the error payload and escalate — that's a signature-determinism regression.

**Corrupted agent config** — Restore from the newest `*.atlas-backup-*` file next to the config, or paste the snippet from Advanced manual setup into a fresh file.

**Payment issue / refund** — Pro checkout is disabled at launch ("Coming soon"), so any charge claim is suspect — request the receipt; Paddle is Merchant of Record for future charges. Refund policy: review within 14 days of charge (see /refund). Reply within 2 business days.

## Escalation template

Ask for: Windows version · Atlas version + build commit (footer/About) · what they clicked · exact error text · `launcher.log` tail. Never ask users to send source code or secrets.
