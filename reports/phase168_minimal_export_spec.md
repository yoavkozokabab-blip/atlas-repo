# Phase 168 — Minimal Atlas Export Spec

Target: **≥95% quality retention** at **≤50% token size**.

## Session envelope (send once after scan)

```
ATLAS_SESSION v1
repo: {name}
graph_health: {label}
modules: {n}  edges: {e}
top_subsystems: [max 5]
top_hubs: [max 3, module + fan_in]
top_risks: [max 3, module only]
confidence_cap: {low|medium|high}
```

Token budget: **≤350** (replaces repeated compact+prose).

## Per-question delta by workflow

### build
- **Include (A):** goal, files_to_inspect_first (max 5), what_may_break (max 5 importers), confidence, risk_level
- **Optional (B):** implementation_order (max 4), tests (max 3), domain concept name only
- **Omit (C+D):** domain understanding prose, repository evidence details, duplicate file lists, entry_points list, subsystem enumeration, rollback plan, safety footer, HOW TO USE boilerplate, trust block duplicate
- **Token budget:** ≤280

### investigate
- **Include (A):** symptom, most_likely_root_cause, top hypothesis + files (H1 only), confidence
- **Optional (B):** verification checklist (max 4), minimal fix (max 3 bullets), H2 hypothesis only
- **Omit (C+D):** H3+ hypothesis detail, how_to_disprove paragraphs, domain failure mode essays, repository evidence dump, safety footer, duplicate limitations
- **Token budget:** ≤320

### impact
- **Include (A):** target path, direct_impact (max 8), confidence, risk_level, semantic_label
- **Optional (B):** indirect_impact (max 5), top 2 evidence bullets
- **Omit (C+D):** what_probably_wont_break, architecture blast prose, generic test hints, subsystem lists beyond top 3, safety footer, recommended_verification boilerplate
- **Token budget:** ≤240

### understanding
- **Include (A):** top 5 subsystems, top 3 hub modules, direct answer sentence
- **Optional (B):** top 3 risk modules (name only)
- **Omit (C+D):** full subsystem dep lines, risk score reasons, preamble per tool, UNCERTAINTY/HOW TO USE blocks
- **Token budget:** ≤120

## Projected per-question tokens (minimal spec)

| Workflow | Current avg (P167) | Minimal spec | Reduction |
| --- | ---: | ---: | ---: |
| build | 1350 | 280 | 79% |
| investigate | 1450 | 320 | 78% |
| impact | 420 | 240 | 43% |
| understanding | 65 | 80 | — (already compact) |

Plus **350 tokens once** per session (not per question).

## Example: FastAPI build export (measured 1,432 tokens → minimal ~280)

**Keep:**
```
Goal: add rate limiting
Concept: rate_limiting (source-backed)
Confidence: medium-high
Files: fastapi/applications.py, fastapi/routing.py, fastapi/middleware/asyncexitstack.py
May break: fastapi/__init__.py, fastapi/dependencies/utils.py (5 max)
```

**Drop:** concept_understanding paragraph, repository evidence block, duplicate MUST/LIKELY lists, rollback, verification essay, architectural risk scores.

**Measured duplication:** same 5 files appear **4×** in full export (MUST inspect, likely change, inspect first, implementation order).