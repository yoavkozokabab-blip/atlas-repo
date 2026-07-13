# Screen inventory

## Launch and access

| Surface | Current implementation | States |
| --- | --- | --- |
| Boot | `#bootSplash`, `startup-error.html` | starting, startup-check failure, bind fallback |
| First-launch trust | `atlas_launch_ux.js` overlay | unsigned notice, acknowledged |
| Authentication | `#auth-layout`, `atlas_accounts.js` | sign in, five-step registration, local mode, created, submit failed, blocked/offline/session restore |
| Account status | `#view-status` | pending, active, restricted/rejected variants |

## Repository workbench

| Destination | Current view | Existing capability |
| --- | --- | --- |
| Home | `#view-home` | empty, indexed/no agent, productive, stale/resume facts |
| Scan | `#view-scan` | sample/local, validation, scope, progress, cancel, success, failure, recents |
| Ask | `#view-ask` | brief, templates, loading, cited report, evidence, files, limits, next actions |
| Debug | `#view-investigate` | symptom, hypotheses, verification, history |
| Impact | `#view-impact` | target, direct/transitive paths, tests, caveats, history |
| Plan | `#view-build` | change brief, sequence, risks, tests, history |
| Graph | `#view-center` | module/subsystem/hierarchy, filter, selection, inspector, list fallback, large-repo mode |
| Agent handoff | `#view-export` | size/target, preview, copy/download, Cursor/CLAUDE.md helpers |

## Operational and secondary surfaces

- MCP setup/manual repair for Claude Code, Cursor, and Codex.
- Diagnostics: system/startup/self-test, support bundle, cache clear, index rebuild, scan and MCP diagnostics.
- Account/profile/devices, inactive account status, admin workspace.
- Usage/pricing/billing preview; payments remain disabled.
- Welcome, walkthrough, About, shortcuts, command palette, confirmations.
- Global states: telemetry warning, trust, update, toast, API/offline failure, no repo, stale repo, partial graph, massive repo.

## Missing first-class destinations

Memory, Files/Symbols/Concepts, Agents, Diagnostics, and Settings exist as capabilities or data sources but not coherent main destinations. They belong in the target IA without backend changes.
