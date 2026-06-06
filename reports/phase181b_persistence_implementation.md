# Phase 181B — Persistence and History Implementation

**Date:** 2026-06-06  
**Principle:** Restoring stale context is worse than rescanning.

## What Was Persisted

### Scan snapshots (`{data_dir}/scans/{repo_id}/`)

| File | Contents |
| --- | --- |
| `latest.json` | Metadata: repo path/id, scan/signature IDs, counts, graph health, language profile, memory ref/hash, trust status, atlas version |
| `scan_snapshot.json` | Full in-memory scan dict (UI/summary fields) |
| `graph.json` | Dependency graph for map + workflows |
| `index.json` | Light index (paths, roles, subsystems — no source text) |
| `risks.json` | Risk ranking snapshot |
| `evidence_store.json` | Symbol/call evidence index |
| `file_manifest.json` | Trust integrity manifest for targeted refresh |
| `memory_packet.json` | Session export / repository memory packet |
| `registry.json` | Recent scan index (max 10) |

### Workflow history (`{data_dir}/histories/{repo_id}/{workflow}.jsonl`)

Records for **build**, **investigate**, and **impact** with:

`history_id`, `workflow_type`, `request_text`, `created_at`, `repo_id`, `scan_id`, `files_named`, `confidence`, `export_tokens`, `export_mode`, `summary_markdown`, sanitized `result_json`, `trust_status`, `export_allowed`.

## Intentionally NOT Persisted

- Raw source file contents
- Full Claude prompts / `export_full` blobs
- Billing, marketing, or website data
- Repository memory engine on-disk format (unchanged — still `{data_dir}/memory/{repo_id}.json`)
- Trust integrity / impact algorithm internals

## Restore Behavior

1. **Startup (`bootstrap_persistence`)** — cleanup, then load most recent scan.
2. **Valid + fresh signature** — auto-restore graph/index/evidence into `_STATE`; health reports `restored: true`.
3. **Stale signature** — no auto-restore; home shows **Refresh** / **Full rescan** card.
4. **Wrong/missing path** — refuse resume (`wrong_repo`, `path_missing`).
5. **Incomplete sidecars** — refuse resume (`partial_scan`).
6. **History export** — blocked when `scan_id` mismatches or `require_fresh_context` fails.

## API Routes

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/api/repositories/recent` | Backend recent repositories |
| POST | `/api/repositories/resume` | Resume persisted scan by `repo_id` |
| GET | `/api/history?repo_id=&workflow_type=` | List workflow history |
| GET | `/api/history/item?history_id=` | Fetch one history item + export eligibility |

## UI

- Home **Resume {repo}** card with Resume / Refresh / Full rescan / Scan another
- **Recent repositories** loaded from backend API
- **Recent results** (last 5) on Change Plan, Debug, and What breaks? screens

## Retention Defaults

- Latest **10** scans
- **100** workflow records per repo per workflow type
- **90** day history age limit
- Cleanup on startup

## Tests

`jarvis_desktop/tests/test_phase181b_persistence.py` — **10 passed**

Also verified: `test_phase179_beta_ship_blockers.py` — **95 passed** (combined run 105 tests).

Coverage:

- Scan written after scan
- Valid scan restored after simulated restart
- Changed file → stale validation
- Wrong repo path refused
- History for build / investigate / impact
- History survives restart
- Stale history cannot export
- Cleanup removes old scans
- Recent repos API
- No raw source in persistence files

## Remaining Limitations

- History reopen displays saved markdown; re-running workflows requires a fresh scan
- Very large graphs may produce partial sidecars (`requires_refresh_before_export`)
- Auto-restore only attempts the single most recent scan
- `refresh-changed-files` after stale resume may still require full rescan for heavy changes
