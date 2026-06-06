# Phase 181F Remaining Blockers

Verdict: **NO-GO**

## P0 Blockers

### B1. Workflow history integrity is not adversarially safe

Attack:

- Append forged history JSONL.
- Recompute deterministic `integrity_hash`.
- Use current scan_id and scan_signature.

Observed:

- Forged history item returned by API.
- Secret-like text and fake paths surfaced.
- Current-scan forged row produced `export_allowed=true`.

Risk:

- Local poisoned history can be treated as trusted workflow history and become exportable.

### B2. Persisted memory packet text is not authenticated

Attack:

- Edit `memory_packet.json`.
- Preserve repo_id, scan_id, and signatures.
- Replace only the packet `text` field.

Observed:

- Restore succeeded.
- Memory was not marked rejected.
- Export succeeded.
- Poisoned memory text was exported.

Risk:

- Local poisoned repository memory can be exported as trusted Atlas context after restart.

## Non-Blocking Observations

- Future-version restore is blocked.
- Fake scan_id blocks export.
- Mismatched memory scan_id blocks export.
- Deleted graph sidecar blocks restore/export.
- Corrupted scan JSON does not restore.
- Renamed and same-path-replaced repositories are refused as missing or stale.
- Support bundle redaction passed the tested secret/path/source probes.

## Test Status

Command:

```powershell
py -3 -m pytest jarvis_desktop/tests/test_phase181b_persistence.py jarvis_desktop/tests/test_phase181e_persistence_red_team_fixes.py -q -p no:cacheprovider
```

Result:

```text
18 passed in 1.78s
```

## Beta Verdict

5 supervised beta users: **NO-GO**

20 supervised beta users: **NO-GO**

