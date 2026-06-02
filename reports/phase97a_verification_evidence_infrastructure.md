# Phase 97A — Verification Evidence Infrastructure

**Status:** Implemented  
**Date:** 2026-05-31  
**Scope:** Infrastructure only — no confirmation, no promotion changes, no benchmark changes  
**Design input:** `reports/phase97_verification_evidence_engine_design.md`

---

## Summary

Phase 97A adds a **verification evidence overlay** that attaches typed,
deterministic evidence atoms to `inconsistent_return` findings after Phase 96C
contract enrichment. Outputs remain **`review_lead_only`** — no confirmed defects,
no automatic promotion, no benchmark behavior change.

The overlay answers: *what repository evidence supports or blocks this lead, how
strong is it, and what proof is still missing?*

---

## Implementation

| Component | Location |
|-----------|----------|
| Evidence schema + extraction | `builder_core/bug_intelligence/verification_evidence.py` |
| Finding field | `Finding.verification_evidence` + `to_dict()` export |
| Engine wiring | `engine.analyze_source()` post–contract-enrichment |
| CLI formatter | `EvidenceFormatterAgent` — per-finding verification summary |
| Review packets | `harness.export_reviewer_packets()` + `review_tool.format_candidate()` |

Feature flags:

| Flag | Default | Effect |
|------|---------|--------|
| `VERIFICATION_EVIDENCE_ENABLED` | `True` | Attach overlays |
| `EVIDENCE_PROMOTION_ENABLED` | `False` | Never emit `promotion_candidate` status |

---

## Evidence types

All five required types are defined and populated where static extraction applies:

| Type | Phase 97A source |
|------|------------------|
| `test_evidence` | Static AST mapping from `test_documents` |
| `assertion_evidence` | Phase 96A assert-backed contract facts |
| `contract_violation_evidence` | Derived from explicit type hint + `return_summary` fall-through |
| `path_feasibility_evidence` | Static witness from return summary + interprocedural caller usage |
| `runtime_reproduction_evidence` | `parse_runtime_artifact()` parser (import-only; no execution) |

---

## Strength levels

| Level | Meaning | Phase 97A usage |
|-------|---------|-----------------|
| `E0` | Unknown / unsafe to bind | Stale or unbound runtime artifacts |
| `E1` | Contextual | Star-import tests, weak bindings |
| `E2` | Grounded support | Mapped static tests, production asserts, derived violations |
| `E3` | Promotion-supporting component | Static feasible path on promoted `value_flow` leads only |
| `E4` | Reproduced | Parser exists; not emitted without separate approval gate |

Strength is capped per atom by provenance and binding quality. **No single atom
promotes** a finding.

---

## Overlay schema

Attached on `inconsistent_return` findings:

```text
verification_evidence:
  schema_version: 1
  finding_id: <Finding.id>
  status: enriched_lead | blocked | refuted | unknown
  review_packet_status: review_lead_only
  atoms: [ evidence atom records ]
  bundle:
    contract_atom_ids: []
    violation_atom_ids: []
    path_atom_ids: []
    consequence_atom_ids: []
    reproduction_atom_ids: []
  supporting_evidence: []
  refuting_evidence: []
  blockers: []
  missing_proof_obligations: []
  why_not_confirmed: [ static bullets ]
```

Statuses **`promotion_candidate`**, **`confirmed_bug`**, **`confirmed_defect`**, and
**`confirmed_actionable`** are never emitted while `EVIDENCE_PROMOTION_ENABLED=False`.

---

## Review packet sections

Reviewer packets and `review_tool.format_candidate()` now include:

```text
VERIFICATION EVIDENCE
SUPPORTING EVIDENCE
REFUTING EVIDENCE
MISSING PROOF OBLIGATIONS
BLOCKERS
WHY NOT CONFIRMED (verification)
```

Phase 96C contract review sections are unchanged and render above verification
evidence when present.

---

## Default behavior (hard)

- No promotion changes (`INTERPROC_PROMOTION_ENABLED` untouched)
- No finding `kind`, `confidence`, severity, or rank changes from evidence
- No confirmed bug category output
- QuixBugs / holdout detector verdicts unchanged
- Target repositories read-only; no code execution

---

## Tests

`builder_core/tests/test_phase97a_verification_evidence.py` — 20 tests covering:

- Overlay attachment and schema
- All five evidence types / strength levels
- Mapped test binding (`E2`) vs star-import weak binding (`E1`)
- Contract violation derivation and optional-return blockers
- Path feasibility (`E3` on promoted leads; refutation on null-checking callers)
- Runtime artifact parser (sanitized, capped strength)
- Promotion gate disabled
- Flag-off rollback
- Stable evidence IDs
- Harness + review-tool export
- Mini-QuixBugs / QuixBugs / holdout parity

**Full suite:** 337 passed.

---

## Rollback

Set `VERIFICATION_EVIDENCE_ENABLED = False` in
`verification_evidence.py`. Findings revert to Phase 96C shape (contract review
only). No migration required.

---

## Next steps (out of scope for 97A)

- Enable `promotion_candidate` output behind `EVIDENCE_PROMOTION_ENABLED` + 0-FP gate
- Ingest pinned CI/runtime artifacts into live scans
- Extend overlay beyond `inconsistent_return`
- Phase 97B confirmation evaluators
