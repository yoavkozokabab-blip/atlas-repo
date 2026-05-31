# Phase 95 - Real Repository Validation Program

**Status:** Design only. No code, detector, reasoning, or benchmark changes.
**Date:** 2026-05-31
**Goal:** Measure whether the current frozen Builder Core is useful on real software repositories before any external alpha.

---

## 1. Purpose

Builder Core has benchmark evidence, but benchmarks answer only a narrow question:
does the engine reproduce known labels on curated corpora?

Phase 95 answers a different question:

> When a software engineer points the frozen Builder Core at an ordinary repository, are the results trustworthy, actionable, and worth the review time?

This is an evaluation program, not a capability phase. It does not add rules, change thresholds, promote detectors, or introduce new reasoning. The engine under review must remain frozen for the duration of the program.

## 2. Current Validation Boundary

The existing validation lineage remains useful as a regression guard:

| Corpus | Role | Previously documented unified result |
| --- | --- | --- |
| QuixBugs | In-domain algorithm-bug regression | 12 TP / 0 FP |
| Existing holdout | Out-of-domain paired regression | 2 TP / 0 FP |

Those corpora must continue to pass, but they do **not** count toward the Phase 95 usefulness score. Phase 95 uses repositories selected independently of benchmark labels and reviews the tool as an engineer would encounter it.

## 3. Hard Constraints

- Freeze the Builder Core commit, configuration, and feature flags before corpus execution.
- Do not add AI behavior.
- Do not add detectors.
- Do not add reasoning systems.
- Do not tune thresholds or suppress rules during the run.
- Do not execute target repository code.
- Do not install target repository dependencies.
- Do not run repository tests as part of Builder Core analysis.
- Do not modify target repository source files.
- Do not use QuixBugs, the existing holdout fixtures, or Builder Core test fixtures as Phase 95 repositories.
- Keep benchmark regression results separate from real-repository results.
- Record unknown or undecidable outcomes honestly. Do not convert uncertainty into success.

If evaluation discovers a defect in the analyzer or validation harness, pause the run. Fixes belong to a later, separately reviewed phase. Restart Phase 95 from a newly frozen candidate rather than mixing pre-fix and post-fix results.

## 4. Program Structure

Phase 95 should run in four steps:

| Step | Purpose | Output |
| --- | --- | --- |
| A. Freeze | Pin the candidate and preregister the corpus | Candidate record and repository manifest |
| B. Scan | Run the frozen engine read-only on every pinned revision | Raw outputs, timings, safety snapshots |
| C. Review | Perform blinded independent human review | Adjudicated finding labels and usefulness scores |
| D. Decide | Apply external-alpha gates without tuning | Validation report with pass, hold, or fail verdict |

The program has two evaluation tracks:

1. **Open-world review:** inspect findings emitted on current real repositories.
2. **Historical-bug review:** analyze selected parent revisions of real bug-fix commits and measure whether emitted findings point toward the later fix.

The first track measures trust and daily usefulness. The second provides a benchmark-independent opportunity-hit rate without claiming exhaustive recall.

## 5. Repository Selection Criteria

### 5.1 Inclusion Criteria

Each repository must:

- Be a real maintained or historically maintained software project, not a coding exercise.
- Have a pinned revision recorded by immutable commit hash.
- Be available under a license or internal approval that permits local static review.
- Contain at least five eligible Python source files outside generated, vendored, and dependency directories.
- Include a meaningful engineering shape: package, service, CLI, library, automation tool, or application.
- Be independent of Builder Core development and its curated benchmark corpora.
- Be scanned from a clean checkout or a read-only copy.

### 5.2 Diversity Criteria

The corpus should include:

- Libraries
- CLI tools
- Web or API services
- Data-processing or automation projects
- Developer tooling
- Repositories with substantial tests
- Repositories with sparse tests
- Single-package layouts
- Multi-package layouts
- Repositories with conventional imports
- Repositories with more complex package structure, aliases, or optional dependencies

### 5.3 Exclusion Criteria

Exclude:

- QuixBugs and existing holdout fixtures
- Builder Core's own synthetic fixtures
- Repositories selected because a known current detector is expected to fire
- Educational algorithm collections
- Repositories dominated by generated or vendored Python
- Repositories requiring source mutation before analysis
- Repositories whose license or confidentiality status is unclear

Private repositories may be evaluated in an opt-in supplemental track, but the reproducible external-alpha gate should use a public pinned corpus.

## 6. Repository Sizes

Use 24 public repositories for the primary program. Size is measured after excluding vendored, generated, virtual-environment, build, and cache directories.

| Size band | Eligible Python LOC | Eligible Python files | Repository count | Purpose |
| --- | ---: | ---: | ---: | --- |
| Small | 500-5,000 | 5-40 | 8 | Fast iteration, simple layouts, precise manual review |
| Medium | 5,001-50,000 | 41-300 | 10 | Typical engineering projects and package structures |
| Large | 50,001-250,000 | 301-1,500 | 6 | Scale, noise, import complexity, and operational stress |
| **Total** | - | - | **24** | Balanced real-repository corpus |

If a repository crosses file and LOC bands, use Python LOC as the primary band and record both values.

Repositories above 250,000 eligible Python LOC belong in an optional stress appendix. They should not dominate the alpha decision until runtime limits and review workload are understood.

## 7. Language Mix

Builder Core's current bug intelligence is Python-focused. The corpus should reflect real Python projects without pretending that non-Python analysis exists.

| Language profile | Definition | Repository count | What it measures |
| --- | --- | ---: | --- |
| Python-dominant | Python is at least 80% of source LOC | 12 | Core precision on conventional Python projects |
| Python-centered polyglot | Python is 40-79% of source LOC; other files may include JavaScript, TypeScript, shell, SQL, templates, or configuration | 8 | Behavior in realistic application repositories |
| Python-secondary | Python is 10-39% of source LOC but still has at least 20 eligible Python files | 4 | Honest handling when Python is not the whole repository |
| **Total** | - | **24** | - |

Record:

- Total files and LOC by language
- Eligible Python files and LOC
- Test-file count and test-to-source ratio
- Generated and vendored exclusions
- Package layout
- Git commit hash

Non-Python files measure repository-loading realism and UX. They do not receive bug-intelligence precision labels unless Builder Core already emits a supported finding for them.

## 8. Sampling Strategy

### 8.1 Corpus Selection

Create the repository manifest before running the frozen candidate.

Selection rules:

1. Choose repositories by the size, language, and project-shape quotas above.
2. Pin a commit hash for every repository.
3. Record why each repository was selected before seeing Builder Core output.
4. Do not replace a repository because it produces no findings.
5. Replace a repository only for documented operational reasons such as unavailable source, license ambiguity, corrupted checkout, or an analysis failure that makes the repository unusable.
6. Preserve replacement history in the final report.

### 8.2 Open-World Finding Sample

Review all verdict-eligible findings when workload permits.

If the frozen candidate emits more than 300 verdict-eligible findings across the corpus:

- Review every high-severity finding.
- Review every finding from repositories with 10 or fewer findings.
- Sample the remaining findings by repository, rule, finding kind, and severity.
- Require at least 25 reviewed findings per active rule when available.
- Report weighted precision using the inverse sampling probability.
- Publish both weighted and unweighted counts.

Quarantined advisory or pattern-only findings must be reported separately. They must not be mixed into the primary precision claim.

### 8.3 Negative Sample

Precision alone can be inflated by emitting almost nothing. Add a negative review sample:

- Select 3 Python files per repository from files with no verdict-eligible finding.
- Stratify by source size: one small, one medium, one large file where available.
- Ask reviewers whether an obvious actionable issue is visible within a fixed review window.
- Record missed-obvious-issue observations as qualitative false-negative leads, not exhaustive recall.

This sample measures silence quality without pretending that a manual skim proves correctness.

### 8.4 Historical-Bug Sample

Create a separate real-history track:

- Select 20-30 bug-fix commits across at least 10 repositories.
- Choose commits from issue trackers, changelogs, or human-curated Git history before running Builder Core on their parent revisions.
- Exclude formatting-only, dependency-only, generated-file, and test-only changes.
- Record the fixed files and a short human-written bug description.
- Analyze the parent revision only.
- Ask whether any emitted finding points to the defect location or violated behavior.

This produces an **opportunity-hit rate**:

```text
historical bugs with a relevant emitted finding
------------------------------------------------
eligible historical bugs reviewed
```

It is a useful directional metric. It is not exhaustive recall.

## 9. Manual Review Workflow

### 9.1 Review Roles

Use:

- Two independent reviewers per sampled finding
- A third adjudicator for disagreements
- At least one reviewer with practical Python engineering experience
- No reviewer who selected the repository solely because of a known detector match

### 9.2 Review Packet

Each finding packet should contain:

- Pinned repository and commit hash
- File path and line
- Builder Core finding text
- Evidence shown by the product
- A bounded source window around the finding
- Related caller or test context only when already available from the current product output or straightforward source inspection

Do not show:

- QuixBugs or holdout labels
- Expected detector outcomes
- Other reviewers' labels
- Later bug-fix diffs during open-world review

Historical-bug review may show the later diff only after the reviewer records whether the emitted finding independently points toward the defect.

### 9.3 Finding Labels

Each reviewer assigns one primary label:

| Label | Meaning | Counts as strict true positive? |
| --- | --- | --- |
| Confirmed actionable | The finding identifies a real defect or a concrete unsafe behavior worth fixing | Yes |
| Useful review lead | The finding is technically grounded and worth inspecting, but the reviewer cannot confirm a defect from static context alone | No |
| Benign or intended behavior | The tool flags correct or intentional code | No |
| Misleading | The finding's explanation or evidence is materially wrong | No |
| Undecidable | The reviewer cannot judge within the bounded review process | No |
| Out of scope | The finding cannot be fairly evaluated under the current review contract | Excluded and reported separately |

For alpha gating, uncertainty is handled conservatively: useful-review-lead and undecidable findings do not count as strict true positives.

### 9.4 Adjudication

- Reviewers label independently.
- Any disagreement goes to the third adjudicator.
- The adjudicator records a short rationale.
- Systematic disagreement by rule, repository type, or severity is reported.
- No labels are revised to improve metrics after the gate is calculated.

### 9.5 Review-Time Capture

Record:

- Minutes to understand the finding
- Minutes to decide the label
- Whether the evidence was sufficient
- Whether the reviewer had to inspect unrelated files
- Whether the finding would be acted on during an ordinary review

This exposes findings that are technically correct but operationally expensive.

## 10. Precision Measurement

### 10.1 Primary Metric: Conservative Strict Precision

```text
confirmed actionable findings
-----------------------------------------------
all reviewed verdict-eligible findings in scope
```

The denominator includes:

- Confirmed actionable
- Useful review lead
- Benign or intended behavior
- Misleading
- Undecidable

This is intentionally conservative. External alpha should not rely on charitable interpretation.

### 10.2 Supporting Metrics

Report:

| Metric | Purpose |
| --- | --- |
| Actionable precision | Confirmed actionable / reviewed in-scope verdict-eligible findings |
| Review-lead rate | (Confirmed actionable + useful review lead) / reviewed in-scope findings |
| Misleading rate | Misleading / reviewed in-scope findings |
| False-positive burden | (Benign + misleading) findings per repository and per 10,000 Python LOC |
| Undecidable rate | Undecidable / reviewed in-scope findings |
| Rule-level precision | Precision grouped by rule |
| Kind-level precision | Precision grouped by semantic, data-flow, value-flow, security, and advisory output |
| Severity calibration | Precision grouped by reported severity |
| Repository-stratum precision | Precision by size, language profile, and project shape |

Report raw counts beside every ratio. A percentage without its denominator is not sufficient.

### 10.3 Zero-Finding Repositories

Repositories with no verdict-eligible findings remain part of the program:

- They count toward operational success.
- They contribute to the negative-file sample.
- They receive a usefulness score.
- They are not removed or replaced merely because output is sparse.

## 11. Usefulness Scoring

Precision is necessary but not sufficient. A correct tool can still be unhelpful if the output is vague, slow to triage, or too sparse.

### 11.1 Per-Finding Usefulness Score

Each adjudicated in-scope finding receives:

| Score | Meaning |
| ---: | --- |
| 0 | Misleading or distracting; costs review time |
| 1 | Technically plausible but not useful in an ordinary engineering review |
| 2 | Useful review lead; narrows inspection meaningfully |
| 3 | Actionable; explains a concrete problem and where to investigate |
| 4 | High-value; likely saves substantial debugging or review time |

### 11.2 Repository Usefulness Score

After reviewing a repository, each reviewer scores the overall experience:

| Score | Meaning |
| ---: | --- |
| 1 | Net negative: output creates more work than value |
| 2 | Limited: occasional signal, but not worth routine use |
| 3 | Useful in selected reviews or investigations |
| 4 | Worth using routinely on this repository |
| 5 | Strongly valuable: clear, trustworthy, and time-saving |

Capture a one-sentence reason with every repository score.

### 11.3 Workflow Metrics

Record:

- Time to first useful finding
- Total scan duration
- Total review minutes per repository
- Useful findings per 10,000 Python LOC
- False-positive review minutes per repository
- Percentage of repositories with at least one score-3-or-higher finding
- Percentage of reviewers who would choose to use Builder Core again

## 12. Benchmark-Independent Evaluation

Phase 95 must remain independent from the existing benchmark loop.

### 12.1 Separation Rules

- Preregister the repository manifest before running Builder Core.
- Pin the candidate commit and configuration before scanning.
- Do not use QuixBugs or holdout fixtures as real-repository evidence.
- Do not select files because a current rule is known to fire.
- Do not use detector names as review labels.
- Do not tune the engine during data collection.
- Keep quarantined advisory findings separate from verdict-eligible findings.
- Publish repositories with zero findings.
- Publish operational failures and excluded repositories.

### 12.2 Historical Bugs Are A Secondary Measure

The historical-bug track is intentionally separate from open-world precision:

- It uses real pre-fix repository revisions.
- It measures whether current output would have helped with a known defect.
- It must not become a new detector-tuning corpus during the same phase.
- Its result is reported as opportunity-hit rate, not exhaustive recall.

### 12.3 Regression Benchmarks Remain Separate

Run QuixBugs and the existing holdout only as non-regression gates. Their numbers should appear in the report under a separate heading and must not be blended into real-repository precision.

## 13. Safety And Operational Measurement

For each repository:

1. Pin and record the commit hash.
2. Capture `git status --short` before analysis.
3. Hash tracked source files before analysis.
4. Run only read-only Builder Core commands needed by the validation protocol.
5. Capture elapsed time, peak memory if available, exit status, and crash status.
6. Capture `git status --short` after analysis.
7. Re-hash tracked source files after analysis.
8. Confirm no target source file changed.

If initialization UX is evaluated, run it only on a disposable clean copy and verify that writes remain restricted to `.jarvis_builder/`.

Operational outcomes:

| Outcome | Meaning |
| --- | --- |
| Success | Scan completes and results are reviewable |
| Degraded | Scan completes but reports skipped files, parse failures, or bounded partial coverage |
| Failed | Scan exits with an actionable error |
| Unsafe | Target source files changed, target code executed, or an undeclared write occurred |

Any unsafe outcome is an immediate external-alpha blocker.

## 14. Required Artifacts

The eventual Phase 95 execution report should include:

- Frozen candidate commit and configuration
- Repository manifest with licenses, commit hashes, sizes, language mix, and selection rationale
- Exclusion and replacement log
- Raw scan outputs
- Safety before/after snapshots
- Timing and memory measurements
- Finding-review worksheet
- Adjudication log
- Precision table with raw counts
- Usefulness-score table
- Negative-file sample results
- Historical-bug opportunity-hit-rate results
- QuixBugs and holdout non-regression results
- External-alpha verdict

Keep source snippets out of the public summary when repository licensing or confidentiality requires it. Publish metadata and aggregate results where detailed evidence cannot be shared.

## 15. Acceptance Criteria Before External Alpha

External alpha may begin only if **all** gates pass.

### 15.1 Safety Gates

| Gate | Required result |
| --- | --- |
| Target source modification | 0 modified tracked source files across all repositories |
| Undeclared target writes | 0; disposable `init` runs may write only under `.jarvis_builder/` |
| Target code execution | 0 |
| Unsafe outcomes | 0 |
| Analyzer crash-free completion | At least 95% of repositories; every failure must be actionable and non-destructive |

### 15.2 Precision Gates

| Gate | Required result |
| --- | --- |
| Conservative strict precision | At least 0.90 overall |
| Misleading rate | At most 0.05 overall |
| Systematic false-positive family | None left unexplained; any repeated harmful pattern blocks alpha until separately addressed |
| Size-band precision | At least 0.80 in each populated size band |
| Language-profile precision | At least 0.80 in each populated language profile |
| Rule-level evidence | Raw counts reported for every emitted rule; rules with insufficient samples marked inconclusive |
| Existing QuixBugs regression | Preserve the frozen candidate's accepted zero-FP result |
| Existing holdout regression | Preserve the frozen candidate's accepted zero-FP result |

### 15.3 Usefulness Gates

| Gate | Required result |
| --- | --- |
| Median repository usefulness score | At least 3.0 / 5 |
| Review-lead rate | At least 0.60 |
| Repositories with at least one score-3-or-higher finding | At least 30% of repositories, unless the negative sample supports a low-defect corpus explanation |
| Reviewer willingness to use again | At least 70% |
| False-positive review burden | Median no more than 10 wasted minutes per repository |

### 15.4 Benchmark-Independent Evidence Gates

| Gate | Required result |
| --- | --- |
| Preregistered real repositories | 24 public pinned repositories meeting the quota |
| Independent review | Two reviewers per sampled finding plus adjudication |
| Historical-bug track | At least 20 eligible pre-fix cases across at least 10 repositories |
| Historical opportunity-hit rate | Reported honestly with raw numerator and denominator; no minimum pass threshold in the first Phase 95 run |
| Zero-finding repositories | Included, not replaced |

The historical opportunity-hit rate deliberately has no first-run pass threshold. Phase 95 establishes the real-world baseline. Setting a target before observing the frozen engine would invite metric gaming.

## 16. Decision Outcomes

| Verdict | Meaning | Next action |
| --- | --- | --- |
| PASS | All external-alpha gates pass | Begin a limited external alpha with the same frozen candidate |
| HOLD | Safety passes, but precision or usefulness is inconclusive due to sample size or review disagreement | Expand review or corpus sampling without changing the engine |
| FAIL | Any safety gate fails, precision misses the threshold, or systematic misleading output appears | Do not start external alpha; open a separate improvement phase after publishing the Phase 95 results |

Do not patch the engine inside Phase 95. Measurement and improvement must remain separate.

## 17. External Alpha Shape After A Pass

If Phase 95 passes, external alpha should remain narrow:

- Invite 5-10 engineers.
- Use opt-in repositories only.
- Keep the candidate version pinned.
- Preserve read-only defaults.
- Capture explicit user feedback and false-positive reports.
- Avoid automatic source modifications.
- Avoid silent background scanning.
- Review every reported safety concern before widening access.

This alpha validates workflow fit. It is not permission to expand intelligence without a separate design and precision gate.

## 18. Definition Of Done

Phase 95 design is complete when:

- The repository corpus criteria and quotas are approved.
- The review rubric is approved.
- The candidate-freeze rule is accepted.
- The safety snapshot protocol is accepted.
- The precision formula and usefulness rubric are accepted.
- The external-alpha gates are accepted.
- No implementation or analyzer changes are included in the design commit.

---

## One-Line Summary

Phase 95 validates the frozen Builder Core on 24 preregistered real repositories with read-only safety snapshots, independent human adjudication, conservative precision, workflow usefulness scores, and a separate real-history opportunity check before any external alpha.
