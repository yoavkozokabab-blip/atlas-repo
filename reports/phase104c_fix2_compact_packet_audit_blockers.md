# Phase 104C-Fix2 — Compact Packet Audit Blocker Fixes

**Instrumentation:** `phase104c-fix2-v1`  
**Verdict:** **GO** on frozen 21-task corpus

## Blockers addressed

| # | Blocker | Fix |
|---|---------|-----|
| 1 | Over-cap packets reported compliant | `cap_compliant = token_estimate <= cap` only; `OVERFLOW\|` when above cap; `packet_cap_compliant()` no longer treats overflow as compliant |
| 2 | Contract rows from prompt keywords | `CONTRACT_SRC` only from `contract_facts.extract_module_contracts()` statistics; `CONTRACT_STATUS=none\|extracted\|disabled` |
| 3 | risk01 / risk02 identical shape | risk01: `RANK_META` + `MODULE` + `RANK_DIAG`; risk02: `RISK_MODEL` + `CENTRALITY` + `LIMIT` (no duplicate ranking table) |
| 4 | Ambiguous refs silently resolved | `_path_candidates()` + `AMBIGUOUS_REF\|CANDIDATES=...`; no silent pick when multiple matches |
| 5 | Generic task packets | Retained task `FOCUS` rows; plan_input no longer inlines full impact builder (pre-cap bloat) |

## Frozen corpus metrics

| Metric | Value |
|--------|------:|
| Verbose tokens | 9,839 |
| Compact tokens | 4,802 |
| Reduction | **51.19%** |
| &lt;5,000 compact | pass |
| ≥50% reduction | pass |
| ≥40% reduction | pass |
| Cap compliance (21/21) | **pass** |
| Evidence preservation | **pass** |

Machine-readable: `reports/phase104c_fix2_metrics.json`

## Cap compliance rule

A packet is compliant **only if** `estimated_count(packet) <= HARD_TOKEN_CAPS[kind]`.

If trimming cannot fit within cap, the serializer emits `OVERFLOW|CAP_EXCEEDED=yes` and sets `cap_compliant=false` and `cap_overflow=true`.

## Contract evidence rule

- `CONTRACT_SRC|ORIGIN=extracted` rows aggregate `statistics.by_source` from real AST extraction.
- Prompt keywords (`type_hint`, `assert`, etc.) do **not** create contract rows.
- When no facts are extracted: `CONTRACT_STATUS|VALUE=none`.

## Risk packet differentiation

- **risk01_ranking:** ranking mechanics, top modules, rank diagnostics.
- **risk02_centrality_vs_risk:** model weights, high fan-in vs risk rank challenge rows, explicit fan-in limitation.

## Tests

- `test_phase104c_compact_fact_packets.py` (7)
- `test_phase104c_fix_compact_evidence.py` (9)
- `test_phase104c_fix2_compact_packet_audit_blockers.py` (7)

Each re-audit blocker has a dedicated regression test in Fix2.

## Out of scope

- Scoring, ask routing, architectural risk engine logic unchanged.

## Regenerate compact package

```powershell
$env:JARVIS_CONTEXT_PACKET_FORMAT = "compact"
py -m builder_core.benchmark_framework.cli generate --run-id phase104c_fix2
```
