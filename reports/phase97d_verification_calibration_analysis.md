# Phase 97D — Verification Evidence Calibration Analysis

**Status:** Analysis complete  
**Date:** 2026-05-31  
**Scope:** Calibration measurement only — no detector, promotion, benchmark, or code changes  
**Inputs:** Phase 97C pilot (`reports/phase97c_pilot/`, 20 cases)  

---

## Executive summary

Phase 97C misleading rate rose **10% → 80%** (2 → 16 false-positive pilot labels)
on the same 20-case cohort. **14** cases changed label;
**6** unchanged.

Root cause: Phase 97A marks **`status: refuted`** from a single
`path_feasibility_evidence` atom (`path.no_implicit_none_exit`) on **16/20** cases.
The Phase 97C pilot rubric maps any `refuted` status or refuting atom to
`false_positive`. That coupling — not detector output — drives the misleading-rate jump.

Calibration breakdown of the **14 reclassifications** (useful/unclear → false_positive):

- **over refutation**: 12
- **correct reclassification**: 2

Secondary tags on reclassified cases:
- `wrong_witness_for_finding_shape`: 8
- `evidence_weighting_issue`: 8
- `return_summary_vs_finding_disagreement`: 4
- `missing_context`: 4
- `optional_contract_visible`: 2

Dominant issue: **over-refutation** — `return_summary.can_fall_through` disagrees
with the inconsistent-return finding on implicit-None fall-through leads (`kind=pattern`),
yet verification elevates the disagreement to **`refuted`** status and the pilot
auto-labels that as misleading.

---

## Why misleading rate jumped

| Factor | Role |
|--------|------|
| 16× `verification_status: refuted` | Triggers enriched `false_positive` in 97C rubric |
| 4× `verification_status: blocked` | Labels unchanged (still useful_advisory) |
| Single atom per case (mean 1.0) | Refutation presented without supporting violation context |
| `status: refuted` wording | Reads as “finding disproven,” stronger than “path witness incomplete” |
| No human adjudication | Proxy labels, not ground-truth defect labels |

The 10% baseline misleading rate came from **contract-only** heuristics (optional
return type in signature on 2 cases). The 80% enriched rate adds **14** refuted-path
cases that contract review still scored as useful advisories.

---

## Confusion matrix

Rows: conservative **ground-truth proxy** (not confirmed defects).  
Columns: Phase 97C **enriched pilot label**.

| Ground-truth proxy \ Enriched label | false_positive | useful_advisory | unclear |
|-----------------------------------|---------------:|----------------:|--------:|
| non actionable lead | 4 | 0 | 0 |
| review worthy lead | 4 | 4 | 0 |
| uncertain | 8 | 0 | 0 |

Interpretation: **review-worthy** implicit-None leads are overwhelmingly labeled
false_positive when verification status is `refuted`. Optional-return leads align
with false_positive under both contract and verification arms.

---

## Per-case reclassification table

| # | Location | Baseline → Enriched | Status | Mechanism | Calibration |
|--:|----------|---------------------|--------|-----------|-------------|
| 1 | `actions/service_actions.py:21` | useful_advisory → false_positive | refuted | no_fallthrough_witness | over_refutation |
| 2 | `actions/website_actions.py:43` | false_positive (unchanged) | refuted | no_fallthrough_witness | unchanged |
| 3 | `alpha/session_log.py:40` | useful_advisory → false_positive | refuted | no_fallthrough_witness | over_refutation |
| 4 | `assistant/investigation_scheduler.py:161` | useful_advisory → false_positive | refuted | no_fallthrough_witness | over_refutation |
| 5 | `backups/jarvis_patches/20260526_121610_95ec3bbe/services__live_paper_engine.py:960` | useful_advisory → false_positive | refuted | no_fallthrough_witness | over_refutation |
| 6 | `brain/patch_command_phrases.py:118` | useful_advisory → false_positive | refuted | no_fallthrough_witness | correct_reclassification |
| 7 | `builder_core/gitutil.py:70` | useful_advisory → false_positive | refuted | no_fallthrough_witness | over_refutation |
| 8 | `desktop/control_runtime.py:208` | useful_advisory → false_positive | refuted | no_fallthrough_witness | over_refutation |
| 9 | `investigation/replay_cache.py:12` | false_positive (unchanged) | refuted | no_fallthrough_witness | unchanged |
| 10 | `runtime/dashboard_health.py:27` | useful_advisory → false_positive | refuted | no_fallthrough_witness | over_refutation |
| 11 | `tests/test_phase41_6_tts_runtime.py:162` | useful_advisory (unchanged) | blocked | path.partial | unchanged |
| 12 | `tests/test_phase71_tool_use.py:127` | useful_advisory (unchanged) | blocked | path.partial | unchanged |
| 13 | `tests/test_tts_failure_visibility.py:35` | useful_advisory (unchanged) | blocked | path.partial | unchanged |
| 14 | `tests_tmp/pytest_temp/pytest-of-babi2/pytest-341/test_cli_ask_returns_bug_findi0/fake_repo/python_programs/off_by_one.py:1` | useful_advisory (unchanged) | blocked | path.partial | unchanged |
| 15 | `ui/console_modal.py:150` | unclear → false_positive | refuted | no_fallthrough_witness | correct_reclassification |
| 16 | `voice/providers/elevenlabs_websocket.py:30` | useful_advisory → false_positive | refuted | no_fallthrough_witness | over_refutation |
| 17 | `voice/pyttsx3_completion.py:333` | useful_advisory → false_positive | refuted | no_fallthrough_witness | over_refutation |
| 18 | `voice/tts_pyttsx3.py:40` | useful_advisory → false_positive | refuted | no_fallthrough_witness | over_refutation |
| 19 | `voice/voice_calibration.py:58` | useful_advisory → false_positive | refuted | no_fallthrough_witness | over_refutation |
| 20 | `website_audit/inspector.py:42` | useful_advisory → false_positive | refuted | no_fallthrough_witness | over_refutation |

---

## Reclassification categorization (14 cases)

Each row tags the **primary** calibration cause plus secondary dimensions
from the Phase 97D taxonomy.

| # | Location | Primary | Missing context | Weighting | Presentation |
|--:|----------|---------|:-------------:|:---------:|:------------:|
| 1 | `actions/service_actions.py:21` | over_refutation | yes | — | yes |
| 2 | `alpha/session_log.py:40` | over_refutation | — | yes | yes |
| 3 | `assistant/investigation_scheduler.py:161` | over_refutation | — | yes | yes |
| 4 | `backups/jarvis_patches/20260526_121610_95ec3bbe/services__live_paper_engine.py:960` | over_refutation | — | yes | yes |
| 5 | `brain/patch_command_phrases.py:118` | correct_reclassification | — | — | yes |
| 6 | `builder_core/gitutil.py:70` | over_refutation | — | yes | yes |
| 7 | `desktop/control_runtime.py:208` | over_refutation | — | yes | yes |
| 8 | `runtime/dashboard_health.py:27` | over_refutation | — | yes | yes |
| 9 | `ui/console_modal.py:150` | correct_reclassification | — | — | yes |
| 10 | `voice/providers/elevenlabs_websocket.py:30` | over_refutation | yes | — | yes |
| 11 | `voice/pyttsx3_completion.py:333` | over_refutation | yes | — | yes |
| 12 | `voice/tts_pyttsx3.py:40` | over_refutation | yes | — | yes |
| 13 | `voice/voice_calibration.py:58` | over_refutation | — | yes | yes |
| 14 | `website_audit/inspector.py:42` | over_refutation | — | yes | yes |

---

## Calibration category definitions

| Category | Meaning in this pilot |
|----------|----------------------|
| **correct_reclassification** | Enriched label better matches proxy ground truth |
| **over_refutation** | `refuted` status overstates refutation; lead may still warrant review |
| **missing_context** | Packet omits why finding and witness disagree |
| **evidence_weighting_issue** | Refutation atom alone drives `refuted` without bundle balance |
| **packet_presentation_issue** | Wording (`refuted`, refutation-only) steers reviewers |

---

## Evidence-type recommendations

| Evidence type | Verdict | Rationale |
|---------------|---------|-----------|
| **test_evidence** | **keep** | Not present in cohort (no `test_documents` in repo scan). Safe when bound; no harm observed. |
| **assertion_evidence** | **keep** | Not emitted in these 20 cases. Phase 96A assert facts remain useful as obligation context. |
| **contract_violation_evidence** | **modify** | Rare in cohort. When absent, refutation-only packets should not imply defect disproof. |
| **path_feasibility_evidence** | **modify** | **Primary driver** of misleading-rate jump. Cap `refuted` status when finding kind is `pattern` and only witness is `path.no_implicit_none_exit`. |
| **runtime_reproduction_evidence** | **keep** | Not present in cohort. Parser-only; no execution. |

### path_feasibility_evidence — required modifications

1. Do **not** set overlay `status: refuted` when the inconsistent-return finding
   remains `kind=pattern` and the only refuting claim is `path.no_implicit_none_exit`.
2. Prefer **`enriched_lead` + refuting atom** (polarity `refutes`, strength E2) instead
   of global `refuted` status.
3. Add **missing_context** bullet when `return_summary` and detector shape disagree.
4. Never map overlay status directly to reviewer **`false_positive`** without
   human adjudication (97C rubric artifact, not product behavior).

### contract_violation_evidence — required modifications

1. Keep derived violation atoms **supporting-only** until promotion gate enabled.
2. Pair violation atoms with path witnesses before any future `refuted`/`blocked` status.

### Packet presentation — required modifications

1. Rename or qualify **`refuted`** → `refutation_witness_present` in review packets.
2. Show **finding vs witness disagreement** explicitly for fall-through cases.
3. Keep **MISSING PROOF OBLIGATIONS** (97C improved confirmation clarity 3.0 → 4.0).

---

## Aggregated calibration counts (20 cases)

| Primary calibration | Count |
|---------------------|------:|
| over refutation | 12 |
| unchanged | 6 |
| correct reclassification | 2 |

### Reclassification mechanisms

| Refutation / blocker mechanism | Count |
|--------------------------------|------:|
| no_fallthrough_witness | 16 |
| path.partial | 4 |

---

## Conclusions

1. The **80% misleading rate is largely a measurement artifact**: 97C enriched labels
   treat `verification_status: refuted` as `false_positive`, affecting 14/20 cases.
2. **12 reclassifications are over-refutation** — `path.no_implicit_none_exit` applied
   to 8 inconsistent-types findings (wrong witness) and 4 fall-through leads where
   `return_summary` disagrees with the detector shape.
3. **2 reclassifications are correct** — optional-return contract visible
   (`patch_command_phrases`, `console_modal`).
4. **Confirmation clarity gains (97C) are real**; misleading-rate spike is not evidence
   of improved defect detection — it reflects status wording + rubric coupling.
5. **No detector, promotion, or benchmark change recommended** from this analysis;
   calibration fixes belong in **verification overlay status logic and review rubric**,
   not finding generation.

---

## Constraints honored

- No detector changes
- No promotion changes
- No benchmark changes
- No code modifications (analysis-only deliverable)

---

## Artifacts

| File | Purpose |
|------|---------|
| `phase97c_pilot/pilot_sample.json` | 20 reviewed findings |
| `phase97c_pilot/pilot_reviews.json` | Baseline vs enriched labels |
| `phase97c_pilot/metrics.json` | 97C aggregate metrics |
| `builder_core/scripts/phase97d_calibration_analysis.py` | Reproducible analysis script |
