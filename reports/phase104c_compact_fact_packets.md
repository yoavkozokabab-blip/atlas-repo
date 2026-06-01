# Phase 104C — Compact Fact Packets

**Status:** Implemented and verified.
**Date:** 2026-06-01
**Goal:** Cut embedded JARVIS benchmark context by ≥50% using deterministic
key-value fact packets, without changing `ask.answer()` semantics or scoring.

---

## 1. Approach

| Layer | Behavior |
|---|---|
| `ask.answer()` | Unchanged prose/structured results |
| `format_jarvis_packet()` | Verbose default (`MODE` / `ANSWER` / `EVIDENCE` / `SOURCES`) |
| `compact_packets.py` | Task-specific `PACKET\|V=1\|KIND=…` serializers |
| `JARVIS_CONTEXT_PACKET_FORMAT` | `prose` (default) or `compact` |

Compact packets encode each fact once as readable `KEY=value` rows. Expanded
deterministic sidecars (`context_packet.expanded.json`) retain omitted detail when
truncation applies.

---

## 2. Packet families (task-driven)

| `task_type` | `KIND` | Notes |
|---|---|---|
| `repository_understanding` | `REPO_MAP` | Excludes `data/real_repo_corpus/**` subsystems |
| `dependency_analysis` | `DEPENDENCY` | Targeted import edges |
| `impact_analysis` | `IMPACT` | Never injects full `ARCH_RISK` ranking |
| `architectural_risk` | `ARCH_RISK` | Score components per module row |
| `contract_analysis` | `CONTRACT` | Contract-shaped findings |
| `verification_evidence` | `VERIFY` | Non-promotion caveats preserved |
| `confirmed_defect_detection` | `DEFECT_REVIEW` | Review-lead status |
| `fix_planning` | `PLAN_INPUT` | Impact facts + planning constraints |
| fallback | `RETRIEVAL` | Bounded excerpts, `CAVEAT=NO_SPECIALIZED_PACKET` |

---

## 3. Measured results (`local_jarvis`, 21 frozen tasks)

Estimator: Phase 104A `ceil(chars / 4)` on embedded JARVIS context only.

| Metric | Verbose | Compact | Change |
|---|---:|---:|---:|
| **Total tokens** | **9,839** | **4,692** | **−52.3%** |
| Per-task average | 468.5 | 223.4 | −52.3% |
| `<5,000` total gate | fail | **pass** | — |
| Tasks with ≥50% reduction | — | **10 / 21** | aggregate passes |

Baseline design target was 9,963 → 4,190 (−57.9%). Measured compact total
**4,692** clears the `<5,000` acceptance gate with headroom.

---

## 4. Run package artifacts

Per task (when using default `default_jarvis_context`):

| File | Purpose |
|---|---|
| `context_token_comparison.json` | Verbose vs compact token accounting |
| `context_packet.expanded.json` | Deterministic expanded sidecar |
| `context_packet.compact.txt` | Compact body (compact mode only) |

`manifest.json` records `context_packet_format`.

---

## 5. Verification

| Suite | Result |
|---|---|
| `test_phase104c_compact_fact_packets.py` | 7 passed |
| `test_phase103_benchmark_framework.py` | 13 passed |
| Full `builder_core/tests` | **425 passed** |

Tests cover: compact < verbose (≥50% on mini repo), caveat preservation,
`IMPACT` vs `ARCH_RISK` relevance, prose fallback, comparison sidecars, no raw
fenced prose inside packet bodies.

---

## 6. Usage

```powershell
# Default verbose packets (unchanged)
py -3 -m builder_core.benchmark_framework.cli generate --run-id my_run

# Compact packets for validation runs
$env:JARVIS_CONTEXT_PACKET_FORMAT = "compact"
py -3 -m builder_core.benchmark_framework.cli generate --run-id my_run_compact
```

---

## 7. Files

| File | Role |
|---|---|
| `benchmark_framework/compact_packets.py` | Serializers, caps, token comparison |
| `benchmark_framework/jarvis_packet.py` | Verbose formatter (unchanged API) |
| `benchmark_framework/runner.py` | Format selection + sidecars |
| `tests/test_phase104c_compact_fact_packets.py` | Regressions |

---

## 8. Non-goals (unchanged)

- No LLM summarization
- No detector / promotion / routing changes
- No benchmark scoring changes
- `compact` not promoted to default until manual quality arm passes (plan §12)
