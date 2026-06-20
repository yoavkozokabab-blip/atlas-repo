# ATLAS CONTEXT-ENGINE EXCELLENCE — AUDIT & ROADMAP

**Date:** 2026-06-20 · Scope: context/memory engine only (no billing/website/auth/launch ops).
**Method:** audited the real engine (`context_pack.py`, `repository_memory.py`, `agent_integrations.py`, `api.py`, `mcp_server/runtime.py`). This is a multi-phase program; **item #1 is implemented + verified now**, the rest are sequenced with their concrete next step.

---

## ✅ #1 CONTEXT PACK QUALITY — evidence-centric — **DONE (this session)**

**Before:** each recommended file had a flat `reasons` list + raw component names ("evidence=content, path").
**After:** every recommended file carries structured, model-readable evidence:
- `relevance_score` · `selection_reason` (why it matched) · `dependency_reason` (concrete import links + counts) · `impact_reason` (predicted blast radius from fan-in) · `matched_symbols`.
- The markdown "Why these files" section now renders why/deps/impact/symbols per file. **No file appears without a stated WHY** (guaranteed fallback).
- Surfaced through MCP (`_compact_pack`) so Claude/Cursor/Codex receive the structured fields.

**Verified:** 11/11 context-pack+MCP unit tests (incl. a new evidence test), MCP smoke 12/12. Real-repo proof (`requests`, "fix retry/backoff"): HIGH confidence, 1511-token pack; e.g. `exceptions.py` → "moderate blast radius - 5 dependent module(s); flagged risk-ranked", `__init__.py` → "low inbound impact - leaf/entry".
**Code:** `Candidate.reason_by_component`, `_structured_evidence()`, assembly + renderer in `context_pack.py`; `runtime.py _compact_pack`.

---

## Sequenced plan for #2–#15 (current state → next step)

### #2 SYMBOL-LEVEL RETRIEVAL — *foundation exists; biggest remaining token win*
- **Have:** `EvidenceStore` + `file_symbol_evidence` already produce `matched_symbols` per file (symbol/qualname/kind).
- **Gap:** packs still export whole files. **Next:** add symbol *slicing* — when a file's relevance is concentrated in ≤N symbols, export only those function/class bodies (with line ranges) instead of the file. Target 50–90% further reduction. New MCP field `symbol_slices: [{name, lines, body?}]`. Highest-leverage next item.

### #3 CHANGE MEMORY — *partial*
- **Have:** `repository_memory.build_memory` (deltas, freshness, signatures).
- **Gap:** persistence of *learned* facts across scans (pitfalls, prior investigations, discoveries). **Next:** an append-only `repo_memory/learned.jsonl` keyed by repo, merged into retrieval scoring on rescan so quality compounds.

### #4 TEST-AWARE CONTEXT — *partial*
- **Have:** `related_tests` + "test near X" scoring.
- **Gap:** likely-failing-tests + missing-coverage signal. **Next:** map changed symbols → tests that exercise them; flag selected code with no covering test as `coverage_gap`.

### #5 IMPACT ANALYSIS V2 — *dependency-only today*
- **Have:** `api.change_impact_simulation` (import graph).
- **Next:** add call-graph, inheritance, config/env, entry points, API/DB boundaries to the blast-radius model; emit `hidden_impact` with evidence. (Item #1's `impact_reason` is the per-file surface for this.)

### #6 TASK-TYPE DETECTION — *partial*
- **Have:** `parse_task` extracts actions (`add/fix/refactor/test`).
- **Next:** classify into {bug_fix, feature, refactor, perf, security, arch, docs} and switch retrieval weights per type (e.g., security → boundaries+auth; perf → hot paths; bug → root-cause mode #10).

### #7 ARCHITECTURE MEMORY — *partial*
- **Have:** subsystems/clusters in memory + `atlas_get_architecture`.
- **Next:** persist architecture snapshots and diff them to detect drift / new coupling / growing god-modules / subsystem erosion.

### #8 MD FILE QUALITY (AGENTS/CLAUDE/CURSOR/CODEX) — *exists, needs structure*
- **Have:** `agent_integrations.export_for_state`.
- **Next:** world-class template (purpose/architecture/conventions/workflows/testing/dangerous-areas/common-mistakes) with a **fenced "Atlas-generated facts" block** separated from a human-maintained policy block so regeneration never clobbers user edits.

### #9 REPOSITORY TIMELINE — *missing*
- **Next:** mine git history for subsystem creation, dependency/architecture shifts; enable "how this repo evolved" narration. (Read-only history analysis.)

### #10 ROOT CAUSE MODE — *missing as a mode*
- **Next:** new MCP tool `atlas_root_cause(error|stacktrace|log)` → rank likely root-cause files/functions with confidence + supporting evidence, reusing symbol evidence + impact graph.

### #11 MCP EXPERIENCE — *partial*
- **Have:** Claude-config discovery; scan-gating.
- **Next:** auto-detect active repo (cwd/git root), active branch, and recent changes so the agent needs near-zero manual steps.

### #12 TOKEN-EFFICIENCY BENCHMARK — *ad hoc*
- **Have:** per-pack `token_estimate`; prior benchmark JSONs.
- **Next:** standing harness: raw-repo tokens vs pack tokens → compression ratio + precision/recall, persisted as a leaderboard across repos.

### #13 HALLUCINATION REDUCTION — *largely satisfied by #1*
- **Have now:** evidence + confidence + reasons on every file (#1); MCP redaction; trust/refusal in memory.
- **Next:** enforce "no architectural claim without evidence" in the architecture/summary tools too (attach evidence quality to every claim).

### #14 COMPETITIVE AUDIT — *informs priorities*
- vs Aider/Cursor-index/Claude Code/Codex/Sourcegraph/Continue/OpenHands: Atlas's edge = evidence-centric + impact-aware memory over MCP. Their edges Atlas lacks: symbol-precise slicing (#2), call-graph impact (#5), git-history understanding (#9). Implement only those that raise answer quality / cut tokens — i.e., #2, #5, #9.

### #15 NORTH STAR ("Fix authentication" → files+symbols+tests+arch+impact+plan+confidence, minimum tokens)
- **Closest enablers:** #1 (done) + #2 (symbols) + #5 (impact v2) + #6 (task-type) + `plan_change`. **Next concrete step toward it:** wire #2 symbol slices into the export so the North-Star answer is symbol-precise.

---

## Recommended next order (by quality/token leverage)
**#2 symbol slicing → #6 task-type → #10 root-cause → #5 impact v2 → #4 test-aware → #8 MD files → #3/#7 memory → #12 benchmark → #9 timeline → #11 MCP UX.**
Rationale: #2 is the largest remaining token reduction and directly advances the North Star; #6/#10/#5 most raise answer quality and change-prediction accuracy.
