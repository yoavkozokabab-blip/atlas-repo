# Phase 161 — Grounding Hardening Sprint

Date: 2026-06-05

Priority: **Correctness > Coverage · Evidence > Confidence · Unknown > Wrong.**

Scope: grounding, evidence, confidence, investigation, impact, and build plans only.
No changes to the website, installer, onboarding, billing, pricing, marketing, or
waitlist. This sprint extends the Phase 158 grounding fixes and adds measurement.

Success criteria: **misleading < 5%**, **wrong < 3%**, Unknown used instead of fake
certainty. Achieved: **misleading 0%, wrong 0%** on the labeled battery (see below).

---

## Task 1 — Kill concept leakage

- Specialized trading concepts (EMA, slippage) may now only be derived from the goal
  text when the user **explicitly asks for trading** OR the **repository has trading
  evidence** (`planning_engine._repository_evidence_bundle`, gated by
  `_request_mentions_trading_explicitly` / `_repo_has_trading_evidence`).
- The "indicator + signal/pipeline → EMA" override (a leakage vector) is now behind the
  same gate. On a non-trading repo, *"add an indicator signal pipeline"* routes to a
  CI/CD pipeline concept, **not** EMA.
- Combined with the Phase 158 trading-domain guardrail, no trading/EMA concept appears
  without explicit domain evidence or an explicit user request.

## Task 2 — Root-cause evidence engine

- Every hypothesis now carries a **0–100 evidence score** (`evidence_score_100`) derived
  from grounded (non-noisy) files, hypothesis confidence, and evidence lines
  (`_hypothesis_evidence_score_100`).
- A hypothesis becomes "most likely root cause" only when it clears
  `_ROOT_CAUSE_MIN_SCORE_100 = 50`. The plan exposes `root_cause_evidence_score` and
  `root_cause_threshold`.
- Below threshold, Atlas returns **"Insufficient evidence."** with the best score and the
  threshold, and asks for a stack trace / file path.

## Task 3 — Unknown Mode

- Honest outputs only when grounding is weak: **"Insufficient evidence."** (root cause),
  **"Unable to resolve target"** (impact `status=target_not_resolved`), and the
  `_insufficient_evidence_response` gap response (unsupported-language repos).
- Stdlib/noise modules (`__future__`, `re`, `os`, …) can never be a root cause.

## Task 4 — Impact hardening

- The legacy `api._impact_mock` no longer fakes success: it returns **`ok=False`**,
  `status="target_not_resolved"`, `mock=False`, an empty blast radius, and honest
  next steps. The `ok=true / mock=true / todo` payload is gone.
- The impact engine (`impact_engine.analyze_impact`) already returns `ok=False` for
  unresolved / out-of-graph / no-graph targets (Phase 158); Phase 161 aligns the legacy
  path so **no impact result claims success without a resolved file, module, or symbol.**

## Task 5 — Graph health truth

- `api._graph_health` now takes the **worse** of its own label and the reliability
  assessment and propagates the unified vocabulary **{healthy, partial, degraded,
  unsupported}** into the summary (and therefore all summary-derived outputs).
- Kubernetes-style scans (24,860 files / 3 modules) report **`unsupported`**, never
  `healthy`. Zero-edge-but-many-modules → `degraded`. The block also carries
  `reliability_category`.

## Task 6 — Confidence calibration

- New `reliability.calibrate_confidence_cap(scan, *, evidence_count, resolution)` caps
  confidence by the **minimum** of graph health, evidence count (0 → low, 1 → ≤ medium,
  ≥2 → high allowed), and target/intent resolution (unresolved → low, partial → ≤ medium).
- Applied in `plan_change`, `investigate_symptom`, and `impact_engine.analyze_impact`.
  **High confidence now requires a healthy graph AND ≥2 grounded signals AND a resolved
  target** — so high is rare (10% on the battery, only the fully-resolved healthy case).
- Compound labels ("medium-high") are compared by their strongest component, so they can
  no longer slip past the cap.

## Task 7 — Build plan precision

- Build plans expose explicit tiers: `implementation_files` (Tier 1),
  `review_files` (Tier 2), `context_files` (Tier 3), a `file_tiers` map, and
  `default_tier = "tier1_implementation"`. Default output is Tier 1 only; review and
  context files are separated, not mixed into the implementation list.

## Task 8 — Measurement

A self-contained harness, `jarvis_desktop/grounding_eval.py`
(`py -3 -m jarvis_desktop.grounding_eval`), runs a 15-scenario labeled battery and
reports the sprint metrics.

Current results (after hardening):

| Metric | Result | Target |
|--------|--------|--------|
| Misleading % | **0.0%** | < 5% |
| Wrong % | **0.0%** | < 3% |
| Confidence high % | 10.0% (1/10 — the one healthy, fully-resolved case) | rare |
| Avg evidence count | 6.0 | — |
| Target resolution quality | 100% | high |

Representative per-scenario outcomes:

- `add an indicator signal pipeline` → concept `ci_cd_pipeline` (**not EMA**).
- `why are duplicate events being fired` → `pub_sub` (**not trading/EMA**).
- Kubernetes-like scan → graph health `unsupported` (**not healthy**).
- Impact on a missing file → `ok=False, status=target_not_resolved` (**no fake blast**).
- Degraded scan plan → confidence `low` (**not high**).
- Noisy-module symptom → root cause **"Insufficient evidence."** (no stdlib guess).

---

## Files changed

- `jarvis_desktop/reliability.py` — `calibrate_confidence_cap`, `_confidence_rank` helpers.
- `jarvis_desktop/planning_engine.py` — trading-concept leakage gate; 0–100 root-cause
  evidence score + threshold + "Insufficient evidence."; calibrated confidence caps;
  explicit build-plan file tiers.
- `jarvis_desktop/api.py` — `_impact_mock` → `ok=False`; `_graph_health` unified label
  propagation.
- `jarvis_desktop/impact_engine/engine.py` — calibrated impact confidence (graph +
  evidence + resolution).
- `jarvis_desktop/grounding_eval.py` (new) — measurement harness.
- Tests: `test_phase161_grounding.py`, `test_phase161_unknown_mode.py`,
  `test_phase161_confidence.py`, `test_phase161_graph_truth.py` (new).
- Test alignments (older contracts superseded by the grounding mandate):
  `test_phase107_desktop_api.py` and `test_phase132_impact_and_quality.py`
  (unresolved impact now `ok=False`), `test_phase140_reliability.py`
  (`UNSUPPORTED_LANGUAGE` added to the taxonomy set).

## Verification

```
py -3 -m jarvis_desktop.grounding_eval        # misleading 0% / wrong 0% / resolution 100%
py -3 -m pytest jarvis_desktop/tests/test_phase161_grounding.py \
                jarvis_desktop/tests/test_phase161_unknown_mode.py \
                jarvis_desktop/tests/test_phase161_confidence.py \
                jarvis_desktop/tests/test_phase161_graph_truth.py -q   # 54 passed
# Regression across grounding/impact/confidence/reliability suites: 241 passed
```

## Remaining work / honest limitations

- The before/after comparison is measured against the current code; the "before" baseline
  is described qualitatively (Phase 158 already removed the worst leakage). The harness is
  the durable regression baseline going forward.
- Evidence scoring for root cause is heuristic (files + confidence + evidence lines), not a
  learned model; the 0–100 scale is a calibrated proxy, not a probability.
- Confidence calibration is conservative by design — some genuinely strong results will be
  reported as "medium". Per the sprint priority (Evidence > Confidence), that is the
  intended trade-off.
