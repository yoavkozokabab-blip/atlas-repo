# Phase 102 — Real Architectural Risk Ranking Engine (Implementation Plan)

**Status:** Plan only. No implementation in this deliverable.
**Date:** 2026-06-01
**Goal:** Turn the current bottleneck output into a real ranked architectural-risk
engine that emits, per module: risk score, reason breakdown, evidence, affected
subsystems, refactor recommendation, and confidence level.

---

## 0. Current state (what already exists)

A **`phase102-v1`** engine already exists and is wired in:

- `builder_core/architectural_risk.py` — `rank_modules(index, graph, top)` returns
  per-module rows with `total_score`, `score_breakdown`, `signals`, `metrics`.
- `ask._answer_bottlenecks` calls it and attaches `result["architectural_risk_ranking"]`
  (tests in `test_phase100g`/`test_phase101a` assert this).

**v1 scoring is a pure additive weighted sum:**
```
total = fan_in*1.0 + fan_out*0.35 + 5(cycle) + 3(component_root)
      + loc_blocks(≤4) + 3(untested) + churn(≤3) + contract + 2(subsystem_hub)
```
Inputs already consumed: fan-in/fan-out, cycles, component roots, LOC
(`node.line_count`), test presence (stem match via `risk._test_corpus`), churn
(`index["churn"]`), contract evidence (`python_analysis`), subsystem cross-fan-in.

### Gaps vs the required 6-part output

| Required output | v1 | Gap to close in v2 |
|---|---|---|
| 1. risk score | `total_score` (unbounded additive) | **normalize to 0–100 + risk band** |
| 2. reason breakdown | `score_breakdown` ✅ | keep, add normalized composite view |
| 3. evidence | `signals` (partial) | **cite importers / cycle path / test file / LOC source** |
| 4. affected subsystems | ❌ missing | **add `affected_subsystems` (+count)** |
| 5. refactor recommendation | ❌ missing | **add deterministic `recommendation`** |
| 6. confidence level | ❌ missing (only graph `degraded`) | **add per-module `confidence`** |

**The core correctness problem v2 must fix:** the additive model lets fan-in
dominate, so `core.logger` (fan-in 144, **26 LOC, tested**) ranks #2 — wrong. Real
architectural risk is **blast radius × change difficulty × missing safety net**, not
fan-in alone. v2 makes size/coverage *modulate* fan-in so foundational-but-safe
modules rank low.

---

## 1. Files to edit

| File | Change |
|---|---|
| `builder_core/architectural_risk.py` | **Primary.** Refine `rank_modules`: normalized 0–100 score + band; add `affected_subsystems`, `recommendation`, `confidence`; richer `evidence`. New helpers: `_normalize_signals`, `_composite_score`, `_affected_subsystems`, `_recommendation`, `_module_confidence`. Bump `ENGINE_VERSION="phase102-v2"`, `SCHEMA_VERSION=2`. |
| `builder_core/ask.py` | `_answer_bottlenecks`: surface the new fields in `answer`/`evidence`/`interpretation` (it already calls the engine). Keep `result["architectural_risk_ranking"]`. |
| `builder_core/cli.py` | Add `arch-risk` subcommand: build index → graph → `rank_modules`; print ranked table; `--top N`, `--json`, optional `--full`. |
| `builder_core/tests/test_phase102_architectural_risk.py` | **New** test module (below). |
| `builder_core/README.md` | Document the `arch-risk` command + engine (1 short section). |

No new external dependency. Engine stays a deterministic consumer of depgraph +
RU-2 + (optional) `python_analysis`/`contract_facts`/`verification_evidence`.

---

## 2. Data model (v2)

```text
ArchitecturalRiskReport
  schema_version: 2
  engine_version: "phase102-v2"
  weights_version: 2
  graph_scope: production | full | degraded
  degraded: bool
  modules_considered: int
  import_cycle_count: int
  normalization: { fan_in_ref, loc_ref, fn_ref, churn_ref }   # the per-repo scales used
  ranked_modules: [ ModuleRisk, ... ]    # sorted by risk_score desc, then label

ModuleRisk
  rank: int
  module_id, path, label, dotted
  subsystem: str
  subsystem_role: str
  file_role: str
  risk_score: float            # 0–100
  risk_band: "critical" | "high" | "medium" | "low"
  confidence: "high" | "medium" | "low" | "unknown"      # (6) confidence level
  reason_breakdown: [ RiskFactor, ... ]                   # (2) reason breakdown
  composite: { blast_radius, change_difficulty, safety_gap, fragility, core }  # 0–1 each
  evidence: [ str, ... ]                                  # (3) evidence (cited)
  affected_subsystems: [ str, ... ]                       # (4)
  affected_subsystem_count: int
  recommendation: str                                     # (5) refactor recommendation
  metrics: { fan_in, fan_out, instability, line_count, function_count,
             in_import_cycle, cycle_id, has_test, churn_commits,
             unresolved_edges, parse_ok, transitive_dependents }

RiskFactor
  name: "fan_in" | "size" | "coverage_gap" | "cycle" | "instability"
        | "churn" | "contract" | "subsystem_hub"
  raw: number|bool
  normalized: float        # 0–1
  weight: float
  contribution: float      # points added to risk_score
  note: str                # human-readable ("import fan-in 212 — very high")
```

---

## 3. Scoring formula (v2 — normalized, modulated, banded)

### 3.1 Per-repo normalization (deterministic, cap-guarded)
Avoids tiny-repo inflation and giant-repo saturation. Refs computed from the scored
module set, floored by absolute constants:
```
fan_in_ref = max(FANIN_FLOOR=20,  p90(fan_in))
loc_ref    = max(LOC_FLOOR=600,   p90(line_count))
fn_ref     = max(FN_FLOOR=25,     p90(function_count))
churn_ref  = max(CHURN_FLOOR=10,  p90(churn_commits))

fan_in_n   = min(1, log1p(fan_in)   / log1p(fan_in_ref))   # log-scaled
loc_n      = min(1, line_count      / loc_ref)
fn_n       = min(1, function_count  / fn_ref)
churn_n    = min(1, churn_commits   / churn_ref)
instability= fan_out / (fan_in + fan_out)   if denom>0 else 0
subsys_n   = min(1, subsystem_cross_fan_in / 5)
coverage_gap = 1.0 if not has_test else COVERAGE_RESIDUAL=0.2   # presence ≠ full coverage
contract_gap = {none:1.0, weak:0.6, strong:0.2, n/a:0.0}        # 0 when unavailable
cycle      = 1.0 if in_import_cycle else 0.0
```

### 3.2 Composite (multiplicative core — fixes the logger problem)
```
blast_radius     = clamp( 0.70*fan_in_n + 0.30*subsys_n )            # widely depended on
change_difficulty= clamp( 0.55*loc_n + 0.25*fn_n + 0.20*churn_n )    # hard/likely to break
safety_gap       = clamp( 0.70*coverage_gap + 0.30*contract_gap )
fragility        = clamp( 0.60*cycle + 0.40*instability )

core   = blast_radius * change_difficulty            # BOTH required for real risk
risk01 = clamp( CORE_W*core*(1 + SAFETY_AMP*safety_gap) + FRAGILITY_W*fragility )
risk_score = round(100 * risk01, 1)

# documented constants (weights_version=2)
CORE_W=0.80   SAFETY_AMP=0.6   FRAGILITY_W=0.25
```

### 3.3 Bands
`critical ≥ 70 · high 45–69 · medium 25–44 · low < 25` (documented; tunable via
`weights_version`).

### 3.4 Worked examples (must hold; become tests)
| Module | fan_in | LOC | tested | cycle | expected |
|---|---:|---:|:--:|:--:|---|
| `config` (hub, huge, untested) | 212 | 2,181 | no | no | **critical** (high blast × high difficulty × untested) |
| `core.logger` (hub, tiny, tested) | 144 | 26 | yes | no | **low** (difficulty≈0 ⇒ core≈0) ← fixes v1 |
| `core.types` (hub, mid, untested) | 133 | 579 | no | no | **high** |
| `ring.x ↔ ring.y` (small cycle) | low | small | — | yes | **medium** (fragility, not core) |
| leaf util (no importers) | 0 | small | — | no | **low** |

### 3.5 reason_breakdown
Each factor reports `raw`, `normalized`, `weight`, `contribution` (its share of
`risk_score`, attributed by decomposing the composite), and a `note`. The composite
sub-scores (`blast_radius`, `change_difficulty`, `safety_gap`, `fragility`) are also
returned so the score is fully explainable.

---

## 4. The six outputs — how each is produced

1. **risk_score / band** — §3.
2. **reason_breakdown** — §3.5 (per-factor contributions + composite).
3. **evidence** — cited, not prose: top importing modules (sample of the reverse
   `imports` edges, with `file:line`), the cycle path if any (`ring/x.py →
   ring/y.py → ring/x.py`), the test file or "no test reference found", and the LOC
   source node. Each evidence line traces to a real graph/index fact.
4. **affected_subsystems** — distinct subsystems (path top-segment) of the module's
   **dependents** (reverse `imports` edges → `to == module`, take each `from`'s
   subsystem). Optionally extend to transitive dependents via the Phase 94B impact
   reverse-closure (flagged, off by default for cost). Returns the list + count.
5. **recommendation** — deterministic template keyed by the **dominant** composite
   term (no LLM):
   - `change_difficulty` dominant + high blast → "Split `<module>` (`<LOC>` LOC,
     `<fan_in>` importers) into focused modules to narrow blast radius."
   - `safety_gap` dominant + high blast → "Add test coverage for `<module>` before
     changing it (`<fan_in>` dependents, no test reference found)."
   - `fragility`/cycle dominant → "Break the import cycle `<A ↔ B>` (extract the
     shared symbols or use a local import)."
   - `instability` dominant → "Reduce `<module>`'s outgoing dependencies
     (fan-out=`<fan_out>`)."
   Marked as a heuristic suggestion.
6. **confidence** — per-module, from data completeness:
   - `high`: `graph_scope=production` (not degraded) ∧ `parse_ok` ∧ test presence
     determinable ∧ few unresolved import edges touch the module.
   - `medium`: parse error, or many `unresolved.imports_external`/`calls_unresolved`
     near the module (fan-in is a lower bound), or contract data absent.
   - `low`/`unknown`: degraded graph, or metrics largely missing.

---

## 5. Edge cases

| Case | Handling |
|---|---|
| **Degraded graph** (still over cap) | report `graph_scope=degraded`, empty/partial ranking, all `confidence=unknown`, honest message (no guessing). Rare after Phase 100G. |
| **Empty repo / no production modules** | empty `ranked_modules` + clear message. |
| **Parse error** (`parse_ok=False`) | LOC kept, `function_count=0`; `confidence ≤ medium`; evidence notes the parse error. |
| **Unresolved / dynamic imports** | fan-in is a **lower bound**; many unresolved edges near a module → `confidence` reduced; never inflate. |
| **Foundational-but-safe** (logger) | the multiplicative core makes it `low`; **explicit test** guards this. |
| **`__init__.py` / packages** | scored normally but flagged in evidence (package re-export fan-in is real coupling but expected); recommendation avoids "split". |
| **Ties** | deterministic order: `risk_score` desc, then `label` asc. |
| **Churn absent** (shallow git) | `churn_n=0`; not penalized; noted (churn unavailable). |
| **Contract/verification unavailable** | `contract_gap=0` (no effect on score); `confidence` notes "contract data not available". |
| **Tiny repo inflation** | absolute `*_ref` floors prevent a 50-LOC file in a 3-file repo ranking critical. |
| **Test false-negative** (dynamic test load) | presence heuristic may miss; `confidence` note; v2 may add the test→production import-edge signal (build graph `include_tests=True`) as a stronger presence check. |
| **Determinism** | identical repo → identical scores/order (no randomness; refs from sorted data). |

---

## 6. Tests (`test_phase102_architectural_risk.py`)

Synthetic repo: a `config`-like hub (high fan-in, large, untested), a `logger`-like
hub (high fan-in, tiny, tested), a mid untested hub, a `ring.x↔ring.y` cycle, and a
leaf util.

| Test | Asserts |
|---|---|
| `test_ranking_orders_by_real_risk` | config-like ranks above logger-like (fixes v1) |
| `test_foundational_safe_module_not_critical` | logger-like `risk_band` is `low` despite high fan-in |
| `test_score_is_bounded_and_banded` | every `risk_score ∈ [0,100]`; band matches thresholds |
| `test_all_six_outputs_present` | each module has score, reason_breakdown, evidence, affected_subsystems, recommendation, confidence |
| `test_affected_subsystems_correct` | config-like's `affected_subsystems` = the dependents' subsystems |
| `test_recommendation_matches_dominant_factor` | untested-hub → "add test"; cycle → "break the import cycle"; large-hub → "split" |
| `test_confidence_high_on_clean_small_repo` and `..._unknown_on_degraded` | confidence reflects graph state (monkeypatch `_MAX_FILES`) |
| `test_cycle_module_reported_with_fragility` | cycle members carry the `cycle` factor + path evidence |
| `test_deterministic` | two runs → identical report |
| `test_no_detector_or_benchmark_change` | engine is read-only; suite + QuixBugs unaffected |

Compatibility: keep `result["architectural_risk_ranking"]` and
`ranked_modules[0]["score_breakdown"]` so existing `test_phase100g`/`test_phase101a`
assertions still pass (extend, don't rename).

---

## 7. Expected CLI / ask output

### 7.1 `ask` (bottleneck mode) — answer text
```
Architectural risk ranking (production scope; confidence in brackets):
1. config — risk 84.2 CRITICAL [high]
   why: blast-radius 0.95 (fan-in 212) × change-difficulty 0.88 (2,181 LOC) × untested
   affects 8 subsystems: brain, core, voice, actions, conversation, assistant, ...
   recommendation: Split config (2,181 LOC, 212 importers) into focused modules.
2. core.types — risk 61.0 HIGH [high]
   why: fan-in 133 × 579 LOC × untested
   ...
core.logger: risk 12.4 LOW [high] — high fan-in (144) but 26 LOC and tested.
```
`findings` = top module labels; `evidence` = cited importer/cycle/test/LOC lines;
`interpretation` carries `graph_scope`, `weights_version`, per-module `confidence`.

### 7.2 CLI `arch-risk`
```
py -3 -m builder_core.cli arch-risk --project . --top 10
RANK  MODULE          SCORE  BAND      CONF   TOP REASONS                  RECOMMENDATION
1     config          84.2   CRITICAL  high   fan-in 212, 2181 LOC, untd   split into focused modules
2     core.types      61.0   HIGH      high   fan-in 133, 579 LOC, untd    add tests; consider split
...
(graph_scope=production · 673 modules · 4 cycles · weights v2)

# --json emits the full ArchitecturalRiskReport for tooling.
```

---

## 8. Safety & scope

- Reuses depgraph (Phase 100G production scope), RU-2 roles/subsystems, and
  optional `python_analysis`/contract/verification — **no new analysis system**.
- No detector, finding-schema, benchmark, or promotion change. Read-only;
  deterministic; "unknown beats guessing" (degraded/parse/unresolved → lower
  confidence, never invented risk).
- Recommendations are labeled heuristic suggestions, not prescriptions.

## 9. Deliverable / report path

- This plan: **`reports/phase102_architectural_risk_ranking_plan.md`**.
- Implementation phase will add `reports/phase102_architectural_risk_engine.md`
  (results on `local_jarvis`: the ranked table, band distribution, confidence
  distribution) — separate from this plan.

---

## 10. Bottom line

`phase102-v1` already turns the graph into an additive bottleneck score and is
wired into `ask`. Phase 102 (v2) makes it a **real** risk engine by: normalizing the
score into 0–100 bands; replacing the fan-in-dominated sum with a **blast × difficulty
× safety** composite (so foundational-but-safe modules like `core.logger` rank low);
and adding the three missing required outputs — **affected subsystems, a deterministic
refactor recommendation, and a per-module confidence level** — each evidence-cited and
deterministic.
