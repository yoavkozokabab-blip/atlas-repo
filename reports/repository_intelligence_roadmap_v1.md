# Repository Intelligence Roadmap v1

**Goal claim to earn:** *"JARVIS tells developers what is broken."*
**Date:** 2026-05-31
**Type:** Evidence-based roadmap. No code.
**Method:** Audit the actual working tree, not the labels. Every "current state"
row below is measured, not assumed.

---

## 0. What the claim honestly requires

"Tells developers what is broken" is only honest when **all four** hold:

1. **Real** — findings are true defects, not pattern noise (precision **measured
   on real repositories**, not just synthetic benchmarks).
2. **Enough** — it catches a meaningful share of the bugs that actually occur
   (recall that is *measured*, even if not exhaustive).
3. **Legible** — each finding ships with evidence a developer can verify in
   seconds ("here is the bug, here is the proof").
4. **Trustworthy by default** — the default output is signal, not a pile the
   developer must triage.

Today the system can *emit* findings on real code. It cannot yet honestly *claim*
they are what is broken, because **#1 was never measured and #4 is not met.**

---

## 1. Where we actually are (measured today)

| Capability | State | Evidence |
|---|---|---|
| Repository understanding (RU-1/2/3) | **Done, green** | role classifier, subsystem map, 11-category question understanding; 337 tests pass (RU-3 impl present, **uncommitted**) |
| Dependency graph (94A) | **Done, committed** | `depgraph.py` (761 lines), nodes/edges/unresolved/statistics |
| Impact analysis (94B) | **Done, committed** | `impact.py` (987 lines) |
| Contract facts (96A) | **Built but DORMANT** | `contract_facts.py`: *"emits NO findings, NO promotion, consumed by NO detector"* |
| Contract enrichment (96C) | **Built but review-only** | `contract_enrichment.py`: *"Does NOT promote findings"* |
| Verification evidence (97A) | **Built but GATED OFF** | `verification_evidence.py`: `EVIDENCE_PROMOTION_ENABLED = False`, review-lead-only |
| Cross-file / callgraph (93A/C) | **Built but DORMANT** | *"consumed by NO detector"* |
| Detection engine | **18 rules, precision 1.0 on benchmarks** | QuixBugs 12 TP / 0 FP (**recall 0.30**); holdout 2 TP / 0 FP (**recall 0.167**) |
| Real-repo validation (95A–D) | **Harness done; verdict HOLD** | pilot emitted **720 findings** (202 grounded, **518 advisory ≈ 72% noise**), **0 human labels**, real-repo precision **unavailable**, **0/24** corpus, **0** historical-bug cases |

**The two facts that dominate the roadmap:**

- **Real-repo precision is UNMEASURED.** The one experiment designed to prove it
  (Phase 95C review) produced 202 reviewable findings and then **stopped before a
  single label**. Verdict `HOLD`.
- **The richest facts are DORMANT.** Contracts, verification evidence, cross-file
  and call-graph facts are all computed and then **thrown away** at finding time.
  Most of the engineering value sits behind `*_ENABLED`/`PROMOTION = False` flags.

---

## 2. Missing capabilities (the gap)

| ID | Missing capability | Why it blocks the claim |
|---|---|---|
| **M1** | **Measured real-repo precision** — finish the 95C human review (label the 202 grounded findings) on a real, independent corpus | Without a precision number on real code, *every* "what is broken" claim is unproven. This is the gate, and it is already 90% built. |
| **M2** | **Signal-by-default output** — suppress/segregate the 518 advisory/pattern findings so the default surface is the grounded set | 72% of current output is noise. A developer who sees noise first stops trusting the tool. |
| **M3** | **Fact→finding promotion** — precision-gated evaluators that turn already-computed contract / verification / cross-file facts into confirmed findings | The only recall source that does **not** require new detectors. The facts exist; the promotion logic does not. |
| **M4** | **Evidence-first finding surface** — flip verification_evidence (97A) from review-lead-only into the developer-facing presentation of each finding | Turns a finding into a *trusted* finding. Built; gated off. |
| **M5** | **Measured recall on real bug classes** — the 95 "historical bug" / opportunity-hit-rate track (today 0 cases) | "Enough" (§0 #2) is currently unknown on real code. Benchmark recall ≠ real recall. |
| **M6** | **Precision CI** — automatic re-measurement of precision when any rule changes | The claim decays silently the moment a rule is edited without re-measuring. |

---

## 3. Leverage ranking (highest first)

Leverage = trust-or-recall earned per unit of effort, given what is already built.

1. **M1 — real-repo precision review.** Converts "we believe" → "we measured."
   Unblocks the external claim and every downstream decision. **Built; not run.**
2. **M4 — evidence-first surface.** Makes findings self-verifying. **Built; one
   flag + presentation work.**
3. **M3 — fact→finding promotion.** The recall engine that reuses dormant facts.
   Highest recall-per-effort because the facts already exist.
4. **M2 — signal-by-default.** Cheap, large day-one usefulness gain.
5. **M5 — real recall measurement.** Proves coverage; longer, corpus-bound.
6. **M6 — precision CI.** Sustains the claim; low urgency until M1 produces a
   number worth protecting.

---

## 4. Dependencies and technical risk

| ID | Depends on | Tech risk | Risk driver |
|---|---|---|---|
| M1 | independent real corpus (the 0/24 gap); 95A–D harness (**done**) | **Low** | Mostly process/labor (review labels). Harness is deterministic and frozen. Risk is *sourcing licensed real repos*, not engineering. |
| M2 | grounded vs. advisory split (**already exists in export**) | **Low** | Re-ordering/suppression of an existing partition. No detector change. |
| M3 | contract_facts (96A), verification_evidence (97A), cross_file (93C) — **all done**; **and M1** (need a precision baseline to gate against) | **High** | Promotion is exactly where precision dies. Each evaluator must clear the 0-FP gate on real code. Must not ship before M1. |
| M4 | verification_evidence (97A, **done**) | **Low–Med** | Flipping `EVIDENCE_PROMOTION_ENABLED` is trivial; making evidence *consistently legible* across rules is the real work. |
| M5 | real corpus + historical bug labels (today **0**) | **Med** | Honest recall needs known-bug ground truth, which is laborious to assemble. |
| M6 | a stable precision number from M1 | **Low** | Engineering is straightforward once M1 defines the metric to guard. |

**Sequencing constraint:** M1 is a hard predecessor of M3, M5, and M6. You cannot
gate promotion (M3) or guard precision (M6) against a number that does not exist.

---

## 5. Must-have / nice-to-have / distractions

### Must-have (the shortest path to the claim)
- **M1** measured real-repo precision (finish 95C review on a real corpus).
- **M2** signal-by-default output.
- **M4** evidence-first finding surface.
- **M3** fact→finding promotion under the precision gate (after M1).
- **M6** precision CI (once M1 yields a number).

### Nice-to-have (real value, not on the critical path)
- **M5** real-recall / opportunity-hit-rate (strengthens the claim's "enough"
  half, but the claim is honest with measured precision + *directional* recall).
- Impact analysis (94B) **as finding enrichment** — annotate a confirmed bug with
  "affects N callers across M subsystems." Reuses built work; do not expand it.
- Cross-file (93C) promotion — a specific instance of M3; pursue only if 93C facts
  clear the gate.

### Distractions (stop or never start)
- More **repository-understanding surface**: RU-4+, more `ask()` question
  categories, more graph query types. The understanding layer is *already more
  than sufficient* as a support tier; it does not tell what is broken.
- More **dormant fact infrastructure** (another 93x/96x "built, consumed by no
  detector" phase). Building facts you never promote is motion without progress.
- **Benchmark recall chasing** (tuning to QuixBugs/BugsInPy). Phase 95's own
  design says benchmarks are regression guards, *not* usefulness evidence.
- **LLM-based "what's broken" generation.** Off-strategy; the whole stack's value
  is determinism and 0-FP discipline. An LLM layer forfeits both.
- **Product pivots** (chat assistant, autonomy features) — orthogonal to the claim.

---

## 6. Dead-end phases — stop these explicitly

| Phase / line of work | Verdict | Reason |
|---|---|---|
| **The "infrastructure only, no findings" treadmill** (93A, 93C, 96A, 96C, 97A as currently flagged) | **STOP building more of it; START promoting what exists** | Five phases produced rich facts that *no detector consumes*. The marginal dormant-fact phase has near-zero value. Convert (M3/M4) or stop. |
| **Repository understanding beyond RU-3** | **STOP / freeze** | RU-1/2/3 + depgraph + impact already answer structure questions well. More categories/queries do not move the "what is broken" needle. Commit RU-3 and freeze the line. |
| **Impact analysis (94B) as a standalone feature** | **DEMOTE to enrichment only** | It answers "what breaks if I change X," not "what *is* broken." Valuable as a finding annotation; a dead end as a headline capability. |
| **Synthetic-benchmark recall expansion** | **STOP as a goal** | Keep QuixBugs/holdout as 0-FP *regression guards*. Do not invest in raising their recall; it is not evidence of real usefulness. |
| **New detectors before M1** | **HOLD** | Adding rules before real-repo precision is measured risks importing false positives you cannot yet detect. Detector growth resumes *after* M1 + M6 exist. |

---

## 7. The shortest honest path

1. **Commit RU-3 and freeze the understanding line.** It is done and green; stop
   here. (Closes the distraction in §6.)
2. **M1 — measure real-repo precision.** Source a small independent, licensed
   Python corpus; run the frozen engine (already does this — 720 findings on the
   pilot); **complete the human review** the 95C harness already set up. Output:
   the first real precision number + verdict.
3. **M2 — make grounded the default; quarantine advisory.** One ordering/suppress
   change to the existing partition. Immediate usefulness.
4. **M4 — turn on evidence-first findings.** Flip 97A on; make each finding carry
   its verification atoms. Findings become self-verifying.
5. **Branch on the M1 number:**
   - **Precision holds →** **M3**: promote dormant contract/verification/cross-file
     facts into findings, one evaluator at a time, each gated by re-measured real
     precision. This is the recall engine.
   - **Precision fails →** fix/retire the noisy rules first; do **not** promote
     anything until the grounded set is clean.
6. **M6 — precision CI** to protect the number M1 produced.
7. **M5 — directional real recall** (historical-bug track) to complete the
   "enough" half of the claim.

**When can JARVIS honestly make the claim?** After **step 5's "precision holds"
branch**: a measured real-repo precision on grounded, evidence-carrying findings
that are the default output. Steps 6–7 sustain and strengthen it. Everything in
§6 is what *delays* that day.

---

## Appendix — evidence sources (audited 2026-05-31)

- `builder_core/tests/` — **337 passed** (RU-1/2/3 + engine + graph + impact).
- `builder_core/bug_intelligence/` — 18 detector rules; `contract_facts.py`,
  `contract_enrichment.py`, `verification_evidence.py`, `depgraph.py` (761),
  `impact.py` (987), `callgraph.py`, `cross_file.py` headers (dormant/gated flags).
- `reports/phase95c_first_real_repository_validation_report.md` — verdict `HOLD`,
  720 findings, 202 grounded, 518 advisory, 0 labels, 0/24 corpus, 0 historical
  bug cases.
- `reports/ru2_repository_understanding_v1.md` — real index roles (665 production,
  1,873 benchmark, 1,361 report_history) and architecture-answer cleanliness.
- Benchmarks: QuixBugs 12 TP / 0 FP (recall 0.30); holdout 2 TP / 0 FP (recall
  0.167) — precision-1.0, low-recall, **synthetic** (regression guards only).
- `git log` — 94B impact committed; RU-3 `question_understanding.py` **untracked**.
