# Phase 174 — Refusal Rules

**Date:** 2026-06-06  
**Design only. No code changes.**

This document is the executable specification for the trust integrity system. Every rule defined here maps to a concrete code change. Rules are ordered by implementation priority, not conceptual importance.

---

## Part A: Hard Refusal Rules

A hard refusal sets `can_export = False` in the `TrustEnvelope` and blocks the workflow from returning ranked file paths, implementation orders, or impact lists. The API still returns a response — it returns an honest failure with a code, a reason, and suggested recovery steps. It never returns HTTP 500 for a trust failure; it returns HTTP 200 with `ok: false`.

---

### HR-01 · Repository path changed without rescan

**Condition:**
```
os.path.abspath(_STATE["path"]) ≠ os.path.abspath(_STATE["scan"]["repo_path"])
```

**Applies to:** All workflow routes — `plan_change`, `investigate_symptom`, `change_impact_simulation`, `copilot_ask`, `context_export`, `session_export_packet`

**Current coverage:**
- `plan_change`: ✅ guarded by `_scan_matches_current_path()`
- `investigate_symptom`: ❌ MISSING
- `copilot_ask`: ❌ MISSING
- `context_export`: ❌ MISSING
- `session_export_packet`: ✅ returns `ok=false` when scan is None (covers most cases)

**Response shape:**
```json
{
  "ok": false,
  "error": "Repository path changed since last scan. Rescan to continue.",
  "code": "stale_repo_switched",
  "can_export": false,
  "recovery": ["Scan the new repository before generating a plan."]
}
```

**Implementation note:** The guard is `_scan_matches_current_path()`, which already exists. The fix is to call it in `investigate_symptom` and `copilot_ask` before calling the planning engine. Two lines of code per function.

**Test required:** Scan repo A → select repo B → call investigate_symptom → expect `code="stale_repo_switched"`.

---

### HR-02 · Git HEAD changed after scan (future gate)

**Condition:**
```
git_head_at_export ≠ _STATE["scan"]["git_head"]
```
where `_STATE["scan"]["git_head"]` is recorded at scan completion.

**Applies to:** `plan_change`, `investigate_symptom`, `change_impact_simulation`

**Current coverage:** ❌ Not implemented. No `git_head` is recorded at scan time.

**Pre-condition for this rule:** `git_head` must be added to the scan metadata:
```python
# During scan_repository(), after graph build:
try:
    import subprocess
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repo,
        capture_output=True,
        text=True,
        timeout=3,
    )
    git_head = result.stdout.strip() if result.returncode == 0 else None
except Exception:
    git_head = None
_STATE["scan"]["git_head"] = git_head
```

**At export time:**
```python
def _check_git_head(repo_path: str, scan_git_head: Optional[str]) -> Optional[str]:
    """Returns a warning string if HEAD changed, None if unchanged or unavailable."""
    if not scan_git_head:
        return None  # git not available at scan time; cannot check
    try:
        import subprocess
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=repo_path,
            capture_output=True,
            text=True,
            timeout=3,
        )
        current = result.stdout.strip() if result.returncode == 0 else None
    except Exception:
        return None
    if current and current != scan_git_head:
        return f"Git HEAD changed from {scan_git_head[:8]} to {current[:8]} after scan."
    return None
```

**Behavior:** Soft warning, not hard refusal, because git HEAD changes are intentional (developer commits). Hard refusal applies only when HEAD changes to a branch with different file content — which requires a file-level check (HR-03).

**Priority:** P2. Requires git-aware scanning infrastructure before this gate can fire.

---

### HR-03 · Indexed file content changed (content-backed invalidation)

**Condition:**
```
GraphFileManifest.content_hash[file_path] ≠ current_content_hash(file_path)
for any file in graph-contributing files
```

**Applies to:** `plan_change`, `investigate_symptom`, `change_impact_simulation`, `copilot_ask`

**Current coverage:** ❌ Not implemented. `_scan_signature` uses size+mtime only. This is the RT-01 / SB-01 failure class.

**Design:**

```python
# At scan completion, build the manifest:
@dataclass
class GraphFileManifest:
    version: int = 1  # manifest schema version
    file_count: int = 0
    sampled: bool = False
    sample_cap: int = 2500
    entries: Dict[str, str] = field(default_factory=dict)  # path → sha256[:8]
    
def build_graph_file_manifest(
    graph: Dict[str, Any],
    repo_root: str,
    max_files: int = 10_000,
) -> GraphFileManifest:
    """Hash content of every file that produced a graph node."""
    manifest = GraphFileManifest()
    node_paths = {
        n.get("path", "")
        for n in (graph.get("nodes") or [])
        if n.get("type") == "module" and n.get("path")
    }
    for rel_path in sorted(node_paths):
        abs_path = os.path.join(repo_root, rel_path)
        try:
            with open(abs_path, "rb") as f:
                content = f.read()
            h = hashlib.sha256(content).hexdigest()[:8]
            manifest.entries[rel_path] = h
            manifest.file_count += 1
        except OSError:
            continue
        if manifest.file_count >= max_files:
            manifest.sampled = True
            break
    return manifest

def verify_graph_file_manifest(
    manifest: GraphFileManifest,
    repo_root: str,
) -> Tuple[bool, List[str]]:
    """Returns (unchanged, list_of_changed_paths)."""
    changed = []
    for rel_path, expected_hash in manifest.entries.items():
        abs_path = os.path.join(repo_root, rel_path)
        try:
            with open(abs_path, "rb") as f:
                content = f.read()
            actual = hashlib.sha256(content).hexdigest()[:8]
        except OSError:
            changed.append(rel_path)  # file deleted = changed
            continue
        if actual != expected_hash:
            changed.append(rel_path)
    return (len(changed) == 0, changed)
```

**At export time (checking cache validity):**
```python
manifest = _STATE["scan"].get("graph_file_manifest")
if manifest:
    unchanged, changed_paths = verify_graph_file_manifest(manifest, repo_root)
    if not unchanged:
        trust_envelope.freshness_status = "stale_content_changed"
        trust_envelope.can_export = False
        trust_envelope.refusal_reason = (
            f"{len(changed_paths)} source file(s) changed since last scan "
            f"(e.g. {changed_paths[0]}). Rescan to update."
        )
```

**Priority:** P0. This is the single most impactful fix for developer trust — normal editing workflows currently produce stale exports.

**Test required:**
```python
# test_stale_graph_after_import_edit:
scan_repo(repo_with_main_importing_dep_b)
edit_main_py(repo, new_import="dep_c", preserve_size=True)  # same byte count
result = plan_change("add feature")
assert result["trust"]["can_export"] is False
assert result["trust"]["freshness_status"] == "stale_content_changed"
```

---

### HR-04 · Memory ref does not match active memory

**Condition:**
```
delta.memory_ref ≠ _STATE["scan"]["scan_id"]
```
or equivalently:
```
result.get("export_memory") is not None AND
_repo_memory.get_memory_ref(_STATE) ≠ _STATE["scan"]["scan_id"]
```

**Applies to:** MEMORY_EXPORT delta generation, UI copy path (Route 5)

**Current coverage:** ❌ Not implemented. `memory_ref` is injected into delta text but never validated.

**Implementation:**

Server-side — in `atlas_export.attach_workflow_exports`:
```python
# Before attaching delta export:
current_scan_id = (state.get("scan") or {}).get("scan_id", "")
if memory_ref and memory_ref != current_scan_id:
    # Memory ref is stale — do not attach delta, fall back to minimal
    delta = ""
    warnings.append(f"Memory reference outdated (memory: {memory_ref[:8]}, scan: {current_scan_id[:8]}). "
                    "Copy the updated session context before using delta exports.")
```

UI-side — in `atlas_zero_friction.js:copyForAi`:
```javascript
function copyForAi(tool, kind) {
    const result = zfWorkflowResult(kind);
    const se = window.STATE && STATE.sessionExport;
    
    // Verify scan_ids match before allowing copy
    const resultScanId = result && result.scan_id;
    const sessionScanId = se && se.scan_id;
    if (resultScanId && sessionScanId && resultScanId !== sessionScanId) {
        toast("Session context is out of date. Reload the session context first.", "error");
        return;
    }
    // ... proceed with copy
}
```

**Priority:** P1 (server-side), P1 (UI-side).

---

### HR-05 · Graph is unsupported and workflow cannot resolve a target

**Condition:**
```
(graph_health == "unsupported_language_limited" OR module_count <= MIN_MODULES)
AND matched_paths == []
```

**Current bypass in planning engine:**
The existing gate fires only when `matched_paths == []`. If the repo has 1000 Go files and 1 Python helper file that matches a keyword (e.g., the helper is named `event_bus.py`), `matched_paths = ["event_bus.py"]` and the gate does NOT fire. The user gets a Build Plan around a Python boilerplate file in a Go repo.

**Required fix — coverage gate must use `module_count` directly:**
```python
# In planning_engine.py, before computing scored:
MIN_MODULES_BUILD = 3
MIN_MODULES_INVESTIGATE = 3

module_count = int(scan_data.get("module_count") or 0)
graph_health = _ghl(scan_data)
is_unsupported = graph_health == "unsupported_language_limited"
is_trivial_coverage = module_count < MIN_MODULES_BUILD

if is_unsupported or is_trivial_coverage:
    return _insufficient_evidence_response(
        goal,
        reason=(
            f"Graph coverage too weak for reliable results "
            f"(modules indexed: {module_count}, graph health: {graph_health}). "
            "Atlas works best on Python and TypeScript repositories."
        ),
        ...
    )
```

**This gate must fire regardless of whether any paths matched.**

**Priority:** P0. The RT-05 / SB-04 failure class is confirmed reproducible and directly destroys user trust.

---

### HR-06 · Scan coverage too weak for the workflow

**Condition:**
```
module_count < MIN_MODULES_FOR_WORKFLOW[workflow]
```

**Thresholds:**
```python
MIN_MODULES_FOR_WORKFLOW = {
    "build": 3,        # need at least 3 modules to produce a meaningful plan
    "investigate": 3,  # same
    "impact": 1,       # impact can work on any graph with at least 1 module
    "copilot": 1,      # copilot can answer with 1 module (architectural context minimal)
    "context": 1,      # context export works on any scanned repo
}
```

**Applies to:** `plan_change`, `investigate_symptom`

**Current coverage:** ❌ Not explicitly gated. Covered implicitly by the unsupported language gate only when `module_count` is near-zero AND `matched_paths == []`.

**Response:**
```json
{
  "ok": false,
  "error": "Repository graph has too few modules for a reliable plan (3 indexed, minimum 3 required).",
  "code": "insufficient_coverage",
  "can_export": false
}
```

---

### HR-07 · Memory from disk does not match current repo signature

**Condition:**
```
loaded_memory["repo_id"] ≠ repo_id(current_path)
OR loaded_memory["graph_fingerprint"] ≠ current_graph_signature
OR integrity check fails (memory_hash mismatch)
```

**Applies to:** `repository_memory.load()` — the first and only validation point

**Current coverage:** ❌ `load()` checks only `memory["version"] == MEMORY_VERSION`.

**Required implementation:**
```python
def load(repo_path: str, data_dir: str) -> Optional[Dict[str, Any]]:
    """Load previous memory. Rejects on identity or integrity mismatch."""
    if not repo_path:
        return None
    path = _memory_path(repo_path, data_dir)
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        return None
    
    valid, reason = _validate_memory(data, repo_path)
    if not valid:
        # Log the rejection reason for diagnostics without leaking paths
        _log_memory_rejection(reason, repo_id=repo_id(repo_path))
        return None
    return data


def _validate_memory(memory: Dict[str, Any], repo_path: str) -> Tuple[bool, str]:
    """Full integrity validation for loaded memory."""
    
    # Version check
    if memory.get("version") != MEMORY_VERSION:
        return False, "version_mismatch"
    
    # Repo identity: repo_id must match
    expected_rid = repo_id(repo_path)
    if memory.get("repo_id") != expected_rid:
        return False, "repo_id_mismatch"
    
    # Canonical path consistency
    stored_rid = repo_id(str(memory.get("repo_path") or ""))
    if stored_rid != expected_rid:
        return False, "path_hash_mismatch"
    
    # Integrity hash (Phase 174B tamper detection)
    declared_hash = memory.get("memory_hash")
    if declared_hash:
        expected_hash = compute_memory_hash(memory)
        if declared_hash != expected_hash:
            return False, "integrity_hash_mismatch"
    
    # Schema bounds — reject implausible values
    if int(memory.get("session_count") or 0) > 50_000:
        return False, "implausible_session_count"
    if int(memory.get("modules") or 0) < 0:
        return False, "negative_module_count"
    if int(memory.get("edges") or 0) < 0:
        return False, "negative_edge_count"
    
    # Timestamp plausibility
    ts = str(memory.get("scanned_at") or "")
    if ts and (ts < "2024-01-01" or ts > "2035-01-01"):
        return False, "implausible_timestamp"
    
    return True, ""
```

**When validation fails:**
- `load()` returns `None`
- `update_after_scan()` starts a fresh memory session
- The session export includes `memory_reset: true`, `memory_reset_reason: "identity_mismatch"`
- Diagnostics log the rejection type (not the path content)

**Priority:** P0. Fixes RT-04 / SB-02 (memory poisoning).

---

### HR-08 · Signature is sampled — large repo freshness guarantee

**Condition:**
```
scan["signature_is_sampled"] == True
```

**Behavior:** Not a hard refusal. A soft warning is appended to all workflow outputs:

```
"Large repository: scan signature covers the first 2,500 files. Changes to 
files outside this sample are not detected automatically. Rescan manually 
after major edits."
```

Additionally, `freshness_status` is set to `STALE_SIGNATURE_SAMPLED` and `confidence_cap = "partial_scan"`.

**Priority:** P1. The flag must be added to `_scan_signature` first.

---

## Part B: Soft Warning Rules

Soft warnings do not block export. They are included in `TrustEnvelope.warnings[]` and may be surfaced in the copy text as a caveat line.

---

### SW-01 · Partial dependency graph

**Trigger:** `graph_health["label"] in ("partial", "watch", "degraded")`  
**Warning:** "Dependency graph is partially complete. Some import paths may be missing. Plans and impact analysis may miss files."  
**Confidence cap:** `partial_scan`  
**Already in UI:** Yes, graph health badge exists. Missing: the warning must also appear in the exported text and in `TrustEnvelope`.

---

### SW-02 · High unresolved import ratio

**Trigger:** `scan["unresolved_ratio"] > 0.5`  
**Warning:** "More than 50% of imports are unresolved. Impact analysis may miss transitive paths."  
**Confidence cap:** `partial_scan`

---

### SW-03 · Memory persistence failed

**Trigger:** `_STATE.get("_memory_persistence_failed") == True`  
**Warning:** "Repository memory could not be saved to disk. Delta context will reset on next restart."  
**How to detect:** `update_after_scan()` must set `_STATE["_memory_persistence_failed"] = True` when `persist()` returns `""`.  
**Current gap:** `persist()` swallows `OSError` and `update_after_scan()` ignores the empty return.

---

### SW-04 · Memory is older than threshold

**Trigger:** `delta["previous_scan_at"]` is more than `MEMORY_STALENESS_HOURS = 24` hours ago  
**Warning:** "Repository memory is more than 24 hours old. Some delta context may not reflect recent changes."  
**Confidence cap:** `stale`

---

### SW-05 · Scan signature sampled (large repo)

**Trigger:** `scan.get("signature_is_sampled") == True`  
**Warning:** "Large repository: scan signature sampled first 2,500 files. Recent changes may not invalidate the cache automatically."

---

### SW-06 · Working tree dirty (future, requires git)

**Trigger:** Uncommitted changes detected in working tree at scan time  
**Warning:** "Working tree has uncommitted changes. Graph reflects the current file state, not the committed version."

---

## Part C: `TrustEnvelope` Attachment Specification

The Trust Integrity Contract envelope must be attached by a new `trust_integrity.py` module. The function signature:

```python
def compute_trust_envelope(
    state: Dict[str, Any],
    workflow: str,
    result: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Compute the TrustEnvelope for an Atlas workflow result.
    
    Called after the workflow produces its result, before exports are attached.
    Returns a dict that is stored as result["trust"] and included in all export blocks.
    
    Parameters:
        state    — _STATE snapshot at time of call
        workflow — "build" | "investigate" | "impact" | "copilot" | "session" | "context"
        result   — the raw workflow result dict (may be mutated to add warnings)
    """
```

**Fields computed:**

| Field | Source | Notes |
|-------|--------|-------|
| `repo_path` | `state["path"]` | Canonical abspath |
| `repo_id` | `repo_id(state["path"])` | sha256[:16] |
| `scan_id` | `state["scan"]["scan_id"]` | Must be stored at scan time |
| `scan_signature` | `state["scan"]["cache"]["signature"]` | Existing |
| `graph_signature` | `compute_graph_signature(state["graph"])` | New function |
| `memory_version` | `state["repository_memory"]["version"]` or "none" | |
| `memory_ref` | `_repo_memory.get_memory_ref(state)` | Existing |
| `scanned_at` | `state["scan"]["scanned_at"]` | Must be stored at scan time |
| `generated_at` | `time.strftime(...)` | Current time |
| `freshness_status` | Computed from all checks | See Section 3 |
| `signature_is_sampled` | `state["scan"]["signature_is_sampled"]` | Must be stored at scan time |
| `can_export` | All hard refusal rules | |
| `refusal_reason` | First firing hard rule | |
| `warnings` | All soft warning rules | |
| `confidence_cap` | Determined by graph health + freshness | |
| `confidence_cap_reason` | Human-readable explanation | |

---

## Part D: Implementation Sequence

Ordered from highest impact to lowest. Do not implement out of order — each step depends on the previous.

### Step 1: Store `scan_id` and `scanned_at` in `_STATE["scan"]`

**Where:** `api.py:scan_repository()` — both cache-hit and cache-miss paths  
**What:**
```python
_STATE["scan"]["scan_id"] = _repo_memory.get_memory_ref(_STATE) or _scan_id_from_scan(_STATE["scan"])
_STATE["scan"]["scanned_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
_STATE["scan"]["signature_is_sampled"] = (signature_sample_count >= 2500)
```
**Why first:** Every other trust check depends on having a stable `scan_id`.

---

### Step 2: Compute and store `graph_signature`

**Where:** `api.py:scan_repository()` — after graph is built  
**What:**
```python
_STATE["scan"]["graph_signature"] = compute_graph_signature(_STATE["graph"])
```
**Why:** `graph_signature` is required by HR-07 (memory validation) and for cache entry verification.

---

### Step 3: Add `_scan_matches_current_path()` to `investigate_symptom` and `copilot_ask`

**Where:** `api.py:investigate_symptom()` line ~2621, `api.py:copilot_ask()` line ~3798  
**What:** Add the same 4-line guard that `plan_change` already has.  
**Why:** HR-01. Two missing guards. Highest trust-per-line-of-code fix in the codebase.

---

### Step 4: Add memory integrity validation to `repository_memory.load()`

**Where:** `repository_memory.py:load()`  
**What:** `_validate_memory()` function with repo_id, path, integrity hash, and schema bounds checks.  
**Why:** HR-07. Fixes memory poisoning (RT-04 / SB-02).

---

### Step 5: Fix the unsupported-language coverage gate in `planning_engine.py`

**Where:** `planning_engine.py` — both `plan_change` and `investigate_symptom` planning paths  
**What:** Gate must use `module_count < MIN_MODULES_BUILD`, not only `matched_paths == []`.  
**Why:** HR-05. Fixes RT-05 / SB-04.

---

### Step 6: Build `GraphFileManifest` at scan time

**Where:** `api.py:scan_repository()` — after graph build, before cache storage  
**What:** `build_graph_file_manifest(graph, repo_root)` stored in `_STATE["scan"]["graph_file_manifest"]` and in the `scan_cache` entry.  
**Why:** HR-03. Addresses RT-01 / SB-01 — the confirmed stale-graph-after-content-edit failure.

---

### Step 7: Add `_memory_persistence_failed` tracking

**Where:** `repository_memory.py:update_after_scan()`  
**What:** When `persist()` returns `""`, set `state["_memory_persistence_failed"] = True`.  
**Why:** SW-03. Fixes RT-03 / SB-03 silent persistence failure.

---

### Step 8: Create `trust_integrity.py` with `compute_trust_envelope()`

**Where:** New file `jarvis_desktop/trust_integrity.py`  
**What:** All hard rules and soft rules assembled into one function.  
**Why:** Single enforcement point. All routes call this before attaching exports.

---

### Step 9: Attach `TrustEnvelope` to all export routes

**Where:** `atlas_export.py:attach_workflow_exports()`, `api.py:session_export_packet()`, `api.py:context_export()`  
**What:** `result["trust"] = compute_trust_envelope(state, workflow, result)`  
**Why:** Completes the contract.

---

### Step 10: UI reads `trust.can_export` before enabling copy button

**Where:** `atlas_zero_friction.js:copyForAi()`  
**What:** Check `result.trust.can_export` before proceeding. If false, show `trust.refusal_reason` instead.  
**Why:** The contract reaches the user. The copy button becomes the trust enforcement point.

---

## Part E: Tests Required for Each Rule

Every hard refusal rule must have an automated regression test that:
1. Produces the triggering condition
2. Calls the workflow
3. Asserts `ok=false`, `can_export=false`, and the specific `code`

| Rule | Test name | Trigger setup |
|------|-----------|---------------|
| HR-01 | `test_investigate_refuses_after_path_switch` | Scan A → select B → investigate |
| HR-01 | `test_copilot_refuses_after_path_switch` | Scan A → select B → copilot_ask |
| HR-03 | `test_plan_refuses_after_content_edit` | Scan → edit file (preserve size) → plan_change |
| HR-04 | `test_delta_export_blocked_on_memory_ref_mismatch` | Force memory_ref ≠ scan_id → attach_workflow_exports |
| HR-05 | `test_build_refuses_on_go_repo_with_python_helper` | Create Go repo + one Python boilerplate → plan_change |
| HR-05 | `test_investigate_refuses_on_trivial_graph` | Scan repo with 1 module → investigate |
| HR-07 | `test_poisoned_memory_rejected_on_load` | Write tampered memory JSON → scan → verify memory reset |
| HR-07 | `test_wrong_repo_id_memory_rejected` | Write memory with wrong repo_id → scan → verify fresh session |
| SW-03 | `test_persistence_failure_sets_degraded_flag` | Make memory dir read-only → scan → verify `_memory_persistence_failed` |
| SW-07 | `test_large_repo_signature_marked_sampled` | Create repo with 3000 files → scan → verify `signature_is_sampled` |
