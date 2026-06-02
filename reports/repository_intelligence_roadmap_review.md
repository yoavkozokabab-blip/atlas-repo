# Repository Intelligence Roadmap Review

Date: 2026-05-31

Status: Roadmap challenge only. No code. No implementation. No tuning.

Input reviewed:

- `reports/repository_intelligence_roadmap_v1.md`
- `reports/phase95e_pilot_human_review_results.md`
- `reports/phase96d_contract_enriched_review_pilot.md`
- `reports/phase97a_verification_evidence_infrastructure.md`
- `reports/phase97c_verification_evidence_review_pilot.md`
- `reports/phase97b_developer_productivity_evaluation_design.md`
- `reports/product_validation_first_10_users.md`

## 0. Executive Verdict

`repository_intelligence_roadmap_v1.md` contains a valuable strategic instinct:

> Stop building dormant infrastructure and force the system to create visible
> developer value.

That instinct is correct.

The roadmap is not safe to execute as written because its current-state audit
is stale and several recommendations overreach the evidence.

The most important corrections are:

1. Real-repository review did not stop before labeling. Phase 95E completed
   human review of `202` grounded candidates.
2. The result was not a precision success. It was `0` confirmed actionable
   defects, `148` useful review leads (`73.3%`), `15` misleading findings
   (`7.4%`), `34` benign or not useful, and `5` unclear.
3. Verification Evidence is not simply waiting to be switched on. Phase 97A
   already attaches overlays while promotion remains off.
4. Phase 97C measured the consequence: verification evidence helped orient
   reviewers in `20/20` sampled cases and improved confirmation clarity, but it
   also exposed `16/20` leads as refuted and `4/20` as blocked. Estimated review
   time increased from `37.71` to `48.34` minutes.
5. The immediate product opportunity is not broad promotion. It is consuming
   built intelligence in a concise developer workflow and validating whether
   that saves external developers time.

The revised strategic posture should be:

```text
consume built capabilities
  -> hide or collapse refuted noise
  -> validate developer time saved
  -> measure historical-defect recall
  -> consider narrow promotion only when evidence earns it
```

Not:

```text
flip promotion flags
  -> call richer static output confirmed bugs
```

---

## 1. Roadmap Claims That Need Correction

### 1.1 Real-repository precision is not unmeasured

Roadmap v1 says:

```text
Real-repo precision is UNMEASURED.
The review stopped before a single label.
```

That is outdated.

Phase 95E completed two-reviewer adjudication:

| Outcome | Count | Share |
| --- | ---: | ---: |
| Confirmed actionable defects | `0` | `0%` |
| Useful review leads | `148` | `73.3%` |
| Misleading findings | `15` | `7.4%` |
| Benign or not useful | `34` | `16.8%` |
| Unclear | `5` | `2.5%` |

The evidence is limited to two pilot repositories and cannot establish broad
real-world precision. But it is still real evidence.

The correct statement is:

> Real-repository review has been measured on a small pilot. It supports a
> review-intelligence product claim, not a confirmed-defect product claim.

### 1.2 Contract and verification facts are not simply thrown away

Roadmap v1 says the richest facts are dormant and thrown away at finding time.

That is only partly true.

| Capability | Actual current consumption |
| --- | --- |
| Phase 96A contract facts | Consumed by Phase 96C review enrichment |
| Phase 96C contract enrichment | Attached to `inconsistent_return` review packets |
| Phase 97A verification evidence | Attached as review-only overlays |
| Phase 93 caller behavior | Used by Phase 93B promotion gate and review evidence |
| Phase 94 dependency graph | Consumed by Impact Analysis and RU-3 questions |
| Phase 94B Impact Analysis | Available as a standalone developer workflow |

The problem is no longer:

```text
facts exist but nobody consumes them
```

The problem is:

```text
facts exist, but the developer-facing workflow has not yet proven that the
extra detail saves time
```

### 1.3 Verification Evidence is enabled for review, not confirmation

Roadmap v1 treats the evidence-first surface as a future flag flip.

Phase 97A already ships:

```text
VERIFICATION_EVIDENCE_ENABLED = True
EVIDENCE_PROMOTION_ENABLED = False
```

That distinction is correct.

The overlay can produce:

- `enriched_lead`
- `blocked`
- `refuted`
- `unknown`

It does not emit:

- `promotion_candidate`
- `confirmed_bug`
- `confirmed_defect`
- `confirmed_actionable`

The next decision is not whether to enable evidence. It is how to present its
most useful parts without making review slower.

### 1.4 Impact Analysis should not be demoted to enrichment only

Roadmap v1 says Impact Analysis should be demoted to finding enrichment.

That is too narrow.

Impact Analysis answers a different developer question:

```text
If I change this, what may be affected?
```

This is valuable even when no defect exists. It is one of the clearest
standalone workflows for external testing because it helps with:

- refactor planning;
- pull-request review;
- regression-test selection;
- onboarding;
- unfamiliar-code navigation.

Impact context can enrich a finding, but it should remain a standalone product
surface.

---

## 2. Strongest Recommendations

### 2.1 Freeze repository-understanding expansion after RU-3

**Verdict:** Strong. Keep.

RU-3, the subsystem map, Dependency Graph, and Impact Analysis already provide
enough structural intelligence to test real developer value.

Additional RU-4-style taxonomy expansion risks producing more answer types
without proving that developers work faster.

Consume RU-3 now. Do not extend it until external sessions show a repeated
missing question.

### 2.2 Stop building dormant fact infrastructure

**Verdict:** Strong. Keep, with revised wording.

The roadmap is right to reject an endless series of infrastructure-only phases.
Every new fact layer must answer:

```text
Which existing user workflow gets faster, clearer, or more trustworthy?
```

If the answer is unclear, do not build it.

The revised rule:

> No new repository-intelligence fact family until the existing graph, impact,
> contract, and verification surfaces are consumed in external developer
> sessions.

### 2.3 Keep benchmark recall chasing out of the product loop

**Verdict:** Strong. Keep.

QuixBugs and holdout remain useful regression guards:

| Corpus | TP | FP | Recall |
| --- | ---: | ---: | ---: |
| QuixBugs | `12` | `0` | `0.30` |
| Holdout | `2` | `0` | `0.1667` |

They do not prove real-repository usefulness.

Do not optimize roadmap priority around synthetic benchmark recall. Use
benchmarks to prevent regressions while product validation happens elsewhere.

### 2.4 Separate signal from advisory noise

**Verdict:** Strong, but strengthen it.

The roadmap proposes signal-by-default output. Phase 97C makes this more urgent:

| Phase 97C verification status | Count |
| --- | ---: |
| Refuted | `16 / 20` |
| Blocked | `4 / 20` |
| Helped reviewer orientation | `20 / 20` |

The product surface should not ask developers to read every static lead in
detail.

The strongest consumption pattern is:

```text
show the highest-value lead
collapse refuted noise
show blocked proof obligations concisely
expand full evidence on demand
```

### 2.5 Block new detector growth until external validation

**Verdict:** Strong. Keep.

The current product question is not whether Builder Core can emit more
findings. It is whether developers save time using the findings and structural
answers already available.

New detectors increase triage load and confound product validation.

### 2.6 Preserve LLMs as optional workflow companions, not truth generators

**Verdict:** Strong. Keep.

Roadmap v1 is correct to reject LLM-generated "what is broken" claims.

The best near-term use of Claude/Cursor is external comparison and optional
synthesis around deterministic JARVIS evidence. LLM output must not become
proof.

---

## 3. Weakest Recommendations

### 3.1 Broad fact-to-finding promotion as the next recall engine

**Roadmap recommendation:** Promote dormant contract, verification, and
cross-file facts into findings after a precision review.

**Verdict:** Weak and unsafe as a program-level recommendation.

Why:

1. Phase 95E found `0` confirmed actionable defects in `202` reviewed grounded
   findings.
2. Phase 97C found that verification evidence refuted `16/20` sampled
   `inconsistent_return` leads and blocked the remaining `4/20`.
3. Verification detail increased estimated review time.
4. Richer facts are currently more valuable as **filters, blockers, and
   explanations** than as promotion inputs.

Promotion may still be valid for a narrowly defined evidence bundle later. It
must be earned by historical positive cases and 0-FP validation.

Cancel the blanket idea:

```text
facts exist -> promote them
```

Preserve the narrower idea:

```text
historical defect + complete evidence bundle + zero rejected candidates
  -> consider one scoped promotion gate
```

### 3.2 Flip the evidence-first surface on broadly

**Roadmap recommendation:** Turn on evidence-first findings as a low-effort
presentation win.

**Verdict:** Stale and incomplete.

The evidence overlay is already enabled. Phase 97C shows that full evidence
packets add value but also reading burden:

| Metric | Contract-only | Verification-enriched |
| --- | ---: | ---: |
| Confirmation clarity | `3.0` | `4.0` |
| Estimated review minutes | `37.71` | `48.34` |
| Helpful orientation | - | `20 / 20` |

The correct product question is:

> Which evidence should be visible first, collapsed, or expanded on demand?

Do not mistake more visible text for a better developer experience.

### 3.3 Treat historical-bug recall as nice-to-have

**Roadmap recommendation:** Historical-bug recall strengthens the claim but is
not on the critical path.

**Verdict:** Too weak.

The target claim is:

> JARVIS tells developers what is broken.

That requires evidence that JARVIS can recognize real defects, not only avoid
false claims.

A system that emits nothing can achieve excellent precision.

Historical buggy/fixed cases are not optional before making the target claim.
They are required to measure:

- candidate recall;
- evidence quality on real defects;
- buggy-to-fixed directionality;
- whether verification evidence can ever support promotion.

### 3.4 Make the target claim immediately after precision holds

**Roadmap recommendation:** The claim becomes honest after measured precision
holds on evidence-carrying default findings.

**Verdict:** Too early.

Minimum additional requirements:

- historical buggy/fixed cases;
- measured non-zero accepted defect candidates;
- fixed revision removes or refutes the candidate;
- external-developer usefulness signal;
- no severe trust failures.

Precision alone is necessary but insufficient.

### 3.5 Demote Impact Analysis to annotation only

**Roadmap recommendation:** Treat Impact Analysis mainly as finding enrichment.

**Verdict:** Incorrect product framing.

Impact Analysis is currently one of the strongest standalone surfaces. It
supports a practical workflow without requiring confirmed defects:

```text
before changing shared code, understand what may be affected
```

That workflow belongs in external validation now.

### 3.6 Prioritize precision CI before product signal

**Roadmap recommendation:** Add precision CI after a baseline number exists.

**Verdict:** Reasonable eventually, but not a near-term product priority.

Precision regression automation matters once:

- the confirmed-candidate taxonomy exists;
- the historical corpus exists;
- a useful product surface has been validated.

Until then, it protects a metric definition still under construction.

---

## 4. Built Phases To Consume Now

The immediate job is not to build more intelligence. It is to use what already
exists in one coherent developer workflow.

| Built phase | Consume now as | Why now | Do not claim |
| --- | --- | --- | --- |
| RU-3 | First-run repository map and architecture Q&A | Helps developers find where to start reading | Complete semantic architecture understanding |
| Phase 94A Dependency Graph | Grounded dependency context with explicit unresolved edges | Makes structural relationships inspectable | Complete runtime call graph |
| Phase 94B Impact Analysis | Standalone change-planning workflow | Directly answers a recurring developer question | Proof that affected code is broken |
| Phase 94D/94E resolution improvements | Invisible graph-quality substrate | Improves resolved edges safely | Full dynamic resolution |
| Phase 95 review workflow | External validation discipline and review labels | Provides honest product feedback structure | External-alpha readiness |
| Phase 95F taxonomy | User-facing separation of defects, risk leads, security review leads, advisories | Prevents overclaiming | Every grounded lead is a defect |
| Phase 96C Contract Review | Selective finding detail, collapsed by default | Explains obligations and conflicts | Contract proof for every lead |
| Phase 97A Verification Evidence | Refutation-first summary, blockers, expandable evidence | Prevents wasted review effort | Automatic confirmation |
| Phase 97B productivity design | Controlled follow-up study after concierge sessions | Measures time saved versus Claude/Cursor alone | Large-sample causal proof |
| First-10-user validation plan | Immediate external concierge alpha | Fastest route to real product signal | Product-market fit |

### 4.1 Recommended developer-facing flow

Consume the phases as one story:

```text
What is this repository?
  -> RU-3

What depends on the code I may change?
  -> Dependency Graph + Impact Analysis

Which review lead deserves attention?
  -> Phase 95F taxonomy

Why is it a lead?
  -> Contract Review

What supports, blocks, or refutes it?
  -> Verification Evidence

What remains unknown?
  -> explicit unresolved edges and proof obligations
```

### 4.2 Progressive disclosure is mandatory

Phase 97C is the warning.

The evidence overlay improved clarity but increased estimated review time.
Therefore:

- default to a concise status;
- show one or two decisive evidence atoms;
- collapse refuted leads;
- keep blocked leads available but de-emphasized;
- expand full packets only when the developer asks.

The product should consume evidence as a **triage accelerator**, not as a
document dump.

---

## 5. Future Phases To Cancel Entirely

Cancel these lines of work, not merely defer them.

| Future line of work | Verdict | Reason |
| --- | --- | --- |
| RU-4+ repository-question taxonomy expansion | **Cancel** | RU-3 is sufficient for validation. New question categories should arise only from repeated external-user demand, not a phase sequence. |
| Generic dormant fact layers with no named user workflow | **Cancel** | More facts without a consumption path repeat the infrastructure treadmill. |
| Synthetic benchmark recall expansion as a product objective | **Cancel** | QuixBugs and holdout are regression guards, not roadmap drivers. |
| Blanket fact-to-finding promotion program | **Cancel** | Phase 97C shows the same facts are often more useful for refutation. Permit only individually justified evidence-bundle gates later. |
| Broad evidence-packet expansion across every rule | **Cancel** | Full packets already increase reading time. Use selective progressive disclosure. |
| Impact Analysis demotion to finding annotation only | **Cancel** | It discards a strong standalone change-planning workflow. |
| LLM-generated "what is broken" conclusions | **Cancel** | Violates deterministic evidence discipline and creates ungrounded trust risk. |
| Autonomous repair generation before validated confirmation | **Cancel** | A plausible patch against an unconfirmed diagnosis is product theater, not repository intelligence. |
| New detectors before external product validation | **Cancel for the current program** | More findings make the first-ten-user signal harder to interpret and risk more triage burden. Re-open only from measured user need. |

### 5.1 Defer, do not cancel

These capabilities remain potentially valuable but should not run now:

| Capability | Verdict | Re-open when |
| --- | --- | --- |
| Narrow promotion candidate for one rule | Defer | Historical positive cases and 0-FP review show one complete evidence bundle |
| Historical-bug validation corpus | Proceed before any "what is broken" claim | Needed to measure non-zero real defect recognition |
| Precision CI | Defer | Candidate taxonomy and historical corpus stabilize |
| Runtime reproduction artifact ingestion | Defer | Static workflow proves value and opt-in safety boundary is ready |
| Root-cause evidence chain | Defer | At least one real confirmed candidate exists |
| Repair verification closure | Defer | A bounded repair workflow exists downstream of confirmed diagnosis |

---

## 6. What To Do With Each Roadmap Item

| Roadmap item | Review verdict | Revised use |
| --- | --- | --- |
| `M1` measured real-repo precision | Keep, corrected | Consume completed Phase 95E pilot; expand with external sessions and historical cases |
| `M2` signal-by-default output | Keep, strengthen | Collapse refuted noise and show concise blockers |
| `M3` fact-to-finding promotion | Cancel as broad program | Permit only narrow, evidence-bundle-specific candidates after historical validation |
| `M4` evidence-first finding surface | Keep, rewrite | Already enabled; optimize selective presentation and progressive disclosure |
| `M5` measured real recall | Promote to must-have for target claim | Use pinned historical buggy/fixed revisions |
| `M6` precision CI | Defer | Add after candidate taxonomy and corpus stabilize |

---

## 7. Revised Strategic Focus

The strongest near-term product is not:

```text
JARVIS tells developers what is broken.
```

The strongest evidence-backed product is:

```text
JARVIS helps developers understand unfamiliar Python repositories, assess
change impact, and discard weak review leads faster using explicit evidence.
```

That is not a retreat. It is the part of the system that is already built and
closest to external validation.

The next evidence question is:

```text
Do external developers save time using this workflow?
```

The first-ten-user concierge alpha should test exactly that.

Only after the answer is positive should the program invest in proving:

```text
Can a narrow evidence bundle identify real historical defects with zero
rejected promotion candidates?
```

---

## 8. Final Answer

### Strongest recommendations

1. Freeze RU expansion after RU-3.
2. Stop building unused fact layers.
3. Keep benchmark tuning out of the product roadmap.
4. Make signal-by-default output real by collapsing refuted noise.
5. Block new detector growth during external validation.
6. Preserve deterministic evidence as the source of truth.

### Weakest recommendations

1. Broad fact-to-finding promotion as the next recall engine.
2. Treating evidence-first presentation as a simple flag flip.
3. Calling historical real-defect recall optional.
4. Making the "what is broken" claim after precision alone.
5. Demoting Impact Analysis to annotation only.
6. Prioritizing precision CI before product signal.

### Built phases to consume now

Consume RU-3, Dependency Graph, Impact Analysis, Phase 95F taxonomy, Contract
Review, and Verification Evidence in one concise external-developer workflow.

### Future phases to cancel entirely

Cancel RU-4+, generic dormant facts, synthetic recall chasing, blanket
promotion, broad packet expansion, Impact demotion, LLM truth generation,
premature autonomous repair, and new detectors during the current validation
program.

