# Phase 181C Remaining Blockers

Verdict: **NO-GO**

## P0 Blockers

### B1. Poisoned history rows are surfaced to the UI/API

Attack: history poisoning.

Observed:

- Forged history JSONL row was returned by `list_workflow_history_api()` / `get_workflow_history_item_api()`.
- Old `scan_id` prevented export.
- Fake paths and secret-like strings were still visible in returned history payloads.

Risk:

- Local history can mislead the user or expose injected sensitive text even when export is blocked.

### B2. Persisted memory sidecar is trusted on restore

Attack: memory / scan mismatch.

Observed:

- Tampered `memory_packet.json` was restored.
- Export succeeded.
- Exported packet included poisoned `scan_id` and poisoned memory text.

Risk:

- Wrong or malicious repository memory can be exported as trusted context after restart.

### B3. Incompatible future persistence version is accepted

Attack: version mismatch.

Observed:

- `latest.json` with `atlas_version = 999.0.0-future-incompatible` restored successfully when file signatures matched.
- Restore validation reported `valid` and `fresh`.

Risk:

- Upgrade/rollback or stale-schema persistence can be treated as compatible and trusted.

## Process Blocker

### B4. Phase 181A architecture report was not available

Observed:

- `reports/phase181a_persistence_architecture.md` was referenced by the verification task but was not present in the workspace.

Risk:

- The verifier could compare implementation against Phase 181B, Phase 174, and Phase 172A, but not the missing Phase 181A persistence design contract.

## Beta Verdict

5 supervised beta users: **NO-GO**

20 supervised beta users: **NO-GO**

