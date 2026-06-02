# Phase 100A — Historical Corpus v1 (Assembly Plan)

**Status:** Assembly plan. No code.
**Date:** 2026-05-31
**Goal:** Turn the Phase 99C corpus design into an **executable** first batch — a
concrete, preregistered slate of **30 cases** prioritizing `inconsistent_return`,
optional-return misuse, and return-contract violations, each with a real source,
trigger test, fixed revision, and an expected packet to complete at assembly.
**Consumes:** Phase 99C (corpus design), Phase 99D (replay manifest format),
Phase 99B (evaluation protocol), Phase 99 (gate tiers/bundle).

---

## 0. What is already on disk (grounding)

This plan is grounded in **real, locally available** bug metadata — not invented
commits.

| Source | Available locally | What each case provides |
|---|---|---|
| **BugsInPy probe** `data/external_benchmarks/BugsInPy_probe/projects/*/bugs/*` | 17 projects, **~187 return-touching bugs** (deterministic grep §2) | `bug.info` (`buggy_commit_id`, `fixed_commit_id`, `test_file`), `run_test.sh` (trigger test), `bug_patch.txt` (fix diff) |
| **In-repo holdout pairs** `builder_core/benchmarks/holdout/pairs/*` | 12 pairs (`buggy.py`/`fixed.py`) | Zero-setup, single-file, instantly replayable via 99D `pair_dir` |
| **QuixBugs** `C:\Repos\QuixBugs` | 40 programs + json tests | Breadth/negative (mostly not return-contract) |
| **Public GitHub bug-fix commits** | (to preregister) | Fills any return-contract gap; pinned SHAs resolved at assembly |

Per-project **return-touching** bug counts (verified via §2): pandas 74, thefuck
20, youtube-dl 16, keras 14, luigi 13, scrapy 12, black 10, fastapi 5, matplotlib
4, tornado 4, tqdm 4, ansible 3, cookiecutter 2, sanic 2, spacy 2, PySnooper 1,
httpie 1. **≥10 repositories are trivially satisfied.**

---

## 1. Selection priority

Per the task, the 30 cases prioritize three return-contract defect shapes (the
Phase 99 first-gate scope = `inconsistent_return`):

1. **`inconsistent_return`** — some reachable path returns a value, another falls
   through to implicit `None` (or returns an incompatible shape).
2. **Optional-return misuse** — a function may return `None` and a caller
   dereferences it without a guard.
3. **Return-contract violation** — declared/inferred return contract (type hint,
   docstring, test expectation) is violated on a feasible path.

A minority of **distractors** (other-rule real bugs) and **hard negatives**
(optional-by-design / guarded look-alikes) are included because a gate cannot be
validated on positives alone — the negatives prove 0-FP.

---

## 2. Deterministic selection procedure (reproducible, preregistered)

The return-contract candidate pool is selected by a **rule, not by taste**:

```
1. For every BugsInPy bug_patch.txt, select bugs whose fix diff adds/removes a
   `return` line:           grep -E '^[+-]\s*return( |$|[^a-z_])'
2. Prefer small return-fix diffs (< 12 changed lines) — the cleanest
   inconsistent_return / missing-return shape.
3. Spread across ≥10 projects; cap any single project at ~20% of positives.
4. At assembly, for EACH selected bug, read bug_patch.txt + the buggy source to
   assign the precise bug_class (inconsistent_return / optional-misuse /
   return-contract) and the expected tier. This step is dual-reviewed (99B §7).
5. Preregister the final slate (commits + tests + expected packets) BEFORE any
   replay. Misses (detector silent / test unbound) stay in the recall denominator
   (99B §4.4). Do not drop a case after seeing gate output.
```

**Honesty note:** §2.1 verifies a fix *touches a return*; it does **not** prove the
defect is `inconsistent_return` or that the detector fires. Final `bug_class` and
`expected_tier` are assigned per case at assembly (§2.4), not assumed here.

---

## 3. The 30-case slate (v1)

Composition: **20 return-contract positives** (BugsInPy, real IDs, 10 projects) +
**3 zero-setup in-repo return pairs** + **3 distractors** (other-rule, must not be
confirmed by the `inconsistent_return` gate) + **4 hard negatives** (must be
`Refuted`). All BugsInPy IDs below are **verified return-touching** via §2.

### 3.1 Return-contract positives — BugsInPy (real commits + tests)

| # | case_id | Source (`…/projects/<p>/bugs/<id>/`) | Trigger test (`run_test.sh`) | Fixed revision | Priority class (candidate) |
|--:|---|---|---|---|---|
| 1 | bip_black_9 | black#9 | `bug.info test_file` | `fixed_commit_id` | return-contract |
| 2 | bip_black_17 | black#17 | run_test.sh | fixed_commit_id | inconsistent_return |
| 3 | bip_black_19 | black#19 | run_test.sh | fixed_commit_id | inconsistent_return |
| 4 | bip_fastapi_11 | fastapi#11 | run_test.sh | fixed_commit_id | optional-return |
| 5 | bip_fastapi_12 | fastapi#12 | run_test.sh | fixed_commit_id | inconsistent_return |
| 6 | bip_fastapi_16 | fastapi#16 | run_test.sh | fixed_commit_id | return-contract |
| 7 | bip_luigi_2 | luigi#2 | run_test.sh | fixed_commit_id | inconsistent_return |
| 8 | bip_luigi_10 | luigi#10 | run_test.sh | fixed_commit_id | return-contract |
| 9 | bip_luigi_17 | luigi#17 | run_test.sh | fixed_commit_id | optional-return |
| 10 | bip_luigi_23 | luigi#23 | run_test.sh | fixed_commit_id | return-contract |
| 11 | bip_tornado_7 | tornado#7 | run_test.sh | fixed_commit_id | inconsistent_return |
| 12 | bip_tornado_8 | tornado#8 | run_test.sh | fixed_commit_id | return-contract |
| 13 | bip_tornado_9 | tornado#9 | run_test.sh | fixed_commit_id | optional-return |
| 14 | bip_tqdm_1 | tqdm#1 | run_test.sh | fixed_commit_id | inconsistent_return |
| 15 | bip_tqdm_2 | tqdm#2 | run_test.sh | fixed_commit_id | return-contract |
| 16 | bip_sanic_4 | sanic#4 | run_test.sh | fixed_commit_id | optional-return |
| 17 | bip_cookiecutter_2 | cookiecutter#2 | run_test.sh | fixed_commit_id | return-contract |
| 18 | bip_httpie_1 | httpie#1 | run_test.sh | fixed_commit_id | return-contract |
| 19 | bip_pysnooper_2 | PySnooper#2 | run_test.sh | fixed_commit_id | inconsistent_return |
| 20 | bip_ansible_17 | ansible#17 | run_test.sh | fixed_commit_id | return-contract |

Projects represented: black, fastapi, luigi, tornado, tqdm, sanic, cookiecutter,
httpie, PySnooper, ansible = **10 distinct repositories**.

### 3.2 Zero-setup return pairs — in-repo holdout (instant replay)

| # | case_id | Source (`pair_dir`) | Trigger test | Fixed revision | Class |
|--:|---|---|---|---|---|
| 21 | hold_black_executor | `…/holdout/pairs/bugsinpy_black_executor` | distilled in-pair assertion | `fixed.py` | return-contract (distilled) |
| 22 | hold_pysnooper_encoding | `…/holdout/pairs/bugsinpy_pysnooper_encoding` | distilled in-pair assertion | `fixed.py` | return/contract (distilled) |
| 23 | hold_tqdm_enumerate | `…/holdout/pairs/bugsinpy_tqdm_enumerate` | distilled in-pair assertion | `fixed.py` | return/contract (distilled) |

### 3.3 Distractors — other-rule real bugs (must NOT be confirmed by the gate)

| # | case_id | Source | Trigger | Fixed | Expected |
|--:|---|---|---|---|---|
| 24 | dist_off_by_one | `…/holdout/pairs/classic_off_by_one` | in-pair test | `fixed.py` | gate: **not confirmed** (rule ≠ inconsistent_return) |
| 25 | dist_wrong_operator | `…/holdout/pairs/classic_wrong_operator` | in-pair test | `fixed.py` | gate: **not confirmed** |
| 26 | dist_missing_base_case | `…/holdout/pairs/classic_missing_base_case` | in-pair test | `fixed.py` | gate: **not confirmed** |

### 3.4 Hard negatives — optional-by-design / guarded (must be `Refuted`)

| # | case_id | Shape (curated minimal pair) | Expected |
|--:|---|---|---|
| 27 | neg_optional_by_design | Function declared `-> Optional[T]`, caller guards correctly | **Refuted** (optional allowed) |
| 28 | neg_dominating_guard | `if x is None: return` dominates the deref | **Refuted** (guard excludes path) |
| 29 | neg_raise_only_exit | Non-value branch exits via `raise`, not implicit `None` | **Refuted** (no fall-through) |
| 30 | neg_expected_negative_test | `pytest.raises`/intended failure path | **Refuted** (expected negative) |

**Slate totals:** 30 cases · ≥10 repositories · priority classes 23/30 ·
distractors 3 · hard negatives 4 · families ≥3 (inconsistent_return,
optional-return, return-contract, + distractor + negative families).

---

## 4. Per-case definitions (the four required fields)

For every case the assembly produces these, mapped to existing formats.

### 4.1 Source
- **BugsInPy:** `projects/<p>/bugs/<id>/` → `bug.info.buggy_commit_id`,
  `fixed_commit_id`, upstream `repository_url`; `bug_patch.txt` (the fix);
  `affected_files`/`affected_functions` read from the patch.
- **In-repo holdout:** `pairs/<id>/{buggy,fixed}.py` (99D `pair_dir` shorthand).
- **GitHub (reserve):** `owner/repo@<sha_parent>` / `@<sha_fix>`, preregistered.
- **Synthetic negative:** curated minimal `{buggy,fixed}` pair, license-clean.

### 4.2 Trigger test (the executable witness)
- **BugsInPy:** the command in `run_test.sh` (e.g.
  `pytest -q -s tests/<file>::<test>`), `test_file` from `bug.info`. Must be
  **re-verified at assembly**: fails on `buggy_commit_id`, passes on
  `fixed_commit_id`.
- **In-repo / synthetic:** a minimal bound test/assertion that fails on `buggy.py`,
  passes on `fixed.py`.
- A case whose trigger test does **not** bind to the defect → eligible only up to
  **Strong Suspect** (no Confirmed), per Phase 99.

### 4.3 Fixed revision
- **BugsInPy:** `fixed_commit_id` (99D `git` revision kind: `repo_path=<upstream
  checkout>`, `ref=fixed_commit_id`, `files=affected_files`).
- **In-repo:** `fixed.py` (99D `file`/`pair_dir`).
- Used as the **matched negative**: the gate must be silent on it (99B §6.2 / §8.5).

### 4.4 Expected packet (the answer key)
Per Phase 99C §2.4 / Phase 99B §2.2, assigned at assembly and dual-reviewed:
```
case_id, repository_id, buggy_commit, fixed_commit, affected_files/functions
bug_class            inconsistent_return | optional-return | return-contract | distractor | negative
gate_eligible_rule   inconsistent_return | none
expected_tier        Confirmed Defect | Strong Suspect | Review Lead | Refuted
expected_bundle      contract, violating_condition, feasible_path, refuting_guard(none|present),
                     witness(trigger test | none), consequence/impact
detector_expected_to_fire   yes | no        (separates detector recall from gate behavior)
ground_truth_source         BugsInPy bug.info / patch / upstream issue
```

---

## 5. 99D manifest mapping & materialization

Each case becomes one 99D manifest entry:

```json
{ "id": "bip_tornado_7",
  "target_rules": ["inconsistent_return"],
  "buggy_revision": { "kind": "git", "repo_path": "<tornado checkout>",
                      "ref": "<buggy_commit_id>", "files": ["<affected>"] },
  "fixed_revision": { "kind": "git", "ref": "<fixed_commit_id>", "files": ["<affected>"] },
  "fixed_files": ["<affected>"],
  "test_documents": [ "<test AST docs for verification evidence>" ] }
```

In-repo cases use `"pair_dir": "builder_core/benchmarks/holdout/pairs/<id>"`.

**Materialization step (assembly):** BugsInPy bugs reference **upstream** commits;
the probe holds metadata, not full history. Assembly must check out each upstream
repo at `buggy_commit_id` / `fixed_commit_id` (BugsInPy `setup.sh`/checkout, or
`git show <ref>:<file>`) to provide the revisions to the 99D harness. This is the
one real preparation cost of the BugsInPy positives; the in-repo pairs (cases
21–26) and synthetic negatives (27–30) need **no** setup and can replay immediately.

---

## 6. Execution & safety

- **Replay:** `historical_bug_replay.cli run --manifest <100A> --output … --enable`
  (99D), default-off, gate enabled in-session only, read-only revision access.
- **Trigger tests** run only in a **developer-controlled sandbox per project**
  (97A/99D boundary); no implicit execution of untrusted target code; BugsInPy env
  via its own `requirements.txt`/`setup.sh`.
- **Determinism:** pinned commits + frozen manifest → byte-stable replay (99B §5.6).
- **No detector/benchmark change:** corpus lives under `data/` (RU-2 `benchmark`
  role, excluded from `ask`/production). QuixBugs 12/0, holdout 2/0 untouched.

---

## 7. Acceptance (definition of done for v1 corpus)

| Criterion | Met by |
|---|---|
| First 30 cases selected, prioritizing the 3 return classes | §3 (23/30 priority) |
| Sources defined (BugsInPy real commits, in-repo pairs, synthetic negatives) | §3, §4.1 |
| Trigger tests defined + verification rule (fail-on-buggy/pass-on-fixed) | §4.2 |
| Fixed revisions defined (commit IDs / `fixed.py`) | §4.3 |
| Expected packet schema per case | §4.4 |
| ≥10 repositories, ≥3 families, positives + distractors + hard negatives | §3 totals |
| Deterministic, preregistered selection; misses kept in denominator | §2 |
| Maps cleanly to the 99D manifest; materialization step explicit | §5 |

**Honest caveats (carried to assembly):**
1. §2 verified *return-touching*; each positive's precise `bug_class` and
   `expected_tier` are finalized by reading the patch + buggy source, dual-reviewed.
2. Whether the `inconsistent_return` **detector** fires on each positive is unknown
   until replay — detector misses are recorded separately and kept in the recall
   denominator (they are not corpus failures).
3. This batch supplies ~20 BugsInPy positives; reaching Phase 99B **7/10**
   (≥10 *human-accepted* confirmed + ≥25% recall) depends on replay + human review
   outcomes, which this plan sets up but does not pre-judge.
4. Real `inconsistent_return` *defects* are rare; the honest expectation is a small
   Confirmed set, a larger Strong-Suspect set, and every hard negative `Refuted`.

---

## 8. Bottom line

Phase 100A turns Phase 99C into a runnable v1: **30 preregistered cases — 20 real
BugsInPy return-fix bugs across 10 repositories (real commits + trigger tests),
3 zero-setup in-repo return pairs, 3 distractors, 4 hard negatives** — selected by
a reproducible rule, each carrying a source, a fail-on-buggy/pass-on-fixed trigger
test, a fixed revision, and an expected packet. It is the first executable input to
the Phase 100 historical-confirmation workflow, and it is honest about what replay
and human review must still decide.
