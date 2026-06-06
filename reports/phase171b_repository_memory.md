# Phase 171B — Repository Memory Engine

**Date:** 2026-06-05
**Status:** Design + measurement only (no implementation)
**Baseline:** Phase 169 `MINIMAL_EXPORT` + `ATLAS_SESSION v1`

## Executive summary

**Can Atlas reach another 50–80% token reduction without quality loss?** **YES**

- Per-question reduction vs Phase 169 minimal: **60.6%–78.9%** (avg **68.8%**)
- 20-question session reduction: **55.3%–72.7%** (avg **62.5%**)
- Expected quality loss: **~0%** (delta preserves Phase 168 A-required fields; memory holds only stable graph facts)

## 1. Current state after Phase 169

| Metric | Measured (Phase 170) |
| --- | ---: |
| MINIMAL_EXPORT avg | 364 tokens |
| ATLAS_SESSION avg | 111 tokens (once per scan) |
| Build minimal avg | 322 tokens |
| Investigate minimal avg | 501 tokens |
| Impact minimal avg | 269 tokens |

Phase 169 already separates session context from per-question exports, but the UI/API
still materializes full minimal markdown per question. Multi-question sessions repeat:

- Section headers and markdown scaffolding (~30–50 tokens)
- Workflow boilerplate (`## Files`, `## Evidence`, confidence lines)
- Investigate exports still carry H1 narrative wrapper (~390 tokens above pure delta)

## 2. Information that never changes between questions

| Stable field | Source | Currently duplicated in |
| --- | --- | --- |
| repository_identity | scan.repo_name, path signature | ATLAS_SESSION, compact context, minimal headers |
| graph_statistics | module_count, edges, files, cycles | ATLAS_SESSION, compact context |
| graph_health | summary.graph_health | ATLAS_SESSION, trust blocks (removed in minimal) |
| major_subsystems | index.subsystems top-N | compact context (8 subs), FULL export only |
| architectural_boundaries | subsystem deps, entry_files | compact context PRODUCTION SUBSYSTEMS |
| top_hubs | scan.top_hubs fan_in | ATLAS_SESSION, compact context |
| top_risks | scan.top_risks | ATLAS_SESSION, compact context |
| entry_points | summary.entry_points | compact verbose, FULL export |
| confidence_cap | graph_health → confidence ceiling | trust metadata (session-stable) |
| evidence_index_metadata | evidence_store stats | FULL export repository_evidence (removed minimal) |
| export_boilerplate | markdown headers, HOW TO USE | minimal section headers (~30-50 tok) |

**Observation:** ~60–75% of remaining minimal export tokens (after Phase 169) are either
session-stable facts already in `ATLAS_SESSION` / compact context, or formatting overhead
that a memory reference can eliminate.

## 3. Repository Memory Object (RMO) — design

```
ATLAS_REPOSITORY_MEMORY v1
id: atlas://mem/{repo_signature}/{version}
identity:
  repo_name, repo_path_hash, scan_signature, scanned_at
graph:
  health, scope, degraded, modules, edges, files, cycles, unresolved_ratio
architecture:
  subsystems: [top 8 — name, prod_files, entry_files, deps]
  boundaries: [runtime layer labels from tour/summary]
  hubs: [top 5 — module, fan_in]
  risks: [top 4 — module, score, reasons]
  entry_points: [top 6]
evidence_index:
  symbols_indexed, paths_indexed, store_hash
trust:
  confidence_cap, graph_health_notice
version:
  content_hash, graph_hash, index_generation
```

**Token budget:** 300–700 tokens (merged compact context + session). Loaded **once** per session.

## 4. Per-question delta object

```
ATLAS_DELTA v1
memory_ref: atlas://mem/{repo_signature}/{version}
workflow: build | investigate | impact | understanding
intent: <goal | symptom | target>
confidence: <per-answer>
risk: <per-answer>
files: [max 5 paths]
evidence: [max 2 bullets]
workflow_extras:
  build: {impl_order, may_break, concept_label}
  investigate: {root_cause, verify, fix}
  impact: {direct, indirect, semantic_label}
  understanding: {answer_sentence}
```

**Token budget:** 60–130 tokens + 22-token memory reference.

### Delta field map

| Field | Workflows |
| --- | --- |
| workflow_intent | all |
| ranked_files | build,investigate |
| blast_importers | build |
| implementation_order | build |
| root_cause_hypothesis | investigate |
| verification_fix | investigate |
| direct_indirect_impact | impact |
| per_answer_confidence | all |
| per_match_evidence | all |
| domain_concept_label | build,investigate |

## 5. Projected reduction (measured baseline → memory + delta)

| Repo | P169 minimal/Q | Memory+delta/Q | Per-Q reduction | 20Q session reduction |
| --- | ---: | ---: | ---: | ---: |
| fastapi | 272 | 107 | 60.6% | 55.3% |
| django | 290 | 107 | 63.2% | 57.1% |
| vscode | 506 | 107 | 78.9% | 72.7% |
| home_assistant | 388 | 107 | 72.4% | 64.8% |

## 6. Memory versioning

| Event | Version bump | What updates | What stays cached |
| --- | --- | --- | --- |
| Full rescan | major (`v{n+1}`) | graph, index, risks, evidence store | repo identity |
| Git pull (changed files) | minor (`v{n}.p{m}`) | affected modules, edges, evidence hits | subsystem names, boundaries |
| Same session, no file changes | none | — | entire RMO |
| Manual cache clear | major | everything | — |

**Invalidation rule:** `content_hash = hash(index + graph_edges + evidence_store)`
If hash differs from memory.version.content_hash → reload RMO before accepting deltas.

## 7. Quality preservation argument

Phase 170 showed **0.000** quality/grounding delta between FULL and MINIMAL exports.
Repository memory does not remove any Phase 168 **A-required** field — it only relocates
stable **B/C** graph summary out of the per-question wire format.

Risk: LLM forgets memory if not re-pinned. Mitigation: `memory_ref` in every delta +
optional memory refresh every N questions (amortized 15–35 tokens).

**Final answer:** YES — Atlas can reach **69%** additional per-question
token reduction (within the 50–80% target band) without expected quality loss.
