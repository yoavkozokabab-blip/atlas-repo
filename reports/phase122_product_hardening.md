# Phase 122 — Atlas Product Hardening

**Date:** 2026-06-02  
**Version:** `phase122-atlas-product-hardening`  
**Beta readiness:** **GO** (with known limitations below)

## Part A — Feature audit

| Feature | Current value | Decision | Reason |
|---------|---------------|----------|--------|
| Home | Onboarding, repo pick, task cards | **KEEP** | Entry point; cards aligned to 5 beta flows |
| Scan | Index + graph build | **KEEP** | Required for all flows |
| Command Center | Graph + cockpit + copilot | **KEEP** → renamed **Repository Map** | Core “understand repo”; intelligence merged into left panel |
| Intelligence | Subsystems, entry points, explanation | **MERGE** | Duplicated summary; now in Repository Map cockpit |
| Build | Change planner | **KEEP** → **Build Plan** | Actionable plans with files, order, verification |
| Investigate | Symptom engine | **KEEP** → **Investigate Bug** | Grounded investigation plan format |
| Impact | Direct reverse-import impact | **KEEP** | Labeled **direct impact only** |
| Bug Hunt | Stack-trace heuristic API | **MERGE** | UI removed; traces pasted in Investigate; API kept for compatibility |
| AI Export | Context packets | **KEEP** → **Export** | Useful Claude/Cursor packets |
| Demo/Tour | Demo mode + tours | **HIDE** | Demo on Home; graph tours under Advanced toolbar |
| Analytics/Health | Cockpit metrics | **KEEP** (trimmed) | Token savings hidden unless verified; ratio explained |

### Target navigation (implemented)

1. Home  
2. Scan  
3. Repository Map  
4. Build Plan  
5. Investigate Bug  
6. Impact  
7. Export  

## Part B — Graph

- Module graph uses force-visible native spheres (Phase 121F).
- **Module list panel** under graph: filterable hubs/files when module view is active.
- Graph debug overlay **off** in normal mode (`ATLAS_SHOW_GRAPH_DEBUG = false`).
- Architecture summary in left cockpit — product usable if 3D graph is ignored.

## Parts C–E — Flows

- **Investigate:** `BUG INVESTIGATION PLAN` with symptom, source, hypothesis, evidence, verification, risk, confidence, limitations.
- **Build:** files to inspect/change/break, implementation order, verification plan, risk level.
- **Impact:** `impact_scope: direct_only`, `transitive_available: false`.

## Part F — Metrics

See `reports/phase122_metric_truth_audit.md`.

## Part G — Buttons

See `reports/phase122_button_audit.md`.

## Part H — Beta flows

| Flow | Status |
|------|--------|
| Understand (scan → summary → risks) | **Strong** |
| Build (feature → plan → prompt) | **Strong** (keyword-grounded) |
| Investigate (symptom → plan) | **Strong** (heuristic; needs paths for high confidence) |
| Impact (file → direct importers) | **Strong** (direct only, honest) |
| Export (context packet) | **Strong** |

## Removed / hidden

- Nav: Intelligence, Bug Hunt, Command Center label
- Views: `view-intel`, `view-bug` (HTML sections removed)
- Cockpit: unverified token savings %
- Normal UI: graph render diagnostics overlay
- Primary toolbar: PNG/SVG/tours moved under **Advanced**

## Still needs work

- Transitive impact engine (Phase 94B TODO)
- Runtime/log-based investigation (not static graph only)
- Manual screenshot checklist for marketing (operator)
- Verified token savings metric (if ever shown)

## Tests run

```text
py -3 -m pytest local_jarvis/jarvis_desktop/tests -q
```

## Screenshots checklist (operator)

- [ ] Home — 5 task cards  
- [ ] Scan complete → Repository Map  
- [ ] Module list + graph visible  
- [ ] Build Plan output  
- [ ] Investigate Bug — paper trading symptom  
- [ ] Impact — direct impact only badge  
- [ ] Export — compact packet  

## Commit

`phase122: harden Atlas product flows for beta usability`
