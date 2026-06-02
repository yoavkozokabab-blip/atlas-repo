# Phase 96 — Contract Analysis Layer (Design Only)

**Status:** Design only. No implementation, no code shipped, no behavior changed.  
**Date:** 2026-05-31  
**Constraints honored:** no detector changes, no benchmark changes, no promotion
changes, no LLM reasoning, read-only/local/deterministic, **unknown beats
guessing**.

This document specifies *what to build* and *how it must behave*. It defines no
functions and writes no code. It binds the design to structures that already
exist (Phase 92B–94E facts, Phase 94B impact, Phase 95 review taxonomy) so a
later implementation has zero ambiguity.

---

## 0. Executive summary

Phase 95E reviewed 202 grounded findings on two real pilot repositories and
produced **0 confirmed actionable defects**. Reviewers found **148 useful review
leads** (73%) but consistently refused to upgrade static suspicion into a
confirmed bug because the packets did not answer:

> What behavior was expected, and does a feasible path actually violate it?

Impact analysis (Phase 94B) and graph resolution (Phase 94D/94E) improve
**scope** — who may be affected, which paths are resolved — but cannot prove
**breakage**. The next blocker is **contract violation evidence**.

Phase 96 introduces a **Contract Analysis layer** that sits between static
findings and defect confirmation:

```text
review lead (detector output)
  + contract facts (expected behavior)
  + path-feasibility facts (guards, branches, resolved calls)
  + consequence model (what goes wrong if violated)
  -> confirmation verdict: confirmed | strong lead | weak lead | unknown
```

The layer does **not** emit new detector warnings by default. It **evaluates**
existing leads against explicit or strongly inferred contracts and produces an
evidence packet suitable for promotion gating.

**First targets:** `inconsistent_return`, None misuse, unsafe dereference  
**First gate:** 0 false positives on QuixBugs correct, holdout fixed, and Phase 95
pilot re-label criteria before any `confirmed_bug` promotion.

---

## 1. Problem statement

### 1.1 What exists today

| Capability | Answers | Does not prove |
| --- | --- | --- |
| Detectors (`valueflow`, `patterns`, `security`) | Suspicious shape exists | Obligation violated |
| Interprocedural facts (93A–94E) | Caller usage: deref / null-check / return | Caller **requires** non-None |
| Impact analysis (94B) | Dependents, paths, blast radius | Code is broken |
| Human review (95E) | Lead usefulness | Automated confirmation |

Phase 93B already uses a **proto-contract** for `inconsistent_return`: a caller
that **dereferences** without **null-checking** implies a non-None return
obligation. That promotion is intra-file, usage-based, and quarantines on mixed
evidence — but it still does not state the contract explicitly, account for
guards on the path to the dereference, or produce a **confirmed defect** label.

### 1.2 What Phase 95 proved

From `phase95e_pilot_human_review_results.md`:

| Finding family | Count | Confirmed | Dominant reviewer treatment |
| --- | ---: | ---: | --- |
| `null_dereference` | 176 | 0 | “maybe None — verify guard” |
| `command_injection` | 14 | 0 | “trace caller trust boundary” |
| `path_traversal` | 12 | 0 | “operator-local path — document boundary” |

Misleading findings (15) clustered around:

- **visible guards** the flow analysis missed (false alarm);
- **constant / locally controlled** argv or paths treated as untrusted;
- **unclear provenance** across calls.

Contract analysis must supply the missing **expected behavior** and **negative
evidence** (guards that block the violating path) so confirmation is evidence-
backed, not rhetorical.

### 1.3 Design principle

Mirror Phase 94B’s three-channel model:

| Channel | Meaning |
| --- | --- |
| **Asserted contract** | Explicitly sourced (annotation, docstring, assert, test) |
| **Inferred contract** | Derived from caller/callee behavior with stated assumptions |
| **Unknown** | Insufficient evidence; lead retained, never promoted |

And mirror the confirmation standard from `defect_confirmation_research.md`:

```text
Expected contract
  + feasible violating path
  + observable incorrect consequence
  + verification evidence (optional but strengthening)
  -> confirmed defect | retained lead | unknown
```

**Impact must never substitute for contract proof.** Reachable ≠ broken.

---

## 2. What a contract means

A **contract** is a deterministic, checkable obligation attached to a
**subject** (function, method, parameter, return value, object state, or call
site). Contracts are facts extracted or inferred from the repository; they are
not LLM summaries.

Each contract record MUST include:

| Field | Purpose |
| --- | --- |
| `subject` | `(file, qualname, slot)` — e.g. `return`, `param:name`, `state:attr` |
| `kind` | One of the five kinds below |
| `obligation` | Machine-readable predicate (see §2.1–2.5) |
| `source` | Provenance tag(s) from §3 |
| `confidence` | `explicit` \| `inferred_strong` \| `inferred_weak` \| `unknown` |
| `evidence_refs` | Pointers to AST nodes, facts, graph edges, test ids |
| `scope` | `intra_file` \| `cross_file` \| `module` \| `repository` |
| `exceptions` | Documented escape hatches (e.g. `raises`, `@overload`) |

Contracts MAY resolve to **unknown**. Unknown is a valid output, not a failure
mode to hide.

### 2.1 Return contract

**Question:** What must the function return on every reachable exit?

| Obligation class | Example |
| --- | --- |
| `return.non_none` | All exits yield a value usable without None-check |
| `return.optional` | `None` is an allowed outcome |
| `return.shape_uniform` | All exits return the same structural kind (e.g. `list`, `dict`, `str`) |
| `return.never_implicit_none` | No fall-through to implicit `None` when other paths return values |
| `return.raises` | Function always raises (no return obligation) |

**Violation examples:**

- Callee has `return.non_none` (inferred from deref callers) but an implicit-None path exists → `inconsistent_return` confirmation candidate.
- Callee annotated `-> str` but returns `None` on a branch → explicit contract violation.

**Non-contract:** “Caller might ignore the return value” — that is usage context, not a return obligation on the callee unless combined with documented API docs or uniform caller requirements.

### 2.2 Argument contract

**Question:** What must hold for inputs at call time?

| Obligation class | Example |
| --- | --- |
| `arg.non_none` | Parameter must not be `None` at entry |
| `arg.type_bound` | Hint-backed bound (`list[str]`, `int`, …) |
| `arg.range` | Assert/docstring bounds (`n > 0`) |
| `arg.validated_externally` | Documented precondition (“caller must sanitize”) |

**Violation examples:**

- Call site passes `maybe_none` into callee with `arg.non_none` explicit hint.
- Internal call after guard removal passes value that guards previously narrowed.

Argument contracts apply at **call edges** (caller obligation + callee requirement). Mismatch is a contract violation only when **both sides** are evidenced or one side is explicit and the other is a resolved call with proven argument flow.

### 2.3 Nullability contract

**Question:** May this value be `None` at this program point?

| Obligation class | Example |
| --- | --- |
| `null.forbidden` | Dereference, attribute access, or subscript requires non-None |
| `null.allowed` | `.get()` missing key, optional return, `| None` hint |
| `null.checked_before_use` | Prior `is None` / truthiness guard on all feasible paths |
| `null.narrowed_by_guard` | Branch implies non-None in taken path |

Nullability is the **bridge** between value-flow leads and confirmation. Phase 95’s `null_dereference` leads fail confirmation today because the packet states “maybe None at dereference” but not:

- whether `None` is **allowed** at that point (contract), nor
- whether a **feasible unguarded path** exists (path feasibility).

Nullability contracts attach to **values** (SSA-ish slots), not just functions.

### 2.4 Exception contract

**Question:** Which exceptions may propagate, and must any be caught?

| Obligation class | Example |
| --- | --- |
| `raises.documented` | Docstring `Raises:` clause |
| `raises.never` | Asserted total function (rare; needs strong evidence) |
| `raises.must_be_handled` | Caller try/except pattern or framework contract |
| `raises.not_on_valid_input` | Invalid-input paths raise; valid paths do not |

**Phase 96 scope note:** Exception contracts are **defined** in this design for completeness but are **not** in the first implementation target set (§5). They inform packet schema only.

### 2.5 State mutation contract

**Question:** What object/module state may or must change?

| Obligation class | Example |
| --- | --- |
| `state.initialized_before_read` | Field read only after `__init__` sets it |
| `state.monotonic` | Counter only increases |
| `state.immutable_after` | Flag set once in setup |
| `state.shared_requires_lock` | Documented threading obligation |

**Violation examples:**

- Read of `self._cache` before assignment on a feasible path.
- Method assumes `_registry` populated but constructor leaves it `None`.

State mutation contracts require **alias and initialization facts** from the fact model. Phase 96 first targets may consume only lightweight state facts (field assigned in `__init__`, read in method) before full heap reasoning.

---

## 3. Sources of contracts

Contracts are extracted only from **observable artifacts** in the repository.
Each source has a default confidence ceiling (§4).

| Source | Typical contract kinds | Default confidence | Extraction rules |
| --- | --- | --- | --- |
| **Type hints** | return, arg, nullability | `explicit` when unambiguous; `unknown` when `Any`, forward ref unresolved, or union without narrowing | PEP 484/604 annotations on defs; respect `# type: ignore` as “do not infer from hint here” |
| **Docstrings** | return, arg, exception, state | `explicit` only for structured sections (`Args:`, `Returns:`, `Raises:`) with parseable predicates; else `inferred_weak` | Deterministic docstring parser; no NLP guessing of free text |
| **Asserts** | arg, nullability, state | `explicit` for literal asserts (`assert x is not None`); `inferred_strong` for compound asserts | Intra-function only unless assert is module-level invariant |
| **Tests** | return, arg, nullability, exception | `explicit` when test asserts outcome (`assert fn() == …`, `pytest.raises`) | Map test name/file to subject via import graph; unresolved dynamic test builders → skip |
| **Caller behavior** | return (non-None required), nullability | `inferred_strong` when **all resolved callers** agree; `inferred_weak` when mixed | Uses Phase 93A `usage_by_callee`: deref without null-check → `return.non_none` obligation on callee; any null-check → weakens to `return.optional` or blocks promotion |
| **Callee behavior** | arg, nullability | `inferred_strong` when callee dereferences param without guard | Param used in deref/attr/subscript/call without prior None guard on all paths |
| **Guards** | nullability (negative evidence) | `inferred_strong` for explicit `is None` / `is not None` / truthiness on dominating path | Guards **refute** violation; they do not create positive contracts unless paired with else-branch misuse |

### 3.1 Source precedence (conflict resolution)

When sources disagree, apply strict precedence:

```text
explicit test assertion
  > explicit assert in code
  > explicit type hint (non-Any)
  > explicit docstring section
  > inferred_strong caller/callee agreement (all resolved callers)
  > inferred_weak partial caller evidence
  > unknown
```

Never silently merge conflicting obligations. Emit **contract conflict** as a
first-class outcome → `unknown` for confirmation; retain lead.

### 3.2 Inputs from existing infrastructure

| Existing module | Contract use |
| --- | --- |
| `facts.extract_module_facts` | Function shapes, raises, returns |
| `callgraph.usage_by_callee` | Caller deref / null-check / return usage |
| `depgraph` resolved `calls` | Cross-file caller evidence (when enabled) |
| `valueflow` | Maybe-None slots, dereference sites |
| `impact.py` | **Scope only** — list callers to prioritize contract gathering; never as proof |
| Phase 95 review labels | Calibration targets for weak vs misleading |

---

## 4. Confidence levels

Four levels govern **both** contract extraction and confirmation output.

| Level | Definition | May promote to Confirmed Bug? | Typical use |
| --- | --- | --- | --- |
| **explicit contract** | Stated in hint, assert, structured docstring, or test assertion with resolved subject binding | **Only if** path + consequence also proven (§6) | `-> str` + implicit None path; test expects non-None |
| **inferred strong contract** | Single consistent obligation from **all** resolved callers or callee param use; no conflicting explicit source | **Only if** path feasibility is strong and no guard refutation | All resolved callers deref without null-check |
| **inferred weak review lead** | Partial caller evidence, mixed usage, docstring free-text, or cross-file gaps | **Never** — remains review lead | Some callers null-check, some deref; unresolved call graph |
| **unknown** | Missing subject binding, conflicting sources, dynamic dispatch, unresolved calls on critical edge | **Never** | Star import caller; `getattr` dispatch |

### 4.1 Mapping to finding / review taxonomy

| Contract analysis outcome | Maps to Phase 95 review label | Engine `kind` behavior |
| --- | --- | --- |
| Confirmed violation | `true_positive` / confirmed actionable | New confirmation attachment on existing finding; does **not** change detector emission |
| Strong unresolved lead | `useful_advisory` with contract packet | Existing `value_flow` / `pattern` + `contract_status: lead_strong` |
| Weak lead | `useful_advisory` | `contract_status: lead_weak` |
| Unknown | `unclear` or downgraded advisory | `contract_status: unknown` |
| Refuted by guard | `false_positive` candidate | `contract_status: refuted` — feeds FP reduction, not confirmation |

### 4.2 Relationship to Phase 93B promotion

Phase 93B promotion (`inconsistent_return` → `value_flow`) is a **subset** of
contract analysis:

| 93B rule | Phase 96 generalization |
| --- | --- |
| Deref + no null-check → promote | `return.non_none` inferred_strong + path to implicit None |
| Any null-check → quarantine | Caller evidence weakens nullability obligation |
| No resolved caller → quarantine | `unknown` — no inferred return contract |

Phase 96 **supersedes the promotion story** conceptually but implementation
must preserve 93B behavior until measurement proves parity. Contract analysis
adds explicit contract records, guard-aware path checks, and a confirmation
verdict distinct from “verdict-eligible finding.”

---

## 5. First implementation targets

Phase 96 implementation (future) ships **one module** (`contract_analysis.py` or
equivalent) with three **confirmation evaluators**. Detectors unchanged.

### 5.1 Target A — `inconsistent_return`

**Lead source:** Phase 92B shape + Phase 93B interprocedural gate.

**Contract under test:**

```text
callee.return.non_none   (inferred_strong from caller deref w/o null-check)
OR
callee.return.shape_uniform (explicit hint or docstring)
```

**Violation condition:**

```text
∃ reachable exit: implicit None OR bare return
AND explicit/value return exists on another path
```

**Path feasibility:**

- Account for `raise` exits (exclude from fall-through obligation if `raises.documented` or `has_raise` fact).
- Unresolved callers → obligation cannot be `inferred_strong`; confirmation blocked.

**Consequence:**

```text
Caller dereferences result → TypeError-like misuse OR logic error on None
```

**Minimum confirmation bar:**

| Contract confidence | Path | Guard refutation | Verdict |
| --- | --- | --- | --- |
| inferred_strong | implicit-None path feasible | no caller-side guard compensates | **confirmed** (synthetic + benchmark only initially) |
| inferred_strong | same | unresolved callee internal guards | strong lead |
| inferred_weak / mixed callers | — | — | weak lead |
| unknown | — | — | unknown |

### 5.2 Target B — None misuse

**Lead source:** Optional/union hints vs call sites; `.get()` without default passed to non-optional param; inconsistent `| None` return vs caller assumption.

**Contract under test:**

```text
arg.non_none OR null.forbidden at use site
```

**Violation condition:**

```text
Proven maybe-None value flows to forbidden slot on a feasible path
```

**Path feasibility:**

- Dominating `is None` / truthiness guards on all paths to use → **refuted**.
- Try/except or defaulting (`or ""`, `if x is None: return`) → evaluate per path.

**Consequence:**

```text
AttributeError / TypeError / incorrect branch when None occurs
```

**Minimum confirmation bar:** Requires **explicit** or **inferred_strong**
nullability on **both** producer and consumer sides. Hint-only on one side →
weak lead maximum.

### 5.3 Target C — Unsafe dereference

**Lead source:** Existing `null_dereference` value-flow findings.

**Contract under test:**

```text
null.forbidden at dereference site
```

**Violation condition:**

```text
Maybe-None fact reaches dereference
AND no guard refutes on feasible path
AND None is not contractually allowed at that point
```

**Path feasibility (critical for Phase 95 FP reduction):**

| Guard pattern | Effect |
| --- | --- |
| `if x is None: return/continue/raise` before deref | Refute on guarded path |
| `if x:` / `if not x:` | Weak refutation — only `inferred_weak` unless paired with else-branch deref |
| `assert x is not None` | Strong refutation if assert on all feasible paths |
| Walrus + check | Strong refutation when dominated |

**Consequence:**

```text
Runtime failure at dereference OR silent wrong-path logic
```

**Minimum confirmation bar:**

| Evidence | Verdict cap |
| --- | --- |
| Explicit non-optional hint + unguarded feasible path | confirmed (subject to 0-FP gate) |
| Inferred_strong from callee contract only | strong lead |
| Maybe-None from `.get()` / param with no callee contract | weak lead (Phase 95 default) |
| Guard visible in AST on all paths | refuted → suppress misleading lead flag |

This target directly addresses Phase 95E’s 176 null-dereference leads where
reviewers saw guards the engine missed.

### 5.4 Explicit non-targets for Phase 96 v1

| Out of scope | Reason |
| --- | --- |
| Security sink confirmation (`command_injection`, `path_traversal`) | Requires trust-boundary contracts — Phase 97+ |
| Full exception contract enforcement | Insufficient fact infrastructure |
| Heap / full alias analysis | Risk of polished false positives |
| LLM-generated contracts | Violates deterministic constraint |
| New detector rules | Phase 96 evaluates existing leads only |

---

## 6. What must never be promoted to Confirmed Bug

A finding MUST NOT receive `confirmed_bug` (or equivalent verdict-eligible
confirmed status) when **any** of the following hold:

### 6.1 Evidence failures

| Blocker | Rationale |
| --- | --- |
| Contract confidence is `inferred_weak` or `unknown` | Promotion requires explicit or inferred_strong obligation |
| Conflicting contract sources without adjudication | Unknown beats guessing |
| Critical call edge unresolved on the violating path | Cannot prove caller/callee obligation chain |
| Guard or sanitizer **refutes** violation on all feasible paths | Phase 95 dominant FP family |
| Dynamic dispatch, `getattr`, `eval`, star-import caller | No stable subject binding |
| Value provenance is third-party / external module with no project contract | Cannot infer obligation |

### 6.2 Category errors (reachability ≠ defect)

| Blocker | Rationale |
| --- | --- |
| Impact analysis shows dependents but no contract violation | 94B scopes blast radius, not breakage |
| Execution path exists but nullability obligation unknown | Path without contract is incomplete |
| “Maybe None” alone without forbidden-use proof | Phase 95 advisory pattern |
| Operator-local / constant data flagged as untrusted without boundary contract | Phase 95 security FP pattern |
| Single reviewer usefulness without confirmation packet | Human lead ≠ automated confirmation |

### 6.3 Semantic mismatches

| Blocker | Rationale |
| --- | --- |
| Intended optional behavior (`Optional`, `.get`, documented None) | Not a defect |
| Defensive check flagged as dereference (reviewer “verify guard”) | Refutation incomplete in engine → weak lead, not confirmed |
| Test encodes allowed None but static analysis missed test binding | Test contract wins → refuted |
| Algorithmic / style findings without incorrectness consequence | Maintainability ≠ confirmed bug |

### 6.4 Process gates

| Blocker | Rationale |
| --- | --- |
| Fails QuixBugs correct / holdout fixed 0-FP gate | Same bar as 93B promotion |
| Fails Phase 95 pilot re-label gate (§7.3) | Real-repo calibration |
| Synthetic confirmation cases not all passing | Unit proof obligation |

**Default posture:** When in doubt, emit `unknown` or `inferred_weak review lead`.
Confirmed Bug is an **extraordinary** label requiring a complete packet.

---

## 7. Architecture (design)

### 7.1 Layer placement

```text
┌─────────────────────────────────────────────────────────┐
│ Detectors (unchanged) → Findings (review leads)         │
└───────────────────────────┬─────────────────────────────┘
                            │
┌───────────────────────────▼─────────────────────────────┐
│ Contract Extraction (read-only facts → contract store)  │
│  sources: hints, docs, asserts, tests, caller/callee    │
└───────────────────────────┬─────────────────────────────┘
                            │
┌───────────────────────────▼─────────────────────────────┐
│ Contract Analysis (per lead)                            │
│  match obligation ↔ violation ↔ path ↔ consequence    │
└───────────────────────────┬─────────────────────────────┘
                            │
┌───────────────────────────▼─────────────────────────────┐
│ Confirmation Verdict (attachment to finding packet)     │
│  confirmed | strong_lead | weak_lead | refuted | unknown│
└───────────────────────────┬─────────────────────────────┘
                            │
              optional: Impact (94B) for scope context only
```

Contract extraction runs **once per module** (like facts). Confirmation runs
**per candidate finding** that matches a first-target rule.

### 7.2 Confirmation packet schema (output)

Each analyzed lead attaches:

```text
contract_analysis:
  status: confirmed | strong_lead | weak_lead | refuted | unknown
  contract:
    kind: return | arg | nullability | exception | state
    obligation: <predicate id>
    confidence: explicit | inferred_strong | inferred_weak | unknown
    sources: [<source tags>]
  violation:
    site: (file, line, qual)
    description: <deterministic string>
  path:
    feasible: true | false | unknown
    guard_summary: [<guard ids that block or fail to block>]
    unresolved_edges: [<graph reasons>]
  consequence:
    class: incorrect_result | runtime_error | security | unknown
    description: <deterministic string>
  blockers: [<§6 codes if not confirmed>]
  impact_context: optional pointer to 94B summary (non-proof)
```

Packets must be **JSON-serializable**, deterministic, and reproducible from
pinned commits.

### 7.3 Non-goals

- No modification to detector thresholds or rule sets.
- No automatic benchmark promotion changes.
- No LLM contract inference.
- No execution of target repository code in v1 (static + test AST only).
- No user-facing “confirmed” UI until gates pass.

---

## 8. Validation plan

Validation mirrors Phase 93B (synthetic proof + corpus 0-FP) and Phase 95
(real-repo human calibration).

### 8.1 Synthetic cases (unit proof)

Mandatory fixtures before any promotion flag:

| Suite | Cases |
| --- | --- |
| **Return** | implicit None + deref caller → confirm; null-check caller → refute/weak; raise-only exit → no violation |
| **None misuse** | `Optional` param + unguarded deref → confirm; guarded branch → refute; `.get()` without default → weak max |
| **Dereference** | visible `if x is None: return` before use → refute; nested closure with dominating guard → refute; maybe-None no guard → strong/weak by contract level |
| **Negative** | impact-only evidence → never confirmed; mixed caller usage → never confirmed; star-import caller → unknown |
| **Conflict** | hint says Optional, all callers deref → conflict → unknown |

Each case asserts exact `contract_analysis.status` and blocker codes.

### 8.2 Real-repository pilot rerun

Re-run contract analysis on Phase 95C pilot artifacts:

| Repository | Purpose |
| --- | --- |
| `openai-plugins-public-pilot` | Null-dereference guard refutation; CLI trust boundaries stay non-confirmed |
| `openai-skills-public-pilot` | Smaller sample; label stability |

**Success criteria (design targets, not yet measured):**

| Metric | Target |
| --- | --- |
| Confirmed bugs promoted | > 0 only if human adjudication agrees; **0 is acceptable** on this corpus |
| Misleading null-deref (guard refuted) | Material reduction vs 95E 13 FP bucket |
| Weak/strong lead separation | Reviewers report clearer “what to verify” in packet |
| No new strict FP | Zero new `confirmed` labels that reviewers reject |

Process: attach contract packets to existing 202 review candidates; blind
re-review of a stratified sample (≥30) comparing 95E labels to contract verdicts.

### 8.3 Zero-FP gate (hard requirement)

No `confirmed` promotion enabled unless:

```text
QuixBugs correct (40 files):     0 contract-confirmed FP
Holdout fixed (12 files):        0 contract-confirmed FP
Synthetic suite:                 100% expected verdicts
Phase 95 pilot re-sample:        0 reviewer-rejected confirmations
```

If any gate fails → `CONTRACT_CONFIRMATION_ENABLED = False` (mirror
`INTERPROC_PROMOTION_ENABLED` pattern).

Benchmark TP/FP counts for QuixBugs/holdout **must remain unchanged** unless
a separate explicit benchmark phase is approved. Contract confirmation is an
**overlay**, not a detector change.

### 8.4 Metrics to report (Phase 96 implementation phase)

| Metric | Definition |
| --- | --- |
| `contract_explicit_count` | Contracts with explicit confidence |
| `contract_inferred_strong_count` | Strong inferred |
| `lead_confirmed_count` | Leads → confirmed verdict |
| `lead_refuted_count` | Leads refuted (guard/contract) |
| `lead_unknown_count` | Blocked by §6 |
| `confirmation_precision` | Human-adjudicated confirmed that reviewers accept |
| `misleading_reduction_rate` | Δ FP vs 95E on pilot |

---

## 9. Integration with existing phases

| Phase | Relationship |
| --- | --- |
| **92B** | Supplies intraprocedural inconsistent-return shape |
| **93B** | Proto-contract via caller usage; Phase 96 formalizes and extends |
| **93D gate** | Cross-file caller evidence may strengthen to `inferred_strong` when enabled + measured |
| **94B** | Impact populates `impact_context` only |
| **94D/94E** | Better caller resolution → more inferred_strong opportunities; unresolved stays unknown |
| **95E** | Calibration corpus and confirmation standard |
| **95F** | Taxonomy split: defect vs lead vs advisory |

---

## 10. Implementation phases (future, not in Phase 96)

Suggested build order after design approval:

| Step | Deliverable |
| --- | --- |
| 96A | Contract extraction (hints, asserts, caller usage) + schema |
| 96B | Evaluator: `inconsistent_return` confirmation |
| 96C | Evaluator: unsafe dereference + guard refutation |
| 96D | Evaluator: None misuse |
| 96E | Pilot rerun report + gate measurement |
| 96F | Promotion wiring (separate approval) |

Each step requires its own report and test gate. **Phase 96 design does not
authorize 96F.**

---

## 11. Acceptance (for design review)

| Criterion | Status |
| --- | --- |
| Five contract kinds defined | §2 |
| Seven contract sources identified | §3 |
| Four confidence levels defined | §4 |
| First targets: inconsistent_return, None misuse, unsafe dereference | §5 |
| Non-promotion rules explicit | §6 |
| Validation: synthetic, pilot rerun, 0-FP gate | §8 |
| No implementation | This document only |
| Aligns with 93B/94B/95E evidence | §1, §9 |
| Unknown beats guessing | §1.3, §4, §6 |

---

## 12. Reproducibility references

```text
reports/defect_confirmation_research.md
reports/phase93b_inconsistent_return_promotion.md
reports/phase94b_impact_analysis_design.md
reports/phase95e_pilot_human_review_results.md
reports/phase95f_post_review_calibration_plan.md
builder_core/bug_intelligence/fact_detectors.py   (caller usage proto-contract)
builder_core/bug_intelligence/valueflow.py        (null_dereference leads)
builder_core/bug_intelligence/impact.py           (scope-only consumer)
```

---

## 13. Design conclusion

Phase 95 proved Builder Core is useful as a **review accelerator** but not yet
as a **defect confirmer**. The missing layer is not more warnings — it is
**contract violation proof** with guard-aware path reasoning.

Phase 96 defines that layer conservatively:

- contracts are typed, sourced, and confidence-scored;
- confirmation requires obligation + violation + feasible path + consequence;
- impact and reachability never substitute for proof;
- Confirmed Bug remains rare, gated, and measurable.

The realistic outcome on the Phase 95 pilot may remain **zero confirmed bugs**
while still delivering value by **refuting misleading leads** and **sharpening
strong vs weak review guidance**. That outcome is compatible with this design
and preferable to false confirmation.
