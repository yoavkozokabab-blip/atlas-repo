# Phase 174C Trust Integrity Red Team Verification

Date: 2026-06-06
Role: adversarial verifier
Scope: verify Phase 174B stale-context, poisoned-memory, export, support, and workflow trust integrity claims.

No Atlas production code was modified. The probe created disposable repositories under `reports/phase174c_runtime/` and wrote raw results to `reports/phase174c_attack_results.json`.

## Inputs Reviewed

- `reports/phase173c_red_team.md`
- `reports/phase173c_attack_surface.md`
- `reports/phase173c_ship_blockers.md`
- `reports/phase172a_repository_memory_attack_surface.md`
- `reports/phase174b_trust_integrity_p0_implementation.md`

## Executive Verdict

NO-GO for 20 supervised beta users.

Phase 174B substantially improves stale-context protection: repository switching, edited files, git HEAD changes, late-file changes beyond the old 2500-file cap, memory tampering, forced memory persistence failure visibility, and concurrent scan/select/export probes all behaved safely in this run.

However, three trust blockers remain:

1. Unsupported-language / shallow graph workflows still return `ok=true` and point to an incidental Python helper file.
2. Old memory packets include `scan_id`, but no signature/staleness/replay warning.
3. Support bundle redaction includes trust status and path redaction, but leaked `api_key=LEAK_ME` from logs.

## Results Summary

- Total attacks: 10
- Passed: 7
- Failed: 3
- Failed attacks: A7_unsupported_repo_shallow_graph, A9_export_replay_after_repo_change, A10_support_bundle_trust_redaction

## Attack Table

| Attack | Result | Expected | Actual status |
| --- | --- | --- | --- |
| A1_repo_switch_without_rescan | PASS | refusal or requires_rescan; no repo A memory in repo B output | plan=requires_rescan, investigation=requires_rescan, impact=requires_rescan, export=requires_rescan |
| A2_edit_scanned_file_export | PASS | stale context export refusal (expected stale_scan; stale_outside_plan acceptable if blocked) | export=stale_outside_plan, session_export=stale_outside_plan |
| A3_git_head_changed_export | PASS | stale_git_head_changed refusal | export=stale_git_head_changed |
| A4_late_file_outside_2500_export | PASS | stale context detected for file outside old 2500 cap | export=stale_outside_plan |
| A5_tampered_memory_json_reload | PASS | memory discarded or refusal; no poisoned memory in export | export=ok, session2=ok |
| A6_forced_memory_write_failure | PASS | memory_persistence_status=failed visible, no persistent memory claim | session_export=ok |
| A7_unsupported_repo_shallow_graph | FAIL | honest insufficient_evidence / unsupported_language_limited unless exact evidence exists | plan=ok, investigation=ok, impact=target_not_resolved |
| A8_concurrent_scan_select_export | PASS | no wrong-repo memory leakage | leak_count=0 |
| A9_export_replay_after_repo_change | FAIL | new export blocked; old packet includes scan_id/signature warning | new_export=requires_rescan, has_signature_warning=False |
| A10_support_bundle_trust_redaction | FAIL | trust-integrity status included, absolute paths redacted, no secrets | has_secret=True |

## Detailed Findings

### A1: Repo Switch Without Rescan

Result: PASS

Setup: scanned repo A, selected repo B without rescan, then tried Change Plan, Investigation, Impact, and Copy for Claude.

API calls: `api.scan_repository(repo_a); api.session_export_packet(); api.select_repository(repo_b); api.plan_change(...); api.investigate_symptom(...); api.change_impact_simulation(...); api.context_export("claude","compact")`

Actual: Change Plan returned `requires_rescan`; Investigation and Impact returned `requires_rescan`; Copy for Claude returned `requires_rescan`. No repo A marker leaked into repo B output.

Risk if failed: wrong-repo memory or graph output.

### A2: Edit Scanned File Then Export

Result: PASS

Setup: scanned a Python repo, edited `main.py`, then tried session and Claude export.

API calls: `api.scan_repository(repo); edit scanned file; api.context_export("claude","compact"); api.session_export_packet()`

Actual: both exports refused with `stale_outside_plan`. The user-specified expected label was `stale_scan`; Phase 174B's targeted-refresh path uses `stale_outside_plan`, but the trust behavior is correct because export is blocked.

Risk if failed: stale source context exported after local edits.

### A3: Git HEAD Changed

Result: PASS

Setup: scanned a repo with synthetic `.git/HEAD` and `refs/heads/main`, changed the HEAD ref, then exported.

API calls: `create synthetic .git HEAD; api.scan_repository(repo); change .git refs/heads/main; api.context_export("claude","compact")`

Actual: export refused with `stale_git_head_changed`.

Risk if failed: old branch/revision context exported after checkout or commit.

### A4: File Outside Old 2500-File Cap

Result: PASS

Setup: scanned 2511 Python modules, modified `z/late.py`, then exported.

API calls: `api.scan_repository(repo with 2511 modules); edit z/late.py; api.context_export("claude","compact")`

Actual: export refused with `stale_outside_plan`, proving the old first-2500-file blind spot is closed for export safety.

Risk if failed: large-repo edits outside sampled files would bypass invalidation.

### A5: Tampered Memory JSON

Result: PASS

Setup: scanned repo, tampered persisted memory JSON to include `MALICIOUS_FAKE_HUB` without recomputing `memory_hash`, reset state, rescanned, and exported.

API calls: `api.scan_repository(repo); api.session_export_packet(); tamper memory JSON without recomputing memory_hash; reset process state; api.scan_repository(repo); api.session_export_packet(); api.context_export("claude","compact")`

Actual: no `MALICIOUS_FAKE_HUB` appeared in session export or Claude export. Memory was discarded or rebuilt cleanly.

Risk if failed: poisoned memory could become trusted LLM context.

### A6: Forced Memory Write Failure

Result: PASS

Setup: monkeypatched `repository_memory.persist()` at runtime to return failure, then scanned and exported.

API calls: `monkeypatch repository_memory.persist to return failure; api.scan_repository(repo); api.session_export_packet(); api.beta_diagnostics()`

Actual: `memory_persistence_status=failed` appeared in session export and diagnostics, and `persistent_memory_available=false` was present.

Risk if failed: Atlas could silently claim durable memory when persistence failed.

### A7: Unsupported Repo Shallow Graph

Result: FAIL

Setup: scanned a Go-style repo with two Go files and one incidental Python helper (`hack/boilerplate.py`), then ran Build, Investigation, and Impact.

API calls: `api.scan_repository(Go repo with incidental Python helper); api.plan_change("add event bus tracing"); api.investigate_symptom("why are duplicate events being fired"); api.change_impact_simulation("pkg/events/bus.go")`

Actual:

- Scan graph health was `healthy` despite `module_count=1`, `dependency_edges=0`, and only `hack/boilerplate.py` being represented.
- Build returned `ok=true`, confidence `low-medium`, and recommended `hack/boilerplate.py` for `add event bus tracing`.
- Investigation returned `ok=true`, confidence `low-medium`, and used the same helper file for `why are duplicate events being fired`.
- Impact correctly returned `target_not_resolved` for `pkg/events/bus.go`.

Root cause:

`trust_integrity.gate_weak_graph_workflow()` only gates when graph health label equals `unsupported_language_limited`. This repo was mislabeled `healthy`, so the gate never fired.

Risk:

Unsupported or mixed-language repositories can still receive plausible but wrong Build/Investigation outputs. This is the most direct remaining trust failure.

Suggested mitigation:

Classify shallow unsupported coverage using language mix and module coverage, not only unresolved imports. If the graph represents one incidental Python helper while most production files are unsupported language files, Build and Investigation should return `unsupported_language_limited` or `insufficient_evidence` unless exact user-provided file evidence exists.

### A8: Concurrent Scan/Select/Export

Result: PASS

Setup: repeated 12 concurrent cycles of exporting repo A context while selecting and scanning repo B.

API calls: `repeat 12 times; api.scan_repository(repo_a); concurrently: api.context_export, api.select_repository(repo_b), api.scan_repository(repo_b); api.context_export final`

Actual: no wrong-repo memory leakage was detected. The RLock/state guards appear to prevent the tested interleaving.

Risk if failed: mixed repository state or wrong-repo export.

### A9: Export Replay

Result: FAIL

Setup: copied old repo A memory packet, selected repo B, then requested a new session export.

API calls: `api.scan_repository(repo_a); api.session_export_packet() old packet; api.select_repository(repo_b); api.session_export_packet() new packet`

Actual:

- New export was blocked with `requires_rescan`.
- Old packet included `scan_id`.
- Old packet did not include a signature, staleness warning, replay warning, or rescan caveat.

Root cause:

`ATLAS_REPOSITORY_MEMORY v1` text has a scan id but no self-describing validity boundary. Once copied into an external LLM, Atlas cannot revoke it.

Risk:

A user can paste an old memory packet into a new chat after switching repos or editing code, and the packet does not warn the model/user that it is valid only for a specific signature/current scan.

Suggested mitigation:

Include a compact validity line in memory packets: repo_id, scan_id, scan_signature prefix, and a warning that the packet is valid only until repo changes or Atlas says rescan/refresh required.

### A10: Support Bundle Redaction

Result: FAIL

Setup: wrote a launcher log containing an absolute path, `SECRET_PHASE174C_LOG`, and `api_key=LEAK_ME`, then exported the support bundle.

API calls: `api.scan_repository(repo); write launcher.log with path and secret canaries; api.export_support_bundle(); decode support zip and inspect entries`

Actual:

- Trust-integrity status was included.
- Absolute paths were redacted.
- `SECRET_PHASE174C_LOG` was redacted.
- `api_key=LEAK_ME` leaked in `logs/launcher.log`.
- Source-code canary did not leak.

Root cause:

`install_support._redact_support_text()` redacts absolute paths and `SECRET_*` tokens but does not redact common key/value secret patterns such as `api_key=...`.

Risk:

Support bundles can leak secrets from logs. This is a privacy and beta-trust blocker.

Suggested mitigation:

Add generic redaction for `api_key`, `token`, `secret`, `password`, `authorization`, bearer tokens, and common cloud credential names. Add a regression test around logs and JSON diagnostics.

## Code Evidence

- `jarvis_desktop/trust_integrity.py:233-268`: changed-file detection over stored manifest.
- `jarvis_desktop/trust_integrity.py:349-425`: staleness classification and targeted-refresh status.
- `jarvis_desktop/trust_integrity.py:450-466`: stale context refusal payload.
- `jarvis_desktop/trust_integrity.py:558-588`: weak-graph gate only fires on `unsupported_language_limited`.
- `jarvis_desktop/repository_memory.py:106-124`: memory hash verification.
- `jarvis_desktop/repository_memory.py:214-231`: persistence status return path.
- `jarvis_desktop/api.py:2666-2705`: Build Plan wiring and export blocking.
- `jarvis_desktop/api.py:2708-2743`: Investigation wiring and export blocking.
- `jarvis_desktop/api.py:2735-2762`: session export freshness gate.
- `jarvis_desktop/api.py:2874-2905`: context export freshness gate.
- `jarvis_desktop/install_support.py:365-371`: support bundle redaction currently handles paths and `SECRET_*` only.

## Final Verdict

NO-GO for 20 supervised beta users.

Phase 174B blocks the main stale-context and poisoned-memory failures tested here, but beta trust can still be damaged by unsupported-repo false success and support bundle secret leakage.
