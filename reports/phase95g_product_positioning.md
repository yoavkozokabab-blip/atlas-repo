# Phase 95G — Product Positioning Analysis

Date: 2026-05-31

Scope: Evidence-based positioning only. **No code. No tuning. No roadmap changes.**

Inputs:

- `reports/phase95e_pilot_human_review_results.md`
- `reports/phase95f_post_review_calibration_plan.md`
- Phase 95C verification (QuixBugs + holdout, frozen candidate)
- Phase 88 architecture review (benchmark interpretation)

---

## 0. Executive answer

**What Builder Core is today (best fit):** **B + C** — a **Review Intelligence System** that also behaves as a **Risk Discovery Tool** on real code.

It is **not** honestly a general **Bug Finder** on real repositories yet. It is **not** primarily an **Architecture Analyzer**, though it includes lightweight repo Q&A/indexing from Phase 82.

**E — Something else (precise label):** *Local, deterministic static review assistant* — reads source, emits ranked findings with evidence, never executes target code, expects human confirmation before any defect claim.

---

## 1. Evidence inventory

Three separate evidence layers must never be blended in marketing or docs.

### 1.1 Curated algorithm benchmarks (in-domain + holdout)

Source: Phase 95C verification on frozen candidate (`e3b55a81`), unified engine benchmark path.

| Corpus | Pairs / cases | TP | FP | Precision | Recall | What it measures |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| **QuixBugs** | 40 algorithm pairs | 12 | 0 | **100%** | **30%** | Grounded findings flag buggy vs correct files on known algorithm bugs |
| **Holdout** | 12 out-of-domain pairs | 2 | 0 | **100%** | **16.7%** | Same verdict logic on synthetic holdout corpus |

Interpretation (Phase 88): **precision-saturated, recall-starved**. The engine fires rarely and with high confidence on **paired, known-bug corpora**. Benchmark path deliberately excludes security from verdict kinds for QuixBugs/holdout; security is measured separately.

**What this supports:** Controlled detection of **specific, pre-validated algorithm/logic defect shapes** with **zero FP on correct files** in those corpora.

**What this does not support:** General bug-finding on arbitrary production repos; security posture of real apps; recall claims (“finds most bugs”).

---

### 1.2 Real-repository pilot (Phase 95C → 95E)

Source: Two public pilot repos (plugin + skills tooling), 202 grounded findings blind-reviewed.

| Metric | Value |
| --- | --- |
| Repos scanned | 2 (pilot track, not primary corpus) |
| Grounded findings reviewed | 202 |
| Human-confirmed defects | **0** |
| Useful review leads | **148 (73%)** |
| Misleading (FP) | **15 (7.4%)** |
| Strict precision (defect definition) | **0.0** |
| Usefulness mean | **~2.4–2.7 / 4** |
| Alpha readiness | **HOLD** |
| Target repo writes | **0** |

Finding mix: 87% `null_dereference`, 7% `command_injection`, 6% `path_traversal`.

**What this supports:** The product **helps humans decide what to inspect** on real code; operational safety (read-only); dual-review workflow.

**What this does not support:** Claiming confirmed bugs found; high defect precision; production security scanning; external-alpha readiness.

---

### 1.3 Product capabilities (implementation fact, not validation)

From Builder Core README + unified engine (`engine.py`):

| Capability | Validated on real repos? |
| --- | --- |
| Local CLI scan (`analyze-file`, `bug-scan`, `security-scan`) | Yes (pilot ran) |
| Deterministic pipeline (parse → facts → agents → rank) | Yes |
| Repo index + `ask` + `risk-report` (Phase 82) | Exists; **not** part of 95E review |
| Algorithm semantic profiles | Benchmark-validated only |
| Value-flow / taint security | Pilot leads + 7.4% misleading |
| Never executes analyzed code | Yes (pilot safety gates) |

---

## 2. Question 1 — Which category is Builder Core today?

| Option | Fit | Evidence |
| --- | --- | --- |
| **A. Bug Finder** | **Weak / misleading as primary label** | 0/202 confirmed defects on real repos; strict precision 0.0. Benchmark recall 30% / 16.7% — misses most paired bugs even when precision is 100%. |
| **B. Review Intelligence System** | **Strong — best primary label** | 73% review-lead rate; blinded dual review + adjudication completed; findings packaged with explanation, evidence, source window, verification steps. |
| **C. Risk Discovery Tool** | **Strong — secondary label** | 26 grounded security + 176 null-deref signals on pilot; reviewers valued subprocess/path/null **leads**; not confirmed exploits. |
| **D. Architecture Analyzer** | **Weak** | Index/ask/risk exist but are not the validated core of 95E. No architecture-model evidence (services, boundaries, drift). Phase 80 `project_intelligence` is separate and unvalidated in 95E. |
| **E. Something else** | **Accurate precision label** | *Deterministic local static review assistant* — prioritizes explainable signals over autonomous defect claims. |

### Recommended primary positioning (today)

> **Builder Core is a local Review Intelligence System** that scans Python repositories read-only and produces **ranked, evidence-backed review leads** for logic, nullability, and security — with **human review expected** before treating any output as a confirmed bug.

Secondary: **Risk Discovery Tool** for taint/null **review leads**, not verified vulnerabilities.

---

## 3. Question 2 — Claims supported by evidence

| Claim | Evidence | Strength |
| --- | --- | --- |
| Read-only local analysis; does not execute target code | Pilot: 0 unsafe scans, 0 target writes | **Strong** |
| Deterministic, explainable findings (rule, line, evidence, why-might-be-wrong) | 95C packets + unified `Finding` schema | **Strong** |
| Useful for prioritizing human review on real repos | 73% review-lead rate; usefulness ~2.5/4 | **Strong (pilot, n=2 repos)** |
| High precision on **curated** buggy/correct pairs | QuixBugs 100% FP-free; holdout 100% FP-free | **Strong (bounded corpora)** |
| Detects **some** known algorithm defect shapes | QuixBugs 12/40 recall | **Moderate (low recall)** |
| Security/static **review leads** (injection, path, null) | 202 grounded signals; mixed human value | **Moderate** |
| Separates advisory pattern noise from grounded review set | 518 advisory vs 202 grounded in pilot export | **Strong (product design)** |
| Operational validation workflow (manifest, blind review, gates) | 95A–95E harness | **Strong** |
| Benchmark regression stability while evolving engine | 95C re-verification: QuixBugs/holdout unchanged | **Strong** |

---

## 4. Question 3 — Claims not supported by evidence

| Claim | Why not supported |
| --- | --- |
| “Finds bugs in your codebase” (unqualified) | 0 confirmed defects on 202 real-repo grounded findings |
| “High precision” on real repositories | Strict precision **0.0** on pilot |
| “Production-ready security scanner” | 7.4% misleading; subprocess FPs on constant argv; no exploit validation |
| “Catches most bugs” / high recall | QuixBugs 30%, holdout 16.7%; no historical-bug recall on real repos |
| “Zero false positives” (global) | True only on **benchmark correct files**, not on real-repo review |
| “External alpha ready” | Verdict **HOLD** (0/24 primary repos, 0 historical cases, strict precision gate failed) |
| “AI/autonomous bug fixing” | No auto-fix; no LLM in analysis path; read-only |
| “Architecture analysis platform” | No validated service/layer/dependency architecture model in 95E |
| “Replaces code review” | Human review required; 41/202 reviewer disagreements on pilot |
| QuixBugs metrics imply real-world performance | Different corpora, different verdict population, different human outcome |
| “Validates algorithm correctness broadly” | Profile/name-bound semantic rules on limited pairs; 70% QuixBugs pairs missed |

---

## 5. Question 4 — Honest positioning today

### One-line

**Local deterministic review intelligence for Python — surfaces what to inspect, not what is definitively broken.**

### Short paragraph (external-safe)

Builder Core is a **local, read-only** Python repository analyzer. It runs a deterministic static pipeline (data-flow, value-flow, taint, and algorithm checks) and returns **ranked findings with evidence and verification steps**. On **curated benchmark pairs**, grounded findings achieve **100% precision** with **limited recall** (30% QuixBugs, 16.7% holdout). On an initial **real-repository pilot**, human reviewers rated **73%** of grounded outputs as **useful review leads** and **0%** as confirmed defects without further investigation. Builder Core is **not external-alpha ready** and should be used as a **review aid**, not an autonomous bug finder or production security gate.

### Tiered output language (aligned with 95F, not yet shipped)

| Tier | Honest user-facing phrase |
| --- | --- |
| Benchmark-detected defect shape | “Matched a known defect pattern on paired benchmark” |
| Real-repo grounded output | “Review lead — confirm in context” |
| Advisory / pattern | “Style or robustness note” |

### Audience-specific framing

| Audience | Honest pitch |
| --- | --- |
| Developer | “Tells you where to look and why — you decide if it’s a bug.” |
| Security reviewer | “Flags taint paths worth tracing; not a substitute for pentest or SAST sign-off.” |
| Engineering lead | “Pilot showed review prioritization value; defect precision on real code unproven at scale.” |

---

## 6. Question 5 — Positioning that *might* become valid after 24-repo validation

**Conditional only.** None of the below is true today.

| Future claim | Preconditions (from 95F gates) |
| --- | --- |
| “Validated defect finder on diverse open-source Python” | Primary 24-repo corpus + blind review; **Confirmed Bug strict precision ≥ 0.90**; misleading ≤ 5% |
| “Measured security review lead quality” | Separate security-lead usefulness ≥ 2.5; FP families (argv, guards) calibrated |
| “Recall on known historical fixes” | ≥ 20 historical bug cases across ≥ 10 repos with documented hit/miss |
| “External alpha candidate” | Composite **PASS** (operational + corpus + taxonomy gates) |
| “Enterprise pilot ready for review augmentation” | Repository usefulness median ≥ 3.0; would-use-again ≥ 70% |

If gates pass, primary label could evolve to:

> **Validated Review Intelligence System with measured defect promotion on a preregistered primary corpus**

Still not: “autonomous bug finder,” unless confirmed-defect rate and historical recall justify it in a **new** evidence pass.

If gates **fail** (plausible given pilot 0.0 strict precision), honest label remains **Review Intelligence / Risk Discovery** indefinitely.

---

## 7. Question 6 — Wording that should never be used

### 7.1 Never (today — no evidence)

| Phrase | Reason |
| --- | --- |
| “Finds bugs automatically” | 0 confirmed on real-repo review |
| “Guaranteed zero false positives” | 7.4% misleading on pilot; FPs exist |
| “Production security scanner” | No validation; CLI tooling corpus |
| “Alpha ready” / “production ready” | HOLD verdict |
| “100% precision” (without corpus qualifier) | True only on QuixBugs/holdout **correct files**, false as global claim |
| “Comprehensive bug coverage” | Recall 30% / 16.7% on benchmarks |
| “Replaces manual code review” | Review workflow is the product |
| “Detects vulnerabilities in your app” | Leads ≠ confirmed vulns |
| “Architecture-aware analysis platform” | Not validated |

### 7.2 Never (even after 24-repo — unless explicitly re-proven)

| Phrase | Reason |
| --- | --- |
| Benchmark precision → real-world precision | Category error documented in 95E/95F |
| “No false positives” (unqualified) | Unfalsifiable; pilot already had 15 misleading |
| “AI-powered” as core value | Engine is deterministic static analysis |
| “Fixes bugs” / “auto-remediation” | Out of scope; read-only |
| QuixBugs recall → “finds 30% of all bugs” | Paired algorithm corpus only |

### 7.3 Dangerous conflations to avoid in docs and CLI

| Wrong | Right |
| --- | --- |
| “12 bugs found” (QuixBugs) | “12/40 paired buggy files flagged with grounded findings” |
| “Precision 100%” | “100% precision on QuixBugs correct files (grounded kinds)” |
| “202 issues found” (pilot) | “202 review candidates; 0 confirmed defects after human review” |
| “Security scan clean” | “No grounded security leads” vs “no confirmed vulns” — different claims |

---

## 8. Category scorecard (evidence-weighted)

| Category | Score | Rationale |
| --- | ---: | --- |
| A. Bug Finder | **2 / 10** | Benchmark recall low; real-repo confirmed defects 0 |
| B. Review Intelligence System | **8 / 10** | Pilot review-lead rate, workflow, evidence packaging |
| C. Risk Discovery Tool | **7 / 10** | Taint/null leads valued; not validated as risk **truth** |
| D. Architecture Analyzer | **3 / 10** | Peripheral index/ask; not 95E core |
| E. Static review assistant (explicit) | **9 / 10** | Matches implementation + all three evidence layers |

---

## 9. Dual nature (must be communicated)

Builder Core has **two measured personalities**:

```
┌─────────────────────────────────────────────────────────────┐
│  CURATED BENCHMARKS          │  REAL REPOSITORIES (pilot)   │
├──────────────────────────────┼──────────────────────────────┤
│  Paired buggy/correct files  │  Unpaired production-ish code│
│  Precision 100% (grounded)   │  Strict defect precision 0%  │
│  Recall 30% / 16.7%          │  Review-lead rate 73%        │
│  Regression gate             │  Human review required       │
└──────────────────────────────┴──────────────────────────────┘
```

Any positioning that cites only the left column without the right is **dishonest**. Any positioning that dismisses the left column ignores real regression value.

---

## 10. Summary table

| Question | Answer |
| --- | --- |
| **What is it today?** | **Review Intelligence System** (+ Risk Discovery leads); not a validated Bug Finder |
| **Supported claims** | Read-only local review aid; explainable leads; benchmark precision on pairs; pilot usefulness |
| **Unsupported claims** | Autonomous bug finding; real-repo defect precision; prod security; alpha ready |
| **Honest positioning** | Deterministic local review assistant — inspect this, don’t trust blindly |
| **Future positioning (conditional)** | Validated review intelligence with measured defect promotion after 24-repo PASS |
| **Never say** | Auto bug finder, global zero FP, prod security, alpha ready, benchmark = real world |

---

## 11. Acceptance

| Criterion | Met |
| --- | --- |
| Evidence from 95E, 95F, QuixBugs, holdout | yes |
| No code / tuning / roadmap changes | yes |
| 95E conclusion preserved (HOLD, 0 confirmed, leads useful) | yes |
| Bad results not hidden | yes |
| Category question answered | yes (B+C primary; not A; not D) |

No files outside this report were modified in Phase 95G.
