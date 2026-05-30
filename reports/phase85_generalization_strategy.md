# Phase 85 — Generalization Strategy

**Status:** Strategy / decision record (report-only phase — no code changes)
**Date:** 2026-05-30
**Author:** Builder Core / Bug Intelligence
**Decision owner:** CTO / Principal Architect

---

## 0. TL;DR

- **Recommended next subsystem (one):** **Data Flow Analysis (DFA)** — an
  intraprocedural def-use + container-behavior fact layer, built on a minimal
  CFG, that existing rules consume instead of matching on names/variable shapes.
- **Why:** Our detector is overfit. 12/18 semantic rules map 1:1 to QuixBugs
  names and variable shapes; the holdout proves they don't transfer
  (precision 100% → 66.7%, recall 30% → 16.7%). More heuristics deepen the
  overfit. DFA changes the *representation* rules reason over — from syntax to
  value behavior — so one DFA predicate replaces many name-bound rules and
  fires correctly on code it has never seen.
- **Immediate hygiene:** delete the 6 zero-TP rules, merge the triple-overlap
  visited/cycle logic into one rule, and **disable** the 2 holdout-FP rules
  (`bfs_missing_visited_tracking`, `graph_traversal_cycle_handling`) because
  they encode a false universal invariant.
- **Phase 86 gate:** holdout precision ≥ 85%, holdout recall ≥ 16.7%, QuixBugs
  recall ≥ 25%, plus a new **name-blind regression** that renames all symbols
  to opaque identifiers and requires recall to hold.

---

## 1. Diagnosis: what the numbers actually say

| Metric | Phase 83D (QuixBugs) | Phase 84 (holdout) | Movement |
|---|---|---|---|
| Precision | 100% | 66.7% | **−33.3 pts** |
| Recall | 30% (12/40) | 16.7% | **−13.3 pts** |

Two failures, not one:

1. **Precision collapse on unseen code** → we are *flagging correct programs*.
   Root cause: rules assert invariants that are not universally true
   (e.g., "a traversal must have a visited set"). On the holdout, correct
   tree/DAG/acyclic traversals that legitimately omit a visited set get flagged.
   The two named FP rules are the proof.

2. **Recall collapse on unseen code** → our "wins" were *memorized*. 12/18 rules
   key on QuixBugs function names (`breadth_first_search`, `bfs`) and specific
   variable/method shapes (`successors`, `popleft`, `queue.extend(...)`). Rename
   the function or restructure the loop and the rule goes silent. This is a
   lookup table wearing the costume of an analyzer.

The pre-audit's structural finding nails the mechanism:
**the profile system is bypassed by hard-coded function-name rules.** We have
declarative `algorithm_profiles.py` (BFS/DFS/shortest-path/…) but detection
actually runs through name-matched branches in the `algorithm_mismatch` family.
The profiles are documentation; the names are the logic. That is exactly
backwards for generalization.

**Conclusion:** the problem is *representational*, not *coverage*. We do not
need more rules. We need the rules to reason over what the program does to its
data, not over what its symbols are called.

---

## 2. Rule disposition (Question 1)

Worked from the audit (18 semantic rules: 12 TP, 6 zero-TP, 2 holdout-FP,
triple overlap in visited/cycle) and the live rule inventory.

### 2.1 KEEP — generalizable, structural, name-agnostic, low FP
These already reason over structure rather than names; they will become the
first consumers of DFA facts.

| Rule | Why keep |
|---|---|
| `recursion_no_termination` | Structural (recursive call + no guarded base return). Transfers. |
| `mutation_while_iterating` | Pure control/data pattern. High precision, name-agnostic. |
| `unreachable_code` | Control-flow fact. Transfers. |
| `duplicated_branches` | Structural equality of branches. High precision. |
| `impossible_condition` | Structural contradiction. Transfers. |
| `exception_swallowed` | Structural (`except: pass`/`continue`). Transfers. |
| `off_by_one` (the `range(len(...)+1)` variant) | Structural index-overrun. Keep. |
| `syntax_error` | Parse signal, not a heuristic. Keep. |

### 2.2 NARROW — real signal, currently over-broad (drives holdout FP)
| Rule | Narrowing (to be enforced via DFA in Phase 86, **not** new rules) |
|---|---|
| `suspicious_conditional` (`while True`) | Only flag when the loop body **consumes a container whose size the guard does not depend on** (the data-flow reframing of the BFS bug). Plain `while True` with a reachable break/return is *not* a finding. |
| `off_by_one` (inclusive `<= len(...)`) | Only flag when the compared variable is **used as an index** into the same `len()`'d sequence (def-use link), not on any inclusive comparison. |
| `inconsistent_return` | Restrict to "value on some paths, implicit/`None` on others." Drop multi-shape-but-consistent cases (noise on correct code). |
| `reversed_comparison` | Restrict to min/max **selection** patterns where the compared value flows to the return/assignment. |

### 2.3 MERGE — collapse the triple overlap
The audit's "triple overlap in visited/cycle logic" is three rules asserting the
same thing three ways:
- `bfs_missing_visited_tracking`
- `graph_traversal_cycle_handling`
- the `algorithm_mismatch` "no visited-set membership test" branch

→ **Merge into one capability: `unbounded_traversal`.** Critically, it must be
**precondition-gated**: only assert when the frontier can re-encounter a node
(cycle is *possible*) AND grows from neighbors without a membership filter. That
precondition is a data-flow property DFA can approximate; a name/shape rule
cannot. Until DFA supplies the precondition, the merged rule stays **disabled on
the unseen path** (see 2.4).

### 2.4 DELETE — 6/18 zero-QuixBugs-TP, no generalization value
These contribute zero true positives and are style/test-awareness noise or pure
name heuristics. Remove them from the **bug-detection decision** (test-awareness
items may survive as advisory output, but must not vote on precision/recall):

1. `unused_variable` (style)
2. `unused_result` (style)
3. `untested_module` (test-awareness, not a bug)
4. `untested_function` (test-awareness, not a bug)
5. `shadowed_name` (builtin-shadow; style, near-zero bug signal)
6. `reversed_comparison` **as a standalone name heuristic** (fold its surviving,
   narrowed form into the min/max selection check under 2.2; delete the rest)

### 2.5 QUARANTINE as benchmark-specific — the 12 name/shape-bound TP rules
The 12 TP rules that map 1:1 to QuixBugs names/variable shapes (the
`algorithm_mismatch` family that hard-codes `breadth_first_search`/`bfs`,
`successors`/`neighbor` words, `popleft`/`extend` shapes) are **kept runnable but
quarantined**:
- Tagged `benchmark_specific = True`.
- **Excluded from the unseen/holdout decision path** and from any precision/recall
  claim on unseen repos.
- Allowed only inside the QuixBugs benchmark harness, as a *ceiling reference*,
  until re-expressed as DFA predicates.

The 2 holdout-FP rules (`bfs_missing_visited_tracking`,
`graph_traversal_cycle_handling`) do **not** get quarantine — they get
**disabled/deleted**, because they actively reduce precision and have a
generalizing replacement coming (the precondition-gated `unbounded_traversal`).

**Net effect of §2:** 18 → ~9 active, generalization-oriented rules; the overfit
12 are isolated behind a benchmark flag; the 2 harmful rules are off.

---

## 3. The missing capability (Question 2)

Choosing one from the menu, with explicit rejection of the others.

| Candidate | Verdict | Reason |
|---|---|---|
| **Data Flow Analysis** | **CHOSEN** | Re-represents detection over value behavior (def-use, container mutation/consumption, index ranges, guard dependencies). One predicate replaces many name-bound rules; transfers to unseen code. |
| Control Flow Graph | Folded in | Necessary substrate for termination/reachability, but alone it can't express container-semantics or off-by-one. We build a *minimal* CFG **inside** the DFA subsystem, not as a separate deliverable. |
| Algorithm Profile Matcher | Deferred to Phase 87 | The profiles exist but are bypassed. A *structural* matcher is the right long-term router — **but it can only match on facts DFA produces** (FIFO vs LIFO consumption, guard-depends-on-container). Profiles before DFA = name/shape matching again = same overfit. Correct order is DFA → Profiles. |
| Invariant Engine | Premature | Invariants need facts to check. Without DFA it would re-encode today's heuristics as "invariants" and re-overfit. |
| Test Expectation Engine | Deferred | Improves *confirmation* and FP-trimming where tests exist, not *detection generalization*; unseen repos may lack tests. Complements DFA later. |
| Symbolic Execution Lite | Out of altitude | Highest power, highest cost, path explosion. Wrong maturity step. |

---

## 4. Recommendation (Question 3): build **Data Flow Analysis** — and nothing else

**One subsystem for Phase 86: an intraprocedural Data Flow Analysis fact layer
(with a minimal CFG as its internal foundation).**

It does **not** add bug rules. It produces *facts* that the KEEP/NARROW/MERGE
rules consume. Concretely, the facts that immediately retire name-matching:

- **Container lifecycle:** for each local collection, where it is *grown*
  (append/extend/add/push) vs *consumed* (pop/popleft/pop(0)) — yielding a
  name-agnostic **FIFO/LIFO/priority** classification.
- **Loop-guard dependency:** does a loop's guard read the size/emptiness of a
  collection that the loop body consumes? (The BFS termination bug becomes:
  *consumed-container ∉ guard's read-set* → finite-frontier invariant violated —
  true for any queue-draining loop in any repo, named BFS or not.)
- **Def-use chains / reaching definitions:** is an index variable bounded by the
  same sequence it indexes? (Generalizes off-by-one beyond `range(len()+1)`.)
- **Cycle-possibility approximation:** can the frontier re-receive a node it
  already emitted? (Supplies the precondition that makes `unbounded_traversal`
  sound instead of a false universal.)

---

## 5. Why DFA beats more heuristics on unseen repos (Question 4)

1. **Heuristics memorize syntax; they accumulate as a lookup table.** Each new
   rule encodes one more surface shape (a name, a method, a variable). The
   holdout is the receipt: adding shape-rules drove QuixBugs to 100%/30% but
   unseen code to 66.7%/16.7%. More of the same moves both holdout numbers the
   wrong way.

2. **DFA changes the representation, not the rule count.** Rules stop asking
   *"is this function called `breadth_first_search` and does it use `popleft`?"*
   and start asking *"is a container consumed inside a loop whose guard doesn't
   depend on that container?"* The second question has **no proper nouns in it**.
   It is true of correct code (no finding) and false of the bug (finding),
   regardless of names, in repos we've never seen.

3. **One DFA predicate retires many name rules.** The container-lifecycle +
   guard-dependency facts alone re-express the entire BFS/DFS `algorithm_mismatch`
   family (queue-as-stack, missing termination) without a single function-name
   match. Fewer rules, broader transfer — the opposite of the heuristic treadmill.

4. **It makes false invariants falsifiable.** The visited/cycle FP exists because
   "must have a visited set" is asserted unconditionally. DFA lets us assert it
   *only when a cycle is reachable in the data flow* — converting a precision-
   killing universal into a precondition-gated, sound check.

5. **It is the prerequisite for every deferred subsystem.** Profile Matcher,
   Invariant Engine, and Test Expectation Engine all need value-behavior facts.
   DFA is the foundation they stand on, so it has the highest downstream leverage
   per unit of build cost.

In one line: **more heuristics raise the QuixBugs score and lower the real-world
score; DFA raises the real-world score by reasoning about data instead of names.**

---

## 6. Phase 86 acceptance criteria (Question 5)

Phase 86 ships **only** the DFA fact layer plus the §2 rule re-wiring. It passes
iff **all** hold:

**Generalization (primary gate)**
1. **Holdout precision ≥ 85%** (up from 66.7%).
2. **Holdout recall ≥ 16.7%** (no regression).
3. **Name-blind regression (new):** rename every QuixBugs function and local
   variable to opaque identifiers (`f1`, `v1`, …). **Recall on the renamed set
   must stay within 5 percentage points of recall on the original set.** This is
   the direct test that names are no longer doing the work. (Harness-internal
   transform; **not** a benchmark expansion.)

**No-regression (secondary gate)**
4. **QuixBugs algorithm recall ≥ 25%** (≥ 10/40; target hold at ~30%).
5. **QuixBugs precision = 100%** maintained on the non-quarantined path, OR any
   drop is solely attributable to quarantined rules being excluded.

**Hygiene (must-do)**
6. `bfs_missing_visited_tracking` and `graph_traversal_cycle_handling`
   **removed/disabled** (zero holdout FP from visited/cycle logic).
7. Triple-overlap merged into a single precondition-gated `unbounded_traversal`.
8. The 6 zero-TP rules **deleted** from the bug-decision path.
9. The 12 name/shape-bound rules **tagged `benchmark_specific`** and excluded
   from the unseen decision path.

**Process (must-hold)**
10. **No new bug rules added in Phase 86.** DFA may only produce *facts*; net
    active rule count must **decrease** (≈18 → ≈9).
11. **At least the BFS termination finding is produced with zero function-name
    matching** — proven by the name-blind regression still flagging it.

---

## 7. Implementation boundaries for Phase 86 (Question 6)

**Scope of the DFA subsystem**
- **Intraprocedural only.** No cross-function/whole-program analysis.
- **Python AST only.** No multi-language work.
- **Additive module(s)** under `builder_core/bug_intelligence/`
  (e.g. `cfg.py` for the minimal control-flow graph, `dataflow.py` for the fact
  layer). Existing rule files are *re-wired to consume facts*, not expanded with
  new rules.
- **Facts, not findings.** DFA emits structured facts; the KEEP/NARROW/MERGE
  rules turn facts into findings. DFA contains no `rule=` strings.
- **Read-only and local.** No writes outside existing `.jarvis_builder/` paths;
  no network; no LLM.
- **Bounded.** Per-function node/loop/iteration caps; a single uncomputable or
  oversized function degrades to "no facts" (silent), never crashes the scan.

**Hard boundaries (this phase, Phase 85)**
- **No new rules.** (This phase adds zero code beyond this report.)
- **No code changes except this report.**
- **No benchmark expansion.** QuixBugs set and holdout set are frozen; the
  name-blind regression is a *transform* of the existing set, not a new corpus.
- **No changes to voice / browser / trading / website / router / memory.**
- **No changes to Phase 79**, Project Intelligence, or any subsystem outside
  `builder_core/bug_intelligence/` (and only in Phase 86, not now).

---

## 8. Sequencing after Phase 86 (context, not commitment)

1. **Phase 86 — Data Flow Analysis** (this recommendation).
2. **Phase 87 — Algorithm Profile Matcher**, now *structural*: profiles match on
   DFA facts (FIFO/LIFO, guard dependency, visited-set presence), finally making
   `algorithm_profiles.py` load-bearing and deleting the quarantined name rules.
3. **Phase 88 — Test Expectation Engine**: use tests to confirm/raise confidence
   and trim FP where tests exist.
4. **Invariant Engine / Symbolic-lite**: only once facts + profiles are solid.

---

## 9. Returned answers (summary)

- **Report path:** `reports/phase85_generalization_strategy.md`
- **Recommended next subsystem:** **Data Flow Analysis** (intraprocedural,
  CFG-backed fact layer; profiles/invariants/tests deferred behind it).
- **Delete (6, zero-TP, from bug decision):** `unused_variable`,
  `unused_result`, `untested_module`, `untested_function`, `shadowed_name`,
  standalone `reversed_comparison` (narrowed remnant folded into min/max check).
- **Disable/remove (2, holdout-FP):** `bfs_missing_visited_tracking`,
  `graph_traversal_cycle_handling`.
- **Merge (triple overlap → 1):** the two above + `algorithm_mismatch` "no
  visited-set" branch → one **precondition-gated `unbounded_traversal`**.
- **Narrow (4):** `suspicious_conditional`(while-True), `off_by_one`(inclusive),
  `inconsistent_return`, `reversed_comparison`.
- **Quarantine (12, benchmark-specific):** the name/variable-shape-bound
  `algorithm_mismatch` TP family — excluded from the unseen decision path.
- **Phase 86 acceptance:** holdout precision ≥ 85%, holdout recall ≥ 16.7%,
  QuixBugs recall ≥ 25%, name-blind recall within 5 pts, zero-value rules removed,
  visited/cycle FP rules off, net rule count decreases, no new rules.
