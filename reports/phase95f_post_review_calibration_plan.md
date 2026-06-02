# Phase 95F — Post-Review Calibration Plan

Date: 2026-05-31

Scope: Analysis and planning only. **No code changes. No detector changes. No benchmark changes.**

Inputs:

- `reports/phase95e_pilot_human_review_results.md`
- Local Phase 95C/95D/95E artifacts under `reports/phase95c_first_run/` (metrics, reviews, decision audits — local, not committed)

Preserved conclusion from Phase 95E: the pilot human review **worked operationally** but did **not** demonstrate external-alpha readiness. Strict precision was **0.0**. Alpha verdict remains **HOLD**.

---

## 1. Executive summary

The frozen Builder Core engine on two public pilot repositories (plugin + skills tooling, 202 grounded findings reviewed) produced:

| Outcome | Adjudicated count | Share |
| --- | ---: | ---: |
| Confirmed defects | **0** | 0% |
| Useful review leads | 148 | 73% |
| Misleading (false positives) | 15 | 7.4% |
| Noise / benign | 34 | 17% |
| Unclear | 5 | 2.5% |

The product today treats all grounded findings (`semantic`, `data_flow`, `value_flow`, `security`) as **verdict-eligible defects** for strict precision. Human review found **zero confirmed-actionable defects** in that set. Strict precision is therefore **0.0 by definition**, not by rounding.

Calibration before another real-repo campaign must:

1. **Split product output** into defect claims vs review leads vs advisory noise.
2. **Fix the dominant FP families** (guard blindness in value-flow null analysis; over-broad taint on local CLI subprocess/open).
3. **Re-gate alpha** on taxonomy-specific metrics, not a single strict-precision number applied to leads.
4. **Complete corpus + historical-bug protocol** before a 24-repo primary run.

---

## 2. Why strict precision was 0.0

### 2.1 Metric definition (unchanged in 95E)

From the Phase 95A harness:

```
strict_precision = confirmed_actionable / reviewed_in_scope
```

Where `reviewed_in_scope` excludes `unreviewed` and `out_of_scope`.

After adjudication:

| Numerator | Denominator | Result |
| --- | --- | --- |
| `confirmed_actionable` = **0** | `reviewed_in_scope` = **202** | **0.0** |

This is **not** TP/(TP+FP). The Phase 95D slot-local “precision estimate” (also 0.0 on Reviewer A/B) used TP/(TP+FP) but had **zero true_positive labels** as well.

### 2.2 Why zero confirmed-actionable labels

Three compounding reasons — all must be stated honestly:

| Reason | Explanation |
| --- | --- |
| **A. Corpus shape** | Pilot repos are public plugin/skill tooling at pinned commits — maintenance scripts, CLI helpers, not a bug-rich primary corpus. Absence of confirmed defects does not prove the engine finds no bugs anywhere; it proves none were confirmed **here**. |
| **B. Engine behavior on this corpus** | 87% of grounded candidates were `null_dereference` (`value_flow`). Most fired as conservative “maybe None” signals. Reviewers treated them as **leads to confirm**, not as proven bugs. |
| **C. Taxonomy mismatch** | Grounded findings are scored as if they were **confirmed defects**. Human reviewers consistently refused that upgrade: 0/202 → `true_positive` / `confirmed_actionable`. |

### 2.3 What strict precision 0.0 does **not** mean

| Misread | Reality |
| --- | --- |
| “The engine is useless” | Review-lead rate was **73%**; usefulness mean **~2.4–2.7** / 4. Reviewers found value in nudging confirmation. |
| “All 202 findings are false” | Only **15 (7.4%)** adjudicated misleading; **34 (17%)** benign/noise; **5 (2.5%)** undecidable. |
| “Benchmarks are broken” | QuixBugs/holdout gates were not re-run or changed in 95E; pilot metrics are **separate** by design. |

### 2.4 Per-rule strict precision (all 0.0)

| Rule | In scope | Confirmed | Strict precision |
| --- | ---: | ---: | ---: |
| `null_dereference` | 176 | 0 | 0.0 |
| `command_injection` | 14 | 0 | 0.0 |
| `path_traversal` | 12 | 0 | 0.0 |

No rule family produced a human-confirmed defect on this pilot.

---

## 3. Finding separation (adjudicated taxonomy)

Mapping Phase 95E harness labels → calibration buckets:

| Calibration bucket | Harness label(s) | Count | Role in product |
| --- | --- | ---: | --- |
| **Confirmed defects** | `confirmed_actionable` | **0** | Ship as “likely bug — verify/fix” |
| **Useful review leads** | `useful_review_lead` | **148** | Ship as “worth human check” |
| **Misleading findings** | `misleading` | **15** | Should not have been grounded at current severity |
| **Noise** | `benign_or_intended` | **34** | Low value; clutters output |
| **Unclear** | `undecidable` | **5** | Insufficient packet/context |

### 3.1 By rule (adjudicated)

| Rule | Confirmed | Leads | Misleading | Noise | Unclear |
| --- | ---: | ---: | ---: | ---: | ---: |
| `null_dereference` | 0 | ~130 | ~11 | ~34 | 0 |
| `command_injection` | 0 | ~11 | ~3 | 0 | 0 |
| `path_traversal` | 0 | ~7 | ~1 | 0 | ~5 |

(Approximate split derived from Reviewer A + adjudication policy; exact per-rule adjudicated counts align with aggregate misleading=15 and benign=34.)

### 3.2 Advisory findings (not in 202 sample)

Phase 95C exported **518 additional `pattern`-kind findings** (e.g. inconsistent_return quarantined, other pattern smells). These were **excluded from grounded review sample** and **not reviewed** in 95E. Calibration must not conflate their behavior with the 202 grounded set.

---

## 4. Top false-positive causes and recommended response

Each recommendation is a **planning stance** for a future phase — **not implemented in 95F**.

### 4.1 Negated guards (`if not x:` before use) — 5 FPs

| Attribute | Detail |
| --- | --- |
| Rule | `null_dereference` |
| Mechanism | Value-flow nullability does not treat `if not var` as `definitely_not_none` on the false branch’s fall-through or subsequent uses |
| Example pattern | `if not provided: return` then later use of `provided` on paths where analysis lost narrowing |

**Recommendation:** **detector fix** (value-flow narrowing in `valueflow.py` / fact layer).  
**Not:** suppress — guards are common and high-signal when modeled correctly.  
**Also:** **require stronger evidence** until fixed — do not emit high-confidence null-deref when a negated guard appears in the same function window.

---

### 4.2 Explicit None guards (`if x is None: return/continue`) — 4+ FPs

| Attribute | Detail |
| --- | --- |
| Rule | `null_dereference` |
| Mechanism | Intraprocedural analysis misses `is None` / short-circuit `x is None or …` already visible in source window |
| Reviewer note | “flow analysis missed it” |

**Recommendation:** **detector fix** (extend branch narrowing in value-flow; align with Phase 92B return-summary investment).  
**Secondary:** **reword as advisory** for remaining maybe-None cases — title/explanation should say “may be None on some paths” not “null dereference”.  
**Not:** downgrade severity alone without fixing guard recognition — severity downgrade would hide fixable analysis gaps.

---

### 4.3 HTTP status guards (`if response.status_code == 200`) — 2 FPs

| Attribute | Detail |
| --- | --- |
| Rule | `null_dereference` |
| Mechanism | Taint/null lattice does not infer “response body safe to use” after status check |
| Context | `requests.get` + conditional use |

**Recommendation:** **detector fix** (small domain rule: after `status_code == 200` guard, do not flag dereference of response on guarded path).  
**Alternative if fix deferred:** **reword as advisory** + **downgrade severity** to low for HTTP response use without proven None path.  
**Not:** suppress entirely — unguarded response use can still be a lead.

---

### 4.4 Constant argv lists (git/ffmpeg/python script wrappers) — 3+ FPs

| Attribute | Detail |
| --- | --- |
| Rule | `command_injection` |
| Mechanism | Parameter taint + subprocess sink fires even when argv is literal list, no `shell=True`, no string concatenation into shell |
| Examples | `subprocess.run(["git", "-C", …])`, `[sys.executable, script_path]`, ffmpeg literal cmd |

**Recommendation:** **detector fix** (security/value-flow: require tainted **string** reaching shell or unsanitized string argv; exempt list-literal argv with no shell).  
**Until fixed:** **reword as advisory** (“review subprocess call”) not “command injection”; **downgrade severity** medium/high → low for list-form argv.  
**Not:** suppress all subprocess findings — wrapper functions accepting `cmd: list[str]` remain **Security Review Leads** (11 Reviewer-A advisories).

---

### 4.5 Additional FP families (smaller counts)

| Cause | Count | Recommendation |
| --- | ---: | --- |
| Truthiness guard on `best` / `raw` before subscript | 2 | **detector fix** (narrowing) |
| None path rejected before `open()` | 1 | **detector fix** (Optional path pattern) |
| Internal template path, not user traversal | 1 | **detector fix** or **require stronger evidence** (path must be tainted from external input) |
| Path provenance unclear in window | 5 unclear | **reword as advisory**; **require stronger evidence** (interprocedural path source) |

---

### 4.6 Summary decision matrix

| Issue family | Primary action | Secondary | Do not |
| --- | --- | --- | --- |
| Negated guards | detector fix | stronger evidence gate | suppress |
| Explicit None guards | detector fix | reword as advisory | severity-only patch |
| HTTP status guards | detector fix | downgrade + advisory | benchmark tweak |
| Constant argv lists | detector fix | reword + downgrade | suppress all subprocess |
| CLI user-chosen paths | reword as advisory | Security Review Lead tier | claim confirmed bug |
| `.get()` maybe-None | reword as advisory | Risk Lead tier | raise severity |

---

## 5. Proposed product taxonomy

Replace the implicit “all grounded = defect” model with four **user-visible tiers**:

| Tier | Meaning | Typical source today | Default severity |
| --- | --- | --- | --- |
| **Confirmed Bug** | Static analysis + human review agree: likely defect on inspected path | Future: promoted after review or high-confidence structural rules (BFS unguarded consumption on benchmark-validated paths) | high |
| **Risk Lead** | Plausible logic/null/flow issue worth confirming in IDE/tests | `null_dereference`, some `data_flow` | medium |
| **Security Review Lead** | Taint reaches sensitive sink; exploitability not proven | `command_injection`, `path_traversal`, other `security` | medium (high only with tainted string + shell) |
| **Style/Robustness Advisory** | Pattern smells, quarantined rules, maintainability | `pattern` kind (518 in pilot export) | low |

### 5.1 Mapping from current engine kinds

| Current kind | Current treatment | Proposed default tier |
| --- | --- | --- |
| `semantic` | Grounded defect | Confirmed Bug **only after** benchmark + spot-check; else Risk Lead |
| `data_flow` | Grounded defect | Confirmed Bug for promoted rules (e.g. unguarded_container); else Risk Lead |
| `value_flow` | Grounded defect | **Risk Lead** (null_dereference) until guard FP rate < gate |
| `security` | Grounded defect | **Security Review Lead** until injection/traversal evidence rules tightened |
| `pattern` | Advisory (already separate in inventory) | Style/Robustness Advisory |

### 5.2 CLI / report presentation (future)

| Section | Contents |
| --- | --- |
| **Defects** | Confirmed Bug only |
| **Review queue** | Risk Lead + Security Review Lead |
| **Advisories** | Style/Robustness (collapsed by default) |

Strict precision applies to **Confirmed Bug** tier only — not to leads.

---

## 6. Alpha readiness gates by taxonomy

Verdict remains **PASS / HOLD / FAIL**. Pilot result: **HOLD**.

### 6.1 Operational gates (unchanged — must pass)

| Gate | Pilot | Required |
| --- | --- | --- |
| unsafe_outcomes | pass | 0 unsafe |
| crash_free_completion | pass | ≥ 95% |
| review_completion | pass | 0 unreviewed in sample |
| adjudication_completion | pass | 0 pending |

### 6.2 Corpus gates (failed on pilot — must pass before alpha claim)

| Gate | Pilot | Required |
| --- | --- | --- |
| primary_repository_count | 0/24 | ≥ 24 primary, preregistered |
| historical_bug_cases | 0 | ≥ 20 cases, ≥ 10 repos |
| repository_usefulness | not scored | median ≥ 3.0 on primary |
| would_use_again | not scored | ≥ 70% |

### 6.3 Taxonomy-specific quality gates (proposed)

| Tier | Metric | Pilot | Proposed gate |
| --- | --- | --- | --- |
| **Confirmed Bug** | strict_precision | **0.0** | ≥ **0.90** on reviewed sample |
| **Confirmed Bug** | misleading_rate (bugs wrongly promoted) | N/A (0 bugs) | ≤ **0.05** among Confirmed Bug tier |
| **Risk Lead** | lead_usefulness_mean | ~2.4–2.7 | ≥ **2.5** |
| **Risk Lead** | misleading_rate (should have been lead not bug) | 7.4% of all grounded | ≤ **0.10** of Risk Lead tier after reclassification |
| **Security Review Lead** | lead_usefulness_mean | similar | ≥ **2.5** |
| **Security Review Lead** | confirmed_injection_rate after review | 0% | track separately; do not require ≥90% precision on leads |
| **Style/Robustness Advisory** | separate from defect precision | 518 unreviewed | optional spot-check; never mixed into strict precision |

### 6.4 Composite alpha verdict (proposed)

| Verdict | Condition |
| --- | --- |
| **PASS** | All operational + corpus gates pass **and** Confirmed Bug strict_precision ≥ 0.90 **and** misleading_rate ≤ 0.05 **and** lead usefulness ≥ 2.5 |
| **HOLD** | Protocol complete but quality or corpus incomplete (pilot state) |
| **FAIL** | unsafe scan, or misleading_rate > 0.15 on promoted Confirmed Bug tier, or crash-free < 95% |

**Pilot honestly maps to HOLD** — not FAIL (operations succeeded) and not PASS (quality + corpus).

---

## 7. What must happen before another 24-repo run

Do **not** launch primary corpus until the following are complete:

### 7.1 Calibration implementation phase (post-95F, separate approval)

| # | Work item | Rationale |
| ---: | --- | --- |
| 1 | Guard-aware null narrowing (negated, `is None`, truthiness, HTTP 200) | Cuts ~60%+ of pilot FPs |
| 2 | Subprocess/list-argv evidence rule | Cuts security FP on CLI tooling |
| 3 | Product taxonomy in finding schema + CLI sections | Stops scoring leads as defects |
| 4 | Re-measure on **same pilot artifacts** (replay review or diff scan) | Prove FP reduction without hiding regressions |
| 5 | QuixBugs + holdout regression unchanged | No benchmark drift |

### 7.2 Corpus protocol (Phase 95B requirements)

| # | Work item |
| ---: | --- |
| 6 | Preregister 24 primary repos (license, pin, size band, language profile) |
| 7 | Register 20–30 historical bug cases across ≥ 10 repos |
| 8 | Normalize manifest + sampling seed before scan |
| 9 | Pre-commit: output dir outside all target repos |

### 7.3 Review protocol

| # | Work item |
| ---: | --- |
| 10 | Blinded dual review + adjudication (95D tooling) |
| 11 | Repository usefulness + would_use_again scoring |
| 12 | Negative-file sample review (from 95C harness) |
| 13 | Historical-bug worksheet: did engine surface known fixed bug? |

### 7.4 Success criteria for **pilot re-validation** (before 24-repo)

Re-run frozen pilot (same two repos, same commits):

| Metric | Current | Re-validation target |
| --- | --- | --- |
| Misleading rate (grounded) | 7.4% | **≤ 5%** |
| Review-lead rate | 73% | ≥ 60% (maintain usefulness) |
| Confirmed Bug count | 0 | **not required to be >0** on pilot; but taxonomy must be honest |
| Reviewer disagreement rate | 41/202 | ≤ 25% after taxonomy clarity |

Only after pilot re-validation passes should the 24-repo primary scan begin.

---

## 8. What should NOT be changed yet

Explicit freeze list to prevent reactive damage:

| Do not change | Why |
| --- | --- |
| **QuixBugs / holdout benchmarks** | Separate regression gates; pilot FPs must not be “fixed” by loosening benchmark verdict kinds |
| **Promotion flags** (`INTERPROC_PROMOTION_ENABLED`, etc.) | Change only in a dedicated phase with paired tests |
| **Phase 79 router safety code** | Unrelated |
| **Scoring rules in 95A harness mid-campaign** | Would invalidate cross-run comparison; update only with schema version bump + documented migration |
| **Review labels from 95E to inflate precision** | Do not relabel leads as confirmed bugs to pass gates |
| **Sampling seed or review sample retroactively** | Hides strata; preregister before scan |
| **24-repo corpus before calibration** | Would multiply uncalibrated noise and waste reviewer time |
| **Suppress all null_dereference or all security** | Hides real signal; pilot showed leads have value |
| **Voice / browser / trading / website / brain/router** | Out of scope |

---

## 9. Recommended phase sequence (after 95F)

| Phase | Focus | Exit criterion |
| --- | --- | --- |
| **96A** | Value-flow guard narrowing + FP fixtures from pilot FPs | Pilot misleading rate ≤ 5% on replay |
| **96B** | Security argv evidence + Security Review Lead tier | Constant-argv FPs eliminated in pilot replay |
| **96C** | Finding taxonomy + CLI/report sections | Confirmed Bug vs Lead visible; harness schema v2 |
| **96D** | Pilot re-scan + human review (subset or full 202) | HOLD → eligible for primary |
| **97** | 24-repo preregistered run + full review | PASS/HOLD/FAIL on composite gates |

---

## 10. Honest limitations of the pilot review

These must remain visible in all downstream reports:

1. **Two pilot repos only** — plugin/skill tooling, not representative primary corpus.
2. **Zero historical bug cases** — recall on known real bugs untested.
3. **Reviewer disagreement 20%** — taxonomy ambiguity between useful_advisory and not_useful on null warnings.
4. **Grounded sample skewed** — 87% null_dereference; security conclusions based on 26 findings.
5. **No confirmed defects** — does not prove the engine never finds bugs; proves current **defect claim level** is miscalibrated for this corpus.

Phase 95E conclusion stands: **operational success, substantive HOLD**.

---

## 11. Deliverable checklist

| Required item | Section |
| --- | --- |
| Why strict precision was 0.0 | §2 |
| Confirmed / leads / misleading / noise split | §3 |
| Top FP causes (negated, None, HTTP, argv) | §4 |
| Per-issue recommendation (fix / downgrade / advisory / suppress / evidence) | §4, §4.6 |
| New product taxonomy (4 tiers) | §5 |
| Alpha gates per taxonomy | §6 |
| Before 24-repo run | §7 |
| What not to change | §8 |

---

## 12. Acceptance

| Criterion | Met |
| --- | --- |
| Analysis only, no code | yes |
| No detector changes | yes |
| No benchmark changes | yes |
| Bad results not hidden | yes (0.0 precision, 7.4% misleading, 0 confirmed) |
| 95E conclusion preserved | yes (HOLD; leads useful; not alpha-ready) |

No engine, detector, or benchmark files were modified in Phase 95F.
