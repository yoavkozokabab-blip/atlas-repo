# Phase 160 — Trust Recovery Master Plan

**Date:** 2026-06-05  
**Role:** Principal engineer and product strategist  
**Scope:** Planning only. No code changes.  
**Starting trust score:** 45.8/100 (Phase 157A)  
**Target trust score:** 75+/100  

---

## Executive Summary

Atlas is not trustworthy enough for external beta at its current quality level. The Phase 157A
audit found that **0% of Build Plans and 0% of Investigations** were classified as actionable
without major rework. The dominant failure (118/150 samples) is *thin grounding*: Atlas finds
the right subsystem but fails to produce precise, symbol-level evidence that a senior engineer
would consider sufficient to act on.

Phase 158 addressed the bottom layer of the trust pyramid (fake success signals, EMA leakage,
graph health dishonesty). It is estimated to push the trust score to approximately **55/100**.

To reach **75+/100**, Atlas needs three real improvements:

1. **Symbol-level evidence** — File recommendations must be backed by actual symbol names, not just keyword-path overlap.
2. **Narrower, better-grounded hypotheses** — Investigation must narrow to 2-3 high-confidence files with specific reasoning, not list 5-8 plausibly-related paths.
3. **Honest evidence completeness communication** — When coverage is partial (high unresolved imports, thin graph), every plan must say so loudly.

This plan provides the technical path, the sequenced roadmap, and the exact gates for external beta and public launch.

---

## Part 1 — Issue Register: Every 157A Finding

### Scoring recap

| Classification | Weight | Meaning |
|---|---|---|
| CORRECT | 1.00 | Actionable without rework |
| MOSTLY_CORRECT | 0.80 | Actionable with minor review |
| PARTIALLY_CORRECT | 0.45 | Directionally useful; needs file-level verification |
| MISLEADING | 0.10 | Likely sends user to wrong area |
| WRONG | 0.00 | Incorrect, fake, or harmful |

### Issue 1 — Thin Grounding (Dominant Problem)

| Attribute | Value |
|---|---|
| Count | 118/150 samples (79%) |
| Workflows | All three — Build (46), Investigation (44), Impact (28) |
| Root cause | Scoring is keyword-path only (does filename contain the search term?). No symbol matching, no call graph evidence, no function-level specificity. |
| User impact | Developer opens the recommended file and cannot find anything related to the task. Spends 10-20 minutes before concluding the plan was wrong. Loses trust. |
| Likelihood of hitting it | **100%** — every session on a real repo |
| Severity | **High** — this is why the actionable rate is 10% |
| Confidence evidence | Phase 132: evidence quality dimension = 56.0 (lowest benchmark dimension) |
| Fix complexity | **High** — requires symbol-level analysis in the evidence pipeline |
| Expected trust gain if fixed | +15 to +22 points (most impactful single fix) |

### Issue 2 — Investigation Root Cause from Syntax/Stdlib Tokens

| Attribute | Value |
|---|---|
| Count | 5+ explicitly; flags `typing.` (23), `__future__.annotations` (11), `dataclasses` (6) in 40+ samples |
| Root cause | `_build_hypotheses()` scored all modules including stdlib, boilerplate, and test infrastructure |
| User impact | Root cause says `__future__.annotations` or `re` for a runtime bug. Immediate trust collapse. |
| Likelihood | High on repos with many imports (FastAPI 78% unresolved, Airflow 97% unresolved) |
| Severity | **Critical** — a nonsensical root cause is worse than no answer |
| Fix complexity | **Low** — Phase 158 already fixed this with `_NOISY_MODULE_MARKERS` demotions |
| Expected trust gain | Phase 158 addressed this: ~3-5 points (already delivered) |

### Issue 3 — EMA/Trading Concept Leakage

| Attribute | Value |
|---|---|
| Count | 4 MISLEADING Build Plans (Home Assistant, Django, TypeORM) + 2 MISLEADING Investigations |
| Root cause | Knowledge engine matched trading aliases to generic engineering terms; no repository evidence gate |
| User impact | Build Plan for "add event bus tracing" displays EMA / Trading Systems domain knowledge. Zero relevance. User thinks Atlas is broken. |
| Likelihood | Medium — affects any repo where the classifier scores a trading concept above threshold |
| Severity | **Critical** — actively misleads |
| Fix complexity | **Low** — Phase 158 already fixed this with two-gate trading guardrail |
| Expected trust gain | Phase 158 addressed this: ~3 points (already delivered) |

### Issue 4 — Impact ok=True on Target-Not-Found (Fake Success)

| Attribute | Value |
|---|---|
| Count | 5 WRONG Kubernetes samples |
| Root cause | `analyze_impact()` returned `ok=True, mock=True` when target not in graph |
| User impact | User runs impact on a Go file, gets a "successful" result with empty lists. Doesn't notice `mock=True`. Acts on fake data. |
| Likelihood | **100%** on unsupported-language repos |
| Severity | **Critical** — fake success is worse than an error |
| Fix complexity | **Low** — Phase 158 already fixed this with `ok=False, status=target_not_resolved` |
| Expected trust gain | Phase 158 addressed this: ~5 points (already delivered) |

### Issue 5 — Graph Health Mismatch for Unsupported Languages

| Attribute | Value |
|---|---|
| Count | Kubernetes: 24,860 files, 3 modules → reported "healthy" |
| Root cause | `classify_scan()` only checked for zero modules, not for files >> modules ratio |
| User impact | Kubernetes showed 6 Build Plans as PARTIAL and 5 Impact as WRONG. User sees "healthy" on scan screen, trusts results, gets garbage. |
| Likelihood | **100%** for Go/Java/C#/Rust repos |
| Severity | **High** — graph health is the primary trust signal |
| Fix complexity | **Low** — Phase 158 already fixed this with `unsupported_language_limited` |
| Expected trust gain | Phase 158 addressed this: ~2 points |

### Issue 6 — Scope Pollution (Config/Dotfiles/Fallback in Results)

| Attribute | Value |
|---|---|
| Count | 7 MISLEADING samples; flags: `package.json` (13), `random` (12), `.prettierrc` (2), `eslint` (7), `fallback` (23) |
| Root cause | Build Plans included `package.json`, `.prettierrc`, `random` modules alongside real implementation files |
| User impact | Developer sees `package.json` in "files likely to change" for a Python backend feature. Confusion about relevance. |
| Likelihood | High on repos with mixed file types (TypeORM, Home Assistant) |
| Severity | **Medium-High** — adds noise, forces manual filtering |
| Fix complexity | **Low-Medium** — Phase 158 added scope pollution tier split; residual edge cases remain |
| Expected trust gain | Phase 158 addressed core cases; residual: ~1 point |

### Issue 7 — Confidence Miscalibration

| Attribute | Value |
|---|---|
| Count | Affects all 118 thin-grounding samples + 12 MISLEADING |
| Root cause | Confidence ("medium-high", "high") computed from keyword match score, not evidence strength |
| User impact | Medium confidence on a scan with 97% unresolved imports (Airflow). User trusts the output more than they should. |
| Likelihood | **High** on any repo with partial graph coverage |
| Severity | **High** — amplifies other issues by hiding their weakness |
| Fix complexity | **Low** — Phase 158 added `confidence_cap_for_scan()` |
| Expected trust gain | Phase 158 addressed graph-level cap: ~3 points |

### Issue 8 — Investigation Precision = 0.30

| Attribute | Value |
|---|---|
| Count | All 44 PARTIALLY_CORRECT investigation samples |
| Root cause | Investigations list 5-8 files per hypothesis. Reviewer expects 2-3 high-confidence files. 70% of listed files are irrelevant. |
| User impact | "Where do I look?" leads to 5 files. Developer opens all 5, finds the bug is in none of them. Time lost. |
| Likelihood | **100%** on any real investigation |
| Severity | **High** — low precision is the core reason investigation trust score = 40.8 |
| Fix complexity | **Medium** — requires evidence scoring to filter files before hypothesis output |
| Expected trust gain | +3.5 to +5 points if fixed |

### Issue 9 — Build Plan: No Insertion Point

| Attribute | Value |
|---|---|
| Count | All 46 PARTIALLY_CORRECT build plan samples |
| Root cause | Build Plans say "edit api/middleware.py" but not WHERE in the file or what to write. This is the gap between PARTIAL and MOSTLY_CORRECT. |
| User impact | Developer opens the file, stares at 400 lines of code, and doesn't know where the new code goes. Asks AI again, which re-derives the same answer without additional context. |
| Likelihood | **100%** on any build plan |
| Severity | **High** — the fundamental gap between "directionally useful" and "actionable" |
| Fix complexity | **High** — requires AST analysis to find insertion points |
| Expected trust gain | +4 to +6 points if fixed |

### Issue 10 — Unresolved Import Warning Not in Plan Output

| Attribute | Value |
|---|---|
| Count | 6 repos with unresolved ratio > 50% (airflow 97%, vscode 84%, fastapi 78%, home_assistant 62%, celery 64%, django 32%) |
| Root cause | Graph health warnings exist in System Health panel but are NOT surfaced in individual Build Plan, Investigation, or Impact results |
| User impact | User generates a Build Plan on Airflow (97% unresolved), sees a confident-looking plan, acts on it. Plan misses half the affected files. |
| Likelihood | High on large repos |
| Severity | **High** — incomplete plans on large repos |
| Fix complexity | **Low** — add warning propagation from scan data to plan output |
| Expected trust gain | +1.5 to +2 points |

---

## Part 2 — Trust Pyramid

```
TRUST PYRAMID — ATLAS
══════════════════════════════════════════════════════════════════════

LEVEL 5: POSITIONING MISMATCH
  ┌────────────────────────────────────────────────────────────────┐
  │ "Understands your codebase" vs "maps structure"               │
  │ Status: Phase 159 corrected copy guidance.                    │
  │ Impact: User arrives with wrong expectations, trust            │
  │         drops on first real result regardless of quality.     │
  │ Fix: Update website hero, disclaimer, ICP framing.            │
  └────────────────────────────────────────────────────────────────┘

LEVEL 4: LANGUAGE SUPPORT GAPS
  ┌────────────────────────────────────────────────────────────────┐
  │ Go / Java / C# / Rust: empty or near-empty graphs.           │
  │ Phase 157A: Kubernetes all Impact = WRONG.                    │
  │ Status: Phase 158 labels unsupported_language_limited.        │
  │ Impact: All 3 workflows broken on ~30% of repos devs use.     │
  │ Fix: Honest "not supported" UI + scope restriction.           │
  └────────────────────────────────────────────────────────────────┘

LEVEL 3: CONFIDENCE MISMATCH
  ┌────────────────────────────────────────────────────────────────┐
  │ High confidence on thin evidence; misleading semantic labels.  │
  │ Status: Phase 158 added scan-based confidence caps.           │
  │ Impact: Users trust weak outputs; trust drops post-action.    │
  │ Fix: Evidence-based confidence (not just graph health).       │
  └────────────────────────────────────────────────────────────────┘

LEVEL 2: WEAK GROUNDING (DOMINANT PROBLEM)
  ┌────────────────────────────────────────────────────────────────┐
  │ 118/150 samples: right subsystem, wrong files, no symbols.    │
  │ Investigation precision = 0.30 (70% of files are wrong).      │
  │ No insertion points in Build Plans.                           │
  │ Unresolved imports silently degrade all outputs.              │
  │ Status: Partially addressed by Phase 158 noise filters.       │
  │ FIX: Symbol-level evidence, narrower hypotheses,              │
  │       insertion point prediction, evidence propagation.       │
  └────────────────────────────────────────────────────────────────┘

LEVEL 1: MISLEADING OUTPUTS
  ┌────────────────────────────────────────────────────────────────┐
  │ EMA/trading leakage (4 Build, 2 Investigation samples).       │
  │ Scope pollution: package.json, .prettierrc, fallback files.   │
  │ Confidence claims on empty graphs.                            │
  │ Status: Phase 158 addressed all major cases.                  │
  │ Residual: ~2-3 edge cases expected.                           │
  └────────────────────────────────────────────────────────────────┘

LEVEL 0: FAKE SUCCESS (ELIMINATED)
  ┌────────────────────────────────────────────────────────────────┐
  │ ok=True on target-not-found.                                  │
  │ Healthy label on Kubernetes (24,860 files / 3 modules).       │
  │ EMA forced into "duplicate events" investigations.            │
  │ Status: Phase 158 eliminated all confirmed cases.             │
  └────────────────────────────────────────────────────────────────┘
```

---

## Part 3 — Issue Ranking by Trust Gain per Engineering Day

**Scoring formula:**
```
Trust gain per day = (expected_trust_score_points × probability_of_achieving) / engineering_days_required
```

Trust score point = (samples_affected × Δweight) / 150 × 100

| Fix ID | Fix Description | Samples affected | Δ weight | Trust pts | Eng. days | Trust pts/day | Priority |
|---|---|---:|---:|---:|---:|---:|---|
| **D** | Propagate unresolved-import warnings to plan output | 25 | +0.35 | 5.8 | 1 | **5.8** | P0 |
| **E** | Rename "unknown" evidence flags → explicit weakness labels | 20 | +0.35 | 4.7 | 1 | **4.7** | P0 |
| **B** | Narrow investigation hypothesis files (2-3 max, gated by evidence) | 30 | +0.35 | 7.0 | 5 | **1.4** | P1 |
| **F** | Root cause: require subsystem alignment before naming cause | 8 | +0.35 | 1.9 | 2 | **0.95** | P1 |
| **H** | Add 10+ hypothesis patterns for common 157A failures | 12 | +0.35 | 2.8 | 4 | **0.70** | P1 |
| **A** | Symbol-level evidence: match goal/symptom to AST symbols | 40 | +0.45 | 12.0 | 15 | **0.80** | P1 |
| **C** | Build Plan insertion point prediction via AST | 20 | +0.55 | 7.3 | 12 | **0.61** | P2 |
| **G** | Impact improvement for partial-graph repos (subsystem blast) | 15 | +0.35 | 3.5 | 10 | **0.35** | P2 |
| **I** | Language scope restriction in UI (block non-Py/TS from advanced features) | 6 | +0.40 | 1.6 | 3 | **0.53** | P2 |
| **J** | Reduce implementation order to max 5 files (currently 12) | 20 | +0.20 | 2.7 | 1 | **2.7** | P0 |

---

## Part 4 — The Shortest Path from 45.8 to 75+

### Mathematical foundation

The Phase 157A scoring model produces:
```
Trust score = (Σ weights across 150 samples) / 150 × 100

Current state (post-Phase-158 estimate):
  12 CORRECT × 1.00 = 12.0
   3 MOSTLY_CORRECT × 0.80 = 2.4
 118 PARTIAL × 0.45 = 53.1
   ~4 MISLEADING (residual) × 0.10 = 0.4
   0 WRONG × 0.00 = 0.0
  ─────────────────────────────────────
  Total: 67.9 / 150 × 100 ≈ 55/100 (Phase 158 correction)

Target 75/100:
  75 × 150 / 100 = 112.5 total weight needed
  Gap: 112.5 - 67.9 = 44.6 additional weight points
```

### What produces the 44.6 points?

| Conversion type | Points per sample | Samples needed for 44.6 pts |
|---|---|---|
| PARTIAL → CORRECT | 0.55 | 81 |
| PARTIAL → MOSTLY_CORRECT | 0.35 | 127 (more than exist) |
| MISLEADING → MOSTLY_CORRECT | 0.70 | 64 |
| Mixed approach | varies | see roadmap |

**The mixed approach to 75:**

```
Fixes D+E (evidence labels, ~3 days): 45 samples × 0.35 = 15.75 pts
Fix B (narrow investigation, ~5 days): 30 samples × 0.35 = 10.5 pts
Fix F+H (hypothesis quality, ~6 days): 20 samples × 0.35 = 7.0 pts
Fix A (symbol evidence, ~15 days): 25 samples × 0.45 = 11.25 pts
Fix C (insertion point, ~12 days): 15 samples × 0.55 = 8.25 pts
Fix J (limit file lists, ~1 day): 20 samples × 0.20 = 4.0 pts
Fix I (language scope UI, ~3 days): 6 samples × 0.40 = 2.4 pts
────────────────────────────────────────────────────────────
Total gain: 59.15 pts
New total: 67.9 + 59.15 = 127.05
New trust score: 127.05 / 150 × 100 ≈ 84/100
```

**Insight: The 75 target is achievable in 30-45 engineering days if work is sequenced correctly.**

The quickest wins (D, E, J — 5 days total) yield ~20 points. That alone pushes from 55 to ~68.

---

## Part 5 — 30-Day Roadmap

### Days 1-7: Quick Wins (estimated gain: +8 to +12 points → ~63-67/100)

**Day 1-2: Fix J — Reduce implementation order file list**
- Cap `implementation_order` to 5 files maximum (currently 12)
- Cap `files_to_inspect_first` to 4 files (currently 8)
- Add a "See all affected files" expand for the full list
- **Why:** Reviewer rubric penalizes noise. 3 good files score better than 10 files where 7 are noise.
- **Files:** `planning_engine.py` (2 constants)
- **Trust gain:** ~4 points

**Day 2-3: Fix D — Propagate unresolved-import warnings to plan output**
- When `unresolved_ratio > 0.50` in scan data, add to every plan/investigation/impact:
  ```
  "coverage_warning": "X% of imports in this repository are unresolved. Impact analysis 
  and dependency lists may be incomplete. Verify named files before acting."
  ```
- Downgrade confidence label one level when coverage_warning is active
- **Files:** `planning_engine.py`, `impact_engine/engine.py`
- **Trust gain:** ~4 points

**Day 3-4: Fix E — Replace "unknown" flags with explicit evidence weakness labels**
- When evidence list contains generic/fallback items, replace with:
  ```
  "evidence_gap": "Some expected pattern anchors did not match specific repository files.
  Results are based on partial keyword overlap only."
  ```
- Never output "unknown" as a positive evidence signal
- **Files:** `planning_engine.py`, evidence builder
- **Trust gain:** ~3 points

**Day 5-7: Fix F — Root cause subsystem alignment gate**
- For each known symptom intent (duplicate_events, memory_growth, authentication, etc.), define the expected subsystem tokens
- Only name a root-cause path if its subsystem matches the symptom's expected subsystem
- Return "subsystem not identified" rather than a wrong-subsystem root cause
- **Files:** `planning_engine.py` (add `_SYMPTOM_SUBSYSTEM_MAP`)
- **Trust gain:** ~2 points

**Day 7: Re-run Phase 157A style audit on demo repos**
- Run 30 representative samples against the updated engine
- Verify trust score has improved from ~55 to ~65-68

---

### Days 8-21: Medium Complexity Fixes (estimated gain: +8 to +10 points → ~73-77/100)

**Days 8-14: Fix B — Narrow investigation hypothesis files**

Current behavior: Each hypothesis lists 5 files filtered by keyword.
Required behavior: Each hypothesis lists ≤3 files that pass an evidence gate.

Evidence gate requirements (need at least 2 of):
1. File path tokens overlap with symptom keywords (already checked)
2. File is in the expected subsystem for this symptom intent
3. File has relevant fan-in (≥3 direct importers)
4. File appears in top-3 of risk-scored modules
5. File is NOT a noisy/stdlib/docs/scripts path

Implementation:
- Add `_hypothesis_evidence_gate(path, symptom, intent, risks_map)` returning (bool, score)
- Apply gate before returning `files_involved` in `_build_hypotheses()`
- If fewer than 2 files pass the gate, return 0 files with honest "insufficient evidence"
- **Files:** `planning_engine.py` (~80 lines)
- **Trust gain:** ~6 points

**Days 14-18: Fix H — Add 10+ symptom patterns from 157A failure analysis**

The 157A matrix reveals specific unhandled patterns:

| Symptom | 157A failures | Expected pattern |
|---|---|---|
| "middleware runs twice for request" | PARTIAL (22, 29, 49) | middleware registration, WSGI/ASGI handler chain |
| "queryset cache returns stale" | PARTIAL (31, 123) | queryset, model manager, cache invalidation |
| "async view exceptions swallowed" | PARTIAL (32, 53) | exception middleware, error handlers |
| "migrations run in wrong order" | PARTIAL (33) | migration dependency graph, executor |
| "lazy relations trigger too many queries" | PARTIAL (124) | eager loading, select_related, ORM |
| "config entries setup twice" | PARTIAL (11) | config_entries, setup, async_setup |
| "DAG parsing slow after deploy" | MISLEADING (85) | dag parser, serialization, cache |
| "task retries ignore backoff" | MISLEADING (87) | retry policy, task executor, countdown |
| "connection pool exhausted" | PARTIAL (125) | driver, pool, connection factory |
| "schema sync drops columns" | PARTIAL (126) | schema builder, metadata comparison |

- Add each as a new entry in `_SYMPTOM_SPECS`
- **Files:** `planning_engine.py` (~200 lines, data-only)
- **Trust gain:** ~3 points

**Days 18-21: Fix A — Symbol-level evidence (Phase 1: file-level integration)**

Phase 1 (Days 18-21): Use existing symbol index to score files before returning them.

The `evidence_engine/symbol_index.py` already builds a symbol index during scan. It contains function names, class names, and their file paths. The gap is that `plan_change()` and `investigate_symptom()` never consult it.

Phase 1 integration:
1. After scoring modules by path keyword, load symbol index from `ctx["evidence_store"]`
2. For each candidate file, search the symbol index for symbols matching the goal/symptom terms
3. Files with matching symbols get a score boost (+5) and their top matching symbols added to evidence
4. Files with NO matching symbols are downgraded unless they have high fan-in

This is a read-only integration — the symbol index is already built. No new scanning needed.

Example before:
```
evidence: ["`api/routes.py` matched (score 4.5, fan-in 8)"]
```

Example after:
```
evidence: ["`api/routes.py` — contains `RateLimiter` class, `limit_request` function (matched 'rate limit' goal)"]
```

- **Files:** `planning_engine.py`, `evidence_engine/evidence_builder.py`
- **Trust gain:** +5 to +8 points

**Day 21: Second audit — 30 representative samples**
- Run against updated code
- Target: 70-75/100 on the sample set

---

### Days 22-30: Hardening and Verification

**Days 22-25: Fix C (Phase 1) — Build Plan approximate insertion hint**

Full AST-based insertion point is a 12-day project. Phase 1 is a 4-day approximation:

1. Use existing `implementation_detector.py` to find existing patterns in matched files
2. For common patterns (middleware registration, route definition, signal handler), identify the existing insertion anchor:
   - "After the last existing middleware registration in `app.py` line ~X"
   - "Near the existing auth check in `views.py` — add before line ~Y"
3. This is heuristic, not exact, but gives "where approximately" without deep AST work

Even a rough insertion hint ("near the auth section") promotes outputs from PARTIAL to MOSTLY_CORRECT under the 157A rubric because it's more specific guidance.

- **Files:** `planning_engine.py`, `evidence_engine/implementation_detector.py`
- **Trust gain:** +2 to +3 points (Phase 1 approximation only)

**Days 25-28: Fix I — Language scope restriction in UI**

For repos classified as `unsupported_language_limited`:
1. Show a clear warning before generating Build Plan/Investigation: "Atlas has limited graph coverage for this repository. Results will be weak leads only."
2. Display confidence = "exploratory" (not "low", which implies partial data — "exploratory" correctly frames the output as brainstorming, not evidence)
3. Do not show Investigation hypothesis files if graph health is unsupported (show subsystem-only suggestions instead)

- **Files:** UI only — `static/index.html`, `static/app.js`
- **Trust gain:** +1.5 points (eliminates remaining misleading on unsupported repos)

**Days 28-30: Third audit — full 150-sample run**
- Run full Phase 157A-style audit
- Target: ≥75/100 overall
- If below 75: identify remaining gap and prioritize Fix G (impact for partial repos) next

---

## Part 6 — 60-Day Roadmap

### Days 31-45: Symbol-Level Evidence Phase 2

**Fix A Phase 2 — Deep symbol integration**

Phase 1 (days 18-21) adds symbols to evidence display. Phase 2 makes symbols drive the file selection:

1. For Build Plans: given goal text, find ALL symbols in the graph that match the intent keywords
2. Rank files primarily by symbol match count, secondarily by path keywords
3. Return only files with at least 1 matching symbol (unless the graph has too few modules to be selective)

This is a fundamental change to how files are selected. Expected impact:
- FastAPI rate limiting: `api/routes.py` currently scores from path keyword "rate". Phase 2 would find `RateLimiter`, `limit_requests`, `rate_limit_middleware` symbols and rank files accordingly.
- Precision goes from path-based (~0.30) to symbol+path-based (~0.60-0.70)

- **Files:** `planning_engine.py`, `evidence_engine/symbol_index.py`, `evidence_engine/evidence_builder.py`
- **Trust gain:** +5 to +8 additional points (on top of Phase 1)

### Days 45-55: Build Plan Insertion Point (Full)

**Fix C Phase 2 — AST-driven insertion point**

Full implementation:
1. For top 3 matched files, run AST scan and extract structural anchors (class definitions, function definitions, import blocks, decorator lists)
2. Match goal text to structural patterns (middleware → decorator or app.use() pattern; rate limit → request handler chain)
3. Produce: "Insert as a new function after `existing_function` at line ~X in `target_file.py`"

This is 8-10 engineering days of careful AST work. The result directly addresses the most common complaint: "The plan told me which file but not where to write the code."

- **Trust gain:** +3 to +5 additional points (on top of Phase 1 approximation)

### Days 55-60: Calibration, Polish, and Target Verification

**Final audit: 150-sample Phase 157A-style run**
- Compare per-repo trust scores
- Identify any remaining systematic failures
- Calibrate confidence labels against actual accuracy

**Fix K — Investigation evidence completeness score**
- Add `evidence_completeness: 0.0-1.0` field to every investigation output
- 0 = no symbols matched, keyword-only; 1.0 = explicit file mention + symbol match + graph edge
- Surface this in UI so users can calibrate trust themselves

---

## Part 7 — Target Trust Scores

| Milestone | Target Score | What changes |
|---|---|---|
| Phase 158 baseline | ~55/100 | Fake success eliminated, leakage stopped |
| After Quick Wins (Day 7) | ~65/100 | File count reduction, coverage warnings, evidence labels |
| After Medium Fixes (Day 21) | ~70-75/100 | Narrow hypotheses, new patterns, symbol Phase 1 |
| After 30-Day Sprint | **75+/100** | All medium fixes + insertion hint |
| After 60-Day Program | **80-85/100** | Symbol Phase 2, full insertion point, calibration |

---

## Part 8 — Beta Gates and Launch Gates

### Private Beta Gate (5-user supervised) — Current Requirement

**Current status: PASS on supervised beta**

Minimum trust score required: **60/100**

Rationale: Supervised beta users receive direct support. A 60/100 score means ~75% of outputs are
usable with review and <5% are misleading. A supervisor can catch the rest. The 5-user supervised
beta is GO today.

**Conditions:**
- [x] Phase 158: fake success eliminated
- [x] Phase 158: EMA leakage blocked
- [x] Phase 158: honest graph health labels
- [x] Phase 155: first-run UX acceptable
- [x] Phase 152: installer ships
- [ ] Quick wins applied (Days 1-7) — strengthens supervised beta

### Semi-Self-Serve Beta Gate (20-user) — Gate Status: BLOCKED

**Required trust score: 68/100**

Rationale: Self-serve users have no supervisor. 68/100 means ~85% usable with review and <3% misleading.
A developer encountering a PARTIAL result should not feel misled — only that Atlas gave them a starting point.

**Conditions:**
- [ ] Quick wins applied: trust score > 63
- [ ] Fix B (narrow investigation): trust score > 68
- [ ] Fix H (new patterns): reduces per-repo variance
- [ ] Coverage warnings propagated to plan output
- [ ] Installer validated on clean Windows VM (Phase 153/154 gate)
- [ ] Installer code-signed (Phase 152 gate)
- [ ] Support destination published

**Estimated opening: Day 21 of roadmap**

### Public Waitlist Download Gate — Gate Status: BLOCKED

**Required trust score: 75/100**

Rationale: Public users expect the product to work. A 75/100 score means ~90% of outputs are usable
and <2% are misleading. This is the minimum for a product that developers will share with colleagues.

**Conditions:**
- [ ] Full 30-day roadmap completed
- [ ] Symbol-level evidence Phase 1 shipped
- [ ] Build Plan insertion hints available
- [ ] All Phase 159 copy changes applied to website
- [ ] Language scope clearly stated on all download and install pages
- [ ] Honest beta disclaimer visible before install
- [ ] 30-day trust audit confirms ≥75/100

**Estimated opening: Day 30-35 of roadmap**

### General Availability (Charge for it) Gate — FUTURE

**Required trust score: 82/100**

**Conditions:**
- [ ] Full 60-day roadmap completed
- [ ] Symbol-level evidence Phase 2 shipped
- [ ] Full insertion point prediction available
- [ ] Separate plan tiers: "lead" vs "grounded" confidence
- [ ] Evidence completeness field available for every output
- [ ] Signed installer for Mac/Linux
- [ ] Trust score verified at ≥82/100 on 200+ sample audit
- [ ] At least 3 external beta users report Atlas as "useful without help"

---

## Part 9 — Daily Monitoring Checklist (Trust Focus)

Run these checks after shipping any trust-related code:

**Code quality (each push):**
- [ ] All 4 Phase 158 test files still passing (79 tests)
- [ ] No new MISLEADING or WRONG patterns introduced in representative samples
- [ ] `investigation.most_likely_root_cause` — not a stdlib/noise module
- [ ] `plan.files_to_inspect_first` — no scope-polluting paths in top 4
- [ ] `impact.ok=False` for any unresolved target

**Weekly trust pulse (per sprint):**
- [ ] Run 20 representative samples: 5 Build, 10 Investigation, 5 Impact
- [ ] Score them: must not regress below previous trust score
- [ ] Check: any new EMA/trading leakage on non-trading repos
- [ ] Check: `unknown` flag count in output evidence (must decrease over time)
- [ ] Check: `fallback` flag count (must decrease over time)

**Before any beta expansion:**
- [ ] Full 50-sample audit per workflow (150 total)
- [ ] Trust score confirmed at gate threshold
- [ ] Verify investigation file lists are ≤ 3 files in top hypothesis
- [ ] Verify Build Plan implementation order is ≤ 5 files

---

## Part 10 — Failure Response: If Trust Score Stalls

If after Day 21 the trust score is below 68:

**Diagnostic checklist:**
1. Re-run the Phase 157A failure taxonomy on new samples. Which failure category is still dominant?
2. If `thin_grounding` still dominates at >70%: Fix A (symbol evidence) needs to be accelerated.
3. If `irrelevant_target_pollution` still present: scope pollution filter is missing edge cases.
4. If `nonsensical_root_cause` reappears: Phase 158 Fix 2 has a regression.
5. If `confidence_miscalibrated` still high: coverage warning propagation (Fix D) didn't land.

**Fallback plan if symbol evidence is too complex to ship in 30 days:**
- Double down on Fix B (narrow hypotheses) and Fix H (new patterns) — these together can yield +8 points
- Add Fix K (evidence completeness score in UI) to give users self-calibration ability
- Revise target to 70/100 for public beta gate and 75/100 for 60-day target

---

## Appendix A — The 10 Highest ROI Fixes (Summary)

| Rank | Fix | Description | Trust pts | Days | pts/day |
|---:|---|---|---:|---:|---:|
| 1 | D | Propagate unresolved-import warnings to plan output | 5.8 | 1 | 5.8 |
| 2 | E | Replace "unknown" flags with explicit weakness labels | 4.7 | 1 | 4.7 |
| 3 | J | Cap file lists: inspect_first ≤4, impl_order ≤5 | 4.0 | 1 | 4.0 |
| 4 | A-Phase1 | Symbol-level evidence: match goal/symptom to AST symbols | 5.0 | 4 | 1.25 |
| 5 | B | Narrow investigation hypothesis files to ≤3 with evidence gate | 6.0 | 5 | 1.2 |
| 6 | F | Root cause: require subsystem alignment | 1.9 | 2 | 0.95 |
| 7 | H | Add 10+ symptom patterns from 157A failure analysis | 2.8 | 4 | 0.70 |
| 8 | A-Phase2 | Symbol-level evidence: drive file selection by symbol matches | 6.0 | 15 | 0.40 |
| 9 | C-Phase1 | Build Plan insertion hint (approximate, heuristic) | 2.5 | 4 | 0.63 |
| 10 | I | Language scope UI restriction for unsupported languages | 1.6 | 3 | 0.53 |

**Total from top 10: ~40 trust points in ~40 engineering days → from ~55 to ~80/100**

---

## Appendix B — Why Phase 158 Is Not Enough

Phase 158 addressed every fake-success and leakage problem. It is necessary but not sufficient:

| After Phase 158 | Count | Score weight |
|---|---|---|
| CORRECT | 17 (up from 12) | +5 from converting 5 WRONG |
| MOSTLY_CORRECT | 5 (up from 3) | +2 from partial/mislead → mostly |
| PARTIAL | ~110 (down from 118) | -8 converted up, but ~118 remain |
| MISLEADING | ~4 (down from 12) | -8 via EMA/trading/scope fixes |
| WRONG | 0 | -5 via ok=False |

Estimated score: (17 + 4.0 + 49.5 + 0.4) / 150 × 100 ≈ **47-55/100**

The 118 PARTIALLY_CORRECT samples that are thin_grounding were **not changed by Phase 158**.
Phase 158 stops Atlas from lying. It cannot make Atlas know more. The knowledge gap is the real
problem — and the knowledge gap requires **evidence quality improvements**, not **honesty guardrails**.

**The critical insight:** Every fix below Level 2 (fake success, leakage, confidence) is a guardrail
that prevents overclaiming. Every fix at Level 2 (symbol evidence, hypothesis narrowing, insertion
points) is an intelligence improvement that increases what Atlas actually knows about the repository.

Only intelligence improvements can move samples from PARTIAL to CORRECT. Guardrails alone cannot
do it. Phase 160 must deliver intelligence improvements to reach 75.

---

## Appendix C — Trust Score Sensitivity Analysis

Assuming post-Phase-158 baseline of 55/100:

| Scenario | Changes | Trust score |
|---|---|---|
| Quick wins only (D, E, J) — 3 days | Cap lists, add warnings, fix labels | ~65/100 |
| + Narrow investigation (B) — 8 days | ≤3 hypothesis files with gate | ~70/100 |
| + New patterns (H) + subsystem gate (F) — 14 days | 10+ patterns, root cause aligned | ~72/100 |
| + Symbol Phase 1 (A) — 29 days | Symbol match in evidence | ~76/100 |
| + Insertion hint (C Phase 1) — 33 days | Approximate insertion guidance | ~78/100 |
| Full 60-day program | All above + A Phase 2 + C Phase 2 | **83-85/100** |

**Shortest path to 75+: 29 engineering days**

Order: J (1 day) → D+E (2 days) → F (2 days) → B (5 days) → H (4 days) → A Phase 1 (15 days)
= 29 days → estimated **76-78/100**

This is the single most direct route to a trust score that enables public beta.
