# Phase 172A — Repository Memory Attack Surface

**Date:** 2026-06-05  
**Scope:** Red-team the Phase 171B Repository Memory Engine **as specified**, wired through today’s Phase 169 scan/cache/session paths.  
**Method:** External-adversary mindset — assume memory exists, deltas reference it, users paste into LLMs.

---

## Executive summary

Repository Memory **will fail in production** unless invalidation is stricter than Phase 169’s `ATLAS_SESSION v1`. The architecture optimizes tokens by **splitting truth across two channels** (RMO once + delta per question). That split introduces **11 confirmed or high-likelihood failure classes**. Two are **already reproducible** on current code (repo switch, rebuild without session clear).

| Severity | Count | Representative failure |
| --- | ---: | --- |
| **P0 — ship blocker** | 5 | Wrong-repo memory after `select_repository` |
| **P1 — high** | 6 | Stale cache after git pull; shallow→full graph drift |
| **P2 — medium** | 5 | LLM memory drift; fake `memory_ref` |
| **P3 — low** | 3 | On-disk tampering (future persistence) |

**Verdict:** Architecture is sound for token economics but **unsafe as default** until memory–delta **version coupling** and **hard invalidation gates** are enforced server-side and in the copy path.

---

## Threat model

| Actor | Capability | Goal |
| --- | --- | --- |
| **Busy developer** | `git checkout`, edit files, switch repos, skip rescan | Fast answers |
| **LLM session** | Long context, no Atlas API | Answer from whatever is pinned |
| **Malicious local process** | Write files under repo; optional disk store | Poison graph/evidence (low risk desktop) |
| **Atlas bugs** | Cache, partial scan, scope | Serve fast stale intelligence |

Assumption: attacker does **not** need network; attacks are **workflow + state-machine** bugs.

---

## Architecture under attack

```
Scan → RMO (persistent) ──pin once──► LLM context
              ▲                              │
              │ memory_ref (string only)     │
              └── ATLAS_DELTA per question ──┘
```

**Core vulnerability:** `memory_ref` is a **hint**, not a **capability**. Nothing in the 171B design forces the LLM to hold the matching RMO bytes when a delta arrives.

---

## P0 — Ship blockers

### A1. Wrong-repo memory after path switch (PROVEN today)

**Attack:**
1. Scan repo A → RMO_A / `session_export` for A.
2. `select_repository(repo_B)` **without rescan**.
3. Run Build on B.

**Result:** `_STATE["scan"]`, `session_export`, and workflow intelligence still describe **repo A** while UI shows repo B path.

**Evidence:** `select_repository()` only sets `_STATE["path"]` — does not clear `scan`, `session_export`, or future `repository_memory`.

```743:761:jarvis_desktop/api.py
def select_repository(path: str) -> Dict[str, Any]:
    ...
    _STATE["path"] = abspath
    _STATE["demo_mode"] = False
    return {"ok": True, "path": abspath, ...}
```

**Memory impact:** Delta cites B’s question text but `memory_ref` resolves to A’s graph. **Silent cross-repo contamination.**

---

### A2. Poisoned memory survives index rebuild (PROVEN today)

**Attack:**
1. Scan repo.
2. Inject or corrupt `_STATE["session_export"]` (or future on-disk RMO).
3. `rebuild_index(rescan=False)`.

**Result:** `scan=None` but **memory object unchanged** — deltas reference live planning on empty graph **or** stale memory text.

**Evidence:** `rebuild_index` clears `scan/graph/index` but **not** `session_export`.

---

### A3. `memory_ref` version mismatch (design gap)

**Attack:**
1. User pins `atlas://mem/sig/v3` at session start.
2. Atlas rescans → server emits deltas with `memory_ref: .../v4`.
3. User copies delta only (no re-pin).

**Result:** LLM applies v4 file paths against v3 hubs/risks/subsystems. **Coherent-looking wrong guidance.**

**Root cause:** No server-side rejection of stale refs; no mandatory `memory_stale` block on workflow API; client copy path does not verify version equality.

---

### A4. Scan signature blind spot (existing `_scan_signature`)

**Attack:**
1. Full scan → RMO materialized.
2. Modify files **not visited** in signature walk (repo has >2500 files, or changes outside sampled walk order).
3. Rescan → **cache hit** → old RMO restored.

**Evidence:** Signature hashes path + scope + **first 2500 files only** (size + mtime).

```460:480:jarvis_desktop/api.py
    sample = 0
    for dirpath, dirnames, filenames in os.walk(root):
        ...
            if sample >= 2500:
                break
            ...
            sample += 1
```

**Memory impact:** `content_hash` in 171B inherits this weakness unless signature includes full tree or git HEAD.

---

### A5. Delta without memory in LLM context

**Attack:**
1. User told “send only deltas after pinning memory.”
2. New chat / cleared context / different tool tab.
3. Paste delta containing `memory_ref` only.

**Result:** LLM has paths + confidence but **no graph health cap**, wrong hub priors, no subsystem boundaries → **hallucination fill-in**.

**171B acknowledges** (“LLM forgets memory”) but mitigation (re-pin every N questions) is **optional**, not enforced.

---

## P1 — High severity

### B1. Git branch switch, same directory

**Attack:** `git checkout feature` after scan on `main`. Path unchanged → signature may unchanged if sampled files identical mtime/size → **cache hit** → RMO describes **main** graph.

**Why high:** Most common developer action; no branch in `repo_signature`.

---

### B2. Partial scan → full graph promotion

**Attack:**
1. Massive repo scan with `lazy_full` / `full_graph_pending`.
2. RMO built from **import-level** graph (degraded/partial health).
3. User clicks “Build full graph” — graph updates, **RMO not regenerated** in 171B sketch.

**Result:** Deltas use full-graph planning; memory still says partial/degraded → **confidence cap mismatch**.

---

### B3. Cache restore without memory blob versioning

**Attack:** `scan_cache[signature]` stores graph/index/risks/evidence but **not** RMO version. On restore, session/RMO rebuilt from `current_summary()` while cached graph may be **hours old** relative to disk.

**Evidence:** Cache entry at scan complete:

```1209:1216:jarvis_desktop/api.py
    cache[signature] = {
        "scan": _STATE["scan"],
        "graph": graph,
        "index": index,
        "risks": risks,
        "evidence_store": _STATE.get("evidence_store") or {},
        "cached_at": time.time(),
    }
```

No `repository_memory` / `content_hash` field. **Memory drift across cache hit.**

---

### B4. UI `STATE.sessionExport` never invalidated on workflow

**Attack:**
1. Scan → `STATE.sessionExport` fetched.
2. User runs 10 questions; edits code; **no rescan**.
3. `zfSessionPrefix()` still prepends original session on every copy.

**Evidence:** `finishScanSession` clears `summary/graph` but **not** `sessionExport` or `buildResult`.

**Memory impact:** Even with server-side deltas, **copy path re-injects stale RMO** every question — defeats delta-only economics and doubles stale risk.

---

### B5. Scope change, same folder

**Attack:** Scan `entire_repo` → RMO. Rescan `python_only` scope — different signature → new cache entry — but client still pins old RMO. Deltas from new scope reference new paths against old subsystem list.

---

### B6. Concurrent workflow results mixed

**Attack:** Build result for task 1 in `STATE.buildResult`; switch repo without clear; Investigate shows export from previous repo until new request completes. **Transient wrong delta copy.**

---

## P2 — Medium severity

### C1. Hallucinated `memory_ref` (client-supplied)

Delta format is markdown/text. User or tool can craft:

```
memory_ref: atlas://mem/fastapi/deadbeef/v99
files: [real paths from current code]
```

LLM trusts paths in delta; memory_ref is **cosmetic** unless server signs bundles.

---

### C2. Memory drift over long sessions

After ~15–30 questions, pinned RMO scrolls out of LLM context. Later deltas still assert high confidence. Quality drops without Atlas knowing — **silent quality regression** (Phase 170 methodology would show grounding drop).

---

### C3. Backward-compat dual export

Phase 172 requires `export_minimal` **and** `export_delta`. Attack: automation copies **minimal** (includes embedded session-like fields) **while** memory also pinned → duplicate/conflicting facts; or copies delta only for “savings” without pin.

---

### C4. `clear_scan_cache` without memory purge

`clear_scan_cache()` wipes `scan_cache` only — active `_STATE["session_export"]` and scan remain. User believes cache clear = fresh truth; memory unchanged.

---

### C5. Demo pack ↔ real repo confusion

`demo_mode` flips on path match. Load demo → RMO_demo. Select real repo path without scan → **demo memory + real path** (extends A1).

---

## P3 — Low severity (future / edge)

### D1. On-disk RMO tampering

When Phase 172 persists to `desktop_data/`, local malware edits JSON → wrong hubs until next rescan.

### D2. `content_hash` collision / stale minor bump

171B proposes minor version on git pull without full rescan — **incremental patch bugs** could leave edges/evidence inconsistent while hash matches.

### D3. Multi-instance desktop

Two Atlas processes, shared data dir (if ever) → last-writer-wins memory file.

---

## Attack playbooks (break it before users do)

| # | Playbook | Expected breakage | Status |
| --- | --- | --- | --- |
| 1 | Scan A → select B → Build | A’s files in export | **REPRODUCED** |
| 2 | Scan → rebuild(no rescan) → copy session | Poisoned/stale memory | **REPRODUCED** |
| 3 | Scan → checkout branch → rescan | Cache hit, stale graph | Likely on large repos |
| 4 | Scan partial → full graph → Impact | Confidence/graph mismatch | Design gap |
| 5 | Pin memory → 20 deltas → new Claude chat | Ungrounded deltas | Design gap |
| 6 | Rescan with file 3001 changed | Signature unchanged | Design gap (2500 cap) |
| 7 | Copy delta only after UI refresh | Old `sessionExport` + new delta | UI gap |
| 8 | Two scopes same repo | Wrong subsystem context | Likely |

---

## Required mitigations (before memory engine ships)

### Hard gates (server)

1. **`memory_generation` monotonic** — every scan/rescan/full-graph/index-rebuild bumps version; store in cache entry.
2. **`workflow_requires_memory`** — reject or mark `ok=false` when `delta.memory_ref.version != active_memory.version`.
3. **`select_repository` clears** — `scan`, `session_export`, `repository_memory`, workflow results, `scan_job`.
4. **`rebuild_index` clears** — all memory fields, not only graph.
5. **Signature v2** — include `git HEAD` (if repo), scope, and **full mtime map hash** or stop cache on any mtime change in indexed files.
6. **Cache entry must include** `repository_memory` + `content_hash`; restore is atomic.

### Copy path (client)

7. **`zfSessionPrefix()`** — include `memory.version`; if workflow `delta.memory_version` mismatch → block copy, force reload.
8. **`finishScanSession`** — clear `sessionExport`, `repositoryMemory`, `buildResult`, `investigateResult`, `impactResult`.
9. **Never prepend session when delta mode** — delta must embed ref only; pin panel is separate one-time action.

### LLM bundle (export)

10. **Signed export packet** optional: `{memory_hash, delta, canonical_paths}` so tampering is detectable.
11. **`memory_stale: true`** on any planning executed while `content_hash` drift detected.

### Observability

12. **Telemetry:** `memory_version`, `delta_version`, `cache_hit`, `invalidation_reason` on every workflow.

---

## What Phase 170 methodology would show

If we ran Phase 170 arms **MINIMAL vs MEMORY+DELTA** without mitigations:

| Metric | Prediction |
| --- | --- |
| Tokens | ↓ 60–70% (good) |
| Quality (late session) | ↓ 0.5–1.5 after context loss |
| Grounding | ↓ on branch switch / repo switch |
| Hallucination | ↑ when delta-only without pin |

**Token savings without invalidation gates = trust regression.**

---

## Test coverage added

`jarvis_desktop/tests/test_phase172a_memory_attack_surface.py` — reproduces **A1**, **A2**, and documents guards needed for A3–A5.

---

## Conclusion

Repository Memory is **attackable by normal developer workflows**, not exotic hackers. The highest-risk failures are:

1. **Stale memory** (cache, signature sampling, no invalidation on select/rebuild)
2. **Wrong memory version** (client pin vs server bump)
3. **Split-context hallucination** (delta without RMO in LLM)

**Do not ship Phase 172 as default** until P0 mitigations 1–6 and client gates 7–8 are implemented and covered by regression tests.
