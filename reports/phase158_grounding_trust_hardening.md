# Phase 158 — Grounding and Trust Hardening

**Date:** 2026-06-05  
**Scope:** Confidence calibration, domain guardrails, evidence scoring, impact honesty, graph health truth.  
**No changes to:** website, billing, landing page, installer, pricing, waitlist, marketing, general UI.

---

## Summary

Phase 157A found a trust score of 45.8/100 with:
- Build Plan: 0 correct / 46 partial / 4 misleading / 50 total
- Investigation: 0 correct / 44 partial / 6 misleading / 50 total
- Impact: 12 correct / 3 mostly-correct / 28 partial / 2 misleading / 5 wrong / 50 total

The root causes were: EMA/trading leakage into unrelated repos, stdlib modules named as root causes,
`ok=True` returned when target was not found in graph, healthy label on unsupported-language repos,
scope pollution in Build Plans, and confidence values disconnected from evidence quality.

Phase 158 addresses all 7 P0 root causes. No new features. No UI changes.

---

## P0 Fix 1 — Stop EMA / Trading Leakage

**File:** `jarvis_desktop/planning_engine.py`

**Root cause:** Trading concepts were only suppressed when the symptom text contained one of
a narrow list of trading markers. The check missed the case where:
- Short aliases (≤4 chars like `ema`) matched substrings (e.g. "schema" → "sch**ema**")
- The domain guardrail was symptom-only and didn't check repository evidence
- Build Plans had no trading domain guardrail at all

**Fix:**
1. Added `_TRADING_EXPLICIT_TERMS` set with full trading vocabulary
2. Added `_TRADING_REPO_PATH_SIGNALS` set for repository-level evidence detection
3. `_request_mentions_trading_explicitly(text)` — uses word-boundary regex for short terms (≤4 chars) to prevent substring false-positives
4. `_repo_has_trading_evidence(ctx)` — scans module paths and file index for trading signals
5. Updated `_coerce_investigation_classification()` to require **either** user intent **or** repo evidence (two independent gates)
6. Added the same trading guardrail to `plan_change()` for Build Plans

**Before / after:**

| Input | Before | After |
|---|---|---|
| "why are duplicate events being fired" (non-trading repo) | EMA/trading concept may appear | pub_sub routing, no trading |
| "add rate limiting" (non-trading repo) | trading concept may appear | rate_limiting concept, no trading |
| "schema validation failing" | "schema" → "ema" substring match possible | word boundary check, no trading |
| "signals are NaN in backtest" (trading repo) | trading | trading (repo evidence present) |

**Acceptance tests:** All pass.
- `test_duplicate_events_not_ema` ✓
- `test_add_rate_limiting_not_trading` ✓
- `test_websocket_duplicate_not_ema` ✓
- `test_trading_leakage_blocked_on_symbol_match` ✓

---

## P0 Fix 2 — No Root Cause Without Evidence

**File:** `jarvis_desktop/planning_engine.py`

**Root cause:** Investigation could assign `most_likely_root_cause` to any module that scored >0 on
keyword matching — including stdlib modules (`__future__`, `re`, `os`), test helpers, and conftest
files. `_build_hypotheses()` did not filter these out.

**Fix:**
1. Added `_NOISY_MODULE_MARKERS` — path markers for stdlib, boilerplate, test helpers, examples
2. `_is_noisy_module(path)` — returns True for stdlib/noise paths
3. `_root_cause_evidence_score(path, symptom, ...)` — scores evidence quality on 5 criteria:
   - explicit mention in symptom (+2)
   - top keyword match (+1)
   - risk coupling fan-in≥3 or risk≥10 (+1)
   - symptom token overlap ≥2 (+1)
   - runtime/source module (not config/docs) (+1)
   - stdlib/noise (-10, hard demote)
4. `_build_hypotheses()` now:
   - Strips noisy modules from `files_involved`
   - Passes `symptom` for evidence scoring
   - Demotes generic `scored` candidates if they are noisy
5. `most_likely_root_cause` now requires at least one grounded hypothesis (files present, confidence medium+, not a noisy module)
6. When no grounded hypothesis: returns `"Atlas did not find enough repository evidence for a strong root cause. Provide a stack trace, error message, or exact file path and re-run."`

**Before / after:**

| Input | Before | After |
|---|---|---|
| FastAPI investigation — "duplicate events firing" | `__future__.annotations` as root cause | Event dispatcher area, or honest "insufficient evidence" |
| FastAPI investigation — "why is re used" | `re` as root cause | Honest "insufficient evidence" |
| Requests investigation with strong path match | `requests/auth.py` | `requests/auth.py` (unchanged, good path) |

**Acceptance tests:** All pass.
- `test_future_not_root_cause` ✓
- `test_re_not_root_cause` ✓
- `test_insufficient_evidence_message` ✓
- `test_noisy_module_demoted` ✓

---

## P0 Fix 3 — Impact Must Not Return ok=True With Mock Target-Not-Found

**File:** `jarvis_desktop/impact_engine/engine.py`

**Root cause:** Three cases returned `ok=True, mock=True` when the target was not found:
1. No graph at all
2. Target not found in graph
3. Semantic concept resolved but outside graph scope

A consumer checking `result["ok"]` would believe success and render an impact report. The
`mock=True` flag was a silent qualifier that was easy to miss.

**Fix:**
1. **No graph:** Returns `ok=False, status="no_graph"`
2. **Target not found:** Returns `ok=False, status="target_not_resolved"` with a clear `reason` explaining what to do instead
3. **Concept outside scope:** Returns `ok=False, status="target_outside_graph_scope"`
4. **Resolved target:** Returns `ok=True, status="resolved"` (explicit positive signal)

Additionally:
- Added `confidence_cap_reason` and `graph_health` fields to successful results
- Applied `confidence_cap_for_scan()` from reliability module to cap confidence

**Before / after:**

| Scenario | Before | After |
|---|---|---|
| Target not in graph | `{"ok": True, "mock": True, "confidence": "low"}` | `{"ok": False, "status": "target_not_resolved", ...}` |
| Concept outside scope | `{"ok": True, "mock": True, ...}` | `{"ok": False, "status": "target_outside_graph_scope", ...}` |
| No graph | `{"ok": True, "mock": True, ...}` | `{"ok": False, "status": "no_graph", ...}` |
| Real target resolved | `{"ok": True, ...}` | `{"ok": True, "status": "resolved", ...}` |

**Acceptance tests:** All pass.
- `test_nonexistent_file_returns_ok_false` ✓
- `test_no_graph_returns_ok_false` ✓
- `test_existing_file_returns_ok_true` ✓
- `test_target_not_found_no_mock_true` ✓

---

## P0 Fix 4 — Graph Health Must Reflect Real Language Support

**File:** `jarvis_desktop/reliability.py`

**Root cause:** `classify_scan()` did not detect the pattern of many files + almost no modules,
which is characteristic of Go, Java, C#, and Rust repositories that Atlas cannot graph.
Kubernetes (24,860 files, 3 modules) reported healthy because it had some modules and some edges.

**Fix:**
1. Added `UNSUPPORTED_LANGUAGE = "unsupported_language_limited"` fault category
2. Added `UNSUPPORTED_LANGUAGE` to `FAULT_CATEGORIES`
3. Added threshold check: `files > 1000 and modules < 25` → `unsupported_language_limited`
4. Added warning message that explicitly names the affected languages
5. Added `graph_health_label(scan)` → short human-readable label string
6. Added `confidence_cap_for_scan(scan)` → `"high" | "medium" | "low"` cap
7. Added `_HEALTH_LABELS` dict for category → label mapping

**Health label → confidence cap mapping:**

| Health | Cap |
|---|---|
| healthy | high |
| partial | medium |
| degraded | medium |
| unsupported_language_limited | low |
| failed / empty | low |

**Before / after:**

| Repo | Files | Modules | Before | After |
|---|---|---|---|---|
| Kubernetes | 24,860 | 3 | healthy | unsupported_language_limited |
| Gin (Go) | 1,200 | 1 | healthy | unsupported_language_limited |
| Spring Boot | 700 | 0 | (zero_module_scan) | degraded (unchanged) |
| FastAPI | 2,753 | 73 | healthy | healthy (unchanged) |

**Acceptance tests:** All pass.
- `test_kubernetes_like_scan_not_healthy` ✓
- `test_go_repo_shallow_graph` ✓
- `test_python_repo_can_be_healthy` ✓
- `test_language_limit_boundary_conditions` ✓

---

## P0 Fix 5 — Build Plan Scope Pollution

**File:** `jarvis_desktop/planning_engine.py`

**Root cause:** `plan_change()` ranked all modules by keyword score without filtering out
docs, scripts, examples, fixtures, test helpers, or Playwright-style browser test helpers.
This caused files like `scripts/playwright/tests/image02.py` to appear in "likely affected files"
for a "add rate limiting" request.

**Fix:**
1. Added `_SCOPE_POLLUTION_MARKERS` — path markers for docs, scripts, examples, fixtures, e2e, playwright, etc.
2. `_is_scope_polluting(path)` — returns True for these paths
3. In `plan_change()`, split ranked results into:
   - **Tier 1** (`matched_paths`): clean implementation files — used for everything
   - **Tier 2** (`files_review_only`): docs/scripts/examples — exposed separately, not in implementation order
4. Added `files_review_only` field to the plan dict

**Before / after:**

| Request | Before | After |
|---|---|---|
| "add rate limiting" on FastAPI | `scripts/playwright/.../image02.py` in plan | only API/middleware files in Tier 1 |
| "add authentication" | docs/examples in affected files | docs/examples in `files_review_only` only |
| "add tests for auth" | (test helpers included) | test helpers move to Tier 1 since request is about tests |

**Note:** The filter is conservative — it only removes paths containing explicit pollution markers.
Implementation files adjacent to scripts (e.g. `scripts/deploy.py` with real deployment logic)
still appear in Tier 1 if they're not in an explicitly marked subdirectory.

**Acceptance:** Build Plan for "add rate limiting" no longer includes Playwright/browser/e2e files.

---

## P0 Fix 6 — Confidence Calibration

**Files:** `jarvis_desktop/reliability.py`, `jarvis_desktop/planning_engine.py`, `jarvis_desktop/impact_engine/engine.py`

**Root cause:** Confidence values were computed from keyword match scores alone, without considering
scan health, graph coverage, or evidence count. A Build Plan on a repo with 3 modules could still
claim "medium-high" confidence.

**Fix:**
1. `confidence_cap_for_scan(scan)` in `reliability.py` — returns the maximum confidence Atlas may claim
2. Applied in `plan_change()`:
   - After computing base confidence from keyword scores
   - Apply cap: if base > cap, set to cap and record `confidence_cap_reason`
3. Applied in `investigate_symptom()`: same cap logic
4. Applied in `analyze_impact()`: same cap logic
5. Added `confidence_cap_reason` and `graph_health` to all three plan types

**New fields in plan/investigation/impact results:**
- `confidence_cap_reason` — why confidence was capped (empty string if not capped)
- `graph_health` — short health label from the scan

**Before / after:**

| Scenario | Before | After |
|---|---|---|
| Build Plan, unsupported-language repo | confidence="medium-high" | confidence="low" (capped) |
| Investigation, partial graph | confidence="medium" | confidence="medium" (medium cap from partial graph — unchanged) |
| Impact, healthy Python scan | confidence="high" | confidence="high" (no cap needed) |

---

## P0 Fix 7 — Unknown Mode

**File:** `jarvis_desktop/planning_engine.py`

**Root cause:** Atlas would produce full-looking plans even when the graph was too sparse to
provide any reliable information. There was no explicit "I don't know" path.

**Fix:**
1. Added `_insufficient_evidence_response(request, *, reason, checked, missing, next_steps)` — returns a structured honest gap response
2. In `plan_change()`: if `graph_health == "unsupported_language_limited"` and `matched_paths` is empty, return the gap response instead of an empty plan
3. In `investigate_symptom()`: same gate — if `graph_health == "unsupported_language_limited"` and no modules and no explicit paths, return gap response

**Gap response fields:**
```json
{
  "ok": true,
  "insufficient_evidence": true,
  "evidence_gap": true,
  "message": "Atlas does not have enough evidence to answer this safely.",
  "reason": "...",
  "what_was_checked": [...],
  "what_was_missing": [...],
  "how_to_improve": [...],
  "confidence": "low"
}
```

---

## Test Results

```
py -3 -m pytest jarvis_desktop/tests/test_phase158_grounding_trust.py     → 33 passed
py -3 -m pytest jarvis_desktop/tests/test_phase158_no_leakage.py          → 13 passed
py -3 -m pytest jarvis_desktop/tests/test_phase158_confidence_calibration.py → 15 passed
py -3 -m pytest jarvis_desktop/tests/test_phase158_graph_health_truth.py  → 18 passed

Total phase158: 79 tests, 0 failures

Regression check (key pre-existing tests):
py -3 -m pytest test_phase146b + test_phase146 + test_phase139 + test_phase155 + test_phase152
  → 114 passed, 0 failures
```

Pre-existing failure (unrelated to Phase 158):
- `test_product_version_atlas_hardening_lineage` — asserts version string contains "phase12",
  but current version is "phase146b-true-beta-blocker-fixes". This was failing before Phase 158
  and is a separate task (update product version string).

---

## Remaining Known Trust Gaps

These are not addressed in Phase 158 (would require intelligence changes):

| Gap | Severity | Evidence |
|---|---|---|
| Evidence quality dimension = 56.0 | High | Phase 132 benchmark |
| Investigation file-list precision = 0.30 (recall dominated) | Medium | Phase 132 |
| Build Plan has no insertion-point prediction | Medium | Phase 132: 5 scenarios miss insertion |
| Impact confidence when 0 direct importers is still "low" but could mislead | Medium | Impact engine |
| Investigation hypothesis titles are templated, not repo-specific | Medium | Phase 147 |
| Large-repo scan ETA / partial result UX | Medium | Phase 153/154 |

---

## New Trust Score Estimate

Based on Phase 157A audit categories, Phase 158 directly addresses:

| Problem class | Phase 157A count | Expected remaining after 158 |
|---|---|---|
| concept_leakage (EMA/trading) | ~8 | ~1–2 (trading repo edge cases) |
| false_root_cause (stdlib modules) | ~6 | ~1 (unusual repos) |
| fake_success (ok=True on miss) | ~5 wrong | 0 (P0 Fix 3) |
| graph_health_misreported | ~4 | ~1 (edge cases) |
| scope_pollution | ~6 | ~2 (non-marker paths) |
| confidence_miscalibrated | ~15+ | ~6 (calibration improved, not perfect) |
| weak_evidence / partial | ~46 | ~40 (still real — evidence quality unchanged) |

**Estimated new trust score: 58–68/100** (up from 45.8)

The biggest remaining gap is evidence quality (Phase 132: dimension = 56.0). Phase 158 stops
Atlas from claiming more than it knows — it does not improve what Atlas actually knows.
True trust improvement requires richer evidence from graph edges and symbol analysis.
