# Phase 104C-Fix2 — Compact Packet Remediation Plan

**Status:** Audit + remediation plan. **No code. No benchmark-task changes.**
**Date:** 2026-06-01
**Verdict:** Compact packets are **NO-GO** until the five blockers below are fixed
and a re-audit returns GO.

**Hard rules (govern every fix):**
1. **Evidence truth beats compression** — never drop or fake a fact to hit a token target.
2. **No fake contract facts.**
3. **No silent path selection.**
4. **No false cap compliance.**
5. **No full benchmark until re-audit returns GO.**

---

## 0. Shared root issue

`required_evidence` mixes two kinds of refs (confirmed in the frozen corpus):
- **path refs** — `config.py`, `builder_core/ask.py`, `builder_core/bug_intelligence/engine.py`
- **concept tokens** — `impact`, `depend`, `fan-in`, `LOC`, `cycle`, `inconsistent_return`,
  `review lead`, `type_hint`, `assert`, `caller_behavior`, `blocker`

The compact generator currently treats both the same way: it **resolves a token to
one path and/or synthesizes a fact from the word**. That single conflation produces
blockers 2, 4, and 5. The fix is to **separate path-resolution from
fact-selection**, and to **only emit facts that real extraction produced**.

---

## 1. Blocker 1 — False cap compliance

**Root cause:** the `compliant`/within-budget flag is computed from the *intended*
budget or a *pre-truncation* estimate (or counts only some row types), not from the
**actual rendered output string**. So a packet can render above its hard cap while
reporting `compliant: true`. The `TRUNCATED=...` + sidecar lines themselves also add
tokens that are not re-counted.

**Invariant after fix:**
> For every emitted packet `P`: `estimate_tokens(render(P)) ≤ hard_cap(task_type)`,
> and `compliant == (estimate_tokens(render(P)) ≤ hard_cap)` computed by
> **re-measuring the exact final bytes** (header + all rows + TRUNCATED + sidecar).
> If mandatory safety fields (claim, caveats, scope, quality, ≥1 evidence ref per
> claim) cannot fit under the hard cap, **generation FAILS** (raises / emits
> `status: NO-GO`). It must **never** report `compliant: true` above cap.

**Required tests:**
- `test_compliance_equals_measured_output`: for a sample of packets, `compliant`
  flag == `estimate_tokens(actual_rendered_string) ≤ cap`.
- `test_over_cap_never_reports_compliant`: a packet engineered past cap → `compliant`
  is False (or generation raises); fuzz with oversized inputs.
- `test_truncation_lines_are_counted`: TRUNCATED + sidecar tokens are included in the
  measured total.
- `test_mandatory_fields_overflow_fails`: when safety fields don't fit → generation
  error, never compliant.

---

## 2. Blocker 2 — Synthesized contract facts

**Root cause:** the contract/verification packet families build `contract` rows from
**prompt/evidence words** (`inconsistent_return`, `type_hint`, `assert`,
`caller_behavior`, `review lead`) rather than from real `contract_facts` /
`verification_evidence` extraction on the named symbol. A row asserts a contract the
analyzer never produced.

**Invariant after fix:**
> Every `contract`/`verification` row must be **backed by a real extracted fact** for
> the named symbol, with provenance ∈ {`contract_facts`, `verification_evidence`} and
> a `REF` that resolves to a concrete `file:line`. A row may **never** be derived from
> prompt or `required_evidence` text. Formally: `rows ⊆ extract(subject)`; no row
> with `provenance == prompt`. If extraction yields nothing for the subject, the
> packet emits an explicit `CONTRACT: none extracted` (UNKNOWN), never a fabricated row.

**Required tests:**
- `test_contract_rows_subset_of_extraction`: every emitted contract row appears in the
  real `contract_facts.extract(subject)` output; no extras.
- `test_no_contract_facts_means_no_rows`: a subject with no contract facts → packet has
  zero contract rows (or an explicit "none extracted"), not a synthesized one.
- `test_contract_ref_resolves`: every contract row `REF` resolves to a real file:line.
- `test_prompt_words_do_not_create_rows`: putting `inconsistent_return` in the prompt
  with no real finding produces **no** contract row.

---

## 3. Blocker 3 — risk01 vs risk02 not substantively different

**Root cause:** both are `architectural_risk` type, so the family renders the same
"top-N risk ranking" and ignores that the two questions need different facts:
- `risk01_ranking` (`required_evidence: [risk, centrality]`) → ranking **by risk**.
- `risk02_centrality_vs_risk` (`required_evidence: [fan-in, LOC, cycle]`) → the
  **contrast** between centrality/fan-in and actual risk (e.g. `core.logger`: fan_in
  144 but **low** risk band).

The generator keys on `task_type`, not on the task's intent/evidence cues.

**Invariant after fix:**
> `facts(risk01) ≠ facts(risk02)`, and each packet contains the facts **its** question
> requires: `risk01` ⇒ modules ordered by `risk_score`; `risk02` ⇒ each module's
> `fan_in` **and** `risk_score`/band together, including ≥1 high-fan-in/low-risk
> contrast row. Packet content is a function of the task's evidence cues, not of
> `task_type` alone.

**Required tests:**
- `test_risk01_risk02_facts_differ`: the FACTS blocks differ (not just the header).
- `test_risk02_shows_centrality_vs_risk`: risk02 includes both `fan_in` and `risk_score`
  for the same modules and at least one high-fan-in/low-risk row.
- `test_risk01_ordered_by_risk`: risk01 facts are ordered by `risk_score` desc.

---

## 4. Blocker 4 — Silent path selection on ambiguous refs

**Root cause:** when a ref matches multiple real files, the relevance filter picks
one silently (e.g. first match); when it matches none, it silently drops it; and
**concept tokens** (`impact`, `depend`, `fan-in`) are treated as if they name a single
file. No disclosure of the choice.

**Invariant after fix:**
> Refs are classified first: **path-ref** vs **concept-ref**.
> - A **path-ref** with matches `{p1..pn}`: if `n>1` render `AMBIGUOUS <ref> -> [p1..pk] (+m more)`;
>   if `n==0` render `UNRESOLVED <ref>`; if `n==1` resolve cleanly. **Never** a single
>   silent pick when `n>1`.
> - A **concept-ref** maps to a **fact type / family**, never to a path; it is rendered
>   as the relevant structured fact (e.g. `fan-in` → fan_in rows), never as a fabricated
>   file path.
> Every resolution decision is visible in the packet; no information about the chosen
> or discarded paths is hidden.

**Required tests:**
- `test_ambiguous_path_lists_all_candidates`: a path-ref matching ≥2 files → all listed
  (capped + declared) or an `AMBIGUOUS` marker; no single silent pick.
- `test_zero_match_ref_is_marked_unresolved`: a ref matching no file → `UNRESOLVED`.
- `test_concept_ref_maps_to_fact_not_path`: `impact`/`fan-in`/`depend` produce facts,
  never an invented path.
- `test_resolution_is_disclosed`: every chosen path has visible provenance.

---

## 5. Blocker 5 — Task packets collapse into generic shapes

**Root cause:** the per-task relevance filter narrows on `task_type` only, so all
tasks of a type get the same generic family shape; subject extraction does not
actually restrict facts to the entities named in the prompt + `required_evidence`.
The original 104A symptom ("several unrelated tasks receive identical packets")
persists for the 3 dependency tasks, 3 RU tasks, 3 impact tasks, etc.

**Invariant after fix:**
> A packet contains a fact `f` only if `f.ref` is in the task **subject set**
> `S(task)` = path-refs(required_evidence) ∪ named entities in the prompt. For any two
> tasks `t1 ≠ t2` with `S(t1) ≠ S(t2)`: `facts(t1) ≠ facts(t2)` — **no two
> distinct-subject tasks share an identical FACTS block**, and no packet equals the
> bare family template. Each packet includes the subject-specific facts its question
> needs.

**Required tests:**
- `test_corpus_packets_are_distinct`: across the 21 tasks, no two with different
  subjects produce identical FACTS blocks (`dep01 ≠ dep02 ≠ dep03`, `ru01 ≠ ru02 ≠ ru03`).
- `test_facts_reference_subject`: every fact in a packet references the task's subject set.
- `test_packet_not_equal_generic_template`: a packet never equals the family's empty/
  generic shape.

---

## 6. Acceptable token-reduction threshold

- **Floor:** ≥ **50%** median reduction vs the verbose baseline (consistent with the
  104C 52.3%), **measured only over packets that pass blockers 1–5**.
- **Subordination rule (Hard rule 1):** if the truth fixes (real contract extraction,
  ambiguity disclosure, subject-specific facts) push a packet over its cap, the
  remedy is to **raise that family's hard cap**, *not* to drop or fake facts. A drop
  in reduction caused by truth is acceptable; a truth violation to preserve reduction
  is **not**.
- **Per-packet:** every emitted packet ≤ its (possibly raised) hard cap, measured on
  actual output (blocker 1).
- If, after truth fixes, median reduction < 50%, the phase is **GO on truth / token
  target re-opened** — re-baseline the budget, never the truth.

---

## 7. GO / NO-GO criteria

**GO** only when **all** hold (re-audit):
| Gate | Criterion |
|---|---|
| Cap honesty (B1) | every packet `estimate_tokens(output) ≤ hard_cap`; `compliant` == measured; overflow fails, never false-compliant |
| Contract truth (B2) | 0 synthesized contract/verification rows; all rows ⊆ real extraction with resolving refs |
| risk distinctness (B3) | `facts(risk01) ≠ facts(risk02)`; each has its required facts |
| No silent selection (B4) | 0 ambiguous path-refs resolved to a single silent pick; concept-refs map to facts, not paths |
| No generic collapse (B5) | 0 identical FACTS blocks across distinct-subject tasks; facts subject-filtered |
| Token floor | ≥ 50% median reduction over passing packets |
| Regression | full builder_core suite green; QuixBugs 12 TP / 0 FP unchanged |

**NO-GO** if **any** of: a false cap-compliance, a fabricated contract fact, a silent
path selection, risk01==risk02 facts, any identical distinct-subject packets, or a
reduction claim that was bought by sacrificing truth.

**Hard rule 5:** **no full 21-task benchmark** runs until this re-audit returns GO.
A 5-task spot re-audit (one per affected family: contract, architectural_risk,
dependency, impact, verification) must pass first.

---

## 8. What must NOT be changed

- **The 21 benchmark tasks** (frozen corpus) — refs, prompts, expected answers, rubric.
- **Phase 103 schema/framework** — `RunLog`, `ManualScore`, `MODES`, summary, CLI.
- **Detectors / findings / benchmarks / promotion** — QuixBugs 12/0, holdout 2/0.
- **The deterministic JARVIS sources** — `ask`, `depgraph`, `architectural_risk`,
  `contract_facts`, `verification_evidence`. Fixes **render** their real output more
  truthfully; they do **not** add new analysis or invent facts.
- **Win/loss/tie rules and scoring rubric** (Phase 104E).
- **The verbose format** remains available for A/B (so reduction stays provable).

---

## 9. Bottom line

All five blockers reduce to one discipline failure: the packet **invented or
silently chose** information instead of rendering only what real extraction produced.
The remediation makes truth structural — cap-compliance measured on actual bytes,
contract rows strictly a subset of real extraction, ambiguous refs disclosed,
concept-refs mapped to facts not paths, and facts filtered to each task's subject so
no two distinct tasks collapse to one packet. Compression stays a **floor (≥50%)
subordinate to truth**: when truth costs tokens, raise the cap, never fake the fact.
No full benchmark until the re-audit returns GO.
