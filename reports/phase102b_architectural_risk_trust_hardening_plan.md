# Phase 102B — Architectural Risk Ranking Trust Hardening (Plan)

**Status:** Plan only. No implementation.
**Date:** 2026-06-01
**Scope:** Fix seven confirmed trust/correctness defects in the `phase102` risk
engine (`builder_core/architectural_risk.py`) and its inputs (`depgraph.py`,
`repository_understanding`). Deterministic, read-only; no detector/benchmark change.

---

## 0. Summary of root causes (all confirmed in code)

| # | Issue | Root cause (file:function) |
|---|---|---|
| 1 | Repeated imports inflate fan-in | `architectural_risk._graph_dependency_metrics` counts **edges**, not distinct importers (`fan_in[to]+=1` per imports edge; edges are deduped by `(type,from,to,line,…)`, so multiple `from X import …` lines double-count the X←importer pair). |
| 2 | Fake/weak test presence | `architectural_risk` uses `risk._test_corpus` (a concatenated blob of all test paths + test prose) and `has_test = stem in blob` — a **substring match**. Common stems (`config`, `base`, `app`, `core`) match spuriously. |
| 3 | Static findings counted as contract evidence | `architectural_risk._contract_evidence_score` iterates `analysis["findings"]` (detector **bug** leads) and adds `WEIGHT_CONTRACT_*` by severity — mislabels detector findings as "contract evidence" and folds bug-risk into architectural-risk. |
| 4 | Isolated huge files outrank hubs | Additive score: `loc_score(≤4)` + `untested(3)` + `churn` contribute **independently of fan-in**, so a 2,000-LOC file with **0 importers** can outscore a real low-LOC hub. No blast-radius gate. |
| 5 | Cycles duplicated by rotation | `depgraph._import_cycles` records a cycle per DFS start node; rotations produce different tuples and the `seen` set keys on the exact tuple, so `A→B→A` and `B→A→B` both count. `import_cycle_count` is ~2×. |
| 6 | `component_root` bonus dead/useless | `component_roots = {largest_components[:5].root}`; the union-find `root` is an **arbitrary representative** node, not a centrality signal. The `+3` lands on a meaningless node (one giant component → one arbitrary root). |
| 7 | Real source under `reports`/`fixtures`/`samples` excluded | (a) `depgraph._production_scope_filter` excludes any file whose top segment ∈ `_DATASET_PARTS = {data,dataset,datasets,fixtures,samples}`; (b) `classify_file_role` returns `report_history` for **any** path containing a `reports` dir (not extension-gated), so `reports/generator.py` is dropped. |

---

## 1. Fixes by issue

### Issue 1 — fan-in counts distinct importers
**Change (`_graph_dependency_metrics`):** accumulate **sets**, not counters.
```
fan_in[to]  = |{ from_module of resolved imports edges with to==module }|
fan_out[mod]= |{ to_module of resolved imports edges with from==mod }|
```
Collapse module-level multiplicity (multiple `from X import a` / `from X import b`
lines → one X←importer). Optionally surface `raw_import_edges` separately in
diagnostics so the de-duplication is visible.
*Scoring effect:* hubs imported once-per-importer are unchanged; modules imported
many times by few importers stop being inflated.

### Issue 2 — real test presence via the dependency graph
**Change (`architectural_risk`, remove `risk._test_corpus` dependency):** derive test
presence from **actual test→production import edges**:
- Build/obtain the graph with `include_tests=True` (Phase 100G already supports it),
  or pass a `test_import_map` into `rank_modules`.
- `has_test(module)` ⇔ **∃ a `test`-role module that imports it** (reverse imports
  edge from a test module to the production module).
- Fallback (only when include_tests graph unavailable): **exact** sibling test file
  `test_<stem>.py` / `<stem>_test.py`, not substring-in-blob.
Record the proving test path in evidence (or "no test reference found").
*Effect:* `config.py` is "tested" only if a test actually imports it — not because
the word "config" appears in some test's prose.

### Issue 3 — drop findings; use real contracts (or nothing)
**Change (`architectural_risk`):** **stop reading `analysis["findings"]`.** Architectural
risk must not pull detector bug-leads.
- Replace `_contract_evidence_score` with `_contract_factor(path)` that consumes
  **`contract_facts` (Phase 96A)**: presence/strength of return/nullability/type
  contracts. A module with **weak/absent** contracts on a wide public surface is a
  *risk amplifier* (`contract_gap`), not a bonus from findings.
- If `contract_facts` is unavailable for a module, contribute **0** and lower its
  confidence (no guessing). Remove `WEIGHT_CONTRACT_*`-by-severity logic entirely.
*Effect:* bug volume no longer leaks into architectural risk; the contract channel
measures missing contracts, correctly oriented.

### Issue 4 — gate structural risk on blast radius
**Change (scoring):** an isolated file is **not** an architectural hub. Adopt the
Phase 102 multiplicative core so size/coverage only count when the module is
depended upon:
```
blast = f(distinct_fan_in, subsystem_cross_fan_in)      # 0..1
size/untested/churn/contract enter via change_difficulty and safety_gap
core = blast * change_difficulty                         # 0 when blast≈0
```
Minimal alternative if v2 core is deferred: multiply the `loc`/`untested`/`churn`
contributions by `min(1, fan_in/HUB_REF)` so a 0-importer file gets ~0 structural
risk; report large isolated files under a separate **`large_file`** maintainability
note, not the architectural ranking.
*Effect:* a 2,000-LOC unimported script no longer outranks `config` (212 importers).

### Issue 5 — canonicalize cycles (no rotations)
**Change (`depgraph._import_cycles`):** canonicalize each detected cycle before
recording — drop the closing duplicate node, rotate so the lexicographically
smallest node is first, dedupe by that canonical tuple (and by node-set to catch
reverse traversal). `statistics.import_cycles` then lists each cycle **once**;
`import_cycle_count` is accurate. The engine consumes the de-duplicated list.
*Effect:* 2 real cycles report as 2, not 4; cycle evidence shows one path each.

### Issue 6 — remove the component_root bonus
**Change (`architectural_risk`):** delete `WEIGHT_COMPONENT_ROOT`, the
`component_roots` lookup, and the `component_root` breakdown key. Centrality is
already captured by distinct fan-in + subsystem cross-fan-in. (`largest_components`
stays in depgraph for diagnostics; it is simply no longer a risk input.)
*Effect:* no arbitrary `+3` on a union-find representative; scores become meaningful.

### Issue 7 — keep real source under reports/fixtures/samples
**Change (`depgraph` scope filter), low-risk and RU-2-preserving:**
1. **Narrow the location exclusion** from `_DATASET_PARTS` to the unambiguous corpus
   roots `{data, dataset, datasets}`. `fixtures`/`samples` are no longer
   blanket-excluded by location — their role decides (test fixtures → `test`;
   genuine source → `production_code` kept).
2. **Import-rescue:** re-include any role/location-excluded `.py` that is **imported
   by a kept production module** (resolve kept files' import targets via
   `module_map`; rescue targets that resolve to excluded files). This recovers
   `reports/generator.py` when production code imports it, while leaving the repo's
   own unimported `reports/*.md` history out.
Do **not** change `classify_file_role` (keeps RU-2/indexer/subsystem map and the
Phase 100G `reports/r.py` exclusion stable — `r.py` is unimported, so it stays out).
*Effect:* real, depended-on source under those folders is graphed; data/report
history is still excluded.

---

## 2. Files to edit

| File | Issues | Change |
|---|---|---|
| `builder_core/architectural_risk.py` | 1,2,3,4,6 | distinct fan-in/out; test presence from import edges; replace findings→contract_facts; blast-gated/multiplicative scoring; remove component_root. Bump `ENGINE_VERSION="phase102b"`, `SCHEMA_VERSION=2`. |
| `builder_core/bug_intelligence/depgraph.py` | 5,7 | canonicalize `_import_cycles`; narrow scope location set + import-rescue. |
| `builder_core/risk.py` | 2 | none required (architectural_risk stops calling `_test_corpus`; `risk-report` keeps it). |
| `builder_core/bug_intelligence/contract_facts.py` | 3 | read-only consumer; no change. |
| `builder_core/ask.py` | — | none beyond surfacing new fields already planned in 102. |
| `builder_core/tests/test_phase102b_architectural_risk_trust.py` | all | new (below). |
| existing 100G/101A/102 tests | 5,6 | minor updates where they assert removed keys / cycle counts (see §5). |

---

## 3. Scoring changes (consolidated)

- fan-in/fan-out → **distinct importing/imported modules** (issue 1).
- size/untested/churn → **gated by blast radius** (multiplicative core or fan-in
  scaling); isolated large files excluded from architectural ranking (issue 4).
- contract channel → **contract_facts presence/strength as a gap amplifier**, not
  finding counts (issue 3).
- **remove** `component_root` channel (issue 6).
- cycle channel reads **canonical** cycles (issue 5).
- Document all weights under `weights_version`; bump it. Scores re-baseline — this is
  intended (the old scores were untrustworthy).

---

## 4. Evidence-source changes

| Signal | Old (untrusted) | New (trusted) |
|---|---|---|
| fan-in | edge count | distinct importer modules |
| test presence | substring of stem in test blob | a test module **imports** the module (or exact `test_<stem>.py`) |
| contract | detector findings count | `contract_facts` contract presence/strength |
| cycles | rotation-duplicated list | canonicalized, deduped list |
| centrality | arbitrary UF component root | distinct fan-in + subsystem cross-fan-in only |
| scope membership | top-segment in `_DATASET_PARTS` | `{data,dataset,datasets}` + import-rescue |

Every evidence line should cite the concrete fact (importer paths, the proving test
file, the cycle path, the contract source) — no prose-substring inference.

---

## 5. Tests (`test_phase102b_architectural_risk_trust.py`)

| Test | Proves the fix |
|---|---|
| `test_repeated_imports_count_once` | module importing X on 3 lines → `fan_in[X]==1`; X's score reflects 1 distinct importer (issue 1) |
| `test_test_presence_requires_real_test_import` | a module with the word in test prose but **no test import** → `has_test=False`; a module a test actually imports → `True` (issue 2) |
| `test_findings_do_not_become_contract_evidence` | a module with many static findings but no contracts → contract channel 0; bug volume does not raise architectural score (issue 3) |
| `test_isolated_large_file_not_top_ranked` | a 2,000-LOC, 0-importer file ranks **below** a small real hub; appears (if at all) as `large_file`, not architectural (issue 4) |
| `test_cycles_not_duplicated_by_rotation` | `A↔B` → `import_cycle_count==1`; one canonical path in evidence (issue 5) |
| `test_no_component_root_channel` | `score_breakdown` has no `component_root`; removing it changes no ordering by arbitrary roots (issue 6) |
| `test_imported_source_under_reports_kept` | `reports/gen.py` imported by `core/app.py` is **in** the graph; unimported `reports/x.md` is not (issue 7) |
| `test_fixtures_samples_source_kept_when_real` | top-level `samples/lib.py` (production role) is kept; `fixtures/conftest.py` (test) excluded (issue 7) |
| `test_deterministic_and_bounded` | identical repo → identical report; scores bounded |
| `test_no_detector_or_benchmark_change` | suite + QuixBugs 12/0 unaffected |

Regression compatibility: keep `result["architectural_risk_ranking"]`,
`ranked_modules[*].score_breakdown`, and `score_breakdown["fan_in"]` (still present,
now distinct-count) so `test_phase100g`/`test_phase101a` assertions pass.

---

## 6. Compatibility risks & mitigations

| Risk | Affected | Mitigation |
|---|---|---|
| **Cycle-count change** (issue 5) halves `import_cycle_count` | any test asserting a specific count; bottleneck evidence wording | 101A asserts the substring `"cycle"` only — safe. Audit for `import_cycle_count ==` assertions; update to canonical count. |
| **Removed `component_root` key** (issue 6) | tests asserting that breakdown key | none assert it today; removing a key is safe. Bump `SCHEMA_VERSION`. |
| **Scope narrowing + import-rescue** (issue 7) | Phase 100G filter tests | `data/corpus` still excluded (`data` ∈ narrowed set) → `dataset_tree>=8` holds; `reports/r.py` unimported → still excluded → `not any(reports/)` holds. Verify rescue does not pull `r.py`. |
| **`classify_file_role` untouched** | RU-2 indexer, subsystem map | deliberately unchanged → zero RU-2 risk (the fix lives in the depgraph scope layer + rescue). |
| **Score re-baseline** (issues 1,3,4,6) | tests asserting ordering / `fan_in>0` | synthetic fixtures keep `config`-like #1 and `fan_in>0`; re-baseline is intended and documented via `weights_version`. |
| **Test-presence flips** (issue 2) | modules previously "tested" by substring | intended correctness change; document; the synthetic hub is untested by design so ordering tests are stable. |
| **`include_tests=True` second graph build** (issue 2) | cost on large repos | reuse one include_tests build; tests still excluded from the *scored* set, only consumed for the test-import map. |
| **Detector/benchmark** | engine is read-only | unchanged; re-run QuixBugs 12/0 + full suite as the gate. |

---

## 7. Bottom line

All seven defects are real and located. The hardening keeps RU-2 and the detectors
untouched: fix fan-in to count **distinct importers**; derive test presence from
**actual test imports**; stop laundering **detector findings as contracts** (use
`contract_facts`); **gate structural risk on blast radius** so isolated big files
don't masquerade as hubs; **canonicalize cycles**; **delete the arbitrary
component-root bonus**; and recover **real imported source** under
`reports`/`fixtures`/`samples` via a narrowed location set + import-rescue. Each
change is deterministic, evidence-cited, and re-baselined under a bumped
`weights_version`/`SCHEMA_VERSION`.
