# Phase 162 — PARTIAL → CORRECT Conversion Strategy

**Date:** 2026-06-05  
**Role:** Principal engineer, staff architect, skeptical reviewer  
**Scope:** Analysis and strategy only. No code changes.  
**Evidence base:** Phase 157A, 158A, 160, 161  

---

## Premise: The Problem Has Shifted

Phases 158 and 161 solved the bottom two levels of the trust pyramid:

- **Fake success**: eliminated (`ok=False` on all unresolved targets)
- **EMA/trading leakage**: eliminated (two-gate guardrail)
- **Confidence inflation**: eliminated (`calibrate_confidence_cap` requires healthy graph + ≥2 grounded signals + resolved target for high confidence)
- **Graph health dishonesty**: eliminated (unsupported_language_limited, unified labels)
- **Misleading on battery**: 0%
- **Wrong on battery**: 0%

What remains is the harder and more honest problem:

> Atlas finds approximately the right area. It does not consistently provide the strongest and most useful answer.

The 157A sample audit found **118/150 outputs classified as PARTIALLY_CORRECT** with `thin_grounding`
as the failure category. Phase 158 and 161 did not change this number. They could not — because
thin grounding is not caused by leakage or dishonesty. It is caused by **insufficient evidence depth**.

This document is the engineering strategy for closing that gap.

---

## Task 1 — Why Outputs Are PARTIAL Instead of CORRECT

### Root Cause Analysis

The 157A rubric for the key classifications:

| Classification | Meaning in 157A rubric |
|---|---|
| CORRECT | Matched multiple **repo-specific** anchors with no hallucination markers |
| MOSTLY_CORRECT | Matched core expected anchors; evidence not complete enough for full trust |
| PARTIALLY_CORRECT | Some expected anchors matched; **output was thin or noisy** |
| MISLEADING | Wrong area, wrong concept, or dangerous confidence on weak evidence |

The gap between PARTIAL and MOSTLY_CORRECT is the difference between:
- "api/routes.py matched (score 4.5, fan-in 8)" ← thin
- "api/routes.py — contains `RateLimiter` class, `limit_request` function (matched goal)" ← specific

The gap between MOSTLY_CORRECT and CORRECT is the difference between:
- "Likely files: api/routes.py, api/middleware.py, services/auth.py" ← directional
- "Edit api/middleware.py at line 47, after `authenticate_request`. Add RateLimiter before response dispatch." ← actionable

---

### Category 1 — Path-Only Evidence (Dominant)

**Root cause:** `plan_change()` and `investigate_symptom()` score files by whether the path string
contains the search keyword. `api/rate_limit.py` scores high for "add rate limiting" because
`rate_limit` appears in the path. `api/middleware.py` may score low even though it contains the
class that MUST be edited — because the path string doesn't contain `rate_limit`.

**Frequency:** Affects 100% of Build Plan and Investigation samples (all 100 PARTIAL samples
in those two workflows).

**Impact:** The file list is directional but not precise. A developer opens `api/rate_limit.py`,
finds a constants file, and realizes the relevant code is in `api/middleware.py` which wasn't listed.

**Trust damage:** Medium per incident. Accumulates into "Atlas consistently points near the right
area but never to the exact file." Users develop a skeptical meta-habit of verifying every result
— reducing Atlas from a workflow aid to a starting-point search.

**What CORRECT looks like:** "api/middleware.py — contains `RateLimiterMiddleware` class with
`dispatch(request)` method (matched goal: rate limit, middleware, request)"

---

### Category 2 — Noisy File Lists (Systematic)

**Root cause:** The top-12 scored files are returned to the plan. When only 3-4 are genuinely
relevant, the remaining 8-9 act as noise that reduces the reviewer's confidence in the whole list.

**Frequency:** Phase 157A flags `unknown` in 107/150 samples. The `fallback` flag appears 23
times. These indicate that generic modules with weak evidence were included in output.

**Impact:** Developer sees 8 files. Opens 3 that are noise, concludes Atlas doesn't know the
codebase. Even if file #4 is correct, trust is already eroded.

**Trust damage:** High. The "needle in a haystack" effect makes partial results feel like
failures even when the correct file is present.

**What CORRECT looks like:** 3 files in Tier 1, all verified via symbol evidence. Reviewer
opens all 3, finds them all relevant, concludes Atlas nailed it.

---

### Category 3 — No Insertion Point in Build Plans

**Root cause:** Build Plans say "edit `api/middleware.py`" but not WHERE in the file or what
to add. This is the canonical gap between PARTIAL and actionable.

**Frequency:** 100% of Build Plan samples (46 PARTIAL). Zero insertion points provided.

**Impact:** A developer with a 500-line middleware file stares at it and cannot determine where
to add the rate limiter without re-deriving the context that Atlas already had. They use their
AI coding tool from scratch, making Atlas redundant.

**Trust damage:** Moderate. The output is directionally correct but incomplete in the critical
"so what do I actually do?" dimension.

**What CORRECT looks like:** "Insert after `authenticate_request` middleware registration at
`api/middleware.py:47`. Rate limiting typically wraps the request dispatch before auth checks."

---

### Category 4 — Investigation Hypothesis Imprecision

**Root cause:** Investigation hypotheses list files based on keyword overlap with the symptom.
For "why does middleware run twice for one request", the hypothesis might list `middleware.py`,
`handler.py`, `request.py`, `apps.py`, and `utils.py` — 5 files for a symptom that traces to
a single registration pattern.

**Frequency:** 44/50 Investigation samples (88%) are PARTIAL. Precision = 0.30 in Phase 132
benchmark.

**Impact:** Developer opens 5 hypothesis files. Finds the bug in file #3. But spending time on
files #1, #2, #4, #5 creates friction and undermines the trust in the first hypothesis.

**Trust damage:** Very high for Investigation specifically. The whole value of investigation
is narrowing the search space. 5 files is better than 500, but a developer could grep for the
symptom keywords and get a similar result without Atlas.

**What CORRECT looks like:** One hypothesis, one file (or two with ranked confidence), and the
specific code path: "handler registration at `middleware.py:23` likely registers twice when
module is imported multiple times — check the `__init__.py` import chain."

---

### Category 5 — Missing Context Files in Impact

**Root cause:** Impact on well-supported Python/TypeScript repos already performs well (12/50
CORRECT in Impact). But for repos with high unresolved import ratios (Airflow 97%, FastAPI 78%,
VS Code 84%), the impact list misses files that the developer knows should be affected — because
those files import via unresolved paths.

**Frequency:** Affects 28/50 Impact samples that are PARTIAL. Most severe on large repos with
high unresolved ratios.

**Impact:** Developer changes a module, Atlas says "3 files affected." They merge, and 7 other
files break. Trust in Impact collapses.

**Trust damage:** Very high. Incorrect negative impact (false "nothing will break") is more
dangerous than incomplete positive impact. A missed importer causes a production incident.

**What CORRECT looks like:** "7 direct importers identified. Additionally, 31,640 unresolved
imports exist in this repository — the actual blast radius is likely larger. Manually verify
subsystems: scheduler, dag_parser, executor."

---

### Category 6 — Concept Evidence Without Symbol Grounding

**Root cause:** When the knowledge engine selects a concept (e.g., `rate_limiting`), it
surfaces the domain knowledge block (what rate limiting is, failure modes, etc.). But the
repo-mapping step (`map_to_repository`) scores files by path keywords in the concept's
`path_keywords` field — not by whether those files actually implement rate limiting logic.

**Frequency:** Contributes to all 46 Build Plan PARTIAL samples. Manifests as a well-structured
concept block with irrelevant "must_inspect" file suggestions.

**Impact:** Developer reads a conceptually accurate description of rate limiting, then follows
the file recommendations and finds a file that doesn't contain rate limiting code. Disconnect
between concept quality and repo mapping quality is jarring.

**Trust damage:** Medium. The domain knowledge itself is useful; the repo mapping undermines it.

---

### Summary Table

| Category | 157A samples | Fix type | Expected conversion |
|---|---:|---|---|
| Path-only evidence | ~100 | Symbol Evidence Phase 1-2 | PARTIAL → MOSTLY_CORRECT |
| Noisy file lists | ~80 | Symbol gate + file caps | PARTIAL → MOSTLY_CORRECT |
| No insertion point | ~46 | Insertion point prediction | PARTIAL → CORRECT |
| Investigation imprecision | ~44 | Symbol + call graph | PARTIAL → MOSTLY_CORRECT |
| Missing impact context | ~28 | Unresolved blast guidance | PARTIAL → MOSTLY_CORRECT |
| Concept without symbol | ~46 | Symbol-driven repo mapping | PARTIAL → MOSTLY_CORRECT |

---

## Task 2 — The Evidence Hierarchy

What creates correctness? Ranked by contribution to accurate output, highest to lowest:

```
EVIDENCE HIERARCHY FOR ATLAS OUTPUTS
══════════════════════════════════════════════════════════════════════

TIER A — GROUND TRUTH (makes CORRECT outputs)
────────────────────────────────────────────────────────────────────

1. SYMBOL EVIDENCE (highest individual contribution)
   
   Contribution: ~45% of what converts PARTIAL → CORRECT
   
   What it is: The actual function names, class names, method signatures
   in a file that match the goal or symptom.
   
   Why it matters: Symbols are the atomic unit of code. When Atlas can say
   "api/middleware.py contains RateLimiterMiddleware.dispatch(request)",
   a reviewer can immediately verify — open the file, check if the class
   exists, and confirm the evidence is grounded.
   
   Current status: Atlas HAS a symbol index (symbol_index.py). It is NOT
   used during plan_change() or investigate_symptom(). It IS used during
   target_resolver.py for impact (which is why Impact is the strongest
   workflow at 12/50 CORRECT).
   
   Gap: Build plans and investigations never query the symbol index.
   Fixing this is the single highest-impact engineering task.

2. CALL GRAPH / IMPORT EDGE EVIDENCE
   
   Contribution: ~25% of what converts PARTIAL → CORRECT
   
   What it is: Who imports what, with resolved edges. If X imports Y and
   Y imports Z, a change to Z affects both X and Y.
   
   Why it matters: Call graph evidence is STRUCTURAL PROOF. "api/routes.py
   imports api/middleware.py" is verifiable and unambiguous.
   
   Current status: Atlas uses import edges for Impact (finding importers).
   It ALSO uses edges for plan scoring (fan-in boost). But it does not
   follow call chains for Build Plans or Investigations — it only uses
   direct edges, not call paths.
   
   Gap: Following a 2-3 hop call chain ("X calls Y, Y calls the function
   you need to modify") would significantly improve hypothesis precision.

TIER B — STRONG SIGNAL (makes MOSTLY_CORRECT outputs)
────────────────────────────────────────────────────────────────────

3. FILE EVIDENCE (explicit path mention or high fan-in)
   
   Contribution: ~15% of correctness
   
   What it is: The user explicitly mentioned a file, or the file has
   unusually high fan-in (many importers), suggesting it is a hub.
   
   Why it matters: Explicit file mentions are ground truth from the user.
   High fan-in is a structural signal — hub files are likely relevant.
   
   Current status: Atlas already uses both. Fan-in boost exists in
   _score_modules(). Explicit_paths are promoted.
   
   Gap: Fan-in alone is not sufficient for correctness. A file can have
   100 importers and still be irrelevant (e.g., constants.py).

4. PATH EVIDENCE (keyword in filename/directory)
   
   Contribution: ~8% of correctness when used alone
   
   What it is: The file path contains a word matching the goal/symptom.
   "api/rate_limit.py" for "add rate limiting."
   
   Why it matters: Provides a first-pass filter that is usually better
   than random.
   
   Current status: This is Atlas's PRIMARY scoring mechanism today.
   Phase 157A shows that path-only evidence produces 100% PARTIAL, 0% CORRECT.
   
   Gap: Path evidence is necessary but deeply insufficient. "rate_limit.py"
   might be a constants file while the real implementation is in
   "middleware.py" which doesn't contain the keyword.

TIER C — WEAK SIGNAL (directional, not actionable)
────────────────────────────────────────────────────────────────────

5. IMPORT EVIDENCE (module-level, not call-level)
   
   Contribution: ~4% of correctness
   
   What it is: The file imports something related to the concept.
   A file that imports `RateLimiter` is likely to need modification.
   
   Current status: Not directly used in plan/investigation scoring.
   Available via evidence store but not queried.
   
   Gap: Import evidence is weaker than symbol evidence because a file
   can import a class without the import being relevant to the current change.

6. CONCEPT EVIDENCE (domain knowledge catalog match)
   
   Contribution: ~2% of correctness for grounding (high for framing)
   
   What it is: The goal text matches a curated concept in the knowledge
   catalog (rate_limiting, authentication, pub_sub, etc.).
   
   Why it matters: Concept matching drives the domain knowledge block,
   which provides context about what rate limiting IS and its failure modes.
   This context is genuinely valuable. But concept matching DOES NOT prove
   WHICH FILES in THIS REPO implement it.
   
   Current status: Used for both framing (domain knowledge) and repo
   mapping (path_keywords). The framing value is real; the repo-mapping
   value is weak without symbol grounding.
   
   Gap: Concept match + path_keyword scan should be the STARTING POINT
   for finding candidate files, then SYMBOL EVIDENCE confirms which ones
   are actually relevant.

7. HEURISTICS (fallback, least reliable)
   
   Contribution: Negative when dominating; slightly positive when supplementary
   
   What it is: General heuristics — high-risk files (high fan-in) and
   subsystem guessing based on repo structure.
   
   Current status: Used as a tiebreaker. When nothing else matches, fan-in
   dominates and produces high-coupling files that may not be relevant.
   
   Gap: Heuristics should never dominate. They should only appear when
   no higher-tier evidence exists, and should be labelled "heuristic lead"
   not "matched evidence."
```

### Contribution Estimate to Correctness

| Evidence type | Current use | Impact on PARTIAL→CORRECT | Implementation state |
|---|---|---|---|
| Symbol evidence | Impact only (via target_resolver) | **~45%** | Exists but unused in Build/Investigate |
| Call graph / import edges | Impact (direct importers) | **~25%** | Partially used; 2-hop chain missing |
| File evidence | All workflows | **~15%** | Used; good |
| Path evidence | All workflows (primary) | **~8%** | Used; over-relied on |
| Import evidence | Not used | **~4%** | Available; not queried |
| Concept evidence | All workflows (for framing) | **~2%** | Used for framing |
| Heuristics | All workflows (fallback) | **~1% or negative** | Over-used as primary |

**The critical insight:** Atlas is currently running on Tier B and C evidence. The entire Tier A
(symbol evidence and call graph chains) is available in the codebase but not integrated into
Build Plans or Investigations. That gap is the entire difference between PARTIAL and CORRECT.

---

## Task 3 — Symbol Evidence Phases 1, 2, 3

### Phase 1 — Symbol Match Display (Read-only integration)

**What it does:**
Queries the existing `SymbolIndex` for each candidate file during `plan_change()` and
`investigate_symptom()`. Symbols matching the goal/symptom keywords are surfaced in evidence.
Files with matching symbols get a score boost and rank higher. Files without matching symbols
are not removed but are labelled "path match only."

**Concrete change:**
```python
# BEFORE:
evidence: ["`api/routes.py` matched (score 4.5, fan-in 8)"]

# AFTER:
evidence: ["`api/routes.py` — contains `RateLimiterMiddleware` class (matched: rate, limit),
           `limit_request` function (matched: request). fan-in 8."]
```

**Implementation path:**
1. After scoring modules by path, load `SymbolIndex.from_dict(ctx["evidence_store"]["symbol_index"])`
2. For each candidate file in top-12, call `symbol_index.find_in_source((goal_tokens...,))`
3. Filter results to the specific file, extract matching symbol names
4. Boost score by +4 per matching symbol; add symbols to evidence list
5. For files with 0 symbol matches, add label "path match only (no symbol evidence found)"

**Files to change:** `planning_engine.py` (~60 lines), `evidence_engine/evidence_builder.py` (~20 lines)

**Complexity:** Low — read-only integration of existing index
**Engineering days:** 8-10 days (including tests and edge case handling)

**Expected trust gain:**
- 30-35 PARTIAL → MOSTLY_CORRECT (evidence is now verifiable and specific)
- Score model: 32 × 0.35 × (100/150) = 7.5 points
- Trust score: ~54 → ~62/100

**Implementation risk:** Low
- Symbol index may be empty for some repos (graceful fallback: path evidence only)
- Symbol index may be incomplete (partial AST scan) — label accordingly
- Performance: symbol query is O(symbols × keywords) — should be < 50ms per plan

**Gate:** Symbol index must be non-empty for the file before displaying symbols. No fabrication.

---

### Phase 2 — Symbol-Driven File Selection

**What it does:**
Makes symbol evidence drive which files APPEAR in Tier 1 of the plan, not just their display.
Only files with ≥1 matching symbol remain in the implementation file list. Files with path
matches but no symbol matches move to Tier 2 ("review context"). Follows 1-hop call chains:
if file A calls `function_in_B()`, and that function matches the goal, file B is also included.

**Concrete change:**
```python
# BEFORE: Tier 1 has 8-12 files sorted by path-keyword score
# AFTER:  Tier 1 has 2-4 files with symbol matches
#         Tier 2 has 4-6 files with path matches but no symbols
#         Tier 3 has remaining context

# BEFORE investigation hypothesis:
files_involved: ["middleware.py", "handler.py", "request.py", "apps.py", "utils.py"]

# AFTER investigation hypothesis:
files_involved: ["middleware.py"]  # Only file with symbol matching symptom keyword
evidence: ["`middleware.py` — `MiddlewareManager.run_middleware` method calls `process_request`
            (symptom keyword: middleware, request, twice)"]
```

**Implementation path:**
1. After symbol Phase 1 scoring, separate files into symbol-matched vs path-only buckets
2. Tier 1 = symbol-matched files, sorted by symbol match count desc (max 5)
3. Tier 2 = path-only files that had some score (max 5)
4. For hypothesis files in investigation: apply same filter; each hypothesis gets 1-2 files
5. Call chain: for top-1 symbol-matched file, find functions that call the matched symbol → include their source files

**Files to change:** `planning_engine.py` (~100 lines), `evidence_engine/evidence_builder.py` (~50 lines), `evidence_engine/symbol_index.py` (~30 lines)

**Complexity:** Medium — requires symbol-to-file mapping and 1-hop call traversal
**Engineering days:** 15-18 days

**Expected trust gain:**
- 20-25 additional PARTIAL → MOSTLY_CORRECT (Tier 1 files are now all relevant)
- 5-8 MOSTLY_CORRECT → CORRECT (symbol evidence + call chain is reviewer-verifiable)
- Score model: 22 × 0.35 + 6 × 0.20 = 7.7 + 1.2 = 8.9 points
- Trust score: ~62 → ~70/100

**Implementation risk:** Medium
- Risk 1: Symbol index coverage gap. If a file has relevant code but no symbol in the index, it will be incorrectly demoted to Tier 2. Mitigation: require symbol index completeness check before enabling Phase 2 filtering.
- Risk 2: Call chain false positives. Following callers can lead to unrelated files. Mitigation: limit to 1-hop, require keyword match on both ends.
- Risk 3: Repos with very small graphs (< 20 modules) may produce too few results. Mitigation: fall back to Phase 1 behavior when Tier 1 would be < 2 files.

**Gate:** Symbol index must cover ≥60% of production modules before Phase 2 filtering activates.

---

### Phase 3 — Insertion Point Prediction

**What it does:**
For Build Plans, predicts WHERE in the matched file to insert the new code. Converts the plan
from "edit `api/middleware.py`" to "insert after `authenticate_request` at line ~47, in the
request dispatch chain."

Uses the existing `implementation_detector.py` (which already detects middleware registration,
route definition, signal handler, and service injection patterns) to find structural insertion
anchors.

**Concrete change:**
```python
# BEFORE plan output:
files_to_inspect_first: ["api/middleware.py", "api/routes.py"]

# AFTER plan output:
implementation_target: {
  "file": "api/middleware.py",
  "anchor": "after `authenticate_request` middleware at line ~47",
  "pattern": "middleware_chain_insertion",
  "confidence": "medium",
  "reason": "New middleware should wrap request before response dispatch"
}
```

**Implementation path:**
1. After identifying Tier 1 files via Phase 2, run `implementation_detector.analyze(file_path, goal)` on top-1 file
2. Detector returns: anchor pattern, approximate line range, insertion type
3. Add `implementation_target` field to plan output
4. If detector confidence is low or pattern not found: omit `implementation_target`, keep current behavior

**Files to change:** `planning_engine.py` (~40 lines), `evidence_engine/implementation_detector.py` (~80 lines new logic)

**Complexity:** High — requires AST analysis per-query; insertion point heuristics are feature-specific
**Engineering days:** 12-15 days

**Expected trust gain:**
- 15-20 PARTIAL → CORRECT (now actionable at specific location)
- Score model: 17 × 0.55 × (100/150) = 6.2 points
- Trust score: ~70 → ~76/100

**Implementation risk:** High
- Risk 1: False insertion points. If the wrong pattern is matched, the developer adds code in the wrong place. This could be WORSE than no insertion point. Mitigation: expose confidence level; only show "high/medium" confidence insertions.
- Risk 2: Latency. AST analysis on a 1000-line file may take 200-500ms. Mitigation: cache the AST per file per session.
- Risk 3: Multi-file insertions. Some changes require edits in 2-3 files (e.g., middleware file + config file + tests). The single-file insertion hint is incomplete. Mitigation: label as "primary insertion point" and note additional files.

**Gate:** Insertion point prediction must have ≥70% agreement rate with human reviewer on a 20-sample test set before shipping.

---

### Symbol Evidence Summary

| Phase | Days | Score gain | Cumulative score | Gate |
|---|---:|---:|---:|---|
| Baseline (post-161) | — | — | ~54/100 | — |
| + Fix D+E+J (quick wins) | 4 | +8 | ~62/100 | All tests pass |
| + Phase 1 (symbol display) | 10 | +8 | ~70/100 | SymbolIndex non-empty gate |
| + Phase 2 (symbol-driven selection) | 18 | +9 | ~79/100 | ≥60% symbol coverage gate |
| + Phase 3 (insertion point) | 15 | +6 | ~85/100 | ≥70% insertion agreement gate |
| **Total** | **47 days** | **+31** | **~85/100** | — |

---

## Task 4 — Top 20 Situations Where Atlas Should Say "I Don't Know"

These are the exact conditions where producing a partial answer is more harmful than producing
no answer, and where Atlas must activate its honest gap response.

Each entry includes: the condition, the current behavior, and the required behavior.

---

### Layer 0 — Already Fixed (reference)

**Already returns honest gap or ok=False after Phases 158/161:**
1. Target file not in production graph → `ok=False, status=target_not_resolved`
2. No graph loaded → `ok=False, status=no_graph`
3. Unsupported language + empty graph → `ok=False, insufficient_evidence=True`
4. Root cause evidence score < 50 → "Insufficient evidence."
5. Stdlib/noise module as only root cause → demoted + honest fallback

These five are handled. The following 20 are not yet handled.

---

### Layer 1 — High-Confidence "I Don't Know" Triggers (must implement first)

**#1 — Zero Tier 1 files after scope filtering**

*Condition:* `plan_change()` produces 0 files in `implementation_files` (Tier 1) after scope
pollution filter, meaning all scored files were docs/scripts/examples/tests.

*Current behavior:* Returns plan with empty `files_to_inspect_first`. Confidence = low (after
Phase 158 caps).

*Required behavior:*
```
"Atlas matched your request to this repository but found no implementation files
 after filtering docs, scripts, and test helpers.
 
 Suggestion: Narrow your request to a specific subsystem or add a file path.
 Example: 'Add rate limiting to api/middleware.py' instead of 'Add rate limiting'."
```

---

**#2 — All hypotheses confidence = "low" in Investigation**

*Condition:* Every hypothesis in the investigation has `confidence = "low"` AND no files are
explicitly mentioned in the symptom.

*Current behavior:* Returns the lowest-confidence hypothesis as "most likely root cause."

*Required behavior:*
```
"Atlas identified the likely symptom area but could not ground it in specific files.
 
 To get a stronger investigation:
 - Add a stack trace, error message, or exact file path
 - Specify the subsystem (e.g., 'in the auth module')
 - Re-run with the actual symptom text from your error log"
```

---

**#3 — Unresolved import ratio > 90% on the targeted subsystem**

*Condition:* The subsystem the plan targets has >90% unresolved imports. Example: Airflow's
scheduler_job_runner.py with 97.43% repo-wide unresolved ratio.

*Current behavior:* Plan produced with a coverage_warning (if Fix D is implemented) but still
shows file lists.

*Required behavior:* Show file list BUT prefix with:
```
"Coverage warning: 97% of imports in this repository are unresolved.
 The files listed below are based on limited graph evidence.
 Impact analysis and dependency lists are likely INCOMPLETE.
 Verify all recommendations manually before acting."
```

This is a PARTIAL_EVIDENCE mode, not full "I don't know" — but the warning must be prominent.

---

**#4 — Zero dependency edges + Build Plan for a connectivity-dependent feature**

*Condition:* Graph has `dependency_edges = 0` AND the build plan is for middleware, caching,
rate limiting, or other cross-cutting concerns (which need import edges to place correctly).

*Current behavior:* Produces a plan based on path keywords only. All impact/dependency
information is empty or heuristic.

*Required behavior:*
```
"This repository has no resolved dependency edges in Atlas's graph.
 Build plans for cross-cutting concerns (middleware, caching, authentication) 
 require dependency information to locate the correct insertion point.
 
 Atlas can show candidate files but cannot determine which is the correct integration point.
 Treat this as a starting area, not a grounded recommendation."
```

---

**#5 — Impact with 0 direct importers on a healthy graph**

*Condition:* `analyze_impact()` resolves the target file (ok=True, status=resolved) but
finds 0 direct importers despite the graph being healthy.

*Current behavior:* Returns `confidence=low` with "no direct importers in graph."

*Required behavior:* This IS a legitimate answer — if nothing imports the file, changing it
has low blast radius. But Atlas must distinguish between:
- "Nothing imports this file: isolated module" → honest finding
- "Nothing imports this file because imports are unresolved" → known incomplete data

Add `isolation_reason` field: `"isolated_module" | "unresolved_imports"`. If unresolved ratio > 50%, use `"unresolved_imports"` and add the PARTIAL_EVIDENCE warning.

---

**#6 — Investigation symptom is purely behavioral with no technical anchor**

*Condition:* Symptom text is behavioral only: "it's slow", "it breaks", "things are wrong",
"users complain" — no subsystem name, no file path, no error type, no component name.

*Current behavior:* Routes to `"general"` intent, returns top-scored modules by keyword
overlap (which produces near-random results on generic symptom text).

*Required behavior:*
```
"The symptom description does not contain technical anchors (file paths, component 
 names, error types, or subsystem keywords).
 
 Atlas investigation requires at least one of:
 - A specific symptom: 'middleware runs twice', 'websocket auth fails'
 - A file or module name: 'in auth/session.py'  
 - An error type: 'KeyError in scheduler'
 - A subsystem: 'in the DAG parser'
 
 Without these, results would be unreliable guesses."
```

---

**#7 — Graph has < 8 modules AND user requests investigation**

*Condition:* `module_count < 8` for the scanned repo.

*Current behavior:* Investigation runs but returns mostly empty or generic results.

*Required behavior:*
```
"This repository has fewer than 8 indexed modules. Atlas investigation requires
 a richer dependency graph to localize symptoms effectively.
 
 Possible causes: scan scope was too narrow, language unsupported, or 
 the repository is very small.
 
 Try: re-scan with broader scope, or use Load Sample Repository to 
 verify Atlas can investigate your stack."
```

---

**#8 — Build plan goal matches no known feature pattern AND Tier 1 is empty**

*Condition:* `intent = "general"` (no feature-spec matched) AND no Tier 1 files after
symbol/scope filtering.

*Current behavior:* Returns a plan with a long list of top-ranked modules by path keywords.
This is the weakest possible output.

*Required behavior:*
```
"This request didn't match any known feature patterns and Atlas couldn't find 
 specific implementation files.
 
 Suggestions:
 - Be more specific: 'add Redis-backed rate limiting to API endpoints'
 - Name a file: 'add rate limiting to api/middleware.py'
 - Name a concept: 'add rate limiting middleware' (not 'add rate limiting')"
```

---

**#9 — Impact target is in a known non-production path**

*Condition:* The target file path contains `/scripts/`, `/docs/`, `/examples/`, or `/tests/`.

*Current behavior:* Impact runs; finds importers of test/scripts files which are themselves
test/script files. Produces a nonsensical blast radius.

*Required behavior:*
```
"The target file (`scripts/build.py`) is in a non-production directory.
 Atlas impact analysis is designed for production source files.
 
 If you intended to analyze a production file, provide its path.
 Test/script files are not imported by production code in the standard dependency graph."
```

---

**#10 — Semantic concept resolved to library-pattern modules outside the scanned graph**

*Condition:* Target is a concept name (e.g., "event bus"), semantic resolution finds modules,
but those modules are from the Atlas knowledge catalog (not this repo).

*Current behavior:* Returns impact based on knowledge-catalog patterns. These patterns are for
Home Assistant/Django/FastAPI, not for the user's repo.

*Required behavior:* Already partially handled in Phase 158/161 with `status=target_outside_graph_scope`.
Must ensure the error message names the specific repo and concept clearly.

---

### Layer 2 — Medium-Confidence "I Don't Know" Triggers

**#11 — All impact evidence is from same-subsystem blast (no direct importers)**

A plan that says "X affects the auth subsystem" based on sibling-subsystem blast with 0 direct
importers is heuristic. Should be labelled "subsystem estimate, not graph evidence."

**#12 — Investigation explicitly names a module the graph doesn't index**

"Why is `celery/worker/autoscale.py` not scaling?" — if this path is not in the index,
say so: "That file was not found in the scanned graph. Re-scan or verify the path."

**#13 — Build plan requires cross-service coordination not captured by single-repo graph**

"Add rate limiting across 3 microservices" — Atlas has one repo. Multi-repo analysis is
outside scope. Say: "Atlas analyzes single repositories. Cross-service changes require
examining each service individually."

**#14 — Confidence is "low" AND the only evidence is from fallback paths**

When ALL evidence items come from `"fallback"` or `"path match only"` — not a single
symbol match, not a single edge — the output is speculation. Label accordingly.

**#15 — Graph was produced from a partial scan (PARTIAL_GRAPH category)**

When `reliability.category = "partial_graph"`, all outputs should carry: "This graph
is incomplete. Results are based on partial repository coverage."

**#16 — User asks for implementation of a feature that requires external APIs**

"Add Stripe integration" — Atlas can find files, but cannot know the Stripe API contract.
Say: "Atlas can identify the integration points in your code. External API implementation
details are outside Atlas's scope; consult the Stripe documentation for API specifics."

**#17 — Investigation matches trading/finance domain but repo is NOT trading**

After the Phase 158/161 guardrail, this should return `general` intent. Still, if this
condition is reached via any remaining path, say: "No trading-domain evidence found in this
repository. Re-running with general investigation mode."

**#18 — All hypothesis files are in a single directory (single-subsystem lock-in)**

When all 5 hypothesis files are in `components/recorder/` for a symptom about auth, this
is a false positive from keyword overlap. Should say: "All candidate files are in the
recorder subsystem. If your symptom is in a different subsystem, provide that subsystem name."

**#19 — Build plan Tier 1 has only 1 file**

A single-file recommendation is not evidence it's correct — it could just be the only file
that matched a keyword. Require ≥2 Tier 1 files or escalate to "insufficient grounding":
"Atlas found only one candidate file. This may indicate the feature spans multiple files
that didn't match the keywords. Add a subsystem or file path for better coverage."

**#20 — Investigation root cause score is between 30-50 (borderline)**

Phase 161 implements root cause minimum score of 50. Scores between 30-50 are borderline —
not confident enough for "most likely" but not zero evidence. Instead of returning nothing or
returning a weak guess, return: "Possible area (borderline evidence, score 38/100): X.
This is a weak signal. Verify with a stack trace before acting."

---

## Task 5 — Fastest Path to Trust 70/75/80

### Calibrated Baseline

Post-Phase-161 trust score (estimated from sample arithmetic):

```
Starting 157A: 45.8/100 (weight: 68.7/150)
Phase 158 improvements:
  5 WRONG → CORRECT: +5.0 weight
  7 EMA MISLEAD → PARTIAL: +2.45 weight
  4 scope pollution MISLEAD → PARTIAL: +1.40 weight
  3 stdlib root cause MISLEAD → PARTIAL: +1.05 weight
  5 confidence-cap MISLEAD → PARTIAL: +1.75 weight
  = +11.65 weight

Phase 161 additional improvements:
  3 more EMA leakage paths closed: +1.05 weight
  1 impact mock aligned: +0.35 weight
  2 confidence boundary cases: +0.50 weight
  = +1.90 weight

Total weight: 68.7 + 11.65 + 1.90 = 82.25
Post-Phase-161 estimated score: 82.25/150 × 100 ≈ 55/100
```

The honest post-161 baseline is approximately **55/100**, not 63.
Phase 160's 63/100 estimate assumed some quick fixes that were not yet implemented.

---

### Path to Trust 70

**Starting from:** ~55/100  
**Gap:** 15 points (need +22.5 weight)  
**Target date:** Day 14-18 from start

**Sprint plan:**

| Fix | Days | Weight gain | Cumulative score |
|---|---:|---:|---:|
| Fix J: Cap file lists (≤4 inspect, ≤5 order) | 1 | +4.0 | ~57.7 |
| Fix D: Propagate unresolved import warnings | 1 | +3.5 | ~60.0 |
| Fix E: Replace "unknown" flags with explicit labels | 1 | +3.0 | ~62.0 |
| Fix B: Narrow investigation hypotheses (≤3 files with evidence gate) | 5 | +5.0 | ~65.3 |
| Fix F: Root cause subsystem gate | 2 | +2.0 | ~66.7 |
| Fix H: 10+ new symptom patterns from 157A failures | 4 | +3.5 | ~69.0 |
| Symbol Evidence Phase 1 (partial: display only) | 4 | +2.0 | **~70.3** |

**Total: 18 days → Trust 70**

The Phase 1 partial (4 days) is just the evidence display portion — showing symbols in the
evidence field without yet using them for file selection. This is the fastest value.

---

### Path to Trust 75

**Starting from:** Trust 70 (Day 18)  
**Gap:** 5 additional points  
**Target date:** Day 30-35

| Fix | Days | Weight gain | Cumulative score |
|---|---:|---:|---:|
| Symbol Phase 1 (complete: re-ranking by symbol presence) | 6 | +3.0 | ~72.3 |
| Fix #1+#2+#6 (I Don't Know: zero Tier 1, all-low hypotheses, behavioral symptoms) | 3 | +2.0 | ~74.7 |
| Fix I: Language scope UI restriction | 2 | +1.0 | **~75.2** |

**Total: Day 29 → Trust 75** (from scratch: 18 + 11 = 29 days)

The critical observation: **the Phase 160 plan's 29-day path to 75 requires Quick Wins + Symbol
Phase 1 to complete.** It does not require Symbol Phase 2 or 3. The 75 target is achievable
with display-only symbol evidence plus the hypothesis and file-list improvements.

---

### Path to Trust 80

**Starting from:** Trust 75 (Day 29)  
**Gap:** 5 additional points  
**Target date:** Day 48-55

| Fix | Days | Weight gain | Cumulative score |
|---|---:|---:|---:|
| Symbol Phase 2 (symbol-driven file selection + 1-hop call chain) | 18 | +7.0 | ~81.7 |
| "I Don't Know" Layer 1 complete (remaining 5 triggers) | 4 | +1.5 | ~82.5 |

**Total: Day 51 → Trust 80**

But note: Symbol Phase 2 is the riskiest fix (medium complexity, requires symbol coverage gate,
has call-chain false-positive risk). If Phase 2 takes longer than 18 days, Trust 80 slips to Day 60+.

**De-risked path to 80:** Skip Phase 2 temporarily. Add:
- Fix G (impact for partial-graph repos via subsystem blast guidance): +3 pts, 10 days
- Fix #11-#20 from I Don't Know list: +3 pts, 5 days
Total: ~54 days → Trust ~80/100 without the Phase 2 risk.

---

### Summary: Three Trust Milestones

```
TRUST 70 — Day 18
═══════════════════════════════════════════════════════════════════
Fixes: J + D + E + B + F + H + Symbol Phase 1 (partial)
Key change: File lists capped, noisy labels removed, investigation
hypotheses narrowed to ≤3 files, symbols appear in evidence
Beta use case: Self-serve supervised beta safe (20 users)

TRUST 75 — Day 29
═══════════════════════════════════════════════════════════════════
Adds: Symbol Phase 1 (complete re-ranking), I Don't Know Layer 1, 
language scope UI restriction
Key change: Files in Tier 1 have verifiable symbol evidence;
Atlas says "I don't know" instead of fabricating weak results
Beta use case: Public waitlist download safe

TRUST 80 — Day 51 (or Day 60 de-risked path)
═══════════════════════════════════════════════════════════════════
Adds: Symbol Phase 2 (symbol-driven selection + call chain)
OR alternative: Impact partial-graph improvement + I Don't Know Layer 2
Key change: Tier 1 files are selected by symbols, not keywords;
investigation hypotheses are pinpoint not broad
Beta use case: Premium tier / charge-for-it threshold
```

---

## Key Engineering Insight

The most important thing this document establishes:

> **Every CORRECT result in Phase 157A came from the Impact workflow on files where
> Atlas had BOTH a resolved target AND a complete import graph.**
>
> **Zero CORRECT results came from Build Plans or Investigations.**
>
> The structural reason: Impact gives Atlas a ground-truth starting point (the exact file).
> Build/Investigation do not.
>
> The solution is NOT to make Build/Investigation do their own target-resolution from
> scratch. The solution is to move Build/Investigation to the same evidence tier as Impact
> by integrating the symbol index — which already contains the same ground truth.
>
> The symbol index knows that `api/middleware.py` contains `RateLimiterMiddleware`.
> The plan engine doesn't ask the symbol index.
> Asking the symbol index is the entire answer.

This is not a research problem. The evidence exists. The integration is the work.

---

## Appendix A — Projected Trust Score Trajectory

```
Score
 90 │                                              ████ Phase 3 + full I-don't-know
 85 │                                     ████████
 80 │                             ████████
 75 │                    █████████  ← Day 29 public beta gate
 70 │           █████████  ← Day 18 self-serve beta gate
 65 │    ███████
 60 │████  ← Post-161 (~55 actual, not 63 as estimated)
 55 │
    └─────────────────────────────────────────────────────→ Days
      0     5     10    15    20    25    30    40    50

  Phase:   161  J+D+E  B+F   H   Sym1  Sym1  I-dk  Sym2
                               +H  part  full  L1
```

---

## Appendix B — What CANNOT Reach 80 Without Symbol Evidence

This is the skeptical reviewer's assessment:

**Fixes that do NOT close the thin_grounding gap:**
- More concept patterns in the knowledge catalog → improves domain framing, not file precision
- Better confidence calibration → prevents overclaiming, does not improve file lists
- More I Don't Know triggers → prevents harm, does not increase CORRECT count
- Scope pollution filters → removes noise, but if the remaining files are all path-based, still PARTIAL
- Better symptom routing → reaches the right subsystem faster, but the file-level gap remains

**The hard limit without symbol evidence:**
You can reach approximately Trust 68-70 by making every non-symbol fix perfectly:
- All quick wins (D, E, J): +8 pts → 63
- Perfect hypothesis narrowing (B): +6 pts → 69
- All pattern additions (H): +3 pts → 72
- All I Don't Know triggers: +2 pts → 74

But this 74 is the CEILING without symbol evidence. You cannot push past it via guardrails
and patterns alone because the underlying thin_grounding problem — too many plausible-but-wrong
files with no verification signal — remains unaddressed.

Symbol Evidence Phase 1 is the specific piece that breaks through the 74 ceiling by making
evidence verifiable. A reviewer who can check "does this file contain `RateLimiterMiddleware`?"
will confirm the recommendation; a reviewer who can only check "does this path contain
`rate_limit`?" will be 70% wrong.

**Conclusion: Trust 75+ requires Symbol Evidence. Period.**

---

## Appendix C — The Skeptical Reviewer's Checklist

Before shipping any trust-improvement change, verify:

1. **Does it improve output quality or just reduce harm?**
   - Harm reduction (guardrails): necessary but insufficient for PARTIAL→CORRECT
   - Quality improvement (symbol evidence, insertion points): required for the conversion

2. **Can a developer verify the evidence without opening Atlas?**
   - Path evidence: No (developer must guess what "rate_limit in path" means)
   - Symbol evidence: Yes (developer opens the file, checks the symbol exists)
   - Import edge evidence: Yes (developer can check `import` statements)

3. **Does the fix convert samples or just relabel them?**
   - "Relabel": changing confidence from "medium" to "low" on a PARTIAL output
   - "Convert": actually giving the developer a better answer that a reviewer classifies higher

4. **Is the fix gated on evidence quality?**
   - Ungated: ship it even when symbol index is empty → risk of degradation on empty-index repos
   - Gated: only activate when evidence meets minimum quality threshold → safe to ship

5. **Does the fix have a regression test on the 157A failure set?**
   - Each trust-improvement fix should include a test that runs the specific 157A failure
     case and verifies it now produces MOSTLY_CORRECT or CORRECT output
