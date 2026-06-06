# Phase 174E Final Trust Integrity Verification

Date: 2026-06-06T10:43:02Z
Role: final adversarial verifier
Scope: rerun the exact 10 Phase 174C trust-integrity attacks after Phase 174D fixes. No Atlas production code was modified.

## Executive Verdict

Final verdict: **NO-GO** for 20 supervised beta users.

Result: **8/10 attacks passed**.
Failed attacks: A7_unsupported_repo_shallow_graph, A10_support_bundle_trust_redaction

## Required Blocker Checks

| Check | Result | Evidence |
| --- | --- | --- |
| Unsupported Go/shallow graph Build refuses | FAIL | Build status: `ok`; ok: `True` |
| Unsupported Go/shallow graph Investigation refuses | FAIL | Investigation status: `insufficient_evidence`; ok: `False` |
| Memory exports include replay warning + signature | PASS | scan_id: `True`; signature: `True`; replay warning: `True` |
| Support bundle redacts api_key and token-like secrets | FAIL | secret leak: `True`; raw key pattern leak: `True` |

## Attack Summary

| Attack | Result | Expected | Actual |
| --- | --- | --- | --- |
| A1_repo_switch_without_rescan | PASS | refusal or requires_rescan; no repo A memory in repo B output | plan=requires_rescan, investigation=requires_rescan, impact=requires_rescan, export=requires_rescan, leak=False |
| A2_edit_scanned_file_export | PASS | stale context export refusal after scanned file edit | scan_ok=True, export_status=stale_outside_plan, session_export_status=stale_outside_plan |
| A3_git_head_changed_export | PASS | stale_git_head_changed refusal | scan_ok=True, export_status=stale_git_head_changed |
| A4_late_file_outside_2500_export | PASS | stale context detected for file outside old 2500 cap | scan_ok=True, files=2511, modules=2511, export_status=stale_outside_plan |
| A5_tampered_memory_json_reload | PASS | memory discarded or refusal; no poisoned memory in export | session1_status=ok, session2_status=ok, export_status=ok, poison_visible=False |
| A6_forced_memory_write_failure | PASS | memory_persistence_status=failed visible, no persistent memory claim | scan_ok=True, session_export_status=ok, diagnostics_memory_status=failed, failed_visible=True, persistent_memory_available_false=True |
| A7_unsupported_repo_shallow_graph | FAIL | Build and Investigation refuse on unsupported Go/shallow graph; Impact may target-not-resolved honestly | modules=1, edges=0, graph_health={'reliability_category': 'ok', 'scope': 'production', 'degraded': False, 'modules': 1, 'edges': 0, 'import_cycles': 0, 'resolved_imports': 0, 'unresolved_imports': 0, 'external_package_imports': 0, 'unresolved_ratio': 0.0, 'unresolved_ratio_note': 'External imports (targets outside the internal module set: third-party packages + standard library + any unresolved internal imports) ÷ all imports. High values are normal for apps with many dependencies.', 'external_label': 'external + stdlib imports', 'label': 'healthy', 'unresolved_internal': 0, 'unresolved_external': 0, 'unresolved_dynamic_optional': 0, 'unresolved_internal_ratio': 0.0, 'health_basis': 'internal_unresolved', 'notice': 'Internal graph is reliable: 0 unresolved internal import(s). The 0 external/stdlib import(s) are normal dependencies.', 'reliable': True, 'reason': 'Graph health weights internal_missing and relative_resolution_issue; external_dependency and dynamic_import are expected in large apps.', 'partial_reason': ''}, plan=ok, investigation=insufficient_evidence, impact=target_not_resolved |
| A8_concurrent_scan_select_export | PASS | no wrong-repo memory leakage under concurrent scan/select/export | leak_count=0 |
| A9_export_replay_after_repo_change | PASS | new export blocked; old packet includes scan_id, signature, and replay warning | new=requires_rescan, scan_id=True, signature=True, replay_warning=True |
| A10_support_bundle_trust_redaction | FAIL | trust-integrity status included, absolute paths redacted, no api_key/token/bearer/source leaks | trust=True, path_leak=False, secret_leak=True, key_pattern_leak=True |

## Detailed Reproductions

### A1_repo_switch_without_rescan - PASS

Expected: refusal or requires_rescan; no repo A memory in repo B output

API / command path:
- `api.scan_repository(repo_a)`
- `api.session_export_packet()`
- `api.select_repository(repo_b)`
- `api.plan_change(...)`
- `api.investigate_symptom(...)`
- `api.change_impact_simulation(...)`
- `api.context_export(...)`

Captured result:
```json
{
  "scan_ok": true,
  "select_requires_rescan": true,
  "plan_status": "requires_rescan",
  "investigation_status": "requires_rescan",
  "impact_status": "requires_rescan",
  "export_status": "requires_rescan",
  "repo_a_leak": false
}
```

Risk if failed: Wrong-repo memory or graph output after selecting a different repository.

### A2_edit_scanned_file_export - PASS

Expected: stale context export refusal after scanned file edit

API / command path:
- `api.scan_repository(repo)`
- `edit scanned file`
- `api.context_export(...)`
- `api.session_export_packet()`

Captured result:
```json
{
  "scan_ok": true,
  "export_status": "stale_outside_plan",
  "session_export_status": "stale_outside_plan"
}
```

Risk if failed: Stale source context exported after local edits.

### A3_git_head_changed_export - PASS

Expected: stale_git_head_changed refusal

API / command path:
- `create synthetic .git HEAD/ref`
- `api.scan_repository(repo)`
- `change .git ref`
- `api.context_export(...)`

Captured result:
```json
{
  "scan_ok": true,
  "export_status": "stale_git_head_changed"
}
```

Risk if failed: Old branch or revision context exported after checkout/commit.

### A4_late_file_outside_2500_export - PASS

Expected: stale context detected for file outside old 2500 cap

API / command path:
- `api.scan_repository(2511-file repo)`
- `edit z/late.py`
- `api.context_export(...)`

Captured result:
```json
{
  "scan_ok": true,
  "files": 2511,
  "modules": 2511,
  "export_status": "stale_outside_plan"
}
```

Risk if failed: Large-repo edits outside sampled files bypass invalidation.

### A5_tampered_memory_json_reload - PASS

Expected: memory discarded or refusal; no poisoned memory in export

API / command path:
- `api.scan_repository(repo)`
- `api.session_export_packet()`
- `tamper memory JSON hash-protected fields`
- `reset API state`
- `api.scan_repository(repo)`
- `api.session_export_packet()`
- `api.context_export(...)`

Captured result:
```json
{
  "scan1_ok": true,
  "session1_status": "ok",
  "memory_file_existed": false,
  "scan2_ok": true,
  "session2_status": "ok",
  "export_status": "ok",
  "poison_visible": false
}
```

Risk if failed: Poisoned memory becomes trusted LLM context.

### A6_forced_memory_write_failure - PASS

Expected: memory_persistence_status=failed visible, no persistent memory claim

API / command path:
- `monkeypatch repository_memory.persist failure`
- `api.scan_repository(repo)`
- `api.session_export_packet()`
- `api.beta_diagnostics()`

Captured result:
```json
{
  "scan_ok": true,
  "session_export_status": "ok",
  "diagnostics_memory_status": "failed",
  "failed_visible": true,
  "persistent_memory_available_false": true
}
```

Risk if failed: Atlas silently claims durable memory when persistence failed.

### A7_unsupported_repo_shallow_graph - FAIL

Expected: Build and Investigation refuse on unsupported Go/shallow graph; Impact may target-not-resolved honestly

API / command path:
- `api.scan_repository(Go repo with incidental Python helper)`
- `api.plan_change("add event bus tracing")`
- `api.investigate_symptom("why are duplicate events being fired")`
- `api.change_impact_simulation("pkg/events/bus.go")`

Captured result:
```json
{
  "scan_ok": true,
  "files": 3,
  "modules": 1,
  "edges": 0,
  "graph_health": {
    "reliability_category": "ok",
    "scope": "production",
    "degraded": false,
    "modules": 1,
    "edges": 0,
    "import_cycles": 0,
    "resolved_imports": 0,
    "unresolved_imports": 0,
    "external_package_imports": 0,
    "unresolved_ratio": 0.0,
    "unresolved_ratio_note": "External imports (targets outside the internal module set: third-party packages + standard library + any unresolved internal imports) \u00f7 all imports. High values are normal for apps with many dependencies.",
    "external_label": "external + stdlib imports",
    "label": "healthy",
    "unresolved_internal": 0,
    "unresolved_external": 0,
    "unresolved_dynamic_optional": 0,
    "unresolved_internal_ratio": 0.0,
    "health_basis": "internal_unresolved",
    "notice": "Internal graph is reliable: 0 unresolved internal import(s). The 0 external/stdlib import(s) are normal dependencies.",
    "reliable": true,
    "reason": "Graph health weights internal_missing and relative_resolution_issue; external_dependency and dynamic_import are expected in large apps.",
    "partial_reason": ""
  },
  "plan_status": "ok",
  "plan_ok": true,
  "investigation_status": "insufficient_evidence",
  "investigation_ok": false,
  "impact_status": "target_not_resolved",
  "impact_ok": false,
  "helper_success": true
}
```

Risk if failed: Unsupported or mixed-language repos receive plausible but wrong Build/Investigation outputs.

### A8_concurrent_scan_select_export - PASS

Expected: no wrong-repo memory leakage under concurrent scan/select/export

API / command path:
- `repeat 12 times`
- `concurrent api.context_export, api.select_repository(repo_b), api.scan_repository(repo_b)`

Captured result:
```json
{
  "iterations": 12,
  "leak_count": 0,
  "sample_statuses": [
    "ok",
    "ok",
    "ok",
    "ok",
    "ok",
    "ok",
    "ok",
    "ok",
    "ok",
    "ok"
  ],
  "leaks": []
}
```

Risk if failed: Concurrent workflow mixes repository state or exports wrong-repo memory.

### A9_export_replay_after_repo_change - PASS

Expected: new export blocked; old packet includes scan_id, signature, and replay warning

API / command path:
- `api.scan_repository(repo_a)`
- `old=api.session_export_packet()`
- `api.select_repository(repo_b)`
- `new=api.session_export_packet()`

Captured result:
```json
{
  "scan_ok": true,
  "select_requires_rescan": true,
  "new_export_status": "requires_rescan",
  "old_has_scan_id": true,
  "old_has_signature": true,
  "old_has_replay_warning": true,
  "old_packet_keys": [
    "freshness_status",
    "generated_at",
    "has_delta",
    "memory_persistence_status",
    "mode",
    "ok",
    "persistent_memory_available",
    "replay_warning",
    "repo_id",
    "scan_id",
    "scan_signature",
    "session_count",
    "text",
    "tokens",
    "version"
  ]
}
```

Risk if failed: Old memory packet can be pasted after repo changes without warning.

### A10_support_bundle_trust_redaction - FAIL

Expected: trust-integrity status included, absolute paths redacted, no api_key/token/bearer/source leaks

API / command path:
- `api.scan_repository(repo)`
- `write launcher log with path/api_key/token/Bearer/source canaries`
- `api.export_support_bundle()`
- `decode support zip in memory`

Captured result:
```json
{
  "scan_ok": true,
  "bundle_ok": true,
  "entries": [
    "manifest.json",
    "version.txt",
    "diagnostics.json",
    "environment.json",
    "scan_metadata.json",
    "startup_checks.json",
    "logs/launcher.log",
    "logs/analytics.jsonl"
  ],
  "has_trust_integrity": true,
  "absolute_path_leak": false,
  "secret_or_source_leak": true,
  "raw_key_pattern_leak": true,
  "source_leak": false,
  "launcher_log_excerpt": "Failure at [path-redacted] with [secret-redacted] and api_key=[REDACTED] and token=[REDACTED] and Authorization: [REDACTED] BEARER_LEAK_ME\r\n"
}
```

Risk if failed: Support bundle leaks source, absolute paths, or token-like secrets.

## Validation Notes

- The harness called the same Atlas API surfaces as Phase 174C: `scan_repository`, `select_repository`, `plan_change`, `investigate_symptom`, `change_impact_simulation`, `context_export`, `session_export_packet`, `beta_diagnostics`, and `export_support_bundle`.
- Disposable repositories and Atlas data were created under a Phase 174E runtime directory and removed after capture.
- No production code, tests, intelligence, routing, graph, memory, installer, or UI files were edited by this verification pass.

## Final Decision

NO-GO for 20 supervised beta users. The failed attacks above remain trust blockers.
