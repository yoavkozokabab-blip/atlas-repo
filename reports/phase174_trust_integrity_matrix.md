# Phase 174 — Trust Integrity Matrix

**Date:** 2026-06-06  
**Design only. No code changes.**

This matrix answers one question per cell: for this output route, under this failure condition, is Atlas currently **protected** or **unprotected**? And if unprotected, what is the exact required fix?

---

## Legend

| Symbol | Meaning |
|--------|---------|
| ✅ **PROTECTED** | Current code correctly refuses or warns |
| ⚠️ **PARTIAL** | Guard exists but has known bypass |
| ❌ **UNPROTECTED** | No guard. Stale/wrong/poisoned output reaches user. |
| 🔲 **N/A** | Failure mode does not apply to this route |

---

## Failure Mode Definitions

| Column | Failure class | Source |
|--------|--------------|--------|
| **STALE PATH** | Repo path changed without rescan | RT-06, A1 |
| **GIT CHANGE** | `git checkout` changed HEAD after scan | B1, Phase 172A |
| **FILE CHANGE** | Source file edited, graph not updated | RT-01, AS-F1, SB-01 |
| **MEM MISMATCH** | On-disk memory doesn't match current scan | RT-04, AS-F4, SB-02 |
| **CACHE RESTORE** | Graph loaded from `scan_cache`, content unverified | AS-F1, B3 |
| **UNSUPPORTED LANG** | Repo primary language not Python/TypeScript | RT-05, SB-04 |
| **PARTIAL GRAPH** | `graph_health = partial/watch/degraded` | SW-01 |
| **POISONED MEMORY** | On-disk memory JSON injected with fake facts | RT-04, SB-02 |
| **EXPORT REPLAY** | Stale UI `STATE.sessionExport` prepended to new copy | B4, Phase 172A |

---

## Matrix

### Route 1: Change Plan (`plan_change`)

| Failure | Status | Evidence | Required fix |
|---------|--------|---------|-------------|
| STALE PATH | ✅ PROTECTED | `_scan_matches_current_path()` guard at line 2595 | None needed |
| GIT CHANGE | ❌ UNPROTECTED | No git HEAD recorded at scan time | Store `git_head` at scan; re-check at export |
| FILE CHANGE | ❌ UNPROTECTED | `_scan_signature` uses size+mtime only; RT-01 confirmed | `GraphFileManifest` content hash for indexed files |
| MEM MISMATCH | ❌ UNPROTECTED | `memory_ref` injected but never validated against active scan | Validate `memory_ref == _STATE.scan.scan_id` before attaching delta |
| CACHE RESTORE | ❌ UNPROTECTED | Cache hit trusts signature; graph from hours ago presented as current | Add `graph_signature` to cache entry; verify on restore |
| UNSUPPORTED LANG | ⚠️ PARTIAL | Gate fires only when `matched_paths == []`; bypassed by any incidental Python file | Gate must use `module_count` not `matched_paths` |
| PARTIAL GRAPH | ⚠️ PARTIAL | `confidence_cap_reason` exists in some paths; not on all exports | Attach `confidence_cap` to `TrustEnvelope` on every export |
| POISONED MEMORY | ❌ UNPROTECTED | Memory delta text flows directly into `export_memory.text` | Validate memory before delta generation (HR-07) |
| EXPORT REPLAY | ❌ UNPROTECTED | UI `zfSessionPrefix()` prepends `STATE.sessionExport` without version check | UI must verify `sessionExport.scan_id == buildResult.scan_id` |

**Overall: 1 protected, 2 partial, 6 unprotected**

---

### Route 2: Investigation (`investigate_symptom`)

| Failure | Status | Evidence | Required fix |
|---------|--------|---------|-------------|
| STALE PATH | ❌ UNPROTECTED | **No `_scan_matches_current_path()` guard** at line 2621 | Add same guard as `plan_change` (HR-01) |
| GIT CHANGE | ❌ UNPROTECTED | Same as Route 1 | Same as Route 1 |
| FILE CHANGE | ❌ UNPROTECTED | Same as Route 1 | Same as Route 1 |
| MEM MISMATCH | ❌ UNPROTECTED | Same as Route 1 | Same as Route 1 |
| CACHE RESTORE | ❌ UNPROTECTED | Same as Route 1 | Same as Route 1 |
| UNSUPPORTED LANG | ⚠️ PARTIAL | Gate at `planning_engine.py:1730` but same `matched_paths` bypass | Same coverage gate fix as Route 1 |
| PARTIAL GRAPH | ⚠️ PARTIAL | Same as Route 1 | Same as Route 1 |
| POISONED MEMORY | ❌ UNPROTECTED | Same as Route 1 | Same as Route 1 |
| EXPORT REPLAY | ❌ UNPROTECTED | Same as Route 1 | Same as Route 1 |

**Overall: 0 protected, 2 partial, 7 unprotected — WORSE THAN ROUTE 1**

---

### Route 3: What Breaks / Impact (`change_impact_simulation`)

| Failure | Status | Evidence | Required fix |
|---------|--------|---------|-------------|
| STALE PATH | ⚠️ PARTIAL | `current_summary()` called but no explicit path guard; relies on summary being empty | Add explicit `_scan_matches_current_path()` guard |
| GIT CHANGE | ❌ UNPROTECTED | Same as Route 1 | Same as Route 1 |
| FILE CHANGE | ❌ UNPROTECTED | Same as Route 1 | Same as Route 1 |
| MEM MISMATCH | ❌ UNPROTECTED | Same as Route 1 | Same as Route 1 |
| CACHE RESTORE | ❌ UNPROTECTED | Same as Route 1 | Same as Route 1 |
| UNSUPPORTED LANG | ✅ PROTECTED | Returns `ok=false, target_not_resolved` on empty graph | No change needed; this is the reference behavior |
| PARTIAL GRAPH | ⚠️ PARTIAL | `confidence_explanation` present; not in `TrustEnvelope` | Attach `TrustEnvelope` to impact result |
| POISONED MEMORY | ❌ UNPROTECTED | Same as Route 1 | Same as Route 1 |
| EXPORT REPLAY | ❌ UNPROTECTED | Same as Route 1 | Same as Route 1 |

**Overall: 1 protected, 3 partial, 5 unprotected**

---

### Route 4: Repository Context / Session Export (`session_export_packet`)

| Failure | Status | Evidence | Required fix |
|---------|--------|---------|-------------|
| STALE PATH | ✅ PROTECTED | Returns `ok=false` when no scan; `_invalidate_repository_state` clears memory on path change | None needed |
| GIT CHANGE | ❌ UNPROTECTED | No git HEAD check | Store and re-check git HEAD |
| FILE CHANGE | ❌ UNPROTECTED | Memory is built from scan state; scan is cached; content not verified | Content-backed invalidation (HR-03) |
| MEM MISMATCH | ❌ UNPROTECTED | **Core failure**: `_STATE["session_export"]` returned as-is; no integrity check | Validate memory against current scan before returning |
| CACHE RESTORE | ❌ UNPROTECTED | On cache hit, session rebuilt from cached scan — which may be stale | Include `graph_signature` in cache entry; verify |
| UNSUPPORTED LANG | 🔲 N/A | Session export doesn't rank files | N/A |
| PARTIAL GRAPH | ⚠️ PARTIAL | `graph_health` included in MEMORY v1 text | Should set `confidence_cap` in `TrustEnvelope` |
| POISONED MEMORY | ❌ UNPROTECTED | **`_STATE["session_export"]` from poisoned on-disk memory is returned verbatim** | Validate memory integrity before using it as session_export (HR-07) |
| EXPORT REPLAY | 🔲 N/A | This IS the session export; it is the source of the replay problem | N/A (but this route generates the stale state that other routes replay) |

**Overall: 1 protected, 1 partial, 5 unprotected, 2 N/A**

---

### Route 5: Copy for Claude / Cursor / Codex (UI copy path)

| Failure | Status | Evidence | Required fix |
|---------|--------|---------|-------------|
| STALE PATH | ❌ UNPROTECTED | `zfHasResult(kind)` checks only `STATE.buildResult.ok`; no path/scan match | UI must verify `STATE.buildResult.scan_id == STATE.sessionExport.scan_id` |
| GIT CHANGE | ❌ UNPROTECTED | No git awareness in UI copy path | N/A until git HEAD is tracked server-side |
| FILE CHANGE | ❌ UNPROTECTED | `STATE.sessionExport` never refreshed after user edits files | `finishScanSession` must clear `sessionExport`, `buildResult`, etc. |
| MEM MISMATCH | ❌ UNPROTECTED | `zfSessionPrefix()` prepends whatever `STATE.sessionExport.text` is | Verify scan_ids match before prepending |
| CACHE RESTORE | ❌ UNPROTECTED | `STATE.sessionExport` may reflect an old scan | Server-side `scan_id` on all result objects; UI verifies |
| UNSUPPORTED LANG | ⚠️ PARTIAL | If server returned `ok=false`, `zfHasResult` returns false → copy blocked | Correct behavior, but depends on server-side refusal working first |
| PARTIAL GRAPH | ❌ UNPROTECTED | No warning injected into copy text | Include `confidence_cap` warning in the copied text |
| POISONED MEMORY | ❌ UNPROTECTED | `zfSessionPrefix()` will prepend poisoned memory text to every copy | Version check, or server-side memory validation (HR-07) |
| EXPORT REPLAY | ❌ UNPROTECTED | `STATE.sessionExport` fetched once; used for 20+ questions without check | Clear on rescan; verify `scan_id` match before each copy |

**Overall: 0 protected, 1 partial, 8 unprotected — LOWEST TRUST SURFACE IN THE SYSTEM**

---

### Route 6: Export Bundle (`export_support_bundle`)

| Failure | Status | Evidence | Required fix |
|---------|--------|---------|-------------|
| STALE PATH | ✅ PROTECTED | Bundle is diagnostic; no intelligence exported | N/A |
| GIT CHANGE | ✅ PROTECTED | N/A — diagnostic only | N/A |
| FILE CHANGE | ✅ PROTECTED | N/A — diagnostic only | N/A |
| MEM MISMATCH | ⚠️ PARTIAL | Memory persistence failures not in bundle | Add `memory_persistence_ok` and `graph_signature` to bundle diagnostics |
| CACHE RESTORE | ✅ PROTECTED | N/A — diagnostic only | N/A |
| UNSUPPORTED LANG | 🔲 N/A | N/A | N/A |
| PARTIAL GRAPH | ✅ PROTECTED | Scan health included in bundle | None needed |
| POISONED MEMORY | ❌ UNPROTECTED | Bundle may include poisoned memory fields if diagnostics read from `_STATE` | Validate memory before including in bundle, or mark `memory_trusted: false` |
| EXPORT REPLAY | 🔲 N/A | N/A | N/A |

**Overall: 5 protected, 1 partial, 1 unprotected, 2 N/A**

---

### Route 7: Copilot / Ask (`copilot_ask`)

| Failure | Status | Evidence | Required fix |
|---------|--------|---------|-------------|
| STALE PATH | ❌ UNPROTECTED | No `_scan_matches_current_path()` guard | Add guard (same as plan_change) |
| GIT CHANGE | ❌ UNPROTECTED | Same as Route 1 | Same as Route 1 |
| FILE CHANGE | ❌ UNPROTECTED | Same as Route 1 | Same as Route 1 |
| MEM MISMATCH | ❌ UNPROTECTED | Copilot answers include graph paths from potentially stale state | Same as Route 1 |
| CACHE RESTORE | ❌ UNPROTECTED | Same as Route 1 | Same as Route 1 |
| UNSUPPORTED LANG | ⚠️ PARTIAL | Copilot returns reduced confidence on some unsupported queries | Enforce `TrustEnvelope.can_export = false` on unsupported |
| PARTIAL GRAPH | ⚠️ PARTIAL | Some modes note partial coverage | Standardize via `TrustEnvelope` |
| POISONED MEMORY | ❌ UNPROTECTED | Copilot outputs include architectural assertions from potentially poisoned memory | Validate memory before use |
| EXPORT REPLAY | 🔲 N/A | Copilot doesn't use sessionExport directly | N/A |

**Overall: 0 protected, 2 partial, 6 unprotected, 1 N/A**

---

## Aggregate Risk Summary

| Route | Protected | Partial | Unprotected | Risk Level |
|-------|:---------:|:-------:|:-----------:|:---------:|
| Change Plan | 1 | 2 | 6 | 🔴 HIGH |
| Investigation | 0 | 2 | 7 | 🔴 CRITICAL |
| What Breaks / Impact | 1 | 3 | 5 | 🔴 HIGH |
| Session Export | 1 | 1 | 5 | 🔴 HIGH |
| Copy for Claude/Cursor/Codex | 0 | 1 | 8 | 🔴 CRITICAL |
| Export Bundle | 5 | 1 | 1 | 🟡 LOW |
| Copilot / Ask | 0 | 2 | 6 | 🔴 HIGH |

**The copy path (Route 5) is the most critical surface.** It is where stale, poisoned, or wrong-repo context actually enters the user's LLM context. Every unprotected failure in Routes 1–4 ultimately flows through Route 5 to the AI.

---

## Priority Fix Table

Ordered by: (routes affected) × (severity) × (current protection).

| Fix | Routes protected | Hard/Soft | Estimated LOC |
|-----|-----------------|-----------|--------------|
| HR-01: Path guard on `investigate_symptom` | 2, 7 | Hard | ~5 |
| HR-07: Memory integrity validation on `load()` | 4, 5, all | Hard | ~40 |
| HR-06: Coverage gate via `module_count` not `matched_paths` | 1, 2 | Hard | ~15 |
| UI: `sessionExport` version check before `zfSessionPrefix()` | 5 | Hard | ~20 JS |
| `scan_id` stored in `_STATE["scan"]` at completion | All | Required | ~10 |
| `graph_signature` computed and stored in scan + cache | All | Required | ~20 |
| `TrustEnvelope` attached to all export blocks | All | Architecture | ~100 |
| `GraphFileManifest` content hash for indexed files | 1, 2, 3, 7 | Hard | ~80 |
| Git HEAD recording at scan time | All | Hard (future) | ~20 |
| SW-07: `signature_is_sampled` flag on large repos | All | Soft | ~5 |

---

## The Single Most Dangerous Gap

**Route 5 (Copy path) has zero hard protections.**

When a user clicks "Copy for Claude," the following can happen without any check or warning:

1. The session export prepended to their clipboard is from repo A
2. Their Change Plan was generated against repo B (after selecting without rescan)
3. Their Claude conversation now has contradictory architecture context from two different codebases
4. Claude answers with high confidence, combining facts from both

The user has no signal that anything went wrong. Atlas said `ok: true`. The copy button worked. The clipboard contains text that looks correct. Claude responds as if it understands the codebase.

This is the trust failure state that the Trust Integrity Architecture is designed to prevent.
