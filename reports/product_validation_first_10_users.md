# Product Validation Plan - First 10 External Developers

Date: 2026-05-31

Status: Design only. No code. No implementation. No tuning.

## 0. Executive Answer

The fastest honest path to external product signal is a **concierge private
alpha** with `10` developers in two waves of `5`.

Do not begin with a self-serve launch. Sit with each developer for one focused
session, run JARVIS locally against a pinned public repository, then offer a
second pass on one of their own eligible Python repositories.

The product promise for this alpha is:

> JARVIS helps you understand an unfamiliar Python repository, assess the
> likely impact of a change, and review evidence-backed risk leads without
> pretending uncertainty is proof.

The promise is deliberately narrower than:

> JARVIS finds and fixes your bugs automatically.

Current evidence supports the first statement:

- RU-3 answers architecture questions from repository structure;
- the Dependency Graph exposes resolved and unresolved relationships;
- Impact Analysis separates asserted, possible, and unanalyzed impact;
- Contract Review makes return-contract uncertainty visible;
- Verification Evidence explains support, blockers, and refutations;
- Phase 95 produced useful review leads on real repositories;
- Phase 97C showed that verification evidence improved confirmation clarity and
  helped orient `20/20` sampled reviews.

Current evidence does not support automatic defect-confirmation or repair
claims.

---

## 1. Validation Objective

The first-ten-user program answers four questions:

1. Do developers understand what JARVIS is for within one session?
2. Does JARVIS reduce time spent wandering through an unfamiliar repository?
3. Do developers trust its evidence boundaries, especially when it says
   `unknown`, `blocked`, or `refuted`?
4. After using it, do developers ask to use it again on real work?

The alpha is not a marketing launch and not a benchmark campaign. It is a fast
test of whether the current product shape creates repeatable developer value.

---

## 2. Honest Product Positioning

### 2.1 External-safe one-line pitch

> Local, read-only repository intelligence for Python: understand structure,
> assess change impact, and investigate review leads with explicit evidence.

### 2.2 What users may reasonably expect

JARVIS can help answer:

- What are the important subsystems?
- Where should I start reading?
- What depends on this file or function?
- Which impact is resolved, and which impact remains uncertain?
- Why was this finding raised?
- What evidence supports it?
- What blocks confirmation?
- Is this finding worth investigating now?

### 2.3 What users must not be promised

Do not say:

- JARVIS finds bugs automatically.
- JARVIS proves that every finding is a defect.
- JARVIS replaces code review.
- JARVIS fixes code.
- JARVIS has zero false positives.
- JARVIS is a production security scanner.

The product should be introduced as a **review-intelligence assistant**, not an
autonomous bug finder.

---

## 3. Target User

### 3.1 Primary target

Recruit Python developers who regularly need to understand code they did not
write.

Best-fit profile:

| Attribute | Target |
| --- | --- |
| Role | Backend engineer, platform engineer, senior generalist, maintainer, or technical lead |
| Experience | At least `2` years of professional software development |
| Language | Comfortable reading Python |
| Workflow | Reviews pull requests, inherits services, investigates regressions, or evaluates change risk |
| Pain | Spends meaningful time locating entry points, dependencies, and the right files to inspect |
| Repository access | Can use a public Python repository or an approved local repository |

### 3.2 Useful cohort mix

For `10` users:

| Segment | Count |
| --- | ---: |
| Backend or platform engineers | 4 |
| Senior engineers or maintainers | 3 |
| Technical leads or engineering managers who still review code | 2 |
| Developer-tooling or security-minded engineer | 1 |

Aim for:

- at least `5` developers who review unfamiliar code weekly;
- at least `3` developers who can test an eligible work or personal repository;
- at least `2` developers who use Claude, Cursor, or Copilot regularly;
- at least `2` developers who do not rely heavily on coding assistants.

### 3.3 Exclusions

Do not recruit:

- people who already know the evaluation repository deeply;
- people expecting autonomous code generation as the primary experience;
- repositories dominated by generated code;
- repositories that cannot be scanned locally under the user's security rules;
- non-Python-only users for this first pass.

---

## 4. Recruitment Strategy

### 4.1 Fastest channel

Use warm, direct outreach first:

- trusted developer contacts;
- former colleagues;
- maintainers of small Python projects;
- engineers in local developer communities;
- developer-tooling contacts;
- technical founders with active Python codebases.

Recruit for a `45-60` minute private feedback session.

### 4.2 Invite wording

Use a bounded invitation:

```text
I am testing a local, read-only Python repository intelligence tool. It helps
developers understand unfamiliar code, assess the likely impact of changes,
and review evidence-backed risk leads. It does not edit or execute your code.

Would you spend 45-60 minutes testing it on a public sample repository, and
optionally on one of your own local Python repositories?
```

### 4.3 Two-wave structure

| Wave | Users | Purpose |
| --- | ---: | --- |
| Wave 1 | 5 | Validate positioning, onboarding, demo flow, and major trust failures |
| Wave 2 | 5 | Repeat the same frozen core flow after reviewing Wave 1 feedback |

No product tuning should occur between individual sessions. If Wave 1 exposes
a severe onboarding or trust blocker, record it and decide whether Wave 2 can
continue honestly. Do not quietly change the measurement surface mid-wave.

---

## 5. Repositories To Test

Use two repository modes.

### 5.1 Mode A - Standard pinned public repository

Every developer starts with the same pinned public Python repository.

Requirements:

| Criterion | Requirement |
| --- | --- |
| Size | Approximately `10,000-80,000` Python LOC |
| Structure | At least `4` meaningful subsystems |
| Graph | Resolved imports and calls plus some explicit unresolved edges |
| Documentation | A README and enough source context for independent review |
| Findings | At least `3` review leads with different dispositions |
| Safety | Public, local, read-only scan allowed |
| Familiarity | Most participants should not know it deeply |

The standard repository provides comparability across all `10` sessions.

Choose one repository and freeze its commit before recruitment. Do not rotate
repositories during the first wave.

### 5.2 Mode B - User-owned repository

After the standard demo, invite the developer to scan one local repository they
actually care about.

Eligibility:

| Criterion | Requirement |
| --- | --- |
| Language | Python is a meaningful production language in the repository |
| Size | Prefer `5,000-150,000` Python LOC for the first alpha |
| Privacy | Developer confirms local scan is permitted |
| Execution | No target code execution |
| Writes | No target source modification |
| Output handling | Developer controls whether artifacts may be retained |

The own-repository pass provides ecological signal:

```text
Would this save time in real work?
```

### 5.3 Fallback repository

Prepare a second pinned public Python repository for developers who cannot use
their own code.

The fallback should differ from Mode A:

- different architecture;
- different domain;
- different subsystem layout;
- still small enough for a guided session.

### 5.4 Repository safety statement

Before every scan, state:

```text
JARVIS reads repository files locally. It does not modify source files and does
not execute target repository code. Findings are review leads unless evidence
explicitly supports a stronger conclusion.
```

---

## 6. Onboarding Flow

The onboarding goal is first useful answer within `10` minutes.

### 6.1 Before the session

Send:

- a calendar link;
- the bounded product description;
- the local read-only safety statement;
- expected session length;
- optional own-repository eligibility criteria;
- a request to install only the frozen alpha package or use the prepared
  facilitator environment;
- a reminder that no source code needs to leave their machine.

### 6.2 Session opening - 3 minutes

Say:

```text
JARVIS is a repository-intelligence assistant. It is designed to help you find
the right files, understand dependencies, assess change impact, and review
risk leads with evidence. It is intentionally cautious: unknown and refuted
are valid answers.
```

Do not begin with benchmark metrics. Begin with the developer's workflow.

Ask:

1. When do you most often need to understand unfamiliar code?
2. What is usually slow or frustrating?
3. Which coding assistants do you currently use?

### 6.3 First-run flow - 5 minutes

Use the pinned public repository:

1. Point JARVIS at the local repository.
2. Show indexing progress.
3. Show detected project shape and top subsystems.
4. Ask one architecture question.
5. Confirm that the first answer cites real files.

The first useful moment should be:

```text
I can see where this repository is organized and where I should start reading.
```

### 6.4 Guided demo - 10 minutes

Run the five-step demo in Section 7.

### 6.5 Hands-on exploration - 15 minutes

Let the developer choose questions from Section 8. Do not over-direct them.
Observe where they naturally reach for JARVIS, where they fall back to search,
and where output feels too long.

### 6.6 Own-repository or fallback pass - 10-15 minutes

Invite one real question:

```text
What is one file, subsystem, or risky change you would genuinely inspect in
this repository?
```

Use their own repository when permitted. Otherwise use the fallback public
repository.

### 6.7 Feedback - 10 minutes

Complete the structured feedback form in Section 9.

---

## 7. What The Demo Should Show

The demo should tell one coherent story:

```text
understand
  -> locate dependencies
  -> assess change impact
  -> inspect a review lead
  -> see what supports or blocks confirmation
```

### 7.1 Demo moment 1 - Repository map

Ask:

```text
What are the most important subsystems in this repository?
```

Show:

- production subsystems;
- important entry files;
- evidence-backed source paths;
- architecture confidence;
- no benchmark or report-history drift.

Capability shown: RU-3 plus repository understanding.

### 7.2 Demo moment 2 - Dependency graph

Ask:

```text
Which production modules depend most heavily on this subsystem?
```

Show:

- top resolved import relationships;
- central modules;
- graph summary;
- unresolved edges as explicit unknowns.

Capability shown: Dependency Graph.

### 7.3 Demo moment 3 - Impact analysis

Ask:

```text
If we change this file, what is most likely to be affected?
```

Show:

- direct impact;
- transitive impact;
- affected subsystems;
- possible but unverified impact;
- confidence;
- why `no resolved path` does not mean `safe`.

Capability shown: Impact Analysis.

### 7.4 Demo moment 4 - Contract review

Open one `inconsistent_return` review lead.

Show:

- the suspicious return shape;
- explicit return-contract evidence where available;
- strong caller behavior where available;
- conflicting signals;
- `why_not_confirmed`.

Capability shown: Contract Review.

### 7.5 Demo moment 5 - Verification evidence

Show one review lead with verification overlay.

Prefer a case where the overlay says `refuted` or `blocked`.

Explain:

```text
The useful behavior is not always raising severity. Sometimes the right answer
is that a lead should not consume engineering time yet.
```

Show:

- supporting evidence;
- refuting evidence;
- blockers;
- missing proof obligations;
- evidence status;
- no automatic confirmed-defect label.

Capability shown: Verification Evidence.

### 7.6 Demo anti-patterns

Do not:

- scroll through a giant raw findings list;
- lead with QuixBugs benchmark numbers;
- show a review lead as a proven bug;
- hide unresolved edges;
- spend the whole session explaining internal phase numbers;
- demo autonomous patch generation;
- overload the developer with every available command.

---

## 8. Questions Users Should Ask

Give users a one-page question menu. Encourage natural wording.

### 8.1 Understand the repository

- What are the most important subsystems?
- Which folders contain production code?
- Where should I start reading?
- Which modules are architectural bottlenecks?
- Which subsystem has the highest production concentration?
- What are the central entry files?

### 8.2 Understand dependencies

- Which modules import this module?
- Which functions call this function?
- What are the highest incoming dependencies?
- Are there import cycles?
- Which relationships are unresolved?

### 8.3 Assess a change

- If I change this file, what may be affected?
- What is directly affected versus transitively affected?
- Which subsystems might need regression testing?
- How confident is the impact answer?
- What impact remains possible but unverified?

### 8.4 Trace a path

- What is the strongest supported path to this function?
- Which path edges are resolved?
- Where does the trace become unknown?
- Can you prove this code is reachable from an entry point?

### 8.5 Review a finding

- Why was this finding raised?
- What evidence supports it?
- What evidence weakens it?
- Is this a defect candidate, a useful review lead, or a refuted lead?
- What is the smallest next verification step?
- What proof is still missing?

### 8.6 Questions that test honesty

Ask every user to try at least one:

- Are you sure this path is reachable?
- What do you not know about this impact analysis?
- Why is this not a confirmed defect?
- What evidence would change your answer?
- Which finding should I ignore first?

These questions test whether caution feels useful rather than evasive.

---

## 9. Feedback Form

Use the same feedback form for all `10` users.

### 9.1 Participant profile

| Question | Response type |
| --- | --- |
| Role | Short text |
| Years of professional development | Number |
| Python familiarity | `1-5` |
| How often do you inspect unfamiliar repositories? | Never / monthly / weekly / daily |
| Which coding assistants do you currently use? | Multi-select + text |
| Did you test an own repository? | Yes / no |

### 9.2 Activation and onboarding

| Question | Response type |
| --- | --- |
| Was the read-only safety model clear? | `1-5` |
| How easy was it to get the first useful answer? | `1-5` |
| Time to first useful answer | Minutes |
| Where did onboarding feel confusing? | Free text |
| What would have blocked you from trying this alone? | Free text |

### 9.3 Capability value

Rate each `1-5`:

| Capability | Question |
| --- | --- |
| Repository understanding | Did the subsystem map help you find where to start? |
| Dependency Graph | Did dependency context reduce manual searching? |
| Impact Analysis | Did the impact report improve change planning? |
| Contract Review | Did contract evidence help interpret a finding? |
| Verification Evidence | Did blockers or refutations prevent wasted investigation? |
| Unknown handling | Did uncertainty labels increase trust? |

### 9.4 Output quality

Rate each `1-5`:

- Answers were grounded in real files.
- The amount of detail was appropriate.
- It was clear what was known versus unknown.
- It was clear which findings deserved attention.
- Review packets were easy to scan.
- The tool helped me decide what to inspect next.
- The tool avoided overstating certainty.

### 9.5 Workflow fit

| Question | Response type |
| --- | --- |
| Which workflow would you use this for first? | PR review / onboarding / refactor planning / regression investigation / architecture exploration / other |
| Would you use this before opening files manually? | Yes / maybe / no |
| Would you use this alongside Claude, Cursor, or Copilot? | Yes / maybe / no |
| Would you use it at least weekly? | Yes / maybe / no |
| Would you use it again on a real repository? | Yes / maybe / no |
| Would you ask for access after this session? | Yes / maybe / no |
| Would you recommend it to a teammate? | `0-10` |

### 9.6 Open questions

Ask:

1. What saved you the most time?
2. What felt slow, verbose, or distracting?
3. Which answer did you trust most, and why?
4. Which answer did you trust least, and why?
5. What did you still have to do manually?
6. Was any `unknown`, `blocked`, or `refuted` answer especially useful?
7. What would make you use JARVIS next week?
8. What would stop you from using it?

### 9.7 Facilitator observation sheet

Record:

- time to first useful answer;
- indexing completion time;
- number of questions asked;
- first question asked without prompting;
- files manually opened;
- repeated clarification requests;
- moments of visible confusion;
- output sections skipped;
- whether developer independently asks to try their repository;
- whether developer independently asks to keep using the tool.

---

## 10. Success Metrics

### 10.1 Activation metrics

| Metric | Target for first `10` |
| --- | ---: |
| Sessions completed | `10 / 10` |
| First useful answer within `10` minutes | At least `8 / 10` |
| Read-only safety model understood | Median at least `4 / 5` |
| Developers able to ask an unprompted question after demo | At least `8 / 10` |

### 10.2 Usefulness metrics

| Metric | Target |
| --- | ---: |
| Overall usefulness | Median at least `4 / 5` |
| Repository-understanding usefulness | Median at least `4 / 5` |
| Impact-analysis usefulness | Median at least `4 / 5` |
| Clear known-versus-unknown boundary | Median at least `4 / 5` |
| Tool helped choose next file or next verification step | At least `7 / 10` |
| Verification blockers/refutations prevented wasted work | At least `5 / 10` |

### 10.3 Workflow-intent metrics

| Metric | Target |
| --- | ---: |
| Would use again on a real repository: yes | At least `7 / 10` |
| Would use weekly: yes or maybe | At least `7 / 10` |
| Would use alongside Claude/Cursor/Copilot: yes or maybe | At least `7 / 10` |
| Requests continued access without prompting | At least `4 / 10` |
| Independently asks to try own repository | At least `5 / 10` |
| Recommends to teammate (`NPS` promoter score `9-10`) | At least `3 / 10` |

### 10.4 Trust metrics

| Metric | Target |
| --- | ---: |
| Evidence-grounded answers | Median at least `4 / 5` |
| Avoided overstating certainty | Median at least `4 / 5` |
| Severe trust violations | `0` |
| Finding presented as confirmed without proof | `0` |
| Fabricated path accepted as real | `0` |
| Local source modification | `0` |

### 10.5 Qualitative success

Listen for unprompted statements like:

- This saved me from opening ten files.
- I would use this before a refactor.
- This is useful when reviewing a repository I do not know.
- The unresolved edge warning is helpful.
- The refuted finding saved me time.
- Can I run this on my project?

Record the exact wording with participant consent.

---

## 11. Product-Market Signal

The first `10` users cannot establish product-market fit. They can produce an
early **product-market signal**.

### 11.1 Strong signal

Treat the first-ten-user pass as a strong signal when all are true:

| Signal | Threshold |
| --- | ---: |
| Would use again on a real repository | At least `7 / 10` yes |
| Independently asks to test own repository | At least `5 / 10` |
| Requests continued access without prompting | At least `4 / 10` |
| Names a concrete recurring workflow | At least `7 / 10` |
| Overall usefulness | Median at least `4 / 5` |
| Impact or repository-understanding value | Median at least `4 / 5` |
| Trust boundary clarity | Median at least `4 / 5` |
| Severe trust violations | `0` |

A concrete recurring workflow means a developer says something specific:

- before reviewing a large PR;
- before changing a shared module;
- while onboarding to a service;
- while planning a refactor;
- while investigating a regression;
- while triaging static-analysis noise.

### 11.2 Exceptional signal

Treat these as especially meaningful:

- a developer asks to keep the tool installed;
- a developer asks to run it on a second repository;
- a developer invites a teammate to a follow-up;
- a developer uses a refutation to stop investigating a noisy finding;
- a developer uses impact analysis to narrow regression testing;
- a developer asks for a weekly or PR-review workflow.

### 11.3 Weak signal

Return `HOLD` when:

- developers like the demo but do not ask to use it again;
- value appears limited to one impressive architecture answer;
- users praise the concept but cannot name a recurring workflow;
- outputs feel too verbose to use during real work;
- own-repository scans do not create useful follow-up questions;
- trust is high but time-saving value is unclear.

### 11.4 Negative signal

Return `FAIL` for the current product shape when:

- fewer than `4 / 10` want to use it again;
- fewer than `3 / 10` can name a recurring workflow;
- developers consistently prefer ordinary repository search;
- impact answers create false confidence;
- review packets waste more time than they save;
- `unknown`, `blocked`, or `refuted` states feel confusing rather than useful;
- any source-modification or trust-boundary violation occurs.

---

## 12. Session-Level PASS, HOLD, And FAIL

### 12.1 PASS

The first-ten-user program passes when:

- activation targets pass;
- usefulness targets pass;
- workflow-intent targets pass;
- trust targets pass;
- at least one recurring workflow emerges clearly;
- no severe trust violation occurs.

### 12.2 HOLD

Return `HOLD` when:

- users understand the product but repeat-use intent is mixed;
- the product is useful only with heavy facilitator guidance;
- repository understanding works but finding review feels too verbose;
- own-repository value is promising but inconsistent;
- the sample is too homogeneous to interpret confidently.

### 12.3 FAIL

Return `FAIL` when:

- developers cannot reach value within one session;
- the product promise is not understood;
- the tool routinely adds reading burden;
- users do not trust known-versus-unknown boundaries;
- repeated-use intent is weak;
- a trust or safety boundary is violated.

---

## 13. Fast Execution Checklist

Before recruiting:

1. Select and pin the standard public repository.
2. Select and pin the fallback public repository.
3. Prepare one clean local scan for each.
4. Prepare the five-step demo.
5. Prepare the one-page question menu.
6. Prepare the feedback form.
7. Prepare the facilitator observation sheet.
8. Confirm the local read-only safety statement.
9. Freeze the product surface for Wave 1.
10. Recruit the first `5` developers.

After Wave 1:

1. Summarize activation, usefulness, trust, and repeat-intent metrics.
2. List severe blockers separately.
3. Decide whether Wave 2 can continue on the same frozen product surface.
4. Recruit and run the next `5`.
5. Produce one aggregate report with raw counts and honest limitations.

---

## 14. Final Recommendation

Run a **concierge private alpha** first.

Use the demo to show:

```text
repository map
  -> dependency graph
  -> impact analysis
  -> contract review
  -> verification evidence and refutation
```

Then step back and let developers ask real questions.

The highest-value signal is not:

```text
That demo looked impressive.
```

It is:

```text
Can I use this on my repository next week?
```

