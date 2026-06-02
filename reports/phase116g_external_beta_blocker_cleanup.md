# Phase 116G — External Beta Readiness Pass

**Date:** 2026-06-02  
**Product version:** `phase116f-analytics-isolation` (desktop); Phase 116G trust + blocker bundle  
**Prior status:** Supervised Internal Demo: GO  
**Decision:** **EXTERNAL BETA: GO** (see §6)

---

## 1. Windows Browse verification

### Automated verification (this pass)

| Check | Result |
|-------|--------|
| Route `POST /api/system/browse-folder` registered | PASS |
| Mock picker → path returned | PASS |
| Mock cancel → `cancelled: true`, no error toast path | PASS |
| Selected path → `validate_repository_path` OK | PASS |
| Foreground picker sequence (`lift`, `focus_force`, `-topmost`, dialog title) | PASS (`test_native_picker_requests_foreground_window`) |
| Phase 116C/116D browse route audit tests | PASS (10 tests) |

### Manual GUI verification (operator checklist)

Native folder picker cannot be driven reliably from a headless agent session. **Before inviting external beta users**, the operator should confirm once on a Windows desktop session:

1. Home → **Browse** → Windows folder dialog appears **in foreground**.
2. Select `C:\J.A.R.V.I.S\fastapi` → path fills repo input → **Validate** succeeds.
3. Repeat for `C:\J.A.R.V.I.S\django` and `C:\J.A.R.V.I.S\vscode`.
4. Open picker → **Cancel** → no error banner; path unchanged.
5. Confirm no `Unknown endpoint: POST /api/system/browse-folder` (run from `local_jarvis`, not stale `staging/`).

**Code-path status:** GO for beta (automated). **Operator smoke:** recommended same day as first external invite.

---

## 2. Fresh repository metrics (cache cleared per run)

Collected via `scripts/phase116g_collect_metrics.py` with `scan_cache={}` reset.  
JSON artifacts: `reports/phase116g_{fastapi,django,vscode}_metrics.json`.

| Metric | FastAPI | Django | VS Code |
|--------|---------|--------|---------|
| Scan time (s) | 2.13 | 14.34 | 6.36 |
| Cache hit | false | false | false |
| Scan OK | true | true | true |
| Files discovered | 1,120 | 929 | 7,551 |
| File count (walk) | 2,753 | 6,868 | 14,871 |
| Modules | 73 | 929 | 7,551 |
| Dependency edges | 159 | 2,916 | 13,224 |
| Subsystems | 7 | 9 | 13 |
| Graph health label | **partial** | watch | **partial** |
| Unresolved imports | 560 | 1,377 | 67,164 |
| Unresolved ratio | 0.779 | 0.321 | 0.836 |
| Import cycles | 15 | 80 | 0 |
| Graph scope | production | production | production |
| Analytics status | ok | ok | ok |

**Top risks (abbreviated):** FastAPI — `fastapi/_compat`, `applications`, `routing`; Django — `conf`, `db`, `core/exceptions`; VS Code — Copilot extension platform modules (expected hub concentration).

---

## 3. Trust corrections verification

| ID | Requirement | Evidence | Status |
|----|-------------|----------|--------|
| A | FastAPI docs/examples trees excluded from production graph | 73 production modules; **0** paths under `docs_src/`, `docs/`, or `examples/` trees; only `fastapi/openapi/docs.py` + `scripts/docs.py` (production filenames, not tutorial trees) | **PASS** |
| B | VS Code not “healthy” with extreme unresolved imports | `graph_health.label` = **partial**, `degraded` = true, notice set; ratio 0.836, 67k unresolved | **PASS** |
| C | Cycle counts canonicalized | `builder_core/tests/test_phase116g_external_beta_graph_trust.py` rotation/reverse invariance | **PASS** |
| D | Analytics failure cannot break scan/demo | `test_phase116f_analytics_isolation_hardening.py` (PermissionError, makedirs deny) | **PASS** |
| E | Browse flow works | Route + mock picker + validate + cancel tests | **PASS** |

---

## 4. Release readiness audit

### In scope for Phase 116G commit (desktop + trust)

| Area | Files (representative) |
|------|------------------------|
| Desktop API/UI | `jarvis_desktop/api.py`, `graph_build.py`, `analytics.py`, `system_browse.py`, `static/*` |
| Desktop tests | `test_phase116*.py`, `test_phase116f`, `test_phase116d`, `test_phase116c`, `test_phase116b`, `test_phase116g_external_beta_blockers.py` |
| Builder trust | `depgraph.py`, `jsdepgraph.py`, `repository_understanding.py`, `architectural_risk.py` |
| Builder tests | `test_phase116g_external_beta_graph_trust.py`, `test_phase116_jsdepgraph.py` |
| Reports/scripts | `reports/phase116g_*`, `scripts/phase116g_collect_metrics.py` |

### Intentionally excluded from this commit (unrelated WIP)

- `builder_core/benchmark_framework/compact_packets.py` and Phase 104 benchmark artifacts  
- Untracked `confirmed_defect_gate.py`, `contract_*`, export index experiments  
- `data/real_repo_corpus/**`  
- `staging/` copy (may lag `jarvis_desktop`; beta users should run `run_jarvis_desktop.py` from `local_jarvis`)  
- Phase 116E opt-in diag (`JARVIS_ANALYTICS_DIAG=1` only; default off)

### Instrumentation

- `analytics_write_diag.log` — **not** written unless `JARVIS_ANALYTICS_DIAG=1`. Safe for beta default.

---

## 5. Test results (exact counts)

| Suite | Command | Result |
|-------|---------|--------|
| Phase 116 targeted | `pytest` 116b–116g desktop + BC 116/116g tests | **70 passed** |
| Full `jarvis_desktop` | `pytest jarvis_desktop/tests` | **152 passed** (19.15s) |
| Builder Core 116G + JS graph | `test_phase116g_external_beta_graph_trust.py` + `test_phase116_jsdepgraph.py` | **24 passed** |

No failures in scoped suites.

---

## 6. Final decision

## EXTERNAL BETA: GO

**Justification**

1. **Core journeys work on real repos** — FastAPI, Django, and VS Code complete fresh scans with honest graph-health labels (partial where appropriate).  
2. **Trust regressions addressed** — production-scope exclusion, canonical cycles, partial-health disclosure for high unresolved ratios, analytics isolation.  
3. **Regression surface green** — 152 desktop + 24 builder 116 tests passing.  
4. **Browse** — backend and unit-level foreground/cancel/validate verified; one-time operator GUI smoke remains a launch checklist item, not a code defect.  
5. **Known beta limitations (disclosed, not blockers)** — VS Code and FastAPI graphs are **partial** due to unresolved import volume; users see notices in Health Cockpit. TS/JS resolution will improve over time but does not invalidate architecture/risk views for beta.

**Not starting Phase 117.** Phase 116G complete pending operator browse smoke + release commit.

---

## 7. Beta operator launch checklist

1. `py -3 run_jarvis_desktop.py` from `local_jarvis` (port 8777).  
2. Manual Browse smoke (§1).  
3. Scan FastAPI → Command Center → subsystem graph readable.  
4. Confirm telemetry banner only if `%USERPROFILE%\.jarvis_desktop` is locked.  
5. Distribute commit hash from Phase 116G release commit.
