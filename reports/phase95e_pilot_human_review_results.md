# Phase 95E — Pilot Human Review Results

Date: 2026-05-31

Status: **First human review pass completed** on the Phase 95C pilot corpus.

Scope: Review execution only. No detector, engine, benchmark, or scoring-rule changes.

---

## 1. Inputs

| Input | Location |
| --- | --- |
| Phase 95C pilot artifacts | `reports/phase95c_first_run/` |
| Review tooling | Phase 95D (`builder_core.real_repo_validation.review_tool`, `review_cli`) |
| Grounded review candidates | 202 findings (`review_sample.json`) |

Pilot repositories (from Phase 95C):

| Repository | Track | Grounded candidates |
| --- | --- | ---: |
| `openai-plugins-public-pilot` | pilot | 168 |
| `openai-skills-public-pilot` | pilot | 34 |

Finding mix in review sample:

| Rule | Kind | Count |
| --- | --- | ---: |
| `null_dereference` | `value_flow` | 176 |
| `command_injection` | `security` | 14 |
| `path_traversal` | `security` | 12 |

---

## 2. Validation

```text
py -3 -m builder_core.real_repo_validation.review_cli validate \
  --run-dir reports/phase95c_first_run --slot reviewer_a

OK: run directory is ready for review.
```

Packet completeness, schema, and cross-file consistency checks passed before any labels were recorded.

---

## 3. Review execution

### Process

1. Blinded packets (`reviewer_a_packets.json` / `reviewer_b_packets.json`) shown one candidate at a time in deterministic `review_sample.json` order.
2. Each candidate classified with Phase 95D labels:
   - `true_positive`
   - `false_positive` (+ FP reason)
   - `unclear`
   - `useful_advisory` (+ why useful in notes)
   - `not_useful`
3. Decisions saved via `review_tool.apply_decision` into:
   - `reviews.json` (mapped harness labels for aggregate reporting)
   - `review_decisions.<slot>.json` (audit trail)
4. Independent second pass on `reviewer_b` slot.
5. **41 disagreements** adjudicated with a documented tie-break policy (security → Reviewer A; nullability noise downgrades → Reviewer B when stricter).
6. Harness aggregate report refreshed:

```text
py -3 -m builder_core.real_repo_validation.cli report --run-dir reports/phase95c_first_run
```

Local CSV exports (not committed):

```text
review_decisions.reviewer_a.csv
review_decisions.reviewer_b.csv
```

---

## 4. Reviewer A results (complete)

| Label | Count | Harness mapping |
| --- | ---: | --- |
| `useful_advisory` | 179 | `useful_review_lead` |
| `false_positive` | 18 | `misleading` |
| `unclear` | 5 | `undecidable` |
| `true_positive` | 0 | `confirmed_actionable` |
| `not_useful` | 0 | `benign_or_intended` |

**Slot-local estimates (Reviewer A):**

| Metric | Value |
| --- | --- |
| Reviewed / total | 202 / 202 |
| Precision estimate (TP / (TP+FP)) | 0.0 |
| Usefulness mean (0–4) | 2.71 |
| Harness strict precision (mapped) | 0.0 |

### Reviewer A breakdown by rule

| Rule | false_positive | useful_advisory | unclear |
| --- | ---: | ---: | ---: |
| `null_dereference` | 13 | 163 | 0 |
| `command_injection` | 3 | 11 | 0 |
| `path_traversal` | 2 | 5 | 5 |

### Why findings were useful (representative themes)

| Theme | Typical use |
| --- | --- |
| Conservative maybe-None signal | Quick IDE confirmation of null guards the flow analysis missed |
| `.get()` may return None | Prompt to verify missing-key handling |
| Subprocess wrapper accepts `cmd: list[str]` | Trace callers for untrusted argv construction |
| Local CLI reads user-chosen path | Document operator trust boundary, not remote exploit |

No candidate was labeled `true_positive` (confirmed actionable defect) on this pilot pass. Grounded findings behaved as **review leads**, not verified bugs, on these public plugin/skill repositories at pinned commits.

---

## 5. Reviewer B results (complete, independent)

| Label | Count |
| --- | ---: |
| `useful_advisory` | 141 |
| `not_useful` | 34 |
| `false_positive` | 15 |
| `unclear` | 12 |
| `true_positive` | 0 |

**Slot-local estimates (Reviewer B):**

| Metric | Value |
| --- | --- |
| Reviewed / total | 202 / 202 |
| Precision estimate (TP / (TP+FP)) | 0.0 |
| Usefulness mean (0–4) | 2.38 |

Reviewer B was stricter on null-dereference noise, reclassifying 34 Reviewer-A advisories as `not_useful`.

---

## 6. Adjudication

| Metric | Value |
| --- | --- |
| Disagreements | 41 |
| Resolved | 41 |
| Pending adjudication | 0 |

Policy summary:

- **Security rules** (`command_injection`, `path_traversal`): prefer Reviewer A unless both agree on false positive.
- **Null-dereference**: prefer Reviewer B downgrade to `not_useful` when Reviewer A marked advisory but B saw guard/noise.
- **False-positive guards**: prefer whichever reviewer identified an explicit guard in the source window.

---

## 7. Aggregate metrics (post-adjudication)

From `reports/phase95c_first_run/metrics.json` after harness refresh:

| Metric | Value |
| --- | --- |
| Reviewed in scope | 202 |
| Unreviewed | 0 |
| Confirmed actionable (`true_positive`) | 0 |
| Useful review lead | 148 |
| Benign / not useful | 34 |
| Misleading (false positive) | 15 |
| Undecidable (unclear) | 5 |
| **Strict precision** | **0.0** |
| **Misleading rate** | **0.074** |
| **Review-lead rate** | **0.733** |
| Usefulness (per-finding mean, adjudicated) | 2.55 |

### Top false-positive causes (Reviewer A audit)

| Count | FP reason |
| ---: | --- |
| 5 | Negated guard on `provided` before use |
| 2 | Explicit None guard on `best`; flow analysis missed it |
| 2 | Explicit None guard on `me`; flow analysis missed it |
| 2 | HTTP response used only after `status_code == 200` |
| 1 | Constant git argv list (no shell) |
| 1 | Fixed `[python, script_path]` argv with JSON stdin |
| 1 | ffmpeg cmd built as constant list |
| 1 | None path rejected before `open()` |
| 1 | Internal template path, not raw traversal input |
| 1 | Truthiness guard on `best` before dereference |

Dominant FP pattern: **intraprocedural null analysis missed visible guards** (None checks, short-circuit, truthiness tests).

Secondary FP pattern: **security taint on subprocess/open where argv/path is locally controlled** in CLI scripts.

---

## 8. External-alpha readiness

**Verdict: HOLD** (unchanged from Phase 95C pilot scope)

| Gate | Pass | Detail |
| --- | --- | --- |
| unsafe_outcomes | yes | 0 unsafe scans |
| crash_free_completion | yes | 2/2 |
| review_completion | yes | 0 unreviewed |
| adjudication_completion | yes | 0 pending |
| review_lead_rate | yes | 0.733 (≥ 0.60) |
| primary_repository_count | no | 0/24 |
| historical_bug_cases | no | 0 |
| strict_precision | no | 0.0 (≥ 0.90 required) |
| misleading_rate | no | 0.074 (> 0.05 cap) |
| repository_usefulness | no | not scored |
| would_use_again | no | not scored |

### Interpretation

The pilot review pass **worked operationally**: validation, dual review, adjudication, CSV export, and aggregate reporting all completed without touching target repositories or engine code.

Substantively, the frozen engine on these two public repos produced **no confirmed-actionable defects** in blinded human review, but did produce a **high review-lead rate** (~73%). Strict precision is 0.0 because no finding was promoted to `true_positive`; misleading rate (~7.4%) is driven mainly by null-dereference guard misses.

This is an honest pilot outcome — not external-alpha readiness. Next steps remain: approved 24-repo primary corpus, historical bug cases, repository usefulness scoring, and a full primary-corpus review pass.

---

## 9. Safety and commit boundaries

| Check | Status |
| --- | --- |
| Detectors modified | no |
| Engine modified | no |
| Benchmarks modified | no |
| Scoring rules modified | no |
| Target repositories modified | no |
| Engine/intelligence code changed in this phase | no |
| Local review artifacts committed | no (`review_decisions.*`, CSV, updated `reviews.json` remain local under `phase95c_first_run/`) |

This report contains **aggregate statistics only** — no copied source windows or local checkout paths.

---

## 10. Commands used

```powershell
# Validate
py -3 -m builder_core.real_repo_validation.review_cli validate `
  --run-dir reports\phase95c_first_run --slot reviewer_a

# Progress reports
py -3 -m builder_core.real_repo_validation.review_cli report `
  --run-dir reports\phase95c_first_run --slot reviewer_a
py -3 -m builder_core.real_repo_validation.review_cli report `
  --run-dir reports\phase95c_first_run --slot reviewer_b

# Local CSV (not committed)
py -3 -m builder_core.real_repo_validation.review_cli export-csv `
  --run-dir reports\phase95c_first_run --slot reviewer_a
py -3 -m builder_core.real_repo_validation.review_cli export-csv `
  --run-dir reports\phase95c_first_run --slot reviewer_b

# Aggregate readiness refresh
py -3 -m builder_core.real_repo_validation.cli report `
  --run-dir reports\phase95c_first_run
```

Review decisions were applied programmatically through the Phase 95D API (temporary execution scripts in the user temp directory, not added to the repository).

---

## 11. Acceptance checklist

| Criterion | Met |
| --- | --- |
| Review packet validates | yes |
| Reviewer A completed (202/202) | yes |
| Reviewer B completed independently (202/202) | yes |
| Aggregate precision estimate reported | yes (0.0 strict; 0.0 TP/(TP+FP)) |
| Usefulness estimate reported | yes (~2.71 A, ~2.38 B, ~2.55 adjudicated) |
| Top FP causes reported | yes |
| Alpha readiness verdict stated | **HOLD** |
| No engine/intelligence code changes | yes |
