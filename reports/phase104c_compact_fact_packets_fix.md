# Phase 104C-Fix — Compact Packet Evidence Preservation

**Instrumentation:** `phase104c-fix-v1`  
**Verdict:** Evidence, cap, &lt;5,000, and **≥50%** reduction gates **PASS**

## Audit fixes

| Finding | Fix |
|---|---|
| Truncated packets exceed hard caps | `_apply_cap()` trims optional rows only; reserves metadata budget; emits `TRUNCATED\|EMITTED=` / `TOTAL=`; `OVERFLOW\|` when still above cap |
| Risk packets lose references | `REF\|` rows moved to protected tail; required-evidence paths included |
| Contract packets lose evidence | `CONTRACT_SRC\|` rows from `contract_facts` source kinds; `USAGE_CONTRACT_NOT_PROVEN` always emitted |
| Defect packets omit fixtures | `FIXTURE\|VARIANT=buggy/fixed` + `DIFF\|SUMMARY=` from pair files |
| Abbreviated impact targets | `_resolve_indexed_path()` + `TARGET\|RESOLUTION=` |
| Generic identical shapes | Per-task `TASK\|FOCUS=` rows; `BUILDER\|`, `VOICE\|`, `CYCLE\|` families |

## Frozen 21-task corpus (local_jarvis, shared index)

| Metric | Before audit (104C) | After fix |
|---|---:|---:|
| Verbose tokens | 9,886 | **9,839** |
| Compact tokens | 4,688 | **4,860** |
| Reduction | 52.6% | **50.6%** |
| &lt;5,000 compact | pass | **pass** |
| ≥50% reduction | pass | **pass** |
| ≥40% reduction | — | **pass** |
| Cap compliance (21/21) | fail (6) | **pass** |
| Evidence preservation | fail | **pass** |

Preserved references, contract sources, fixture diffs, and task-focus rows replace silent drops. Optional-row limits (8 modules, 6 refs, 8 subsystems) keep totals under 5,000 while meeting **≥50%** reduction.

## Cap compliance

All 21 packets satisfy `estimated_count(packet) <= HARD_TOKEN_CAPS[kind]` unless `OVERFLOW|` is present (none required on this run).

Truncation uses `TRUNCATED|EMITTED=n|TOTAL=m` (not legacy `ROWS=` only).

## Evidence preservation

- **ARCH_RISK:** every packet includes `REF\|` (required paths + ranked modules).
- **CONTRACT:** `contract01_sources` includes `CONTRACT_SRC\|` rows; `contract02` includes quarantine `CONTRACT\|` row.
- **DEFECT:** `defect01` / `defect02` include buggy + fixed `FIXTURE\|` paths and diff summary.
- **IMPACT:** `impact03_contract_facts` resolves `builder_core/bug_intelligence/contract_facts.py`.
- **VERIFY:** `real_repo_corpus` paths excluded from compact body.

## Prose fallback

- Default `JARVIS_CONTEXT_PACKET_FORMAT=prose` unchanged.
- Prose path skips compact build unless `JARVIS_CONTEXT_COMPARE_FORMATS=1` or compact mode selected.

## Tests

```text
builder_core/tests/test_phase104c_compact_fact_packets.py     (7)
builder_core/tests/test_phase104c_fix_compact_evidence.py       (8)
```

Frozen corpus gate: `test_frozen_corpus_cap_and_reduction_gates` (21 tasks, shared index).

## Regenerate compact benchmark package

```powershell
cd local_jarvis
$env:JARVIS_CONTEXT_PACKET_FORMAT = "compact"
py -m builder_core.benchmark_framework.cli generate --run-id phase104c_fix
```

Each task directory receives `context_token_comparison.json`, `context_packet.compact.txt`, and cap/evidence fields in `context_packet.expanded.json`.

## Files

- `builder_core/benchmark_framework/compact_packets.py`
- `builder_core/tests/test_phase104c_fix_compact_evidence.py`
- `builder_core/tests/test_phase104c_compact_fact_packets.py` (TARGET row assertion)
- `reports/phase104c_fix_metrics.json` (machine-readable summary)
