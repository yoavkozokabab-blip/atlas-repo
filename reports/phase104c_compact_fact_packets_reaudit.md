# Phase 104C-Fix Compact Fact Packets Re-audit

Date: 2026-06-02

Verdict: **NO-GO for compact benchmark use**

## Scope

The shared worktree changed during this audit:

1. Committed Fix2 landed as `fe247f0d`.
2. A newer uncommitted truth-layer edit then changed
   `builder_core/benchmark_framework/compact_packets.py` and its Fix2 regression
   tests.

The final verdict is pinned to the settled current worktree snapshot:

```text
HEAD=fe247f0d
FORMATTER_SHA256=8AF71E934FCFC8906B2402B304C09A5375F8BC7E988E68A19558FCE5E9CD5299
INSTRUMENTATION=phase104c-truth-v1
```

The formatter hash remained stable across four consecutive checks before the
final measurement.

No production code was modified by this audit. This report is the only file
written by the audit.

## Executive Summary

The current truth-layer formatter preserves more evidence and fixes several
earlier trust defects:

- over-cap packets fail compliance honestly
- contract source rows are extracted rather than synthesized from prompt words
- ambiguous paths emit `AMBIGUOUS_REF` rather than silently selecting a path
- risk ranking and centrality packets have different substantive shapes
- defect fixture rows remain intact

It is still **NO-GO** because:

1. frozen-corpus token reduction regressed below the required `50%`
2. two frozen packets overflow their declared caps
3. `ru03_voice_path` still labels an alphabetical file inventory as execution
   stages
4. `risk03_cycles` still emits reverse duplicates for canonical cycles

## Check Results

| Check | Result | Evidence |
| --- | --- | --- |
| ARCH_RISK source references preserved | PASS | Frozen risk packets retain refs: `risk01=9`, `risk02=9`, `risk03=8`. |
| CONTRACT_SRC rows present and meaningful | PASS | Extracted contract rows include `ORIGIN=extracted`; empty prompt-only probe emits `CONTRACT_STATUS=none_extracted` and no invented source rows. |
| DEFECT fixture rows preserved | PASS | Wrong-operator and BFS packets retain buggy path, fixed path, diff summary, and refs. |
| IMPACT targets valid | PASS | `impact03_contract_facts` resolves to `builder_core/bug_intelligence/contract_facts.py`. Ambiguous `config.py` emits no selected target and an `AMBIGUOUS_REF`. |
| Caps honestly enforced | PASS | Crafted `766 > 275` packet reports noncompliant with `cap_overflow=True`. |
| OVERFLOW/TRUNCATED markers correct | PASS | Over-cap packets carry `OVERFLOW`; under-cap truncation carries `TRUNCATED` and `DETAIL`. |
| Task-specific packet shapes meaningful | FAIL | Ranking vs centrality is fixed, but voice-path and cycle packets remain misleading. |
| Frozen reduction >=50% | FAIL | `9,794 -> 5,655` estimated tokens: `42.26%`. |
| Scoring, ask, or analysis behavior changed | PASS WITH SCOPE NOTE | Truth-layer diff is formatter-focused. No scoped scoring, runner, `ask.py`, or architectural-risk implementation edit was introduced by this audit. Unrelated Builder Core WIP exists. |

## Frozen Corpus Metrics

Final stable measurement:

```text
task_count=21
verbose_tokens=9794
compact_tokens=5655
reduction_percent=42.26
meets_fifty_percent_reduction=False
meets_forty_percent_reduction=True
cap_compliance_pass=False
cap_failures=['ru01_subsystems', 'impact02_engine']
missing_refs=[]
evidence_gaps=[]
evidence_preservation_pass=True
```

Over-cap frozen packets:

```text
ru01_subsystems  REPO_MAP  381/350  cap_overflow=True
impact02_engine  IMPACT    290/275  cap_overflow=True
```

Token counts are deterministic `chars / 4` estimates, not tokenizer
measurements.

## Verified Trust Fixes

### Honest Overflow

Direct probe:

```text
cap=275
tokens=766
compliant=False
expanded.cap_compliant=False
expanded.cap_overflow=True
overflow_marker=True
```

### Prompt-Only Contract Probe

An empty index no longer receives invented contract source facts:

```text
PACKET|V=1|KIND=CONTRACT|MODE=retrieval|SCOPE=production
CONTRACT_STATUS|VALUE=none_extracted
WHY_GENERIC|TASK=contract_probe|REASON=insufficient_subject_facts
CAVEAT|CODE=USAGE_CONTRACT_NOT_PROVEN|VALUE=yes
```

### Ambiguous Path Probe

```text
RESOLVED=(None, 'ambiguous', ['a/config.py', 'b/config.py'])
TARGET|PATH=|RESOLUTION=ambiguous|STATUS=needs_verification
AMBIGUOUS_REF|REF=config.py|COUNT=2|CANDIDATES=a/config.py;b/config.py
```

## Remaining Evidence Blockers

### B1. Voice Inventory Is Mislabelled As Execution Path

`ru03_voice_path` still takes the first five indexed files under `voice/`,
`brain/`, or `actions/` and labels each row:

```text
STAGE=execution_path
```

Observed rows:

```text
VOICE|PATH=actions/__init__.py|STAGE=execution_path
VOICE|PATH=actions/app_actions.py|STAGE=execution_path
VOICE|PATH=actions/approval_inbox_actions.py|STAGE=execution_path
VOICE|PATH=actions/apps.py|STAGE=execution_path
VOICE|PATH=actions/assistant_actions.py|STAGE=execution_path
```

This is an alphabetical surface inventory, not a verified spoken-command path.

### B2. Cycle Rows Are Not Canonical

The packet reports:

```text
GRAPH|...|CYCLES=2|...
```

but emits four cycle rows:

```text
CYCLE|ID=CY1|MEMBERS=module:autonomy/__init__.py,module:autonomy/executor.py,module:autonomy/__init__.py
CYCLE|ID=CY2|MEMBERS=module:autonomy/executor.py,module:autonomy/__init__.py,module:autonomy/executor.py
CYCLE|ID=CY3|MEMBERS=module:tools/__init__.py,module:tools/registry.py,module:tools/__init__.py
CYCLE|ID=CY4|MEMBERS=module:tools/registry.py,module:tools/__init__.py,module:tools/registry.py
```

Reverse traversals must be canonicalized before packet emission.

## Tests Run

Phase 104C and Phase 104C-Fix, before the newer truth-layer edit:

```text
15 passed, 64 warnings in 198.02s
```

Combined Phase 103/104, before the newer truth-layer edit:

```text
40 passed, 64 warnings in 204.59s
```

Full Builder Core suite, against committed Fix2 before the newer truth-layer
edit:

```text
446 passed, 128 warnings in 433.96s
```

Current truth-layer quick regressions:

```powershell
py -3 -m pytest builder_core/tests/test_phase104c_fix2_compact_packet_audit_blockers.py -q -p no:cacheprovider -k "not frozen" --basetemp "C:\Users\babi2\AppData\Local\Temp\jarvis_phase104c_truth_quick_20260602"
```

Result:

```text
8 passed, 2 deselected in 42.02s
```

Current stable truth-layer frozen measurement was run directly and failed the
release gate with `42.26%` reduction and two honest cap overflows. A prior
truth-layer regression run during active edits also reported failures, so the
earlier full-suite green result must not be treated as validation of the
current uncommitted formatter.

Fresh Python launcher/worker pairs also appeared while the final audit snapshot
was being verified. They are concurrent external runs, not audit-owned
subprocesses. Their eventual results must be reviewed separately before any
commit decision.

Warnings are existing `SyntaxWarning: invalid escape sequence` messages from
the frozen real-repository corpus.

## Current Dirty Scope

Truth-layer work currently present:

```text
M  builder_core/benchmark_framework/compact_packets.py
M  builder_core/tests/test_phase104c_fix2_compact_packet_audit_blockers.py
```

There is unrelated Builder Core WIP in the shared worktree. It was not modified
by this audit and must not be staged with the truth-layer formatter accidentally.

## Required Before GO

1. Restore frozen reduction to at least `50%`.
2. Bring `ru01_subsystems` and `impact02_engine` below their declared caps.
3. Replace `ru03_voice_path` inventory rows with a real deterministic path, or
   relabel them as candidate surfaces.
4. Canonicalize `risk03_cycles` rows.
5. Run the current frozen gate, combined Phase 103/104 suite, and full Builder
   Core suite after the worktree stops changing.
