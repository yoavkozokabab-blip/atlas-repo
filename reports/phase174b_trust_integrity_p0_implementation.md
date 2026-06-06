# Phase 174B — Trust Integrity P0 Implementation

**Date:** 2026-06-05  
**Scope:** Stale/wrong/unsafe export paths only. No features, UI, billing, intelligence, or benchmark changes.

## Summary

Phase 174B closes seven P0 trust-integrity failures identified in Phase 173C and Phase 172A. Atlas now refuses exports and workflow outputs when repository context is stale, tampered, or graph coverage is insufficient — and exposes persistence/diagnostic status for support.

## P0 Fixes

| ID | Issue | Fix |
|----|-------|-----|
| 1 | Stale graph after source edits | `trust_integrity.verify_scan_fresh()` / `require_fresh_context()` gate all workflow + export paths; returns `stale_scan` or `stale_git_head_changed` |
| 2 | Signature sampled only first 2500 files | `compute_signature_v2()` — git HEAD/branch/dirty + full indexed manifest hash + scope aggregates + optional content hashes |
| 3 | Poisoned repository memory exportable | `repository_memory` persists `scan_signature`, `memory_hash`, `repo_id`, `scan_id`, `generated_by_version`; `load()` / `verify_memory_record()` discard tampered records |
| 4 | Memory persistence failure silent | `persist()` returns `(path, ok, error)`; `update_after_scan()` sets `memory_persistence_status=failed` and `persistent_memory_available=False` on write failure |
| 5 | Exports carry stale/poisoned context | `require_fresh_context(for_export=True)` validates path, signature, memory hash, graph health before `context_export`, `session_export_packet`, and workflow export attachment |
| 6 | Build/Investigation on weak graph | `gate_weak_graph_workflow()` refuses `ok=true` when `graph_health=unsupported_language_limited` unless exact file/symbol evidence exists |
| 7 | Global runtime state race | `trust_integrity.state_guard()` (`threading.RLock`) wraps scan, select, rebuild, memory update, export, and workflow generation |

## Files Changed

| File | Change |
|------|--------|
| `jarvis_desktop/trust_integrity.py` | **New** — signature v2, freshness gates, weak-graph gate, diagnostics, state lock |
| `jarvis_desktop/repository_memory.py` | Memory hash/signature fields, tamper verification, persist tuple return, persistence status |
| `jarvis_desktop/api.py` | Wire trust gates; store `signature_v2` + `graph_health` on scan; cache key vs content signature split; state_guard on critical paths |
| `jarvis_desktop/install_support.py` | `rebuild_index` under state lock; clear persistence flags; `trust_integrity` in `environment_status` |
| `jarvis_desktop/tests/test_phase174b_trust_integrity.py` | **New** — 11 regression tests |
| `jarvis_desktop/tests/test_phase172a_memory_attack_surface.py` | Updated signature v2 assertion (removed 2500-cap test) |
| `jarvis_desktop/tests/test_phase172_memory_engine.py` | Updated `persist()` return-type expectations |

## Refusal Status Codes

| Status | When |
|--------|------|
| `stale_scan` | File manifest/content changed since last scan |
| `stale_git_head_changed` | Git HEAD changed since last scan |
| `memory_invalid` | In-memory or on-disk memory failed hash/path verification |
| `memory_stale` | Memory `scan_signature` does not match active scan |
| `unsupported_language_limited` | Weak graph + no exact file/symbol evidence |
| `requires_rescan` | No scan or path mismatch |

Export-facing message (when `for_export=True`):

> Atlas needs a fresh scan before exporting this context.

## Signature v2 Design

```
version, root, scope,
git_head, git_branch, git_dirty,
file_count, total_size, total_mtime,
manifest_hash (from indexed scan files, not arbitrary walk cap)
→ SHA256 digest → signature
```

- **Cache lookup key:** filesystem manifest (pre-scan, no index yet)
- **Freshness / stored signature:** indexed manifest + content hashes from scan result

## Test Results

```
py -3 -m pytest jarvis_desktop/tests/test_phase174b_trust_integrity.py -q
# 11 passed

py -3 -m pytest jarvis_desktop/tests/test_phase172a_memory_attack_surface.py -q
# 6 passed

py -3 -m pytest jarvis_desktop/tests/test_phase172_memory_engine.py -q
# 49 passed
```

**Total: 66 passed**

## Test Coverage (174B)

- Edit file after scan → export refuses `stale_scan`
- Git HEAD change → export refuses `stale_git_head_changed`
- Memory file tamper → `load()` returns `None`; in-state tamper → export refuses `memory_invalid`
- Memory write failure → `memory_persistence_status=failed` exposed
- Repo path switch → stale memory cleared; export refuses
- Unsupported graph Build → refuses unless exact file evidence
- Concurrent `select_repository` + export → no wrong-repo memory
- `beta_diagnostics()` / `environment_status()` include `trust_integrity` block

## Out of Scope (unchanged)

- Website, billing, UI redesign
- Intelligence / planning engine logic
- Benchmark scoring
