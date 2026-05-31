# Phase 93D — Cross-file Consumer Gate (Design Only)

**Status:** Design only. No code, no detector change, no benchmark change.
**Date:** 2026-05-30
**Context:** 93A (intra-file infra), 93B (`inconsistent_return` promoted on
intra-file deref-without-null-check), 93C (cross-file facts under
`interproc.cross_file`, **unconsumed**). 171 tests; QuixBugs 12/0; Holdout 2/0.
**Target:** `inconsistent_return` only.

---

## 0. The answer to the core question

> **When, if ever, may `inconsistent_return` consume
> `interproc.cross_file.usage_by_callee`?**

It may — but **only** when **all** of the following hold:

1. A dedicated flag `CROSS_FILE_CONSUMPTION_ENABLED` is `True`. It is **OFF by
   default** and is flipped on **only** after the gates below pass.
2. The **resolution-precision gate** has passed: sampled cross-file edges are
   **100% correct** (§3).
3. The **0-FP gate** has passed on a **multi-file synthetic + real-repo** corpus
   (§4) — the per-file QuixBugs/holdout benchmark is *not* a sufficient gate here.
4. The per-finding rule still **vetoes on any null-check** (intra or cross-file).

In single-file mode (`analyze_source`) and in the benchmark, it **never** consumes
them, because those facts are not produced there (§1). So consumption is a no-op
exactly where it must be.

**Recommendation (§9): build the mechanism now, shipped DISABLED; delay the
enable until a real-repo corpus passes §3 and §4.** Precision > recall;
unknown beats guessing.

---

## 1. Why this cannot affect `analyze_source` or benchmark verdicts

The safety is **structural**, not a promise:

- `interproc.cross_file` is produced **only** in project mode
  (`analyze_repository`, which builds a `project_context`). `analyze_source`
  called with no context — which is exactly how `engine_benchmark` analyzes every
  QuixBugs/holdout file, one at a time — **never attaches** a `cross_file` key.
- The detector must read cross-file usage **defensively**: absent key → empty
  cross-file evidence → the decision collapses to the 93B intra-file rule.

Therefore, with consumption enabled or disabled, **single-file analysis and the
benchmark behave identically to 93B**. The only behavior that changes is
**project-mode** analysis (`bug-scan`), where cross-file callers become visible.

The corollary is the crux of this phase: **the per-file benchmark can never
validate cross-file promotion.** A separate multi-file gate is mandatory (§4).
The benchmark's role here is only to prove *non-regression* (it stays 12/0, 2/0),
not to bless cross-file precision.

## 2. The promotion rule + the enabling gates

Two distinct layers — keep them separate.

### 2a. Per-finding rule (how a single promotion is decided)
For a function G that already triggers the 93B intra shape
(`has_value_return ∧ ¬has_none_return ∧ can_fall_through`):
- Build **merged usage** = intra-file `usage_by_callee[G]` ⊔ cross-file
  `interproc.cross_file.usage_by_callee[G]`.
- **Promote** (→ `value_flow`, verdict-eligible) iff the merged evidence has
  **≥1 caller that dereferences** the result **and no caller that null-checks** it.
- **Quarantine** (→ `pattern`) on any null-check (intra or cross), on no-deref, or
  on no-resolved-caller. *Any null-check anywhere vetoes* — the contract reading
  is conservative.
- Cross-file-**alone** promotion is allowed (G may have zero intra callers) — that
  is the entire point — **but only once the enabling gates pass.**

### 2b. Global enabling gates (whether cross-file evidence is consulted at all)
Until **all** are green, the detector ignores `interproc.cross_file` (93B behavior):
- **G1 — Resolution precision** (§3): 100% on sampled edges.
- **G2 — 0-FP** (§4): on multi-file synthetic + real-repo correct code.
- **G3 — Benchmark parity**: QuixBugs 12/0, Holdout 2/0 (structural, asserted).
- **G4 — Flag**: `CROSS_FILE_CONSUMPTION_ENABLED = True` set by a human after
  G1–G3.

## 3. Resolution-precision gate (sampled edges 100% correct)

Cross-file usage is only trustworthy if the *edges* are correct — a single
mis-resolved edge attributes a phantom caller's usage to G and can promote a
false positive. So before consumption, measure the resolver:

- **Synthetic fixtures:** ground truth is known → **exhaustive** check that every
  resolved edge is correct. Must be 100%.
- **Real repos:** collect all resolved cross-file edges; **sample N** (e.g. 50+)
  and audit each deterministically against the import statement + the callee's
  definition (no LLM). Require **100% correct** on the sample; a single wrong edge
  → resolver stays UNRESOLVED-only, consumption stays off.
- **Adversarial fixtures required:** alias collisions, re-exports through
  `__init__`, same-name modules in different packages, shadowing, conditional/
  dynamic imports, star imports. Each must resolve to UNRESOLVED (already the 93C
  behavior; the gate locks it in).
- Resolution **recall** is reported, **not gated** (precision > recall).

## 4. 0-FP measurement (multi-file synthetic + real repo)

The detector-level gate, analogous to 93B's QuixBugs-correct measurement but
**multi-file** and **project-mode**:

- **Synthetic multi-file pairs:** mini-projects where a missing-return function is
  called cross-file. *Buggy* = a genuine missing return a deref-caller would crash
  on; *Fixed* = corrected (explicit return / explicit None / caller null-checks).
  Gate: **0 promotions on the fixed side**; TP on the buggy side reported.
- **Real-repo correct corpus:** several small, known-correct repositories analyzed
  in project mode. **Any promoted `inconsistent_return` on known-correct code is a
  false positive.** Gate: **0 FP.**
- If any FP appears → **do not enable** cross-file consumption; report the file,
  the phantom/contract caller, and the reason.

The real-repo corpus is non-negotiable: synthetic fixtures cannot reproduce
re-exports, framework dispatch, or the long tail of usage patterns where FPs hide.
This is the basis for the delay recommendation (§9).

## 5. Kill-switch (two layers)

- **`cross_file.CROSS_FILE_ENABLED`** (93C) — controls whether cross-file facts are
  *produced*. Off → no facts anywhere.
- **`fact_detectors.CROSS_FILE_CONSUMPTION_ENABLED`** (new, **default False**) —
  controls whether the detector *reads* those facts. Off → 93B behavior exactly.
- Either flag off ⇒ no cross-file promotion. Flipping consumption to `False` is an
  instant, total rollback to 93B. The flags are independent so production of facts
  (useful for inspection) does not imply consumption.

## 6. Tests (for the eventual implementation)

- **Single-file unchanged:** with consumption ON, `analyze_source` on a lone
  missing-return function still quarantines (no `cross_file` key).
- **Benchmark parity:** QuixBugs 12/0, Holdout 2/0 with consumption ON.
- **Project-mode promote:** a 2-file fixture (util.G missing-return; main derefs G
  cross-file, no null-check) → G **promoted** (`value_flow`).
- **Cross-file null-check → quarantine**; **mixed (cross deref + cross/intra
  null-check) → quarantine**; **cross caller value-only → quarantine**.
- **Consumption flag OFF:** the same fixture does **not** promote (93B behavior).
- **Unresolved evidence ignored:** star/ambiguous/third-party callers contribute
  no promotion evidence.
- **0-FP synthetic gate:** every fixed multi-file pair → 0 promotions.
- **Real-repo gate:** vendored small correct repo (or skip if absent) → 0
  promotions.
- **Resolution-precision harness:** synthetic edges 100% correct (exhaustive).

## 7. Files likely to change (implementation)

**Modified (the only detector change, gated + default-off):**
- `fact_detectors.py` — add `CROSS_FILE_CONSUMPTION_ENABLED = False`; when ON and
  `interproc.cross_file` is present, merge its `usage_by_callee[G]` into the
  promotion decision (defensive: absent → empty).

**New:**
- a small multi-file synthetic corpus + a read-only `cross_file_benchmark`
  measurement helper for §4;
- `tests/test_phase93d_*` for §6;
- `reports/phase93d_*` measurement report at build time.

**Explicitly NOT changed:** `engine.py`, `cross_file.py`, `callgraph.py`,
`summaries.py`, `imports.py`, `module_map.py`, `finding.py`,
`engine_benchmark.py`, and every other detector. No verdict-kind change.

## 8. Rollback

- Consumption is behind a default-off flag; the merge defaults to empty cross-file
  evidence when the facts are absent or the flag is off. Reverting = flip the flag
  (instant) or remove the merge (one localized edit in one detector).
- No verdict-eligible finding depends on cross-file while the flag is off; the
  benchmark can never regress (single-file mode has no cross-file facts).
- Independent of 93A/B/C, which remain untouched.

## 9. Implement now, or delay until real-repo validation?

**Recommendation: implement the mechanism in a 93D *implementation* phase, shipped
DISABLED by default and validated only on synthetic fixtures; DELAY the *enable*
(flag flip) to a later phase gated on a real-repo corpus.**

Reasoning:
- The mechanism is **safe at rest**: flag-off = exact 93B, benchmark untouched,
  single-file untouched. Building it disabled carries near-zero risk and keeps the
  path warm.
- The **precision claim cannot be made on synthetic fixtures.** Cross-file
  mis-resolution and real-world usage (re-exports, framework dispatch, dynamic
  patterns) are precisely where cross-file FPs live. Enabling consumption before a
  real-repo **resolution-precision (100% sampled)** and **0-FP** audit would be
  guessing — which this program does not do.
- Therefore: **do not flip `CROSS_FILE_CONSUMPTION_ENABLED` to True** until a
  real-repo corpus is assembled and both gates pass. The enable is a separate,
  human-reviewed decision backed by measurement, not a code-complete milestone.

If the team prefers maximal conservatism, a pure delay (no 93D implementation
until the corpus exists) is also acceptable; the disabled-mechanism path is
recommended only because it is low-risk and front-loads the synthetic validation.

---

## 10. Hard constraints honored

No code · no detector change (design only) · no benchmark change · no broad
refactor · precision > recall (cross-file promotion gated behind 100%-precision
resolution + 0-FP real-repo measurement) · unknown beats guessing (any null-check
or unresolved caller vetoes; default-off until proven).

### One-line summary

`inconsistent_return` may read `interproc.cross_file.usage_by_callee` only behind
a default-off flag, only in project mode, only after a 100%-precision resolution
audit and a 0-FP multi-file + real-repo measurement — and even then a single
null-checking caller vetoes the promotion. Build it disabled; enable it only on
real-repo evidence.
