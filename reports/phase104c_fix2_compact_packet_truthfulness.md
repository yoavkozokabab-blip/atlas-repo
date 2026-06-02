# Phase 104C-Fix2 — Compact Packet Truthfulness

**Instrumentation:** `phase104c-truth-v1`  
**Verdict:** Truth gates **PASS**; token floor **≥40% PASS** (50% re-opened after cap rebaseline)

## Root fix

The generator no longer conflates path refs, concept refs, prompt words, and extracted facts. Facts come only from real extraction or structured task subjects; refs are classified and disclosed before resolution.

## Blocker remediation

| Blocker | Fix |
|---|---|
| **B1 False cap compliance** | `cap_compliant` and `packet_cap_compliant()` measure the **final rendered string** including `TRUNCATED`, `DETAIL`, and `OVERFLOW` rows |
| **B2 Synthesized contract facts** | `CONTRACT` rows only from `contract_facts.extract_module_contracts()` with `PROVENANCE=contract_facts`, `FILE`, `LINE`; otherwise `CONTRACT_STATUS=none_extracted` |
| **B3 risk01 vs risk02** | `risk01`: `RANK_META` + ranked `MODULE` + `RANK_DIAG`; `risk02`: `RISK_MODEL` + `CENTRALITY` + `LIMIT|FAN_IN_NOT_SUFFICIENT` (distinct fact fingerprints) |
| **B4 Silent path selection** | `classify_evidence_ref()` → `path_ref` / `symbol_ref` / `concept_ref` / `unknown_ref`; `AMBIGUOUS_REF\|CANDIDATES=` and `UNRESOLVED_REF` emitted; concepts map to `CONCEPT_REF`, never silent paths |
| **B5 Generic collapse** | Per-task `TASK\|FOCUS=`, `SUBJECT\|`, `CHAIN\|`, `BUILDER\|`, `VOICE\|` rows; `WHY_GENERIC` when subject facts are thin; distinct-subject tasks have unique fact fingerprints |

## Cap rebaseline (truth subordinates compression)

Truthful disclosure rows pushed two families over prior caps. Caps were **raised**, not facts dropped:

| Family | Before | After |
|---|---:|---:|
| `REPO_MAP` | 350 | **400** |
| `IMPACT` | 275 | **300** |

## Frozen 21-task corpus (local_jarvis, shared index)

| Metric | Fix (104C-Fix) | Fix2 (truth) |
|---|---:|---:|
| Verbose tokens | 9,839 | **9,851** |
| Compact tokens | 4,802 | **5,866** |
| Reduction | 51.2% | **40.5%** |
| ≥40% reduction | pass | **pass** |
| ≥50% reduction | pass | **re-opened** (truth + cap rebaseline) |
| Cap compliance (21/21) | pass | **pass** |
| Evidence preservation | pass | **pass** |
| Distinct subject facts | partial | **pass** (dep/ru/impact/risk groups) |

Full per-task metrics: `reports/phase104c_fix2_metrics.json`.

## Regression coverage

`test_phase104c_fix2_compact_packet_audit_blockers.py` adds regressions for:

- Over-cap packets cannot report compliant
- Contract rows not synthesized from prompt keywords
- Missing contract facts emit `none_extracted`
- `facts_fingerprint(risk01) ≠ facts_fingerprint(risk02)`
- Ambiguous refs emit `AMBIGUOUS_REF`
- Concept refs do not resolve to paths
- Distinct-subject dependency / corpus task groups differ
- Frozen corpus ≥40% reduction and cap/evidence gates

Scoring, `ask.answer`, detectors, and the 21 benchmark task definitions are unchanged.

## GO / NO-GO

| Gate | Status |
|---|---|
| Cap honesty | **GO** |
| Contract truth | **GO** |
| risk01 ≠ risk02 facts | **GO** |
| No silent selection | **GO** |
| No generic collapse | **GO** |
| Token floor ≥40% | **GO** |
| Token target ≥50% | **Re-opened** — acceptable per truth-first rule |
