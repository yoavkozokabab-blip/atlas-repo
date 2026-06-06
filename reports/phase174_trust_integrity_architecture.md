# Phase 174 — Trust Integrity Architecture

**Role:** Principal Engineer / Trust Architect  
**Date:** 2026-06-06  
**Status:** Design only. No production code. No UI changes. No new features.

**Source material:**
- Phase 172A: Repository Memory Attack Surface (11 failure classes, 5 P0)  
- Phase 173C Red Team: 7 confirmed failures, confirmed NO-GO  
- Phase 173C Ship Blockers: SB-01 through SB-06  
- Phase 173A Audit: P0-04 scan cache, P0-02 thread safety, P1-04 missing coverage gate

**Core principle:**  
> Atlas must refuse before exporting stale, wrong-repo, poisoned, or unsupported context.  
> An honest refusal is always better than a confident wrong answer.

---

## 1. Output Route Map

Every Atlas output path is mapped below. For each route:  
- what state it reads  
- which identity fields it currently uses  
- what freshness check exists  
- what is missing

---

### Route 1: Change Plan — `POST /api/planning/change`

**Entry point:** `api.plan_change(request)`  
**State consumed:** `_STATE["scan"]`, `_STATE["graph"]`, `_STATE["index"]`, `_STATE["risks"]`, `_STATE["evidence_store"]`, `_STATE["path"]`  
**Current scan check:** `_scan_matches_current_path()` — path-only comparison  
**Current memory used:** `_repo_memory.get_memory_ref(_STATE)` → injected into `memory_ref` of delta export  
**Current cache used:** Graph and index from `scan_cache[signature]` on cache hit  
**Current graph used:** `_planning_context()` → `repository_context_from_state(_STATE)` → full graph and index  
**Freshness check:** Path match only. No content hash, no git HEAD, no scan_id propagation.  
**Unsupported language gate:** Exists in planning engine — but only fires when `graph_health == "unsupported_language_limited"` AND zero paths matched. Falls through to `ok=true` when one incidental Python file exists.  
**Staleness detection:** None beyond path match.  
**Refusal triggered by:** `not scan` or `not _scan_matches_current_path()`.  
**Missing:**
- No `scan_id` on the response
- No `graph_signature` on the response
- No `freshness_status` field
- No `can_export` field
- No content-backed freshness
- Unsupported language gate has bypass when any module matches

---

### Route 2: Investigation — `POST /api/planning/investigate`

**Entry point:** `api.investigate_symptom(symptom)`  
**State consumed:** Same as Route 1 via `_planning_context()`  
**Current scan check:** `_planning_context()` calls `current_summary()` if scan exists — but `investigate_symptom` itself has **no `_scan_matches_current_path()` guard** (unlike `plan_change`).  
**Critical gap:** A user can call investigate after `select_repository(new_path)` without rescan and get answers derived from the previous repo's graph.  
**Refusal triggered by:** Planning engine returns `ok=false` if planning context has no graph — but only if `_STATE["scan"]` is falsy. If path changed but scan wasn't cleared (timing issue), no guard fires.  
**Missing:**
- Path-match guard (same as plan_change)
- All fields missing from plan_change route above

---

### Route 3: What Breaks / Impact — `POST /api/planning/impact`

**Entry point:** `api.change_impact_simulation(target)`  
**State consumed:** `_STATE["graph"]`, `_STATE["scan"]`, `_STATE["index"]`, `_STATE["evidence_store"]`, `_STATE["risks"]`  
**Current scan check:** `current_summary()` called if scan exists — no explicit path guard  
**Staleness detection:** Impact engine returns `ok=false` / `target_not_resolved` when graph is empty or target cannot be resolved. This is the most honest workflow.  
**Missing:** Same as above. No content-backed freshness. No `can_export` field.

---

### Route 4: Repository Context (Session Export) — `GET /api/repositories/current/session-export`

**Entry point:** `api.session_export_packet()`  
**State consumed:** `_STATE["session_export"]`, `_STATE["repository_memory"]`, `_STATE["scan"]`  
**Current check:** Returns `ok=false` if no scan. Falls back to `session_context()` if memory not built.  
**Memory validation:** None. If `_STATE["session_export"]` was poisoned (RT-04), it is returned as-is.  
**Missing:**
- No integrity check on the memory object before returning it
- No `freshness_status`
- No repo_id/scan_id on the envelope

---

### Route 5: Copy for Claude / Cursor / Codex — UI copy path

**Entry point:** `copyForAi(tool, kind)` in `atlas_zero_friction.js`  
**State consumed:** `STATE.sessionExport`, `STATE.buildResult` / `STATE.investigateResult` / `STATE.impactResult`  
**Current check:** `zfHasResult(kind)` — checks `STATE.buildResult.ok` only. No freshness, no version, no scan_id.  
**`zfSessionPrefix()`:** Prepends `STATE.sessionExport.text` to every copy. If sessionExport was fetched 20 minutes ago during a different scan, it is still prepended without any check.  
**Missing:**
- No version verification between `sessionExport.scan_id` and `buildResult.scan_id`
- No staleness detection in copy path
- `STATE.sessionExport` never invalidated when scan completes a rescan
- If user edits files and does not rescan, old sessionExport is copied forever

---

### Route 6: Workflow Export Blocks — `export`, `export_full`, `export_minimal`, `export_memory`

**Entry point:** `atlas_export.attach_workflow_exports(result, workflow, ...)`  
**State consumed:** Plan or result dict, memory_ref from `_repo_memory.get_memory_ref(_STATE)`  
**Current check:** None beyond what the workflow function already validated  
**What is attached:** `export.text`, `export_full.text`, `export_minimal.text`, `export_memory.text` (delta)  
**Missing:**
- No `can_export` field on export block
- No `freshness_status` on export block
- No `repo_id`, `scan_id`, `graph_signature` on export block
- If delta text carries poisoned memory_ref, no validation before attachment

---

### Route 7: Export Bundle — `POST /api/system/support-bundle`

**Entry point:** `api.export_support_bundle()` → `install_support.export_support_bundle()`  
**State consumed:** Diagnostics JSON, launcher.log, analytics.jsonl, scan metadata  
**Current check:** None required — this is a diagnostic bundle, not an intelligence export  
**Trust risk:** Low for source content (prior probe clean). Path/log privacy boundary remains.  
**Missing:** Bundle does not include memory persistence status, graph signature, or freshness status in the diagnostics JSON.

---

### Route 8: Copilot / Ask — `POST /api/copilot/ask`

**Entry point:** `api.copilot_ask(question, target, packet)`  
**State consumed:** `_STATE["scan"]`, graph, index, risks via `classify_copilot_question()` and sub-modes  
**Current check:** Returns `ok=false` if no scan. No path-match guard.  
**Trust risk:** Copilot answers include file paths and architectural assertions. Stale graph produces wrong copilot answers.  
**Missing:** Same freshness and identity fields as workflow routes.

---

## 2. Trust Integrity Contract

Every Atlas output that exports repository intelligence to a user or to an LLM **must include the following envelope**. This is the contract — outputs that cannot populate this envelope should refuse.

```
TrustEnvelope {
    // Identity
    repo_path:          str        # canonical absolute path
    repo_id:            str        # sha256[:16] of canonical path (stable across renames)
    scan_id:            str        # sha256[:8] generated at scan completion time
    scan_signature:     str        # the _scan_signature hex (or "sampled_N" suffix if capped)
    graph_signature:    str        # sha256[:8] of (sorted module ids + sorted edge tuples)
    memory_version:     str        # "ATLAS_REPOSITORY_MEMORY v1" or "none"
    memory_ref:         str        # scan_id of the memory object, or "" if no memory
    
    // Timing
    scanned_at:         str        # ISO 8601 UTC of scan completion
    generated_at:       str        # ISO 8601 UTC of this export generation
    
    // Freshness
    freshness_status:   enum       # see Section 3
    signature_is_sampled: bool     # True when _scan_signature capped at 2500 files
    
    // Trust verdict
    can_export:         bool       # False triggers refusal
    refusal_reason:     str | null # populated when can_export=False
    warnings:           list[str]  # non-blocking trust degradations
    
    // Confidence
    confidence_cap:     str        # "none" | "partial_scan" | "unsupported_language" | "stale"
    confidence_cap_reason: str | null
}
```

### Rules for `can_export`

`can_export = False` when ANY hard refusal rule fires (Section 4).  
`can_export = True` with non-empty `warnings` when only soft warning rules fire (Section 5).

### Rules for `confidence_cap`

| Condition | cap value | reason |
|-----------|-----------|--------|
| Graph health = partial | `"partial_scan"` | "Dependency graph is incomplete — some import paths missing" |
| Graph health = unsupported_language_limited | `"unsupported_language"` | "Primary language outside Atlas strong coverage" |
| `signature_is_sampled = True` | `"partial_scan"` | "Scan signature sampled first 2500 files only — large repo changes may not invalidate cache" |
| Memory older than threshold | `"stale"` | "Repository memory may not reflect recent changes" |
| `freshness_status` ≠ `fresh` | One of above | Depends on specific staleness type |

---

## 3. Freshness States

```
FRESH                    Scan matches current path; signature is complete; 
                         memory matches current scan_id; graph is not degraded.

STALE_FILES_CHANGED      File mtime or size changed since scan, but signature 
                         was content-free (mtime/size only) — possible false positive.
                         
STALE_CONTENT_CHANGED    File content changed with same size and mtime (content hash mismatch).
                         This is the RT-01 failure class — Atlas's current default cannot detect this.

STALE_GIT_HEAD_CHANGED   Git HEAD hash differs from HEAD at scan time. Requires git-aware scanning.

STALE_MEMORY_MISMATCH    On-disk memory repo_id or graph_fingerprint does not match current scan.
                         Covers RT-04 (poisoning) and B3 (cache restore drift).

STALE_REPO_SWITCHED      _STATE["path"] changed since last scan without rescan.
                         Current code mostly handles this, but investigation route has a gap.

STALE_SIGNATURE_SAMPLED  Signature computed over <100% of files. Any change outside the 
                         sampled set is undetectable without a full rescan.
                         Applies to any repo with >2500 files.

UNSUPPORTED_LANGUAGE     Graph module count < threshold relative to file count.
                         Primary language is outside Python/TypeScript strong coverage.

PARTIAL_SCAN             Graph health is "partial" or "degraded" — some edges missing.

UNKNOWN                  Cannot determine freshness. No scan exists, or identity fields missing.
```

### State Transitions

```
[No scan] → UNKNOWN

[Scan complete, full signature, clean memory] → FRESH

[Scan complete] + [>2500 files] → STALE_SIGNATURE_SAMPLED (immediately)

[FRESH] + [path changes without rescan] → STALE_REPO_SWITCHED

[FRESH] + [mtime/size changes detected in next signature] → STALE_FILES_CHANGED

[FRESH] + [content edited, size/mtime preserved] → FRESH (undetectable — the RT-01 gap)
  → This is why content-backed invalidation must be designed

[FRESH] + [git checkout (same path)] → STALE_GIT_HEAD_CHANGED (requires git awareness)

[Memory load] + [memory.repo_id ≠ current repo_id] → STALE_MEMORY_MISMATCH

[Memory load] + [memory.graph_fingerprint ≠ current graph_fingerprint] → STALE_MEMORY_MISMATCH

[Scan] + [module_count < LANG_LIMIT_MODULES and file_count > LANG_LIMIT_FILES] → UNSUPPORTED_LANGUAGE
```

---

## 4. Hard Refusal Rules

A hard refusal sets `can_export = False` and blocks the workflow response from reaching the user as a usable plan or export. The response must include `refusal_reason` and `code`. It must not include ranked file paths, impact lists, or implementation orders.

---

### HR-01: Repo path changed without rescan

**Trigger:** `os.path.abspath(_STATE["path"]) ≠ os.path.abspath(_STATE["scan"]["repo_path"])`  
**Applies to:** All workflow routes (build, investigate, impact, copilot, session export, context export)  
**Current status:** Guarded for `plan_change`. **Missing for `investigate_symptom`, `copilot_ask`, `context_export`.**  
**Refusal code:** `stale_repo_switched`  
**Response:** `{"ok": false, "error": "Repository path changed since last scan. Rescan to continue.", "code": "stale_repo_switched", "can_export": false}`

---

### HR-02: Git HEAD changed after scan

**Trigger:** `git rev-parse HEAD` at export time ≠ `scan_metadata["git_head"]` at scan time  
**Applies to:** All workflow routes  
**Current status:** Not implemented. No git HEAD is recorded at scan time.  
**Refusal code:** `stale_git_head`  
**When to enforce:** Only when git is available and HEAD is deterministic (not bare repos, not detached HEAD on CI). Must gracefully degrade to warning-only when git is unavailable.  
**Design note:** This rule requires adding `git_head` to the scan metadata at scan time. This is a new field, not a refusal that can be added today.

---

### HR-03: Indexed file hash changed (content invalidation)

**Trigger:** Any file that contributed a graph node has a content hash different from the hash recorded at scan time  
**Applies to:** Change Plan, Impact, Investigation, Copilot  
**Current status:** Not implemented. `_scan_signature` uses size+mtime only. Content hash is not tracked.  
**Refusal code:** `stale_content_changed`  
**Design note:** This requires storing a per-file content fingerprint alongside the graph during scan. The fingerprint set does not need to cover all files — only graph-contributing files (files with module nodes). A SHA-256 truncated to 8 bytes per file, keyed by canonical path, is sufficient.

---

### HR-04: Memory ref does not match active memory

**Trigger:** `export.memory_ref ≠ _STATE["repository_memory"]["scan_id"]`  
**Applies to:** Delta exports (MEMORY_EXPORT mode), session export copy path  
**Current status:** Not implemented. Memory ref is injected but never validated at copy time.  
**Refusal code:** `memory_version_mismatch`  
**Consequence:** Block the copy action in the UI. Show: "Repository memory is out of date. Copy the updated session context first."

---

### HR-05: Graph is unsupported and workflow target cannot be exactly resolved

**Trigger:** `graph_health == "unsupported_language_limited"` AND (`matched_paths == []` OR `module_count <= 2`)  
**Applies to:** Change Plan, Investigation  
**Current status:** Partially implemented for Change Plan. **Investigation has a bypass when any incidental module exists.** The RT-05 failure class exploits this bypass.  
**Refusal code:** `unsupported_language`  
**Required:** The coverage gate must use `module_count` and `graph_health` directly, not rely on `matched_paths` as the gate signal. A repo with 1000 Go files and 1 Python boilerplate file must be refused, regardless of whether the 1 Python file matches keyword patterns.

---

### HR-06: Scan coverage too weak for the requested workflow

**Trigger:** `module_count < MIN_MODULES_FOR_WORKFLOW[workflow]` where:
- Change Plan: `MIN_MODULES_FOR_WORKFLOW["build"] = 3`
- Investigation: `MIN_MODULES_FOR_WORKFLOW["investigate"] = 3`
- Impact: impact engine already refuses on target resolution failure
- Copilot: `MIN_MODULES_FOR_WORKFLOW["copilot"] = 1`

**Applies to:** Change Plan, Investigation  
**Current status:** Not implemented as an explicit gate. Planning engine may return low-confidence results instead of refusing.  
**Refusal code:** `insufficient_coverage`

---

### HR-07: Memory loaded from disk does not match current repo signature

**Trigger:** `loaded_memory["repo_id"] ≠ repo_id(current_path)` OR `loaded_memory["graph_fingerprint"] ≠ current_graph_fingerprint`  
**Applies to:** Session export, memory delta generation  
**Current status:** Not implemented. `repository_memory.load()` checks only version string.  
**Refusal code:** `memory_integrity_failure`  
**Consequence:** Discard loaded memory. Start a fresh session. Include in session export: `memory_reset: true`, `memory_reset_reason: "identity mismatch"`.  
**Note:** This is the fix for RT-04 (memory poisoning).

---

### HR-08: Signature is sampled AND workflow requires full coverage

**Trigger:** `signature_is_sampled = True` AND workflow is Change Plan or Investigation for a large repo  
**Applies to:** Change Plan, Investigation  
**Current status:** Not implemented. Sampled signature silently backs full-confidence exports.  
**Behavior:** Do not hard-refuse. Instead, force `confidence_cap = "partial_scan"` and add a warning: "This repository has more than 2,500 files. Some recent changes may not be reflected in this plan."

---

## 5. Soft Warning Rules

A soft warning does NOT set `can_export = False`. It adds to `warnings[]` and may reduce `confidence_cap`. The output is still returned to the user. The user is informed of the limitation. The AI export text includes the warning.

---

### SW-01: Partial graph (some edges missing)

**Trigger:** `graph_health["label"] in ("partial", "watch")`  
**Warning text:** "Dependency graph is partially complete. Some import paths may be missing."  
**Confidence cap:** `partial_scan`

---

### SW-02: Unresolved import ratio high

**Trigger:** `unresolved_ratio > 0.5` (more than half of imports unresolved)  
**Warning text:** "More than 50% of imports are unresolved. Impact analysis may miss transitive paths."  
**Confidence cap:** `partial_scan`

---

### SW-03: File count changed slightly since scan

**Trigger:** Pre-scan estimate shows file count changed by more than 5% since last scan  
**Warning text:** "File count has changed since the last scan. Consider rescanning for accuracy."  
**Confidence cap:** none (too uncertain to cap)

---

### SW-04: Memory older than threshold

**Trigger:** `memory["scanned_at"]` is more than 24 hours ago  
**Warning text:** "Repository memory is more than 24 hours old. Delta context may not reflect recent changes."  
**Confidence cap:** `stale`

---

### SW-05: Memory persistence failed in previous session

**Trigger:** `_STATE["_memory_persistence_failed"] = True` set by `update_after_scan()` when `persist()` returns `""`  
**Warning text:** "Repository memory could not be saved to disk. Session memory will reset on next restart."  
**Confidence cap:** none  
**Existing gap:** `persist()` currently returns `""` silently. `update_after_scan()` does not record this. This field must be added.

---

### SW-06: Branch or working tree dirty

**Trigger:** `git status --short` returns non-empty output at scan time (requires git awareness)  
**Warning text:** "Working tree has uncommitted changes. Some graph paths may differ from the committed version."  
**Confidence cap:** none (informational only)

---

### SW-07: Scan signature sampled (informational)

**Trigger:** Scan covered more than 2500 files  
**Warning text:** "Large repository: scan signature covers the first 2,500 files. Changes to files outside this sample are not detected automatically."  
**Confidence cap:** `partial_scan`

---

## 6. Trust Integrity Contract: Computation

The Trust Integrity Contract is computed **once per workflow invocation**, after the workflow result is produced but **before the export is attached**. It is computed by a new function:

```
compute_trust_envelope(
    state,        # _STATE snapshot
    workflow,     # "build" | "investigate" | "impact" | "copilot" | "session" | "context"
    result,       # raw workflow result dict
) → TrustEnvelope
```

This function:
1. Reads identity fields from `_STATE["scan"]`, `_STATE["path"]`, `_STATE["repository_memory"]`
2. Computes `graph_signature` from the current in-memory graph
3. Checks all hard refusal rules (Section 4)
4. Checks all soft warning rules (Section 5)
5. Determines `freshness_status`
6. Sets `can_export` and `refusal_reason`
7. Returns the envelope

The envelope is attached to the workflow result dict as `result["trust"]`. It is also included in every export block: `result["export"]["trust"]`, `result["export_minimal"]["trust"]`, etc.

**The UI reads `result["trust"]["can_export"]` before showing the copy button.** If `can_export = False`, the copy button is disabled and `refusal_reason` is shown in its place.

---

## 7. Graph Signature Design

The `graph_signature` is a cheap fingerprint of the dependency graph that changes when any module or edge changes.

```python
def compute_graph_signature(graph: Dict[str, Any]) -> str:
    """Stable 8-char fingerprint of graph topology."""
    nodes = sorted(
        n.get("id", "")
        for n in (graph.get("nodes") or [])
        if n.get("type") == "module"
    )
    edges = sorted(
        (e.get("from", ""), e.get("to", ""))
        for e in (graph.get("edges") or [])
        if e.get("type") == "imports" and e.get("resolved")
    )
    h = hashlib.sha256()
    for item in nodes + [f"{a}→{b}" for a, b in edges]:
        h.update(item.encode("utf-8", errors="ignore"))
    return h.hexdigest()[:8]
```

This signature is computed once at scan completion and stored in `_STATE["scan"]["graph_signature"]`. It is also stored in the scan_cache entry and in the repository memory object.

When memory is loaded from disk, `memory["graph_fingerprint"]` must match `current_scan["graph_signature"]`. Mismatch → `STALE_MEMORY_MISMATCH` → HR-07 fires → memory reset.

---

## 8. scan_id Design

The `scan_id` is already generated by `repository_memory.py` (`_scan_id_from_state`). It must be:
1. Stored in `_STATE["scan"]["scan_id"]` at scan completion (both cache-hit and cache-miss paths)
2. Included in every workflow result: `result["scan_id"] = _STATE["scan"]["scan_id"]`
3. Included in every export block: `export["scan_id"]`
4. Matched by the UI copy path: `STATE.sessionExport.scan_id == STATE.buildResult.scan_id`

When scan_ids don't match (e.g., user rescanned mid-session), the UI must warn before copying.

---

## 9. Content-Backed Invalidation Design (addressing RT-01 / SB-01)

The `_scan_signature` function currently hashes file size and mtime only. This fails when:
- A developer edits a file and preserves the same byte count with a touch-preserving editor
- A build system regenerates files with identical mtimes
- A git checkout restores files to the previous mtime

**Required design:**

```
GraphFileManifest {
    signature_v:    int        # manifest version (1 = content-backed)
    file_count:     int        # total files hashed
    sampled:        bool       # True if file_count > 2500
    sample_cap:     int        # the cap applied (2500)
    entries: {
        canonical_path: content_hash_8   # sha256[:8] of file content
    }
}
```

This manifest is computed during scan for all files that produced graph nodes. It is stored in the scan_cache entry alongside the graph. On rescan, the manifest is compared file-by-file for graph-contributing files. If any entry differs, the cache is invalidated.

For repositories with >2500 files:
- The full tree file-count and mtime-xor are computed as a cheap "dirty check"
- If the dirty check passes, a targeted content check on recently-changed files (mtime > last scan time) is performed
- The signature is marked `sampled = True` and `freshness_status = STALE_SIGNATURE_SAMPLED`

This design addresses RT-01, RT-02, SB-01, and SB-05 without requiring full file hashing on every rescan.

---

## 10. Memory Integrity Design (addressing RT-04 / SB-02)

The `repository_memory.load()` function currently validates only the `version` field. Required validation:

```python
def _validate_memory(
    memory: Dict[str, Any],
    expected_repo_id: str,
    current_graph_signature: str,
) -> Tuple[bool, str]:
    """Returns (valid, rejection_reason)."""
    
    # 1. Version
    if memory.get("version") != MEMORY_VERSION:
        return False, "version_mismatch"
    
    # 2. Repo identity
    if memory.get("repo_id") != expected_repo_id:
        return False, "repo_id_mismatch"
    
    # 3. Canonical path match (case-insensitive on Windows)
    stored_id = repo_id(memory.get("repo_path", ""))
    if stored_id != expected_repo_id:
        return False, "path_hash_mismatch"
    
    # 4. Graph fingerprint (topology must match current scan)
    stored_fp = memory.get("graph_fingerprint") or memory.get("hub_fingerprint")
    if stored_fp and current_graph_signature:
        if stored_fp != current_graph_signature:
            return False, "graph_fingerprint_mismatch"
    
    # 5. Schema bounds (reject implausible values)
    if memory.get("session_count", 0) > 10_000:
        return False, "implausible_session_count"
    if memory.get("modules", 0) < 0 or memory.get("edges", 0) < 0:
        return False, "negative_counts"
    if memory.get("scanned_at", ""):
        try:
            # Must be a valid ISO 8601 datetime in a plausible range
            ts = memory["scanned_at"]
            if ts < "2024-01-01" or ts > "2030-01-01":
                return False, "implausible_timestamp"
        except Exception:
            return False, "invalid_timestamp"
    
    return True, ""
```

When validation fails, `load()` returns `None` and the caller logs the rejection reason to diagnostics. The session starts fresh with `memory_reset = True` in the envelope.

---

## 11. Integration Points: Where Changes Land

| Component | Change required | Priority |
|-----------|-----------------|----------|
| `api.py:_scan_signature` | Add `signature_is_sampled` flag; store git HEAD if available | P0 |
| `api.py:scan_repository` | Compute and store `scan_id`, `graph_signature`, `GraphFileManifest` at scan time | P0 |
| `api.py:investigate_symptom` | Add `_scan_matches_current_path()` guard | P0 |
| `api.py:copilot_ask` | Add `_scan_matches_current_path()` guard | P1 |
| `api.py:context_export` | Add `_scan_matches_current_path()` guard | P1 |
| `repository_memory.py:load` | Add `_validate_memory()` gate | P0 |
| `repository_memory.py:update_after_scan` | Record persistence failure in state | P1 |
| `repository_memory.py:compute_graph_signature` | New function | P0 |
| `atlas_export.py:attach_workflow_exports` | Attach `trust` envelope to all export blocks | P0 |
| New: `trust_integrity.py` | `compute_trust_envelope()` function | P0 |
| `planning_engine.py` | Coverage gate must use `module_count` directly, not only matched paths | P0 |
| `jarvis_desktop/static/atlas_zero_friction.js` | Read `trust.can_export` before enabling copy button | P1 |
| `jarvis_desktop/static/app.js` | Invalidate `STATE.sessionExport` on rescan completion | P1 |

---

## 12. Non-Goals for this Design

The following are explicitly out of scope for Phase 174:

- Real-time file watching (would require OS-level file system events)
- Cryptographic signing of export bundles (useful but not required for trust basics)
- Multi-instance Atlas conflict resolution (single user, single process)
- Remote attestation (trust is local-only by Atlas's design)
- Backward compatibility with external tools that parse export text format (trust envelope is additive)
