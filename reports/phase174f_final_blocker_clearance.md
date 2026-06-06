# Phase 174F — Final Blocker Clearance

**Date:** 2026-06-05  
**Goal:** 10/10 PASS on exact Phase 174E attack suite  
**Verdict:** ✅ **CLEARED — 10/10 PASS**

## Blockers fixed

| ID | Issue | Fix | Trace |
|----|-------|-----|-------|
| A7 | Build `ok=true` on shallow Go repo; Investigation refused | Unified weak-graph evidence gate; `contains` edges no longer count | [phase174f_build_gate_trace.md](./phase174f_build_gate_trace.md) |
| A10 | `BEARER_LEAK_ME` survived support bundle redaction | Bearer-first Authorization redaction + canary patterns | [phase174f_redaction_trace.md](./phase174f_redaction_trace.md) |

## 174E attack suite replay

| Attack | Expected | Result |
|--------|----------|--------|
| A1_repo_switch_without_rescan | refusal / requires_rescan | ✅ PASS |
| A2_edit_scanned_file_export | export blocked | ✅ PASS |
| A3_git_head_changed_export | stale_git_head_changed | ✅ PASS |
| A4_late_file_outside_2500_export | stale_outside_plan | ✅ PASS |
| A5_tampered_memory_json_reload | no poisoned memory in export | ✅ PASS |
| A6_forced_memory_write_failure | failed status visible | ✅ PASS |
| A7_unsupported_repo_shallow_graph | Build + Investigation refuse | ✅ PASS |
| A8_concurrent_scan_select_export | no wrong-repo leak | ✅ PASS |
| A9_export_replay_after_repo_change | new blocked; old has replay metadata | ✅ PASS |
| A10_support_bundle_trust_redaction | paths + tokens redacted; trust_integrity present | ✅ PASS |

**Score: 10/10 PASS** (was 8/10 in 174E)

## Code changes

| File | Change |
|------|--------|
| `jarvis_desktop/trust_integrity.py` | Import-only graph evidence; unified `_weak_graph_evidence_allows()` |
| `jarvis_desktop/install_support.py` | Extended `_redact_secret_values()` Bearer/canary coverage |
| `jarvis_desktop/tests/test_phase174f_final_blockers.py` | A7 parity, redaction parametrize, full 174E replay |
| `jarvis_desktop/tests/test_phase174d_final_ship_blockers.py` | Module-node id fix for import-evidence test |

## Test validation

```
pytest jarvis_desktop/tests/test_phase174f_final_blockers.py -q     → PASS
pytest jarvis_desktop/tests/test_phase174d_final_ship_blockers.py -q  → PASS
pytest jarvis_desktop/tests/test_phase174b_trust_integrity.py -q      → PASS
pytest jarvis_desktop/tests/test_phase172a_memory_attack_surface.py -q → PASS
pytest jarvis_desktop/tests/test_phase172_memory_engine.py -q         → PASS

Combined: 108 passed
```

## Constraints honored

- No new features
- No UX changes
- No export logic changes beyond redaction path
- No benchmark modifications
