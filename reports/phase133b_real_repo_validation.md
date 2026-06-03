# Phase 133B — Real-Repository Validation (Home Assistant)

**Date:** 2026-06-03
**Repo:** `external_repos/home_assistant` (~25,893 files, ~9,708 production Python modules)
**Commit:** `phase133b: fix massive-mode graph degradation and real-repo validation`

---

## 1. Root cause (confirmed)

`builder_core/bug_intelligence/depgraph.py :: build_graph_from_files` applied the
**FULL-detail file cap (`_MAX_FILES = 5000`) before the cheap import-level branch**:

```python
if len(file_list) > _MAX_FILES:        # 9708 > 5000  → bail
    return _degraded_graph(...)        # 0 modules, 0 edges
if detail == DETAIL_IMPORTS:           # never reached for HA
    return _build_imports_detail_graph(...)
```

So Home Assistant (9,708 kept files) produced an **empty degraded graph**. The
desktop merge with the JS graph then left exactly **1 module (`.prettierrc.js`)
and 0 edges**, which poisoned Repository Map, Impact, Investigation and Build.

The import-level graph is cheap (one `ast.parse` + import-edge pass per file) and
is already bounded by the time budget, so the cap was never appropriate for it.

## 2. The fix

**`depgraph.build_graph_from_files`** — run the import-level branch *before* the
file cap, and never flag a complete import graph as degraded merely for being over
the FULL-detail cap:

```python
if detail == DETAIL_IMPORTS:
    graph = _build_imports_detail_graph(root, file_list, deadline=..., ...)
    if len(file_list) > _MAX_FILES:
        graph["import_level_file_count"] = len(file_list)  # informational only
    return graph
if len(file_list) > _MAX_FILES:        # FULL detail still protected
    return _degraded_graph(root, "too_many_files", len(file_list))
```

Degradation now only happens on the legitimate guards: **deadline exceeded** or
**parser failures** (handled inside `_build_imports_detail_graph` via the
`deadline`), and the FULL-detail cap. Never solely because `files_kept > cap_files`.

**`graph_build.BUDGET_HIERARCHY_IMPORTS_SEC`** 60 → 150s. Warm import builds take
~16s for HA; the larger budget covers cold-cache disk reads without hiding the
real cost (scans are cached after the first run). Not a "giant" increase.

## 3. Home Assistant — before / after

| Metric | Before | After |
|--------|-------:|------:|
| Modules | **1** | **9,709** |
| Edges | **0** | **36,013** (resolved imports); 45,722 total graph edges |
| Selected node | `.prettierrc.js` | real `homeassistant/*` modules |
| Subsystems | collapsed | homeassistant/{components, auth, helpers, core.py, config_entries.py, components/recorder} |
| Direct depgraph build | 0 modules (cap bail) | 9,708 modules / 45,721 edges in ~16s (warm) |

## 4. Validation results

Run: `py -3 benchmarks/real_repos/home_assistant_validation.py` → **20/20 checks pass.**

**Repository Map**
- `modules > 5000` — modules = **9,709**
- `edges > 10000` — edges = **36,013**
- subsystems present: `homeassistant/components`, `homeassistant/auth`,
  `homeassistant/helpers`, `homeassistant/core.py`, `homeassistant/config_entries.py`,
  `homeassistant/components/recorder`
- not collapsed (modules = 9,709, not 1)

**Impact (semantic targets — no "target not in graph")**
- `remove websocket support` → `homeassistant/components/websocket_api/__init__.py` (risk high)
- `remove the event bus` → `homeassistant/helpers/event.py`
- `remove authentication` → `homeassistant/auth/permissions/const.py`

**Investigation (runtime symptoms never route to dotfiles)**
- `why are duplicate events being fired` → no dotfiles; lands on event/automation area
- `websocket keeps disconnecting` → `auth/jwt_wrapper.py`, `assist_pipeline/websocket_api.py`, `bang_olufsen/websocket.py`
- `integrations loading slowly` → auth/components setup area; no dotfiles

**Build planning (concept → boundary files)**
- `add distributed tracing` → `assist_pipeline/websocket_api.py`, `components/automation/__init__.py`, `bootstrap.py`
- `add rate limiting` → `assist_pipeline/websocket_api.py`, `amazon_polly/tts.py`, `assist_pipeline/__init__.py`

Every check in all four areas passed. `.prettierrc.js` / `package.json` /
`pyproject.toml` can no longer be selected for runtime symptoms.

## 5. Cold-cache note (honest)

The very first (cold-disk) scan on Windows read files at a low rate (antivirus
scans each `open()`), and with the old 60s budget produced ~115 modules before the
deadline. Two principled mitigations: (a) import-level no longer collapses to 1 —
a cold partial still yields hundreds of real modules across subsystems, never one
dot; (b) the 150s budget covers HA cold reads in practice. After the first scan the
OS file cache is warm and re-scan indexes all 9,709 modules in ~16s (the scan is
also content-cached by Atlas). True parallel/chunked file I/O would remove the
cold-disk ceiling entirely and is the recommended future improvement (out of scope:
no new features this phase).

## 6. Remaining limitations

- Cold first-scan on a huge repo is disk-I/O bound; warm/cached scans are fast and
  complete. Parallel file reading is the durable fix.
- The HA graph is import-level (massive mode): module + import edges, no full
  call-graph. This is correct and intended for repos of this size; the lazy full
  module graph can be built on demand from Command Center.
- Impact/Investigation/Build concept localization uses curated keyword + symbol
  maps for common architecture concepts; very novel concepts fall back to keyword
  scoring.
- **Ranking sharpness:** runtime symptoms now correctly avoid dotfiles and land on
  the right *area*, but the exact top-1 is not always the canonical file (e.g.
  duplicate-events surfaces the event/automation area broadly rather than always
  `core.py` first), because domain-knowledge evidence files are merged ahead of the
  boosted keyword matches. The hard requirements (no dotfiles, correct area, no
  "target not in graph") all pass; tighter top-1 ranking is a follow-up.
- **First-scan latency:** a full cold scan of Home Assistant (graph + evidence
  store over 9.7k modules) takes ~2–4 minutes; it is cached afterward. The graph
  build itself is ~16s warm — the evidence-store symbol index dominates first-scan
  time and is the next optimization target.

## 7. Reproduce

```bash
# warm the cache once, then validate
py -3 benchmarks/real_repos/home_assistant_validation.py
# full existing suite
py -3 -m pytest jarvis_desktop/tests benchmarks -q
```
