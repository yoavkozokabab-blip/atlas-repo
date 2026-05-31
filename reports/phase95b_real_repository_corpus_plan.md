# Phase 95B - First Real Repository Corpus Plan

**Status:** Design only. No corpus scan, implementation, detector, benchmark, finding, or promotion change.
**Date:** 2026-05-31
**Goal:** Build and preregister the first real-repository corpus for the Phase 95A validation harness.

---

## 1. Purpose

Phase 95B defines the first real-world measurement corpus for Builder Core.

The objective is not to improve metrics. The objective is to learn:

> Is the frozen Builder Core useful, trustworthy, and worth an engineer's review time on ordinary repositories it was not tuned against?

This phase creates the corpus protocol and review rules. It does not select repositories because Builder Core is expected to perform well on them, and it does not change Builder Core after seeing results.

## 2. Frozen Instrument

Use the committed Phase 95A harness:

```text
builder_core.real_repo_validation
```

The harness treats Builder Core as a frozen instrument:

- Manifest preregistration pins the Builder Core commit.
- Manifest preregistration pins feature flags.
- Every repository checkout is pinned by immutable Git commit.
- A run refuses candidate drift.
- A run refuses repository checkout drift.
- Artifacts are written outside target repositories.
- Target source files are hashed before and after analysis.

The corpus plan must be approved and the manifest must be locked before any repository is scanned.

## 3. First-Corpus Shape

The primary corpus contains 24 public repositories.

| Dimension | Target |
| --- | ---: |
| Public pinned repositories | 24 |
| Small repositories | 8 |
| Medium repositories | 10 |
| Large repositories | 6 |
| Python-dominant repositories | 12 |
| Python-centered polyglot repositories | 8 |
| Python-secondary repositories | 4 |
| Project-shape families represented | At least 5 |
| Historical bug cases | 20-30 |
| Repositories contributing historical cases | At least 10 |

An optional stress appendix may contain repositories above 250,000 eligible Python LOC. Stress repositories are reported separately and do not control the first external-alpha decision.

## 4. Repository Selection Criteria

### 4.1 Required Inclusion Criteria

Every primary-corpus repository must:

- Be a real maintained or historically maintained software project.
- Be publicly available with a clearly recorded license.
- Be independent of JARVIS, Builder Core, QuixBugs, and existing holdout fixtures.
- Represent a genuine engineering artifact: library, CLI, service, developer tool, automation system, data-processing project, or application.
- Contain at least five eligible Python source files after exclusions.
- Have a clean local Git checkout.
- Have a pinned immutable commit.
- Be scannable without dependency installation, code execution, or source edits.
- Be selected before Builder Core output is inspected.
- Have a written selection rationale unrelated to expected findings.

### 4.2 Project-Shape Quotas

The corpus should include at least:

| Project shape | Minimum repositories |
| --- | ---: |
| Reusable library or SDK | 5 |
| CLI or developer tool | 4 |
| Web, API, or service application | 4 |
| Data-processing, automation, or operations tool | 4 |
| Multi-package or plugin-oriented repository | 3 |

A repository may satisfy more than one shape. The manifest should record one primary `project_shape` and optional secondary notes.

### 4.3 Engineering-Context Diversity

Across the corpus, include:

- Repositories with substantial tests
- Repositories with sparse tests
- Flat single-package layouts
- `src/` layouts
- Multi-package layouts
- Conventional imports
- Aliased and optional imports
- Configuration-heavy applications
- Repositories with shell, SQL, templates, or frontend files alongside Python

The purpose is exposure to ordinary engineering variety, not maximal framework coverage.

## 5. Repository Size Buckets

Measure size after excluding dependency, generated, vendored, cache, and build directories.

| Size band | Eligible Python LOC | Eligible Python files | Primary-corpus quota | Purpose |
| --- | ---: | ---: | ---: | --- |
| `small` | 500-5,000 | 5-40 | 8 | Straightforward layouts and affordable exhaustive review |
| `medium` | 5,001-50,000 | 41-300 | 10 | Typical engineering projects |
| `large` | 50,001-250,000 | 301-1,500 | 6 | Scale, import complexity, output burden, and runtime behavior |
| `stress` | More than 250,000 | More than 1,500 | Optional appendix | Operational stress only |

Rules:

- Use Python LOC as the primary bucket when LOC and file counts disagree.
- Record both LOC and file count.
- Do not replace a large repository with a small one merely to reduce review work.
- If a large repository exceeds practical harness limits, keep it in the report as an operational outcome.

## 6. Language Mix

Builder Core currently analyzes Python. The corpus should still include realistic mixed-language projects so repository loading and precision are measured in context.

| Manifest profile | Definition | Primary-corpus quota |
| --- | --- | ---: |
| `python_dominant` | Python is at least 80% of eligible source LOC | 12 |
| `python_centered_polyglot` | Python is 40-79% of eligible source LOC | 8 |
| `python_secondary` | Python is 10-39% of eligible source LOC and at least 20 eligible Python files exist | 4 |

For each repository, record:

- Source LOC by language
- Eligible Python LOC
- Eligible Python file count
- Python test-file count
- Test-to-source ratio
- Generated and vendored exclusions
- Package layout
- Primary project shape

Non-Python files provide repository context only. They are not silently treated as analyzed bug-intelligence input.

## 7. Exclusion Rules

### 7.1 Repository Exclusions

Exclude:

- QuixBugs
- Existing holdout repositories and fixtures
- Builder Core fixtures
- Educational algorithm collections
- Interview-practice repositories
- Repositories selected because a current detector is known to fire
- Repositories dominated by generated or vendored code
- Repositories that require source mutation before analysis
- Repositories whose license is missing or unclear
- Repositories whose checkout cannot be pinned
- Mirrors or forks that would duplicate another selected project's code

### 7.2 Path Exclusions

Do not count or review:

- `.git/`
- `.jarvis_builder/`
- Virtual environments
- Package caches
- Build artifacts
- Generated sources
- Vendored dependencies
- `node_modules/`
- Distribution directories
- Coverage output
- Tool caches

Use the Phase 95A harness and unified-engine skip behavior as the operational baseline. Record any repository-specific exclusions in the manifest notes.

### 7.3 Finding Exclusions

For the primary precision claim:

- Include grounded verdict-eligible kinds only: `semantic`, `data_flow`, `value_flow`, and `security`.
- Report advisory and quarantined findings separately.
- Do not discard a grounded finding because it appears inconvenient or difficult to review.
- Use `out_of_scope` only when the review contract genuinely cannot judge the result.

## 8. Frozen Commit Strategy

### 8.1 Freeze Builder Core

Before corpus execution:

1. Choose the Phase 95B candidate commit.
2. Record the commit in the manifest `candidate.builder_core_commit`.
3. Record the harness-observed `candidate.frozen_flags`.
4. Run existing Builder Core tests.
5. Run QuixBugs and holdout regressions.
6. Save the command output with the corpus artifacts.
7. Do not change the candidate during the corpus run.

The Phase 95A harness refuses a run if the checked-out Builder Core commit or flags differ from the preregistered candidate.

### 8.2 Freeze Repositories

For each selected repository:

1. Clone or obtain the public repository outside the validation run.
2. Checkout a specific commit.
3. Confirm a clean `git status --short`.
4. Record the immutable commit hash in the manifest.
5. Record repository size and language metadata.
6. Do not pull, switch branches, or edit files after preregistration.

The Phase 95A harness refuses analysis if the checkout does not match the manifest.

### 8.3 No Mid-Run Tuning

After scanning begins:

- Do not add suppressions.
- Do not change thresholds.
- Do not edit detectors.
- Do not change feature flags.
- Do not remove low-scoring repositories.
- Do not replace repositories because they emit no findings.
- Do not replace repositories because they emit too many findings.

If a harness or analyzer defect requires a fix, stop the run, publish the partial result as invalidated, create a separate fix phase, and restart with a new frozen candidate.

## 9. Sampling Methodology

### 9.1 Preregistration Sequence

Use this order:

1. Build a candidate repository list from neutral project metadata.
2. Apply inclusion, exclusion, size, language, and shape quotas.
3. Record selection rationales.
4. Pin commits.
5. Record replacement candidates for each bucket.
6. Lock the manifest.
7. Run the frozen harness.
8. Create the review sample from exported findings.

Do not inspect Builder Core findings before step 7.

### 9.2 Open-World Finding Review

Review every verdict-eligible finding when there are 300 or fewer.

If there are more than 300:

- Review all critical and high-severity findings.
- Review all findings from repositories with 10 or fewer findings.
- Stratify remaining findings by repository, rule, kind, severity, size bucket, and language profile.
- Sample deterministically using a preregistered seed.
- Record each finding's sampling probability in `findings.json`.
- Review at least 25 findings per emitted rule when available.
- Report both raw and inverse-probability-weighted precision.

Never sample away an inconvenient rule family.

### 9.3 Negative-File Review

For every repository:

- Select three Python files with no verdict-eligible finding.
- Prefer one small, one medium, and one large file where available.
- Use deterministic ordering and a preregistered seed.
- Give reviewers a fixed review window.
- Record obvious missed issues as qualitative false-negative leads.

This is a silence-quality check, not exhaustive recall.

### 9.4 Historical-Bug Track

Preregister 20-30 real historical bug fixes across at least 10 selected repositories:

- Record case ID.
- Record repository ID.
- Record parent commit.
- Record fix commit.
- Record a short human-written bug description.
- Record fixed files.
- Analyze the parent revision only.
- Measure whether an emitted finding points to the defect location or violated behavior.

Report:

```text
historical opportunity-hit rate =
historical cases with a relevant emitted finding
------------------------------------------------
eligible historical cases reviewed
```

This is benchmark-independent directional evidence. It is not exhaustive recall and has no first-run pass threshold.

### 9.5 Replacement Discipline

Repository replacement is allowed only for:

- Source unavailable
- License ambiguity discovered after preregistration
- Corrupted checkout
- Duplicate or mirror discovered after preregistration
- Repository not meeting its recorded inclusion criteria

For every replacement:

- Preserve the original manifest entry in an exclusion log.
- Record the reason.
- Use the next preregistered replacement from the same size and language bucket.
- Do not choose a replacement after inspecting Builder Core output.

## 10. Reviewer Workflow

### 10.1 Roles

Use:

- Reviewer A
- Reviewer B
- Independent adjudicator
- Program coordinator who manages artifacts but does not alter labels

At least one of Reviewer A or B should have practical Python engineering experience for every finding.

### 10.2 Review Packet

Use Phase 95A exports:

```text
findings.json
reviews.json
repository_scores.json
```

Each review packet contains:

- Stable record ID
- Repository ID
- Pinned repository commit
- File and line
- Finding title and explanation
- Evidence
- Why the finding might be wrong
- Next verification step
- Bounded source window

Reviewers may inspect the pinned repository source read-only. They should not see:

- Other reviewers' labels
- Expected detector outcomes
- Benchmark labels
- Metric totals during review
- Later bug-fix diffs during open-world review

### 10.3 Independent Labeling

Reviewer A and Reviewer B label independently:

| Label | Meaning |
| --- | --- |
| `confirmed_actionable` | Real defect or concrete unsafe behavior worth fixing |
| `useful_review_lead` | Grounded and worth inspection, but not proven defective from static context |
| `benign_or_intended` | Correct or intentional behavior |
| `misleading` | Explanation or evidence is materially wrong |
| `undecidable` | Cannot judge inside the bounded review process |
| `out_of_scope` | Cannot fairly evaluate under the current contract |

If labels match, Phase 95A resolves automatically. If they differ, the adjudicator reviews the packet and records the final label plus a short reason.

### 10.4 Review-Time Capture

For every review, record:

- Review minutes
- Usefulness score
- Notes
- Whether unrelated files were needed
- Whether the result would prompt an ordinary engineering action

For every repository, record:

- Repository usefulness score
- Would-use-again answer
- One-sentence reason

### 10.5 Review Order

To reduce bias:

- Randomize review packets with a preregistered seed.
- Do not group packets by rule when assigning reviewers.
- Do not show aggregate metrics until labeling is complete.
- Do not relabel findings after metrics are calculated except to correct a documented data-entry error.

## 11. Usefulness Scoring Rubric

### 11.1 Per-Finding Usefulness

| Score | Meaning |
| ---: | --- |
| 0 | Distracting or misleading; costs review time |
| 1 | Plausible but not useful in an ordinary engineering review |
| 2 | Useful lead; narrows inspection meaningfully |
| 3 | Actionable; identifies a concrete problem and useful next step |
| 4 | High-value; likely saves substantial debugging or review time |

### 11.2 Per-Repository Usefulness

| Score | Meaning |
| ---: | --- |
| 1 | Net negative; output creates more work than value |
| 2 | Limited; occasional signal but not worth routine use |
| 3 | Useful in selected reviews or investigations |
| 4 | Worth using routinely on this repository |
| 5 | Strongly valuable; clear, trustworthy, and time-saving |

### 11.3 Required Usefulness Outputs

Report:

- Per-finding usefulness distribution
- Mean per-finding usefulness
- Median repository usefulness
- Repositories with at least one score-3-or-higher finding
- Would-use-again rate
- Review minutes per repository
- False-positive review minutes per repository
- Time to first useful finding where measurable

## 12. Precision Scoring Rubric

### 12.1 Primary Precision

Use the conservative definition:

```text
strict precision =
confirmed_actionable
--------------------------------------------------------
all reviewed verdict-eligible in-scope findings
```

The denominator includes:

- `confirmed_actionable`
- `useful_review_lead`
- `benign_or_intended`
- `misleading`
- `undecidable`

Only `out_of_scope` is excluded, and every exclusion must be reported.

### 12.2 Supporting Precision Metrics

Report:

| Metric | Definition |
| --- | --- |
| Review-lead rate | (`confirmed_actionable` + `useful_review_lead`) / reviewed in-scope |
| Misleading rate | `misleading` / reviewed in-scope |
| Undecidable rate | `undecidable` / reviewed in-scope |
| False-positive burden | (`benign_or_intended` + `misleading`) per repository and per 10,000 Python LOC |
| Weighted strict precision | Inverse-probability-weighted precision if sampling occurs |
| Rule-level precision | Strict precision grouped by rule |
| Kind-level precision | Strict precision grouped by grounded kind |
| Severity calibration | Strict precision grouped by severity |
| Size-band precision | Strict precision grouped by repository size |
| Language-profile precision | Strict precision grouped by language profile |

Publish raw counts beside every ratio.

### 12.3 Sparse Output

Do not treat silence as success:

- Keep zero-finding repositories.
- Run the negative-file review.
- Report repositories with no findings.
- Report historical opportunity-hit rate.
- Report usefulness even when no issue is emitted.

## 13. External Alpha Readiness Gates

External alpha begins only if every applicable gate passes.

### 13.1 Safety Gates

| Gate | Required result |
| --- | --- |
| Unsafe outcomes | 0 |
| Modified tracked target files | 0 |
| Target code execution | 0 |
| Undeclared target writes | 0 |
| Candidate commit drift | 0 |
| Candidate flag drift | 0 |
| Repository checkout drift | 0 |
| Crash-free completion | At least 95% of primary repositories |

### 13.2 Precision Gates

| Gate | Required result |
| --- | --- |
| Overall strict precision | At least 0.90 |
| Misleading rate | At most 0.05 |
| Size-band precision | At least 0.80 in each populated band |
| Language-profile precision | At least 0.80 in each populated profile |
| Systematic harmful false-positive family | None left unexplained |
| QuixBugs regression | Preserve accepted zero-FP behavior |
| Holdout regression | Preserve accepted zero-FP behavior |

### 13.3 Usefulness Gates

| Gate | Required result |
| --- | --- |
| Median repository usefulness | At least 3.0 / 5 |
| Review-lead rate | At least 0.60 |
| Repositories with a score-3-or-higher finding | At least 30%, unless negative review supports a low-defect explanation |
| Reviewer would-use-again rate | At least 0.70 |
| Median false-positive review burden | No more than 10 wasted minutes per repository |

### 13.4 Evidence-Quality Gates

| Gate | Required result |
| --- | --- |
| Public pinned repositories | 24 |
| Independent review | Two reviewers per sampled finding |
| Adjudication | Every reviewer disagreement resolved |
| Unreviewed sampled findings | 0 |
| Historical cases | At least 20 across at least 10 repositories |
| Zero-finding repositories | Retained and reported |
| Replacement log | Complete |

Historical opportunity-hit rate has no first-run threshold. It is a baseline to learn from, not a target to optimize during Phase 95B.

## 14. Reporting Format

### 14.1 Harness Artifact Directory

The Phase 95A run writes:

```text
manifest.normalized.json
program.json
findings.json
reviews.json
repository_scores.json
findings.reviewed.json
metrics.json
report.md
```

Store outside all target repositories.

### 14.2 Required Supplemental Files

Add:

```text
corpus_selection_log.md
repository_metadata.csv
replacement_log.md
negative_file_sample.json
negative_file_reviews.json
historical_bug_reviews.json
benchmark_regressions.txt
phase95b_execution_summary.md
```

### 14.3 Final Summary Structure

The Phase 95B execution summary should contain:

1. Frozen candidate
2. Corpus composition
3. Exclusions and replacements
4. Operational safety results
5. Precision with raw counts
6. Precision by rule, kind, severity, size, and language profile
7. Usefulness scores
8. Negative-file review findings
9. Historical opportunity-hit rate
10. Benchmark regressions, reported separately
11. Review disagreements and adjudication
12. Known limitations
13. External-alpha verdict: `PASS`, `HOLD`, or `FAIL`

## 15. Risk Controls

### 15.1 Metric-Gaming Controls

- Preregister repositories before scanning.
- Select repositories using neutral metadata only.
- Keep zero-finding repositories.
- Publish replacements and reasons.
- Freeze candidate commit and flags.
- Do not tune during review.
- Keep benchmark results separate from real-repository precision.
- Give historical opportunity-hit rate no first-run pass threshold.

### 15.2 Safety Controls

- Scan clean pinned checkouts.
- Write artifacts outside targets.
- Hash tracked files before and after analysis.
- Refuse checkout drift.
- Refuse output directories inside targets.
- Do not install dependencies.
- Do not execute target code.
- Do not run target tests.
- Stop immediately on any unsafe outcome.

### 15.3 Review-Quality Controls

- Two independent reviewers per sampled finding.
- Adjudicate disagreements.
- Blind reviewers to aggregate metrics.
- Randomize packet order.
- Record review time.
- Report undecidable findings conservatively.
- Use `out_of_scope` sparingly and publish every exclusion.

### 15.4 Operational Controls

- Keep a signed or hashed copy of the locked manifest.
- Save raw harness outputs before editing reviews.
- Use one artifact directory per frozen candidate.
- Preserve partial artifacts after failure.
- Restart from a new artifact directory after any harness or analyzer fix.

## 16. Execution Sequence

1. Assemble a neutral candidate list.
2. Apply quotas and exclusion rules.
3. Record repository metadata and selection rationale.
4. Preregister 24 repositories and replacement candidates.
5. Preregister 20-30 historical bug cases.
6. Freeze Builder Core commit and flags.
7. Run Builder Core tests, QuixBugs, and holdout regressions.
8. Lock and hash the manifest.
9. Run Phase 95A harness against the primary corpus.
10. Preserve raw artifacts.
11. Build deterministic open-world and negative-file review packets.
12. Complete independent review and adjudication.
13. Regenerate metrics and report.
14. Apply external-alpha gates.
15. Publish `PASS`, `HOLD`, or `FAIL` without tuning the engine.

## 17. Definition Of Done

Phase 95B design is complete when:

- The 24-repository quota matrix is approved.
- Inclusion and exclusion rules are approved.
- The freeze strategy is approved.
- Sampling rules are approved.
- Reviewer workflow and rubrics are approved.
- External-alpha gates are approved.
- Reporting artifacts are approved.
- Risk controls are approved.
- No corpus scan or Builder Core intelligence change is included in this design phase.

---

## One-Line Summary

Phase 95B defines a preregistered 24-repository public corpus, a frozen-candidate protocol, deterministic sampling, independent human review, conservative precision and usefulness scoring, and strict external-alpha gates so the first real-world run measures usefulness rather than optimizes appearances.
