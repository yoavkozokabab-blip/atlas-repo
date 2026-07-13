# Regression risk map

| Area | Risk | Gate |
| --- | --- | --- |
| Launcher/static payload | High | entry delegates to `run_atlas`; startup fallback, bind recovery, self-test, and packaged static files remain |
| Auth/local mode | Critical | account IDs/events, server gate, session restore, offline states, guest-to-sign-in data preserved |
| Scan | High | validate/estimate/select/scan/status/cancel/recent/resume and scope payload preserved |
| Persistence/history | Critical | signed memory, trust/stale/version/path/partial outcomes, source-stripped history, fresh-process restore |
| Ask/Impact/Debug/Plan | High | endpoints, fields, input IDs, history, copy/download, cross-navigation preserved |
| MCP | Critical | per-tool IDs/endpoints, `{confirm:true}`, backups, merging, manual config, tests preserved |
| Graph | High | modes, sampling, selection, inspector, list fallback, performance safeguards preserved |
| Diagnostics | Medium | read-only checks immediate; clear/rebuild explicit |
| Billing/admin | High | no pricing/payment/role/access change; payments remain unavailable |
| Installer/updater | Critical | payload, shortcuts, unsigned message, metadata, updater unchanged |
| Security | Critical | loopback bind and local-origin assumptions preserved; no unrelated hosted origin |

## Special risks

- Global script order is significant; `ask_report.js` and other extensions augment earlier globals.
- The client `api()` returns error payloads rather than throwing; workflows depend on `ok/code/error`.
- FastAPI is not route-equivalent to the canonical registry; do not switch runtime.
- MCP endpoints write outside the repo and remain explicit user actions.
- Scan polling/cancellation is concurrent; prevent duplicate scan actions and stale completion rendering.

## Dirty worktree

User-owned backend, test, docs, generated packaging, report, and submodule changes already exist. Do not clean, reset, stage broadly, or commit unrelated paths. Never use `git add .` or `git add -A`.
