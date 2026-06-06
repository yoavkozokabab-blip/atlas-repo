# Phase 181G — Persistence Signing Fixes

**Date:** 2026-06-06  
**Goal:** Clear the final two Phase 181F blockers (forged history with recomputed hash; poisoned memory text with preserved metadata).

## Root Cause

Phase 181E `integrity_hash` was deterministic SHA-256 over record fields. A local attacker editing JSONL/JSON could recompute the hash after tampering. Memory sidecars could change `text` while preserving `scan_id` / `scan_signature` metadata.

## Fix: Local HMAC Signing

### Persistence secret

- Path: `{data_dir}/security/persistence_secret`
- 32 random bytes, created on first use
- File mode `0600` where supported
- Never included in support bundles, diagnostics exports, or session export

### Signed history (`integrity_hmac`)

HMAC-SHA256 keyed by the local secret over canonical JSON:

- `repo_id`, `scan_id`, `scan_signature`, `graph_signature`
- `atlas_version`, `request_text`, `files_named`, `summary_markdown`
- `result_json_hash` (SHA-256 of sanitized `result_json`, not raw source)
- `history_id`, `workflow_type`, `created_at`

Load behavior:

| State | Behavior |
| --- | --- |
| Valid `integrity_hmac` | Trusted; export allowed when scan/session fresh |
| Missing `integrity_hmac` (legacy `integrity_hash` only) | `legacy_untrusted` — historical display only, no export |
| Invalid / tampered HMAC | Row rejected (not listed) |
| `files_named` / `result_json` / summary changed without re-signing | HMAC mismatch → rejected |

### Signed memory packet (`memory_hmac`)

HMAC-SHA256 over:

- `repo_id`, `scan_id`, `scan_signature`, `graph_signature`
- `memory_text` (`text` field in packet)
- `created_at` / `generated_at`, `atlas_version`

Applied to `memory_packet.json` session export sidecar on scan persist.

Load behavior:

- Missing `memory_hmac` → memory discarded, refresh required
- Invalid HMAC → memory discarded
- Text changed with preserved metadata → HMAC mismatch → discarded
- On-disk `memory/{repo_id}.json` full records still use existing `verify_memory_record()` (unchanged semantics)

### Backward compatibility

- Unsigned legacy history: visible as `historical_only`, cannot export
- Unsigned legacy `memory_packet.json`: discarded on restore; rescan/refresh regenerates signed packet
- No crashes on malformed or partial files

### Support bundle

- Bundle never walks `security/` directory
- `persistence_secret` string redacted from sanitized JSON payloads

## Test Results

```text
py -3 -m pytest jarvis_desktop/tests/test_phase181b_persistence.py -q
10 passed

py -3 -m pytest jarvis_desktop/tests/test_phase181e_persistence_red_team_fixes.py -q
8 passed

py -3 -m pytest jarvis_desktop/tests/test_phase181g_persistence_signing.py -q
11 passed
```

## Files Changed

- `jarvis_desktop/persistence.py` — secret management, HMAC sign/verify for history and memory packets
- `jarvis_desktop/api.py` — pass `data_dir` to memory validation on export
- `jarvis_desktop/install_support.py` — redact `persistence_secret` label in bundle sanitization
- `jarvis_desktop/tests/test_phase181g_persistence_signing.py` — 11 signing/red-team tests

## Remaining Limitations

- Local HMAC protects against manual JSON tampering on the same machine; a process with read access to `persistence_secret` could still forge signatures
- Legacy unsigned history remains viewable (historical only) until users re-run workflows after upgrade
- Repository memory engine on-disk format (`memory/{repo_id}.json`) is not HMAC-signed in this phase — only the scan sidecar `memory_packet.json`

## Verdict vs Phase 181F

Both P0 blockers are addressed:

1. Recomputed `integrity_hash` alone cannot forge trusted/exportable history
2. Memory text tampering with preserved metadata fails `memory_hmac` verification and blocks export
