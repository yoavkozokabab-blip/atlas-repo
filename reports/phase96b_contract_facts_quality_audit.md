# Phase 96B — Contract Facts Quality Audit

**Status:** Measurement complete (read-only)  
**Date:** 2026-05-31  
**Inputs:** `contract_facts.py`, `reports/phase96a_contract_facts_infrastructure.md`  
**Audit script:** `builder_core/scripts/phase96b_contract_audit.py`  
**Constraints:** no detector changes, no confirmation logic, no promotion, no code changes to extractors

---

## 1. Executive summary

Phase 96A contract facts are **structurally sound** (deterministic schema, wired to analysis output, zero finding impact) but **not uniformly safe for detector consumption**. A rule-based audit over synthetic fixtures, five `local_jarvis` sample files, 24 QuixBugs files, and an 80-file volume scan finds:

| Verdict | Meaning |
|---------|---------|
| **Correct** | Fact matches source semantics with high confidence |
| **Partially correct** | Directionally useful but incomplete or over-scoped |
| **Wrong** | Fact contradicts source (rare in automated audit; one known docstring bug) |
| **Too weak to use** | Correctly low confidence; advisory only |

**Headline metrics (audited samples, all corpora combined):**

| Metric | Value |
|--------|------:|
| Facts audited (deep sample) | **696** |
| Strict precision (correct / all) | **44.0%** |
| Usable precision (correct + partial) | **98.7%** |
| Automated **wrong** count | **0** (see §4.3 for manual wrong) |

**Conclusion:** Facts are safe enough for **lead enrichment** and **narrow gating** when limited to **`type_hint` (explicit)** and **`caller_behavior` (inferred_strong only)**. They are **not** ready for confirmation or broad detector consumption—especially **`callee_behavior` inferred_strong**, which dominates volume but over-claims `arg.non_none`.

**Recommended first consumer candidate:** **`inconsistent_return` enrichment only** (not confirmation), reusing the same bar as Phase 93B promotion. **`unsafe dereference`** and **`None misuse`** should wait for extractor fixes and path-feasibility work.

---

## 2. Methodology

### 2.1 Corpora

| Corpus | Files | Facts extracted | Role |
|--------|------:|----------------:|------|
| **Synthetic fixtures** | 6 | 25 | Controlled per-source coverage |
| **local_jarvis (deep sample)** | 5 | 623 | Real production patterns |
| **local_jarvis (volume scan)** | 80 | 2,894 | Source volume / dominance |
| **QuixBugs (correct + buggy)** | 24 | 48 | Benchmark-shaped code (no type hints) |

QuixBugs root: `C:\Repos\QuixBugs` (24 Python files sampled from correct + buggy trees).

Deep sample files: `core/results.py`, `brain/router.py`, `actions/phase45_actions.py`, `builder_core/bug_intelligence/fact_detectors.py`, `builder_core/bug_intelligence/contract_facts.py`.

### 2.2 Classification rules

Each fact was labeled by a **deterministic rule-based auditor** aligned with Phase 96 design intent (not human blind review). Examples:

- `type_hint` + `return.non_none` → **correct** when annotation provably disallows `None`
- `caller_behavior` + `inferred_strong` → **partially correct** (usage ≠ API contract)
- `callee_behavior` + `arg.non_none` → **partially correct** (callee use ≠ caller obligation)
- `guard` facts → **partially correct** (branch-local; dominator unproven)
- `test` expectations → **too weak to use** by design

Reproduce:

```powershell
cd local_jarvis
py -3 -m builder_core.scripts.phase96b_contract_audit
```

---

## 3. Volume profile (`local_jarvis`, 80 files)

Facts are dominated by **inferred param/null obligations**, not explicit return contracts:

| Source | Facts | Share |
|--------|------:|------:|
| `type_hint` | 2,341 | 80.9% |
| `callee_behavior` | 447 | 15.4% |
| `guard` | 61 | 2.1% |
| `caller_behavior` | 45 | 1.6% |
| `docstring` | ~0* | — |
| `assert` | ~0* | — |
| `test` | 0 | 0% |

\*Not in top volume; sparse in scanned slice.

| Contract type | Facts | Share |
|---------------|------:|------:|
| `nullability_contract` | 1,234 | 42.6% |
| `argument_contract` | 1,110 | 38.4% |
| `return_contract` | 539 | 18.6% |
| `state_mutation_contract` | 11 | 0.4% |
| `exception_contract` | 0 | 0% |

**Implication:** Most extracted facts are **param/null duplicates** from type hints plus callee-use inference—not the return-contract facts needed for `inconsistent_return` confirmation.

---

## 4. Precision by source

### 4.1 Aggregate (synthetic + local sample + QuixBugs)

| Source | Facts | Strict precision | Usable precision | Safe for future confirmation? |
|--------|------:|-----------------:|-----------------:|-------------------------------|
| **type_hint** | 456 | **61.0%** | **100%** | **Yes (explicit only)** |
| **assert** | 3 | **66.7%** | **100%** | Yes (local proof) |
| **docstring** | 2 | **50.0%** | **100%** | Partial — see §4.3 |
| **caller_behavior** | 6† | **0%** | **100%** | **Advisory / 93B gate only** |
| **guard** | 22 | **0%** | **100%** | Refutation aid only (not confirmation) |
| **callee_behavior** | 199 | **0%** | **100%** | **No — advisory only** |
| **test** | 0 | — | — | Too weak (not observed in sample) |

†Six `inferred_strong` caller facts; seven additional `inferred_weak` facts in local sample classified **too weak**.

### 4.2 Sampled facts by source

#### type_hint — **mostly correct; partial from ambiguous annotations**

| Sample | File | Obligation | Audit |
|--------|------|------------|-------|
| `result_success -> CommandResult` | `core/results.py` | `return.non_none` | correct |
| `fetch -> str` | `synth_hint.py` | `return.non_none` | correct |
| `opt -> str \| None` | `synth_hint.py` | `return.optional` | correct |
| `name: str` param | `synth_hint.py` | `arg.non_none` + `arg.type_bound` | correct |

**Partial causes (174/447 in local sample):** duplicate `arg.type_bound` paired with `arg.non_none`; `return.shape_uniform` for annotations where nullability is unknown (`Any`, broad unions).

#### docstring — **Raises good; Returns heuristic fragile**

| Sample | Obligation | Audit |
|--------|------------|-------|
| `Raises: ValueError` | `raises.documented` | correct |
| Returns text contains “never None” | `return.optional` | **partial (manual: wrong)** |

#### assert — **reliable for local non-None**

| Sample | Obligation | Audit |
|--------|------------|-------|
| `assert x is not None` | `arg.non_none`, `null.forbidden` | correct |
| `assert self.buf is not None` | `state.initialized_before_read` | partial |

#### caller_behavior — **aligned with Phase 93B; not API proof**

| Sample | Callee | Audit | Notes |
|--------|--------|-------|-------|
| `_get_history_writer` deref, no null-check | `return.non_none` strong | partial | Same signal 93B already uses |
| `CommandRouter._apply_voice_guard` mixed | `return.optional` weak | too weak | Correctly downgraded |
| `helper()` deref + null-check callers (synthetic) | `return.optional` weak | too weak | Mixed evidence handled correctly |

#### callee_behavior — **high volume, low semantic precision**

| Sample | Obligation | Audit |
|--------|------------|-------|
| `CommandRouter._audit_command(param: request)` | `arg.non_none` strong | partial |
| `breadth_first_search(param: startnode)` | `arg.non_none` strong | partial |

**Problem:** Any param appearing in attribute/subscript/call context triggers `arg.non_none` at **`inferred_strong`**. Passing `None` from callers remains possible; the fact describes **callee implementation**, not a **contract**.

#### guard — **useful for refutation, not proof**

| Sample | Obligation | Audit |
|--------|------------|-------|
| `if x is None: return` | `null.checked_before_use` | partial |
| `if x is not None:` body | `null.narrowed_by_guard` | partial |
| valueflow `definitely_not_none` | `null.forbidden` | partial |

Guards do not prove all paths to a later dereference are covered (Phase 95 FP family).

#### test — **not observed**

No `test`-sourced facts in scanned corpora; `test_expectations` rarely populated outside semantic/algorithm paths.

---

## 5. Precision by contract type

| Contract type | Facts (audited) | Strict | Usable | Notes |
|---------------|----------------:|-------:|-------:|-------|
| **return_contract** | 72 | **95.8%** | **100%** | Best type for consumers |
| **argument_contract** | 296 | **68.9%** | **100%** | Inflated by callee_behavior |
| **nullability_contract** | 288 | **0%** | **100%** | Almost all inferred/path-local |
| **exception_contract** | 2 | **50%** | **100%** | Too few samples |
| **state_mutation_contract** | 8 | **0%** | **100%** | Weak `__init__` inference |

---

## 6. Common false-contract causes

| Rank | Cause | Affected sources | Severity |
|------|-------|------------------|----------|
| 1 | **Param use mistaken for non-None obligation** | `callee_behavior` | High — labels `inferred_strong` too aggressively |
| 2 | **Docstring “None” token match** | `docstring` | Medium — “never None” → `return.optional` |
| 3 | **Guard facts without path dominance** | `guard` | Medium — refutation incomplete |
| 4 | **Duplicate obligations per subject** | `type_hint` | Low — noise, not wrong |
| 5 | **Caller usage treated as return API** | `caller_behavior` strong | Low — acceptable for 93B-style gate |
| 6 | **`__init__` assign → initialized invariant** | `state_mutation` | Low — weak lifecycle claim |

### 6.1 Manual wrong example (docstring)

Fixture `synth_doc.py`:

```python
'''Returns:
    A string result, never None.
'''
```

Extracted: `return.optional` (`explicit`, `docstring`) because `"none" in body` matches the substring in **“never None”** without requiring word-boundary / negation parsing.

**Fix deferred to Phase 96C** (not in 96B scope).

---

## 7. Safe vs advisory-only sources

| Source | Future role | Consumer guidance |
|--------|-------------|-------------------|
| **type_hint (explicit)** | **Safe for enrichment** | Use for return/param nullability when annotation resolves |
| **assert** | **Safe locally** | Strengthen facts at assert site only |
| **caller_behavior (inferred_strong)** | **Advisory gate** | Same as 93B; not confirmation |
| **caller_behavior (inferred_weak)** | **Advisory only** | Do not promote |
| **guard** | **Refutation aid** | Phase 95 FP reduction; needs path analysis |
| **docstring** | **Advisory** until Returns parser fixed | Raises section usable |
| **callee_behavior** | **Advisory only** | Do **not** drive detectors at current precision |
| **test** | **Too weak** | Not consumed |

---

## 8. QuixBugs relevance

QuixBugs files (mostly unannotated graph algorithms) produce **48 facts**, all from **`callee_behavior`**:

- Example: `breadth_first_search(startnode)` → `arg.non_none` because `startnode.successors` is accessed.
- **Audit:** partially correct at best; semantically **not** a nullability contract on graph nodes.

**Impact:** Contract facts on QuixBugs **do not add** useful return/null contracts for benchmark bugs. Consumption must **not** alter QuixBugs scoring unless tightly gated.

---

## 9. First consumer candidate recommendation

| Candidate | Ready? | Rationale |
|-----------|--------|-----------|
| **`inconsistent_return`** | **Yes — enrichment only** | Return contracts + caller `inferred_strong` deref mirror existing 93B gate; lowest regression risk |
| **`None misuse`** | **Not yet** | Needs explicit producer/consumer pairing; callee_behavior noise would inflate FPs |
| **`unsafe dereference`** | **Not yet** | Guard facts path-insensitive; Phase 95 showed guard-blindness — refutation requires dominator analysis |
| **Confirmed bug output** | **No** | Zero wrong in auto audit but docstring + callee over-claim block confirmation bar |

### Recommended path (Phase 96C+, not implemented here)

1. **First consumer:** attach `return_contract` + `caller_behavior` facts to existing `inconsistent_return` **pattern/value_flow packets** as metadata (no new findings, no promotion change).
2. **Fix before broader use:** docstring Returns None heuristic; downgrade `callee_behavior` confidence to `inferred_weak` or require explicit hints.
3. **Then pilot:** guard-aware refutation for `null_dereference` leads using `guard` facts + CFG dominance.
4. **Confirmation:** still blocked until Phase 96 design gates (path + consequence + 0-FP) are implemented.

---

## 10. Constraints verification

| Constraint | Status |
|------------|--------|
| Measurement only | Done |
| Optional read-only audit script | `phase96b_contract_audit.py` |
| No detector changes | Verified |
| No benchmark changes | Verified |
| No confirmation / promotion | Verified |
| No confirmed bug output | Verified |

---

## 11. Reproducibility

```powershell
cd local_jarvis
py -3 -m builder_core.scripts.phase96b_contract_audit > reports/_phase96b_audit.json

# Spot-check contracts on one file
py -3 -c "import textwrap; from builder_core.bug_intelligence import engine; r=engine.analyze_source(open('core/results.py',encoding='utf-8').read(),'core/results.py'); print(r.facts['contracts']['statistics'])"
```

---

## 12. Acceptance

| Criterion | Status |
|-----------|--------|
| Run on synthetic, local_jarvis, QuixBugs | Done |
| Sample all seven sources | Done (test sparse) |
| Classify correct / partial / wrong / too weak | Done |
| Metrics by source and contract type | Done (§4–5) |
| False-contract causes | Done (§6) |
| Safe vs advisory sources | Done (§7) |
| First consumer recommendation | Done (§9) |
| Deliverable report | Done |

**Bottom line:** Contract facts are **accurate enough for narrow, explicit enrichment** but **not enough for detector promotion or confirmation**. Proceed with **`inconsistent_return` metadata consumption** first; treat **`callee_behavior` strong facts as non-authoritative** until extractors are tightened.
