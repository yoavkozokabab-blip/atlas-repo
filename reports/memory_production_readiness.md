# Memory System Production Readiness

**Date:** 2026-05-29  
**Evidence:** `memory/store.py`, `memory/session_memory.py`, `memory/semantic_runtime.py`, `memory/search.py`, `memory/repair.py`

---

## Memory System Inventory

| Store | File | Format | Current size |
|-------|------|--------|-------------|
| Personal facts | `memory/store.py` → `data/memory_store.json` | JSON | growing unbounded |
| Session context | `memory/session_memory.py` → `data/session_memory.json` | JSON | growing |
| Semantic embeddings | `memory/semantic_runtime.py` → `data/semantic_memory.json` | JSON | 335 KB |
| Project index | `memory/project_indexer.py` → `data/project_index.json` | JSON | 576 KB |
| Memory graph | `memory/graph.py` → `data/investigation_graph.json` | JSON | 9 KB |
| Legacy facts | `brain/memory.py` → `data/memory.json` | JSON | unknown |

---

## Section 1: Short-Term / Session Memory

**File:** `memory/session_memory.py`

### What Works
- Session context stored per-session
- Used by `resolve_follow_up()` in `brain/command_parser.py` for pronoun resolution

### What Is Broken or Missing

**SM-1: Session memory is an independent store, not integrated with PersonalMemoryStore**  
Session facts written to `data/session_memory.json` are invisible to `forget("Alice")` which only touches `data/memory_store.json`.  
**Fix:** Route session memory writes through `PersonalMemoryStore.remember(category="session")`. (Consolidation Plan C-5)

**SM-2: Session memory never expires between sessions**  
There is no mechanism to expire session context when a new session starts. Old session context accumulates.  
**Fix:** On startup, call `PersonalMemoryStore.vacuum()` which will respect TTL on session entries.

---

## Section 2: Long-Term Memory

**File:** `memory/store.py`

### What Works
- Structured entries with `category`, `tags`, `importance`, `confidence`, `expires_at`
- Secret redaction via `memory/redaction.py` before storage
- Soft-delete via `forget()` (sets `hidden=True`)
- `list_visible()` skips hidden and expired entries

### What Is Broken or Missing

**LT-1: Expired entries never deleted from disk (VF-3 — verified)**  
```python
# memory/store.py:175
if datetime.fromisoformat(expires_at) <= now:
    continue    # skips but never deletes
```
Expired entries accumulate in `memory_store.json` forever. They are parsed on every `_load()` call.  
**Fix:** Add `vacuum()` method; call at startup and every 6 hours.

**LT-2: Hidden entries never deleted from disk**  
`forget()` sets `hidden=True` but never removes the entry from the JSON array.  
**Fix:** `vacuum()` should also remove hidden entries.

**LT-3: No per-entry size limit**  
`remember()` accepts text of any length. A 10 MB text entry would be stored and parsed on every `_load()`.  
**Fix:** Add at line 100 of `store.py`: `if len(safe_text.encode()) > 10_240: safe_text = safe_text.encode()[:10_240].decode(errors="ignore")`

**LT-4: `_load()` reads entire file on every call**  
```python
def _load(self) -> dict[str, Any]:
    data = json.loads(self.path.read_text(encoding="utf-8"))
```
Called on every `remember()`, `forget()`, `list_visible()`, and `search()`. If the file is large (thousands of entries), this is expensive.  
**Fix:** Cache the loaded data in-process with an mtime-based invalidation. Or migrate to SQLite (see LT-6).

**LT-5: Search is linear scan**  
`memory/search.py:search_memory_entries()` iterates all entries. At 10,000 entries, each search reads and scans the entire file.  
**Fix:** Migrate to SQLite with `CREATE INDEX ON entries(text)` and `FTS5` for full-text search.

**LT-6: JSON is not the right storage backend for this use case**  
`PersonalMemoryStore` is a JSON array that is read entirely into memory, mutated, and rewritten on every change. SQLite would provide:
- O(log n) indexed lookup
- Built-in FTS5 full-text search
- Atomic writes without the backup-per-write problem
- Proper TTL enforcement via `DELETE WHERE expires_at < datetime('now')`  
**Fix:** Migrate to SQLite. This is the highest-leverage single change for memory reliability.

---

## Section 3: Semantic Memory

**File:** `memory/semantic_runtime.py`

### What Works
- `upsert_entry()` called automatically from `PersonalMemoryStore.remember()` (`store.py:131–143`)
- `semantic_search()` available and called by `MemoryAgent.semantic_search()`

### What Is Broken or Missing

**SEM-1: Semantic search failure falls back to empty, not keyword search**  
```python
# store.py:231–240
def semantic_search(self, query: str, ...) -> list[dict[str, Any]]:
    try:
        from memory.semantic_runtime import semantic_search
        return [...]
    except Exception:
        return []    # silent empty fallback
```
If the semantic model is unavailable, the function returns `[]` with no indication that the search failed or fell back.  
**Fix:** Log the exception; fall back to keyword search via `search_memory_entries()`.

**SEM-2: Embedding model not validated at startup**  
If the embedding model used by `semantic_runtime.py` is not installed, `semantic_search()` silently returns empty on every call.  
**Fix:** Add to startup health check: attempt `upsert_entry("health_check_probe", ...)` and verify it succeeds.

**SEM-3: `semantic_retrieve` acceptance test is a tautology**  
```python
# memory_health.py:93
return len(hits) >= 0, f"semantic_hits={len(hits)}"
```
See T-5 in truthfulness audit. `len() >= 0` never fails.  
**Fix:** `return len(hits) > 0, ...`

---

## Section 4: Retrieval and Ranking

### What Works
- `importance` and `confidence` fields exist on every entry
- `list_visible()` returns entries in insertion order

### What Is Broken or Missing

**R-1: No ranking by importance or recency**  
`list_visible()` returns entries in insertion order. High-importance recent entries are not surfaced first.  
**Fix:** Sort by `(importance * confidence) * recency_factor` before returning. This is a 5-line change.

**R-2: Search does not use importance or confidence to rank results**  
`memory/search.py:search_memory_entries()` returns all matching entries equally. A 0.9-importance entry ranks the same as a 0.1-importance entry.  
**Fix:** After linear search, sort results by `importance * confidence` descending.

---

## Section 5: Contradiction Handling

### What Exists
`memory/semantic_runtime.py` has a `contradictions` field in the semantic graph (referenced in `memory_health.py:41`).

### What Is Missing

**C-1: No contradiction detection at write time**  
When `remember("I prefer dark mode")` is called after `remember("I prefer light mode")`, both entries are stored with no warning.  
**Fix:** On `remember()`, check semantic similarity to existing entries in the same category. If cosine similarity > 0.85 to an existing entry with contradictory sentiment, flag as `potential_contradiction: True` and log a warning.  
**Effort:** 1 day (requires semantic similarity call at write time).

**C-2: Contradiction list populated but never acted upon**  
The `contradictions` list in the semantic graph is read by `show_memory_ranking_diagnostics()` but never surfaced to the user proactively.  
**Fix:** Include contradiction count in `show_memory_health()` output.

---

## Section 6: Decay

### What Exists
- `expires_at` field on every entry
- `ttl_seconds` parameter in `remember()`
- Expired entries filtered on read by `list_visible()`

### What Is Broken

**D-1: TTL is enforced on read, not on disk**  
See VF-3. Expired entries accumulate on disk forever.  
**Fix:** `vacuum()` method.

**D-2: No default TTL for ephemeral categories**  
`category="session"` entries have no default TTL. They accumulate indefinitely.  
**Fix:** In `remember()`, if `category in {"session", "short_term", "temporary_fact"}` and `ttl_seconds is None`, set `ttl_seconds=86400` (24 hours) as default.

---

## Section 7: Persistence

### What Works
- `_save()` uses `path.write_text()` — atomic on most filesystems (os.replace would be better)
- `memory/repair.py` restores from backup on corruption

### What Is Broken

**P-1: `_save()` is not atomic**  
```python
# store.py:76–83
def _save(self, data: dict[str, Any]) -> bool:
    try:
        self.path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        return True
    except OSError:
        return False
```
If the process is killed during `write_text()`, the file may be partially written and corrupt.  
**Fix:** Use `atomic_write_json()` from `core/persistent_json.py` — which already exists and uses `os.replace()`. Note: this will also create a backup on every write (see VF-1 for the backup growth problem — which should be fixed first).

**P-2: 2,522 backup files from `atomic_write_json` (VF-1 — verified)**  
The backup system works but has no retention limit.  
**Fix:** VF-1 fix: keep 5 most recent per stem.

---

## Actual Readiness

| Component | State | Score |
|-----------|-------|-------|
| Short-term / session memory | Works; not integrated with PersonalMemoryStore | 55% |
| Long-term personal store | Works; no vacuum; no size limit; linear search | 50% |
| Semantic memory | Works; silent fallback to empty on failure | 55% |
| Retrieval / ranking | Works; no importance-based ranking | 45% |
| Contradiction detection | Tracked; not acted on at write time | 20% |
| Decay / TTL | Stored but not enforced on disk | 35% |
| Persistence / atomicity | Non-atomic write; backup system works | 60% |
| **Overall memory** | | **45%** |

---

## Prioritized Fixes

| Priority | Fix | Effort |
|----------|-----|--------|
| P0 | Add `vacuum()` to remove expired + hidden entries from disk | 2 hours |
| P0 | Add per-entry 10 KB size limit to `remember()` | 30 min |
| P1 | Default TTL for session/temporary_fact categories | 30 min |
| P1 | Route session memory through PersonalMemoryStore | 2 days |
| P1 | Semantic search fall back to keyword on failure (log, don't return empty) | 1 hour |
| P1 | Fix truthfulness: acceptance cases T-5 through T-9 | 1 hour |
| P2 | Sort `list_visible()` by importance × confidence × recency | 30 min |
| P2 | Make `_save()` atomic using `atomic_write_json()` (after VF-1 fix) | 1 hour |
| P3 | SQLite backend for PersonalMemoryStore | 3 days |
| P3 | Contradiction detection at write time | 1 day |

---

*End of Memory Production Readiness — 2026-05-29*
