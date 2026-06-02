# Phase 104C: Compact Fact Packets

**Status:** Design only  
**Date:** 2026-06-01  
**Scope:** Compact JARVIS context packets for the frozen Phase 103 manual benchmark task set  
**Constraint:** No implementation, no detector changes, no benchmark-task changes, no reasoning changes

## 1. Goal

Reduce the embedded JARVIS context from approximately `9,963` estimated tokens
to fewer than `5,000` estimated tokens while preserving the information a
developer or Codex needs to answer the same question safely.

This phase does not remove evidence. It replaces repeated narrative text with a
deterministic, line-oriented fact packet:

```text
PACKET_V=1|KIND=ARCH_RISK|MODE=bottleneck|SCOPE=production
MODULE=config.py|RANK=1|SCORE=212.8|FAN_IN=206|FAN_OUT=6|LOC=2181|TESTED=yes|RISK=high
```

Human-readable prose reports remain available. Compact packets are the agent
injection format.

## 2. Measured Baseline

The baseline is the first Phase 103 manual package:

```text
reports/benchmarks/phase103_manual_20260601_184247/
```

It contains 21 `jarvis_plus_codex` prompt packages. Token figures use the
existing deterministic estimator:

```text
estimated_tokens = ceil(character_count / 4)
```

| Metric | Baseline |
|---|---:|
| Embedded JARVIS context | `9,963` estimated tokens |
| Average per task | `474.4` estimated tokens |
| Required maximum | `<5,000` estimated tokens |
| Required reduction | `>49.8%` |
| Required average maximum | `<238.1` estimated tokens per task |

### 2.1 Section distribution

| Current section | Estimated tokens | Share |
|---|---:|---:|
| `EVIDENCE` prose | `4,903` | `49.2%` |
| `ANSWER` prose | `3,032` | `30.4%` |
| `SOURCES` | `1,197` | `12.0%` |
| `ASK_QUALITY` | `546` | `5.5%` |
| Labels and `MODE` | `285` | `2.9%` |
| **Total** | **`9,963`** | **`100.0%`** |

The largest opportunity is not lossy compression. It is removing duplicate
representations of the same fact.

### 2.2 Largest packets

| Task | Current tokens | Primary cause |
|---|---:|---|
| `impact01_config` | `808` | Receives a full architectural-risk ranking instead of a targeted impact packet |
| `risk01_ranking` | `808` | Ranking prose and evidence repeat score breakdowns |
| `risk02_centrality_vs_risk` | `808` | Receives the same full ranking packet as `risk01_ranking` |
| `verify01_evidence_types` | `741` | Long retrieval excerpts and repeated paths |
| `ru01_subsystems` | `611` | Long subsystem explanations and corpus-path pollution |
| `defect02_bfs_queue` | `582` | Retrieval prose instead of concise semantic evidence |
| `ru03_voice_path` | `580` | Long excerpts instead of a compact execution-path packet |
| `defect01_wrong_operator` | `525` | Generic retrieval excerpts instead of fixture-specific facts |

### 2.3 Duplicate packet groups

| Identical packet size | Tasks |
|---:|---|
| `808` tokens | `impact01_config`, `risk01_ranking`, `risk02_centrality_vs_risk` |
| `401` tokens | `impact03_contract_facts`, `plan01_config`, `risk03_cycles` |

Related tasks may share source facts. They should not receive the same narrative
packet when the requested decision is different.

## 3. Audit Findings

### 3.1 Answer prose repeats evidence prose

The current benchmark packet formatter serializes:

```text
MODE
ANSWER
up to 12 EVIDENCE lines
up to 12 SOURCES
ASK_QUALITY percentages
```

For architectural risk, `ANSWER` lists ranked modules and score components.
`EVIDENCE` repeats each ranking and its diagnostics. `SOURCES` repeats paths
already embedded in both sections.

The compact packet must emit one fact row per module and one reference row per
source.

### 3.2 Evidence prose repeats paths and explanations

Evidence currently carries useful facts inside sentences:

```text
rank 1: config total=212.8 breakdown={...}
fan-in=206 unique importers -> +206.0
```

The same information is smaller and easier to inspect as:

```text
MODULE=config.py|RANK=1|SCORE=212.8|FAN_IN=206|FAN_IN_SCORE=206.0
```

### 3.3 Subsystem explanations repeat stable structure

Repository-understanding packets repeatedly explain:

```text
production file(s)
entry files
dependencies
```

Those labels should be encoded once per row:

```text
SUBSYSTEM=voice|ROLE=production_code|FILES=42|ENTRY=voice/voice_loop.py|DEPS=core,brain
```

Architecture packets must also reject `data/real_repo_corpus/**` as product
subsystem evidence. Compactness does not excuse irrelevant context.

### 3.4 Risk explanations repeat scoring vocabulary

Risk packets spend tokens restating fixed scoring labels for every module:

```text
fan-in
fan-out
cycles
loc
untested
test
contract
static
```

Use stable short keys in one row. Retain the score components because they are
trust evidence, not decoration.

### 3.5 Narrative snippets can break envelope parsing

Two baseline retrieval packets contain nested Markdown fences. A naive parser
can mistake an embedded fence for the end of the JARVIS context block.

Compact packets should not embed arbitrary fenced prose. References and
bounded, escaped excerpts are safer and smaller.

## 4. Design Principles

1. Encode each factual atom once.
2. Preserve evidence provenance, uncertainty, and degraded-state warnings.
3. Prefer stable keys over repeated prose.
4. Keep packets readable without a decoder tool.
5. Keep ordering deterministic.
6. Separate compact agent packets from expanded human reports.
7. Do not change `ask.answer()` semantics or legacy prose output.
8. Do not add LLM summarization.
9. Do not elevate confidence or confirmation status during compression.
10. Treat missing facts as unknown, never as false.

## 5. Packet Envelope

Use a newline-delimited, key-value format. It is more prompt-readable than
minified JSON and avoids JSON punctuation overhead.

```text
PACKET_V=1|KIND=IMPACT|MODE=impact|SCOPE=production
TARGET=builder_core/bug_intelligence/engine.py
IMPACT=DIRECT:8|TRANSITIVE:3|RISK:low|CONFIDENCE:unknown
CAVEAT=IMPACT_INCOMPLETE|UNVERIFIED=78
REF=R1|PATH=builder_core/bug_intelligence/engine_benchmark.py|LINE=210
SRCQ=PROD:100|ARCH:0|REPORT:0|BENCH:0
DETAIL=context_packet.expanded.json|SHA256=<digest>
```

### 5.1 Required envelope fields

| Field | Purpose |
|---|---|
| `PACKET_V` | Stable format version |
| `KIND` | Packet serializer selected for this task |
| `MODE` | Existing Builder Core answer mode |
| `SCOPE` | Scope such as `production`, `repository`, or `fixture` |
| Fact rows | Task-specific facts |
| `REF` rows | Deduplicated source paths and optional lines |
| `CAVEAT` rows | Uncertainty, degraded state, unresolved edges, or non-promotion status |
| `SRCQ` | Compact source-quality distribution |
| `TRUNCATED` | Emitted count and full count when any detail is omitted |
| `DETAIL` | Expanded deterministic sidecar path and digest |

`TRUNCATED` is required only when the injected packet omits detail. `DETAIL` is
required whenever an expanded sidecar exists.

### 5.2 Escaping

Values must be single-line ASCII-safe strings:

- replace newlines with `\n`;
- escape `|` as `\|`;
- escape backslashes as `\\`;
- cap excerpt values before serialization;
- never emit raw Markdown fences.

Paths remain repository-relative.

### 5.3 Deterministic ordering

Sort rows by:

1. semantic priority;
2. rank or evidence strength;
3. repository-relative path;
4. line number;
5. stable fact ID.

The same repository commit, task, index, and formatter version must produce
byte-identical packets.

## 6. Packet Families

### 6.1 Repository understanding

```text
PACKET_V=1|KIND=REPO_MAP|MODE=architecture|SCOPE=production
SUBSYSTEM=builder_core|ROLE=production_code|FILES=84|ENTRY=builder_core/cli.py|DEPS=
SUBSYSTEM=voice|ROLE=production_code|FILES=42|ENTRY=voice/voice_loop.py|DEPS=brain,core
REF=R1|PATH=README_ARCHITECTURE.md
SRCQ=PROD:75|ARCH:25|REPORT:0|BENCH:0
```

Preserve:

- subsystem name;
- role;
- file count;
- entry files;
- dependencies;
- source quality;
- architecture references.

Do not emit repeated prose such as "production file(s)" or long retrieval
snippets.

### 6.2 Dependency analysis

```text
PACKET_V=1|KIND=DEPENDENCY|MODE=dependency|SCOPE=production
TARGET=builder_core/bug_intelligence/engine.py
EDGE=E1|FROM=builder_core/cli.py|TO=builder_core/bug_intelligence/engine.py|LINE=18
EDGE=E2|FROM=builder_core/benchmark.py|TO=builder_core/bug_intelligence/engine.py|LINE=11
UNRESOLVED=COUNT:3|REASON:symbol_not_found
REF=R1|PATH=builder_core/cli.py|LINE=18
```

Preserve:

- direction;
- edge kind;
- source line;
- unresolved reason distribution;
- graph degradation caveats.

### 6.3 Impact analysis

```text
PACKET_V=1|KIND=IMPACT|MODE=impact|SCOPE=production
TARGET=config.py
IMPACT=DIRECT:206|TRANSITIVE:14|RISK:high|CONFIDENCE:medium
DEPENDENT=R1|KIND:direct
CAVEAT=IMPACT_INCOMPLETE|UNVERIFIED=7
REF=R1|PATH=core/runtime.py|LINE=12
```

Preserve:

- target;
- direct and transitive counts;
- risk;
- confidence;
- top proven dependent edges;
- unverified count;
- incomplete-impact warning.

Do not inject a full global risk ranking for a targeted impact question.

### 6.4 Architectural risk

```text
PACKET_V=1|KIND=ARCH_RISK|MODE=bottleneck|SCOPE=production
MODULE=config.py|RANK=1|SCORE=212.8|FAN_IN=206|FAN_OUT=6|CYCLES=0|LOC=2181|TESTED=yes|CONTRACT=0|STATIC=0|RISK=high
MODULE=core/logger.py|RANK=2|SCORE=145.0|FAN_IN=144|FAN_OUT=1|CYCLES=0|LOC=26|TESTED=yes|CONTRACT=0|STATIC=0|RISK=high
GRAPH=MODULES:412|PAIRS:1830|CYCLES:0|DEGRADED:no
REF=R1|PATH=config.py
```

Preserve:

- rank;
- total score;
- every score component;
- unique fan-in semantics;
- canonical cycle count;
- graph degradation state;
- risk versus centrality distinction.

The ranking packet may retain all 12 ranked modules when it stays under its
hard cap. It should not repeat prose diagnostics that are directly recoverable
from the structured fields.

### 6.5 Contract facts

```text
PACKET_V=1|KIND=CONTRACT|MODE=contract|SCOPE=production
SYMBOL=parse_config
CONTRACT=C1|TYPE=return_shape|VALUE=dict|STRENGTH=fact|REF=R1
CONTRACT=C2|TYPE=raises|VALUE=ValueError|STRENGTH=fact|REF=R2
CAVEAT=USAGE_CONTRACT_NOT_PROVEN
REF=R1|PATH=config.py|LINE=41
REF=R2|PATH=config.py|LINE=55
```

Preserve:

- contract type;
- source;
- fact strength;
- conflicts;
- unknown usage-contract state;
- promotion quarantine status.

### 6.6 Verification evidence

```text
PACKET_V=1|KIND=VERIFY|MODE=verification|SCOPE=finding
FINDING=F1|RULE=inconsistent_return|STATUS=review_lead|PROMOTION=blocked
EVIDENCE=V1|TYPE=assertion|STRENGTH=E2|REF=R1
BLOCKER=B1|TYPE=missing_usage_contract
CAVEAT=NON_PROMOTING_EVIDENCE
REF=R1|PATH=tests/test_config.py|LINE=27
```

Preserve:

- finding identity;
- evidence type;
- evidence strength;
- source;
- promotion blockers;
- non-promotion rules.

### 6.7 Defect review

```text
PACKET_V=1|KIND=DEFECT_REVIEW|MODE=python_analysis|SCOPE=fixture
TARGET=python_programs/breadth_first_search.py
FINDING=F1|RULE=bfs_queue_semantics|KIND=semantic|SEVERITY=high|STATUS=review_lead|LINE=12
FACT=F1.1|TYPE=queue_operation|VALUE=pop_last|REF=R1
FACT=F1.2|TYPE=expected_semantics|VALUE=fifo
CAVEAT=REVIEW_LEAD_NOT_CONFIRMED
REF=R1|PATH=python_programs/breadth_first_search.py|LINE=12
```

Preserve:

- rule;
- semantic or pattern kind;
- severity;
- line;
- concrete invariant;
- review-lead versus confirmed-defect status;
- test expectations when available.

### 6.8 Fix-planning input

```text
PACKET_V=1|KIND=PLAN_INPUT|MODE=impact|SCOPE=production
TARGET=config.py
IMPACT=DIRECT:206|TRANSITIVE:14|RISK:high|CONFIDENCE:medium
CONSTRAINT=C1|TYPE=preserve_public_contract
VERIFY=V1|TYPE=targeted_tests|REF=R1
REF=R1|PATH=tests/test_config.py
```

The packet supplies facts for planning. It must not generate a repair or imply
that a repair has been verified.

### 6.9 Retrieval fallback

```text
PACKET_V=1|KIND=RETRIEVAL|MODE=retrieval|SCOPE=repository
QUERY=voice command path
HIT=H1|REF=R1|SCORE=8|EXCERPT=route voice commands through the supervised router
REF=R1|PATH=voice/voice_loop.py|LINE=140
CAVEAT=NO_SPECIALIZED_PACKET
```

Preserve:

- query;
- ranked references;
- bounded excerpts;
- source lines where available;
- explicit fallback caveat.

Excerpt caps:

| Field | Maximum |
|---|---:|
| One excerpt | `160` characters |
| Retrieval hits | `5` |
| Total excerpt characters | `500` |

## 7. Information-Preservation Contract

Compression passes only if all of the following survive:

| Information class | Preservation rule |
|---|---|
| Primary answer facts | Encode each unique fact once |
| Evidence | Keep fact type, value, strength, and source reference |
| Provenance | Keep repository-relative path and line where available |
| Confidence | Keep explicit confidence or `unknown` |
| Scope | Keep graph, repository, fixture, or production scope |
| Uncertainty | Keep caveats, unresolved counts, degraded states, and incomplete-analysis warnings |
| Safety state | Keep review-lead, confirmed, quarantined, and non-promoting status |
| Truncation | Emit full count, emitted count, and expanded sidecar |
| Source quality | Keep compact production, architecture, report, and benchmark percentages |

Expanded sidecars preserve the complete deterministic result:

```text
context_packet.compact.txt
context_packet.expanded.json
```

The compact packet is an index into the expanded facts, not an unsupported
summary. A sidecar digest makes the relationship auditable.

## 8. Budget Model

The design target is `4,190` estimated tokens across the same 21 tasks. This is
a `57.9%` reduction from the measured `9,963` baseline and leaves `810` tokens
of headroom below the `<5,000` acceptance gate.

| Task | Current | Compact target | Reduction |
|---|---:|---:|---:|
| `contract01_sources` | `312` | `190` | `122` |
| `contract02_inconsistent_return` | `331` | `190` | `141` |
| `defect01_wrong_operator` | `525` | `180` | `345` |
| `defect02_bfs_queue` | `582` | `200` | `382` |
| `defect03_gate` | `327` | `180` | `147` |
| `dep01_engine_edges` | `329` | `190` | `139` |
| `dep02_ask_edges` | `514` | `220` | `294` |
| `dep03_evidence_chain` | `339` | `190` | `149` |
| `impact01_config` | `808` | `210` | `598` |
| `impact02_engine` | `110` | `110` | `0` |
| `impact03_contract_facts` | `401` | `190` | `211` |
| `plan01_config` | `401` | `180` | `221` |
| `plan02_verification` | `297` | `180` | `117` |
| `risk01_ranking` | `808` | `300` | `508` |
| `risk02_centrality_vs_risk` | `808` | `220` | `588` |
| `risk03_cycles` | `401` | `180` | `221` |
| `ru01_subsystems` | `611` | `240` | `371` |
| `ru02_builder_core_map` | `475` | `220` | `255` |
| `ru03_voice_path` | `580` | `220` | `360` |
| `verify01_evidence_types` | `741` | `230` | `511` |
| `verify02_non_promotion` | `263` | `170` | `93` |
| **Total** | **`9,963`** | **`4,190`** | **`5,773`** |

### 8.1 Packet-class caps

| Packet family | Soft target | Hard cap |
|---|---:|---:|
| Repository understanding | `220` | `350` |
| Dependency analysis | `200` | `325` |
| Impact analysis | `180` | `275` |
| Architectural risk | `260` | `400` |
| Contract facts | `190` | `300` |
| Verification evidence | `220` | `350` |
| Defect review | `190` | `300` |
| Fix-planning input | `180` | `275` |
| Retrieval fallback | `200` | `325` |

When a packet exceeds its hard cap:

1. preserve header, scope, caveats, and quality;
2. preserve highest-priority facts;
3. deduplicate references;
4. emit `TRUNCATED=<row_type>:<emitted>/<total>`;
5. emit `DETAIL=<sidecar>|SHA256=<digest>`;
6. fail generation if mandatory safety fields do not fit.

## 9. Compression Strategy

### 9.1 Replace prose, do not summarize prose

Do not run a text summarizer over current output. Build packet rows directly
from structured result fields.

| Current representation | Compact representation |
|---|---|
| Answer paragraph | Packet header and task-specific fact rows |
| Evidence sentence | Structured fact row with `REF` |
| Repeated source path | One deduplicated `REF` row |
| Repeated quality labels | One `SRCQ` row |
| Repeated caveat sentence | One stable `CAVEAT` code |
| Long retrieval excerpt | Bounded escaped `EXCERPT` |

### 9.2 Separate display from injection

Keep:

```text
ask.answer() -> existing readable result
```

Add later:

```text
ask.answer() -> compact packet serializer -> agent prompt
             -> expanded deterministic sidecar
```

The CLI can continue to show human-readable prose. Phase 104C changes context
packaging only.

### 9.3 Deduplicate with stable references

Deduplicate source references by:

```text
(repository-relative path, line number, optional symbol)
```

Deduplicate evidence atoms by:

```text
(fact type, normalized value, source reference, strength)
```

Do not deduplicate two facts merely because their prose is similar.

### 9.4 Keep task-specific packet selection

Packet selection must follow the question:

| Question | Required packet |
|---|---|
| "What are the architectural risks?" | `ARCH_RISK` |
| "What breaks if config.py changes?" | `IMPACT` |
| "Which folders are production code?" | `REPO_MAP` |
| "What evidence supports this finding?" | `VERIFY` |
| "Explain the BFS bug." | `DEFECT_REVIEW` |

A generic ranking or retrieval packet is an explicit fallback, not an invisible
substitute.

## 10. Validation Plan

### 10.1 Determinism

- Generate each packet twice from the same repository commit and task set.
- Assert byte-identical compact packets.
- Assert byte-identical expanded sidecars.
- Assert stable `SHA256` values.

### 10.2 Token gates

- Assert total compact context across the frozen 21-task package is `<5,000`.
- Assert reduction from `9,963` is at least `50%`.
- Assert average compact packet is `<238.1` tokens.
- Assert each packet class respects its hard cap.
- Assert any capped packet emits `TRUNCATED` and `DETAIL`.

### 10.3 Preservation

- Compare structured atoms before and after rendering.
- Assert every mandatory fact is represented once.
- Assert every emitted evidence fact has a valid `REF`.
- Assert caveats survive compression.
- Assert degraded states survive compression.
- Assert unknown confidence remains `unknown`.
- Assert no review lead becomes confirmed.
- Assert no quarantined detector appears promoted.

### 10.4 Relevance

- Assert `impact01_config` receives `KIND=IMPACT`, not a full risk ranking.
- Assert risk and impact prompts no longer share identical packets.
- Assert `data/real_repo_corpus/**` does not appear as product subsystem evidence.
- Assert fixture defect packets cite the requested fixture.
- Assert retrieval fallback packets declare `CAVEAT=NO_SPECIALIZED_PACKET`.

### 10.5 Envelope safety

- Assert raw Markdown fences never appear inside compact packets.
- Assert escaped pipes and newlines round-trip.
- Assert packets parse without heuristic fence matching.
- Assert source paths remain repository-relative.

### 10.6 Quality check

Run the existing Phase 103 manual comparison with three arms:

| Arm | Purpose |
|---|---|
| `codex_alone` | External baseline |
| `jarvis_plus_codex_prose` | Existing JARVIS baseline |
| `jarvis_plus_codex_compact` | Phase 104C candidate |

The compact arm passes only when token reduction holds without lower task
success, evidence quality, or answer completeness.

## 11. Likely Future Implementation Surface

This report does not implement these changes. A later implementation should be
small and additive.

| File | Likely change |
|---|---|
| `builder_core/benchmark_framework/jarvis_packet.py` | Add packet-family serializers and deterministic envelope |
| `builder_core/benchmark_framework/runner.py` | Select compact packet mode and emit expanded sidecars |
| `builder_core/benchmark_framework/tokens.py` | Record packet-family and per-section token totals |
| `builder_core/benchmark_framework/schema.py` | Add backwards-compatible packet metadata |
| `builder_core/benchmark_framework/summary.py` | Report prose-versus-compact reductions |
| `builder_core/repository_understanding.py` | Correct corpus-code role handling before architecture packet generation |
| `builder_core/ask.py` | Expose existing structured facts to serializers without removing prose output |
| `builder_core/tests/test_phase104c_compact_fact_packets.py` | Add determinism, token, preservation, relevance, and envelope tests |

Current Phase 104B-shaped profiling work in the local worktree is separate
concurrent work. Phase 104C should consume its measurements after review, not
silently absorb or rewrite that work.

## 12. Rollback Plan

Introduce compact packets behind an explicit formatter setting:

```text
JARVIS_CONTEXT_PACKET_FORMAT=prose|compact
```

Initial default:

```text
prose
```

Validation mode:

```text
compact
```

Promote `compact` to the default only after the frozen-task token gate and
quality checks pass. Rollback is a formatter setting change. Existing
`ask.answer()` results, detectors, routing, and human-readable reports remain
unchanged.

## 13. Acceptance Criteria

Phase 104C implementation is complete only when:

1. The frozen 21-task embedded JARVIS context total is `<5,000` estimated tokens.
2. The reduction from `9,963` is at least `50%`.
3. Compact packets preserve facts, references, caveats, confidence, and scope.
4. Expanded deterministic sidecars retain omitted detail.
5. Risk packets preserve score components and risk-versus-centrality evidence.
6. Verification packets preserve non-promotion rules.
7. Retrieval packets never embed raw fenced prose.
8. Product architecture packets exclude corpus pollution.
9. Existing prose output remains available.
10. No detector, benchmark, promotion, router, browser, voice, trading, or
    website behavior changes.

## 14. Recommendation

Proceed with compact packets as a packaging layer, not an intelligence rewrite.

The measured baseline has enough duplicate narrative overhead to reach the
target without sacrificing evidence. The budgeted design lands at `4,190`
estimated tokens, leaving room for preservation metadata while still clearing
the `<5,000` gate.
