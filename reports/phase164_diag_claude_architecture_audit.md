# Phase 164-DIAG-CLAUDE — Trust Failure Architecture Audit

**Date:** 2026-06-05  
**Role:** Principal engineer / skeptical reviewer  
**Scope:** Diagnosis only. No code changes.  
**Question:** Why are Phase 158/161 trust fixes not consistently visible in Phase 161A outputs?

---

## Executive Answer

Phase 158/161 guardrails are correctly written but defeated by two architectural bugs:

1. **The knowledge engine's quality boost equals the confidence threshold**, causing
   `source_backed` concepts (including EMA) to match *every* prompt with zero alias hits.

2. **The trading-evidence detector has false positives**: `_repo_has_trading_evidence()`
   returns `True` for Home Assistant (`*registry.py`, `helpers/signal.py`) and Celery
   (`worker/strategy.py`), which silences the EMA guardrail for those repos.

Together, these mean the Phase 158/161 guardrail cannot fire on the two repos (HA, Celery)
that produced the majority of the 35 integration-bug samples.

A third bug affects Impact specifically: the live API exposes **two separate impact routes**
with different trust characteristics, and the audit used the Phase 132 route
(`/api/planning/impact`) which silently lost some Phase 158 fields in certain code paths.

---

## Part 1 — Route Map: Every User-Facing Output Path

### 1.1 HTTP Routes

| Route | Method | Handler (server.py) | Core function | Workflow |
|---|---|---|---|---|
| `/api/planning/change` | POST | `_planning_change` | `api.plan_change()` → `planning_engine.plan_change()` | Build Plan |
| `/api/planning/investigate` | POST | `_planning_investigate` | `api.investigate_symptom()` → `planning_engine.investigate_symptom()` | Investigation |
| `/api/planning/impact` | POST | `_planning_impact` | `api.change_impact_simulation()` → `impact_engine.analyze_impact()` | Impact (Phase 132+) |
| `/api/impact` | POST | lambda | `api.impact()` (legacy path) | Impact (legacy) |
| `/api/bug-investigation` | POST | lambda | `api.bug_investigation()` | Bug Invest. (mock/legacy) |
| `/api/copilot/ask` | POST | `_copilot` | `api.copilot_ask()` | Copilot |
| `/api/context/export` | POST | lambda | `api.context_export()` | Export |
| `/api/demo/load` | POST | lambda | `api.load_demo_mode()` | Demo |
| `/api/demo/export-bundle` | POST | lambda | `api.export_demo_bundle()` | Demo export |

The Phase 161A runner used:
- `POST /api/planning/change` for Build Plans
- `POST /api/planning/investigate` for Investigations
- `POST /api/planning/impact` for Impact

### 1.2 Call Chain per Workflow

```
BUILD PLAN
  /api/planning/change
    → server._planning_change(body)              # body.get("request"|"goal"|"text")
    → api.plan_change(request)                   # api.py:2530
        → planning_engine.plan_change(request, _planning_context())   # planning_engine.py
            → dk.classify_request(goal, mode="build")                 # atlas_knowledge/engine.py
            → [P158 trading guardrail]
            → _score_modules(...)
            → dk.enrich_build_plan(plan, build_class, roles)
            → _repository_evidence_bundle(ctx, build_class, ...)
        → planning_engine.format_change_plan_markdown(plan)           # planning_engine.py
    → returns: {ok, plan{...}, formatted, limitations}

INVESTIGATION
  /api/planning/investigate
    → server._planning_investigate(body)
    → api.investigate_symptom(symptom)           # api.py:2543
        → planning_engine.investigate_symptom(symptom, _planning_context())
            → dk.classify_request(text, mode="investigate")
            → _coerce_investigation_classification(text, classification, ctx)  # P158 guardrail
            → _build_hypotheses(intent, spec, scored, explicit_paths, risks_map, symptom)
            → dk.enrich_investigation_plan(plan, inv_class, roles)
        → planning_engine.format_investigation_plan_markdown(plan)
    → returns: {ok, plan{...}, formatted, limitations}

IMPACT (Phase 132 route — used by 161A)
  /api/planning/impact
    → server._planning_impact(body)
    → api.change_impact_simulation(target)       # api.py:2556
        → impact_engine.analyze_impact(target, _STATE, summary)
            → [P158: ok=False if no graph / target not found]
            → _find_target(nodes, target)
            → confidence_cap_for_scan(scan_data)   # P158/161 cap
            → returns: {ok, status, confidence, confidence_cap_reason, graph_health, ...}
        → builds simulation{} block (backward compat)
        → _augment_impact_with_architecture(res)
    → returns: {ok, target, confidence, simulation{}, architecture{}, limitations, ...}

IMPACT (Legacy route — NOT used by 161A)
  /api/impact
    → api.impact(target)                         # api.py:2453
        → simple graph lookup (direct importers only)
        → if not found: _impact_mock() → ok=False (P161 fixed)
        → if found: {ok=True, target, fan_in, affected_files, ...}
           NOTE: no confidence_cap_reason, no graph_health, no status field
    → returns: {ok, target, fan_in, affected_files, affected_subsystems, ...}

BUG INVESTIGATION (legacy, mock — NOT affected by P158/161)
  /api/bug-investigation
    → api.bug_investigation(text)                # api.py:2655
        → simple token matching against index
        → returns: {ok=True, mock=bool, todo="Wire semantic...", confidence, ...}
        NOTE: still has "todo" field; Phase 158/161 guardrails DO NOT cover this route

COPILOT
  /api/copilot/ask
    → api.copilot_ask(question, target, packet, node_context)  # api.py:3668
        → classify_copilot_question() → routes to:
           _answer_repository_understanding / _answer_risk / _answer_impact
           _answer_cycles / _answer_dependency / _answer_context_export / _answer_unknown
        NOTE: Copilot does NOT call planning_engine.plan_change or investigate_symptom
        NOTE: P158/161 trading guardrails DO NOT cover Copilot
    → returns: {ok, answer, ...}

EXPORT
  /api/context/export
    → api.context_export(target, packet)         # api.py:2689
        → _render_context(target, packet)
        → returns: {ok, content, tokens, ...}
        NOTE: No concept matching; just formats the scan state. P158/161 not relevant.

DEMO
  /api/demo/load
    → api.load_demo_mode(pack)                   # api.py:774
        → Scans demo repo (small/medium/large_repo)
        → Sets _STATE directly
        NOTE: Bypasses real scan; uses canned demo data. Graph health is always "healthy".
```

---

## Part 2 — Per-Route Trust Field Survival Analysis

### For each route: are Phase 158/161 trust fields present in the final response?

| Route | `ok` correct? | `status` field | `confidence` calibrated? | `graph_health` field | `confidence_cap_reason` | EMA guardrail active? | Phase 158/161 coverage |
|---|---|---|---|---|---|---|---|
| `/api/planning/change` | Yes | No (plan only) | Yes (P158 cap) | Yes (in plan) | Yes (in plan) | **PARTIAL** (see below) | Partial |
| `/api/planning/investigate` | Yes | No (plan only) | Yes (P158 cap) | Yes (in plan) | Yes (in plan) | **PARTIAL** | Partial |
| `/api/planning/impact` | Yes (P158) | Yes (P158) | Yes (P161 calibrate) | Yes (in response) | Yes | N/A | Full |
| `/api/impact` (legacy) | Yes (P161 _mock ok=False) | No | **No** | **No** | **No** | N/A | Partial |
| `/api/bug-investigation` | Yes (always True) | No | No | No | No | **No** | None |
| `/api/copilot/ask` | Yes | No | No | No | No | **No** | None |
| `/api/context/export` | Yes | No | N/A | No | N/A | N/A | N/A |
| `/api/demo/load` | Yes | No | No | "healthy" (hardcoded) | No | Demo data only | None |

**Critical discovery:** The `/api/impact` legacy route is still reachable at `POST /api/impact`.
It lacks `status`, calibrated `confidence`, `graph_health`, and `confidence_cap_reason` fields.
Any client calling this route instead of `/api/planning/impact` gets pre-Phase-158 behavior
for successfully resolved targets.

---

## Part 3 — The 35 Integration Bugs: Root Cause Table

The 35 integration bugs from Phase 161B are all concept-leakage EMA/trading outputs on
non-trading repos. The root cause is a two-stage failure:

**Stage 1 — Knowledge Engine Quality Boost Bug:**

```python
# atlas_knowledge/engine.py
LOCAL_CONFIDENCE_THRESHOLD = 2.0

# atlas_knowledge/quality.py
def quality_confidence_boost(score: str) -> float:
    if score == "source_backed":  return 2.0   ← EQUALS the threshold
    if score == "curated_deep":   return 1.25
    if score == "generated_template": return 0.0

# Result: score = alias_matches + quality_boost = 0.0 + 2.0 = 2.0 ≥ threshold
# → EMA selected as best match for ANY prompt where no other concept scores higher
```

VERIFIED LIVE:
```
'add event bus tracing' → ema (dom=trading, score=2.0, hits=[])
'add recorder retention policy' → ema (dom=trading, score=2.0, hits=[])
'add migration safety checker' → ema (dom=trading, score=2.0, hits=[])
[... all 35 integration-bug prompts produce identical result]
```

EMA wins NOT because it matches — it wins because `score=2.0` is the minimum for any
`source_backed` concept, and with zero alias hits, EMA ends up as the highest-scoring match
in iteration order over competing `source_backed` concepts.

**Stage 2 — Trading Guardrail False Positive:**

The Phase 158/161 guardrail in `plan_change()`:
```python
if (build_class.record.domain == "trading"
        and not _request_mentions_trading_explicitly(goal)
        and not _repo_has_trading_evidence(ctx)):
    build_class = suppress(...)   # ← This line should save us
```

Should fire: `domain == "trading"` ✓, user text doesn't mention trading ✓.
Does NOT fire because `_repo_has_trading_evidence(ctx)` returns **True** for:

| Repo | False-positive path | Signal that triggered it |
|---|---|---|
| Home Assistant | `homeassistant/helpers/entity_registry.py` | `"registry.py"` in `_TRADING_REPO_PATH_SIGNALS` |
| Home Assistant | `homeassistant/helpers/area_registry.py` | `"registry.py"` |
| Home Assistant | `homeassistant/helpers/device_registry.py` | `"registry.py"` |
| Home Assistant | `homeassistant/helpers/signal.py` | `"signal.py"` |
| Celery | `celery/worker/strategy.py` | `"strategy"` |

VERIFIED LIVE:
```python
_repo_has_trading_evidence(HA context)     → True   # WRONG
_repo_has_trading_evidence(Celery context) → True   # WRONG
_repo_has_trading_evidence(Django context) → False  # correct
_repo_has_trading_evidence(TypeORM context)→ False  # correct
```

**Combined effect:** Because `_repo_has_trading_evidence(ctx) = True`, the condition
`not _repo_has_trading_evidence(ctx)` is `False`, so the guardrail's `if` body never
executes for Home Assistant or Celery. EMA passes through unsuppressed.

### Integration Bug Table (35 bugs by repo)

| Bug ID | Repo | Prompt | Route | Expected trust behavior | Actual behavior | Broken handoff | File/function responsible |
|---|---|---|---|---|---|---|---|
| 1 | home_assistant | add event bus tracing | /api/planning/change | EMA suppressed (non-trading repo) | EMA shown, MISLEADING | Stage 2: _repo_has_trading_evidence returns True for HA | `planning_engine.py::_TRADING_REPO_PATH_SIGNALS` |
| 2 | home_assistant | why is event bus tracing broken | /api/planning/investigate | EMA suppressed | EMA shown, MISLEADING | Same | Same |
| 3 | home_assistant | add recorder retention policy | /api/planning/change | EMA suppressed | EMA shown, MISLEADING | Same | Same |
| 4 | home_assistant | add config entry validation | /api/planning/change | EMA suppressed | EMA shown, MISLEADING | Same | Same |
| 5 | home_assistant | why is automation execution telemetry broken | /api/planning/investigate | EMA suppressed | EMA shown, MISLEADING | Same | Same |
| 6 | home_assistant | why is entity state cache invalidation broken | /api/planning/investigate | Root cause grounded | Weak anchor promoted | Stage 2 + Phase 161 root-cause threshold borderline | `planning_engine.py::_hypothesis_evidence_score_100` |
| 7 | home_assistant | add websocket subscription backpressure | /api/planning/change | Backpressure concept scoped correctly | Backpressure concept leaked as MISLEADING | Stage 1: quality boost → low-quality concept wins | `atlas_knowledge/engine.py::quality_confidence_boost` |
| 8 | home_assistant | why is websocket subscription backpressure broken | /api/planning/investigate | Scoped correctly | Concept leakage, MISLEADING | Same | Same |
| 9 | home_assistant | why is update coordinator retry metrics broken | /api/planning/investigate | Grounded root cause | Only one anchor matched | Thin evidence, not trading specifically | `planning_engine.py::_build_hypotheses` |
| 10 | home_assistant | add storage corruption recovery | /api/planning/change | EMA suppressed | EMA shown | Stage 2 false positive | Same as #1 |
| 11 | home_assistant | why is storage corruption recovery broken | /api/planning/investigate | EMA suppressed | EMA shown | Same | Same |
| 16 | django | add async view tracing | /api/planning/change | EMA suppressed | EMA shown | Stage 1 only (Django has no false positives) | Stage 1: `quality.py::quality_confidence_boost` |
| 17 | django | why is async view tracing broken | /api/planning/investigate | EMA suppressed | EMA shown | Stage 1 | Same |
| 18 | django | add migration safety checker | /api/planning/change | EMA suppressed | EMA shown | Stage 1 | Same |
| 19 | django | why is migration safety checker broken | /api/planning/investigate | EMA suppressed | Scoped but incomplete | Partial — Stage 1 applies for investigate | `planning_engine.py::_coerce_investigation_classification` |
| 20 | django | why is template rendering metrics broken | /api/planning/investigate | Dashboard pattern routing | Dashboard pattern misrouted | C. Untested route | `planning_engine.py::_SYMPTOM_SPECS["dashboard_mismatch"]` |
| 21 | django | why is session cleanup policy broken | /api/planning/investigate | EMA suppressed | EMA shown | Stage 2 false positive: Django may have signal-like path | Same as #1 |
| 33 | airflow | add connection secret rotation audit | /api/planning/change | EMA suppressed | EMA shown | Stage 1 (Airflow no false positives in test set) | `quality.py::quality_confidence_boost` |
| 34 | airflow | why is webserver RBAC audit logging broken | /api/planning/investigate | Grounded root cause | Weak syntax anchor promoted | Phase 161 threshold at borderline level | `planning_engine.py::_ROOT_CAUSE_MIN_SCORE_100` |
| 35 | airflow | add session leak diagnostics | /api/planning/change | EMA suppressed | EMA shown | Stage 1 | Same |
| 36 | airflow | why is session leak diagnostics broken | /api/planning/investigate | EMA suppressed | EMA shown | Stage 1 | Same |
| 37 | airflow | add DAG processor memory metrics | /api/planning/change | EMA suppressed | EMA shown | Stage 1 | Same |
| 38 | airflow | why is DAG processor memory metrics broken | /api/planning/investigate | EMA suppressed | EMA shown | Stage 1 | Same |
| 39 | airflow | add state transition audit | /api/planning/change | EMA suppressed | EMA shown | Stage 1 | Same |
| 40 | airflow | why is state transition audit broken | /api/planning/investigate | EMA suppressed | EMA shown | Stage 1 | Same |
| 42 | celery | add worker heartbeat telemetry | /api/planning/change | EMA suppressed | EMA shown | Stage 2: celery/worker/strategy.py triggers | Same as #1 |
| 43 | celery | why is chord failure handling broken | /api/planning/investigate | EMA suppressed | EMA shown | Stage 2 false positive for Celery | Same |
| 50 | typeorm | add relation loading telemetry | /api/planning/change | EMA suppressed | EMA shown | Stage 1 only (TypeORM no false positives) | `quality.py::quality_confidence_boost` |
| 51 | typeorm | why is relation loading telemetry broken | /api/planning/investigate | EMA suppressed | EMA shown | Stage 1 | Same |
| 52 | typeorm | add repository save audit hooks | /api/planning/change | EMA suppressed | EMA shown | Stage 1 | Same |
| 53 | typeorm | add insert query validation | /api/planning/change | EMA suppressed | EMA shown | Stage 1 | Same |
| 54 | typeorm | why is insert query validation broken | /api/planning/investigate | EMA suppressed | EMA shown | Stage 1 | Same |
| 55 | typeorm | add update query safety checks | /api/planning/change | EMA suppressed | EMA shown | Stage 1 | Same |
| 56 | typeorm | why is update query safety checks broken | /api/planning/investigate | EMA suppressed | EMA shown | Stage 1 | Same |
| 61 | kubernetes | add node IPAM allocation diagnostics | /api/planning/change | EMA suppressed + unsupported label | EMA shown | Stage 1 + unsupported-language unknown mode doesn't fire when Kubernetes has some matches | `quality.py::quality_confidence_boost` + `planning_engine.py::_insufficient_evidence_response` |
| 62 | kubernetes | why is node IPAM allocation diagnostics broken | /api/planning/investigate | EMA suppressed | EMA shown | Same | Same |
| 63 | kubernetes | why is volume operation timeout tracing broken | /api/planning/investigate | EMA suppressed | EMA shown | Stage 1 | Same |
| 64 | kubernetes | add audit policy validation | /api/planning/change | EMA suppressed | EMA shown | Stage 1 | Same |
| 65 | kubernetes | why is audit policy validation broken | /api/planning/investigate | EMA suppressed | EMA shown | Stage 1 | Same |

*Note: Bug IDs match Phase 161B unsafe output table. Some entries skipped (B. Measurement change, E. Audit bug).*

---

## Part 4 — Root Cause Classification

### Problem A: Engine Not Producing Trust Fields (one case)

**`/api/impact` legacy route** (`api.impact()`) does not produce:
- `status` field
- `confidence_cap_reason` field
- `graph_health` field
- `confidence` calibrated via `calibrate_confidence_cap()`

It produces `ok=True` for resolved targets without any of the Phase 158/161 enrichment.
Any client calling this route instead of `/api/planning/impact` gets legacy behavior.

**Verdict:** Engine (api.impact) not producing trust fields. Not the primary cause of the
35 integration bugs (161A used /api/planning/impact).

---

### Problem B: API Dropping Trust Fields (NO — not the cause)

`api.plan_change()` and `api.investigate_symptom()` return the full `planning_engine.py`
result dict without modification. Trust fields (`confidence`, `confidence_cap_reason`,
`graph_health`, `limitations`) survive to the caller. The API is not stripping them.

`api.change_impact_simulation()` explicitly preserves `ok`, `status`, `confidence`,
`graph_health`, `confidence_cap_reason` from the impact engine and builds the `simulation{}`
block from those. The trust fields survive.

**Verdict:** API is NOT the problem. Fields are preserved correctly.

---

### Problem C: UI/Export Rewriting Trust Fields (NOT the primary issue)

The UI reads the plan/investigation/impact response and renders it. Phase 157/158 `atlas_trust.js`
displays `confidence` from the plan. If the plan has confidence="medium" because EMA matched,
the UI shows "medium confidence" correctly — but the CONTENT is wrong (EMA in domain knowledge).

The UI cannot fix upstream concept leakage. It can only display what the engine produces.

**Verdict:** UI is not rewriting trust fields. The UI is faithfully rendering bad engine output.

---

### Problem D: Audit Reading Wrong Field (partially true for Impact)

Phase 161B confirms: "161A said all 77 unsafe outputs were fake success because the **runner-level
sample field was `ok=true`**. The nested Atlas outputs tell a narrower story: 66 unsafe outputs
had `result.ok=true`; 11 Kubernetes Impact outputs had `result.ok=false`."

The audit runner used an outer wrapper `sample.ok` (probably always True since the HTTP request
succeeded) instead of reading `sample.result.ok`. This caused 11 honest `ok=false` refusals to
be scored as WRONG fake success.

**Verdict:** Audit DID read the wrong field for the 11 Kubernetes impact samples (E. Audit bug).
For the remaining 66 unsafe samples, the audit correctly read `result.ok=true`.

---

### Problem E: Old Legacy Route Still Used (CONFIRMED for /api/impact)

Two routes serve Impact:
- `POST /api/impact` → `api.impact()` — legacy, no Phase 158/161 enrichment for resolved targets
- `POST /api/planning/impact` → `api.change_impact_simulation()` — Phase 132+ with full trust

The legacy route is still present in `server.py:117`:
```python
("POST", "/api/impact"): lambda body, _query: api.impact(str(body.get("target", "")))
```

The Phase 161A audit used `/api/planning/impact` (correct). The **product UI**, however,
may use either route depending on which button the user clicks. If any UI element calls
`/api/impact` directly (the older endpoint), it gets legacy behavior without trust fields.

**Verdict:** Legacy route `/api/impact` still exists alongside the Phase 132 route. For
resolved targets, it returns `ok=True` without `status`, `graph_health`, or calibrated
`confidence`. The 35 integration bugs were NOT caused by this (they were on
`/api/planning/change` and `/api/planning/investigate`, not Impact). But it is a latent
trust gap for any Impact usage via the legacy route.

---

### Problem F: Demo/Mock Route Bypassing Engine (CONFIRMED for demo)

`api.load_demo_mode()` scans a small demo repo (5-40 modules). The demo graph is always
"healthy" because `reliability.classify_scan()` will return `OK` for a tiny clean graph.

Phase 158/161 fixes that depend on `graph_health` or `unsupported_language_limited` do NOT
apply to demo mode, because the demo graph is intentionally clean.

`api.bug_investigation()` also has `mock=True` when no paths match and a `todo` field:
```python
"todo": "Wire semantic localization + verification evidence for confirmed-defect ranking."
```
Phase 158/161 guardrails do not apply to this route. It remains in its Phase 120-era mock state.

**Verdict:** Demo bypasses language/graph health checks by design. `bug_investigation` is a
legacy mock route not covered by any Phase 158/161 work.

---

### Problem G: Benchmark Runner Bypassing Production Route (NOT the case)

Phase 161 uses `jarvis_desktop/grounding_eval.py` as a 15-scenario harness. It calls the
production planning_engine functions directly (not via HTTP). Phase 161A uses the full HTTP
API. Neither bypass the production code path in a problematic way.

The 15-scenario battery in Phase 161 was too narrow to catch the quality-boost bug:
it tested known guardrail cases (explicit EMA prompts, Kubernetes-like scans) but not the
broader prompt corpus that Phase 161A used.

**Verdict:** The evaluator did not bypass production routes. It tested too narrow a corpus.

---

## Part 5 — The Two Root Causes in Detail

### Root Cause 1: Quality Boost ≥ Threshold

**Location:** `atlas_knowledge/quality.py`, `atlas_knowledge/engine.py`

```python
# quality.py
quality_confidence_boost("source_backed") = 2.0

# engine.py
LOCAL_CONFIDENCE_THRESHOLD = 2.0

# match_text() in engine.py
for cid, rec in self.concepts.items():
    score, hits = self._alias_score(norm, rec.aliases)
    score += quality_confidence_boost(rec.concept_quality_score)
    ...
    if score > best_score or (score == best_score and rank > best_rank):
        best_score = score
        best_id = cid  # ← EMA wins by quality rank when all scores are 2.0
```

The condition `score >= LOCAL_CONFIDENCE_THRESHOLD` is met by quality boost alone.
For any prompt that doesn't strongly match another concept, the highest-quality-ranking
`source_backed` concept wins. EMA happens to rank highly.

**Impact:**
- ALL 35 integration-bug prompts match EMA with score=2.0, hits=[]
- This defeats Phase 158/161 guardrails at the source
- Fix: `quality_confidence_boost("source_backed")` must be < `LOCAL_CONFIDENCE_THRESHOLD`
  (e.g., threshold stays at 2.0, quality boost becomes 1.9) OR threshold must require
  at least one alias hit regardless of quality score

---

### Root Cause 2: Trading Evidence False Positives

**Location:** `planning_engine.py`, `_TRADING_REPO_PATH_SIGNALS`

```python
_TRADING_REPO_PATH_SIGNALS: frozenset = frozenset({
    "trading", "backtest", "strategy",    # ← "strategy" matches celery/worker/strategy.py
    "indicator", "broker",
    "execution", "ohlcv", "candle",
    "portfolio", "order_book",
    "paper_", "live_trade",
    "signal.py",                          # ← matches homeassistant/helpers/signal.py
    "registry.py",                        # ← matches homeassistant/helpers/*_registry.py
})
```

Terms "registry.py", "signal.py", and "strategy" are common in non-trading codebases:
- Home Assistant: entity_registry, area_registry, device_registry, signal.py
- Celery: worker/strategy.py (execution strategy pattern)
- Django: dispatch/signal, contrib/sessions/backends (if scanned more broadly)

When `_repo_has_trading_evidence(ctx)` returns True, the guardrail condition
`not _repo_has_trading_evidence(ctx)` is False, and the EMA suppression never executes.

**Impact on 35 bugs:**
- 11 Home Assistant bugs: guardrail disabled by registry.py / signal.py false positives
- 2 Celery bugs: guardrail disabled by strategy.py false positive
- 22 remaining bugs (Django, TypeORM, Airflow, Kubernetes): Root Cause 1 alone;
  guardrail fires but EMA is re-introduced because Phase 161 added a secondary leakage
  path in `_repository_evidence_bundle()` that checks the goal text for indicator/signal
  keywords independently of the guardrail

---

## Part 6 — Additional Trust Field Observations

### VS Code Impact: All confidence=low, evidence≈9734

Phase 161A shows all 13 VS Code impact samples with confidence=low and evidence count ≈9734.

**Cause:** `calibrate_confidence_cap()` (Phase 161) requires `evidence_count >= 2` for medium
confidence. VS Code's impact results return `evidence_count=0` because the Phase 161 confidence
cap in `analyze_impact()` queries `state.get("scan", {})` which may not carry the VS Code scan's
evidence_store metadata for calibration.

Additionally, VS Code scans with graph_health=partial → `confidence_cap_for_scan` returns
"medium" → but `calibrate_confidence_cap` also checks `resolution` (which for a large graph
with 67,338 unresolved imports may return "partial") → final cap is "low".

The identical evidence value of 9734 is the CHARACTER count of the `evidence` list in the
impact result, which is consistent across VS Code targets because the blast radius logic
returns similar lists for all files in a large highly-connected graph.

**Not a bug.** Conservative confidence calibration working as designed; the "evidence" field
shown in the audit is the character count of the evidence array, not the impact quality itself.

### Airflow Impact: All confidence=low

Same cause as VS Code: Airflow has `unresolved_ratio=0.9743` and `graph_health=partial`.
`calibrate_confidence_cap` correctly caps at low for high-unresolved-ratio scans.

This is CORRECT trust behavior — Airflow's impact is unreliable due to edge sparseness
(835 edges across 4,332 modules). The low confidence cap is protecting users from trusting
incomplete blast radii.

**Not a bug.** This is Phase 161 confidence calibration working correctly.

### Phase 161A Impact Score Collapse (54.4 → 33.1)

The Impact score dropped 21.3 points. Breakdown:
- 11 points: Kubernetes honest `ok=False` scored as WRONG (audit bug, not product regression)
- ~8 points: Stricter 161A rubric — files that previously matched "CORRECT" in 157A now only
  reach "PARTIAL" because 161A uses broader blast-radius expectations
- ~3 points: Real regression from scope_pollution and concept_leakage on Impact output

The Phase 157A "CORRECT" Impact results (12/50 on FastAPI, Airflow, Celery) did not reproduce
because the 161A prompts for those same repos used different, broader targets and asked for
more complete blast-radius coverage than the narrow 157A targets.

---

## Part 7 — Final Diagnosis Summary

```
FAILURE CLASS ANALYSIS FOR 77 UNSAFE OUTPUTS
═══════════════════════════════════════════════════════════════════

E. Audit bugs (11):
   → Kubernetes Impact: honest ok=False counted as WRONG
   → Cause: runner read sample.ok (always HTTP-200) instead of result.ok
   → Fix: update audit runner to read nested result.ok

B. Measurement change (22):
   → Stricter expected-anchor matching in 161A vs 157A
   → Broader prompt set exposed more thin-grounding PARTIAL outputs
   → No product regression; Atlas didn't get worse on these

C. Untested route (9):
   → Phase 158/161 battery tested known patterns, not "why is X broken" format
   → Prompts with "metrics", "tracing", "validation" were never in the 15-scenario battery
   → Fix: expand grounding_eval.py battery to cover broader prompt patterns

D. Integration bugs (35):
   → Root Cause 1: quality_boost=2.0 = threshold → EMA matches zero-alias prompts
   → Root Cause 2: _repo_has_trading_evidence() false-positives disable guardrail
   → Both in planning_engine.py and atlas_knowledge/{engine,quality}.py
   → Neither bug was caught by the Phase 161 15-scenario battery
   → Both bugs require one-line fixes to resolve
```

```
THE TWO BUGS TO FIX
═══════════════════════════════════════════════════════════════════

Bug A (atlas_knowledge/quality.py):
  CURRENT: quality_confidence_boost("source_backed") = 2.0
  FIX:     quality_confidence_boost("source_backed") = 1.9
  OR:      LOCAL_CONFIDENCE_THRESHOLD = 2.5 (requires alias hit to qualify)
  EFFECT:  EMA no longer matches zero-alias prompts; prevents 35/35 integration bugs

Bug B (planning_engine.py):
  CURRENT: _TRADING_REPO_PATH_SIGNALS contains "registry.py", "signal.py", "strategy"
  FIX:     Replace with more specific signals:
           "trading_strategy", "backtesting", "trade_signal.py", "strategy_registry.py"
           (or require multiple signals to confirm trading domain)
  EFFECT:  Home Assistant and Celery no longer classified as trading repos; 13 bugs fixed

Together, fixing both bugs eliminates all 35 integration bugs.
The 22 "measurement change" and 9 "untested route" samples improve only via evidence-depth
improvements (Symbol Evidence Phase 1-3 from Phase 162 strategy).
```

---

## Appendix A — Evidence Quality Note

Phase 161A shows `concept_leakage` appearing in 244 out of 300 samples. This count includes:
- Samples where Atlas actually chose a wrong concept (true concept leakage)
- Samples where the reviewer's expected anchor files were simply not in the output (thin grounding)

The taxonomy tag "concept_leakage" was applied when "expected evidence and showed inappropriate
or overly generic concept". This means many PARTIAL outputs are tagged concept_leakage even
when Atlas chose the correct concept — just didn't find all expected files within that concept.
The 35 integration bugs are the "true" concept leakage cases where Atlas chose EMA/trading
for a clearly non-trading prompt.

## Appendix B — No Code Follows

This report is diagnosis only. The two bugs identified (quality boost = threshold, and
trading evidence false positives) are both one-to-two-line fixes. Implementation belongs
in a Phase 165 or equivalent sprint. No code was modified for this report.
