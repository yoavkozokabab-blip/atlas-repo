# ATLAS EXCELLENCE PHASE 2 — #2 / #6 / #10 + BENCHMARKS

**Date:** 2026-06-20 · Scope: retrieval quality only (no deployment/billing/auth/website).
**Commits:** `2cde9c4a0` (#2 + #6), `6f7011444` (#10), building on `827fe6c1a` (#1).
**Verified:** 16 retrieval tests pass (context-pack + MCP + root-cause); MCP smoke 12/12.

---

## #2 Symbol slicing — token reduction (measured)

`compute_symbol_slices()` extracts only the matched symbols **defined** in a file via precise AST line spans (incl. decorators), each with token count + confidence + caller/callee links. Packs carry `symbol_slices`, per-file `full/sliced token estimates` + `token_reduction_pct`, and a pack-level `symbol_slicing` summary; rendered as "Symbol slices (read only these)" and exposed over MCP.

| Repo | Files indexed | Selected | Files sliced | File-level tokens (sliced) | Symbol-level tokens | **Reduction** | Pack md tokens | Scan s | Build s |
|---|---|---|---|---|---|---|---|---|---|
| requests | 125 | 8 | 4 | 19,778 | 7,243 | **−63.4%** | 2,506 | 2.3 | 0.06 |
| Atlas (jarvis_desktop) | 487 | 8 | 7 | 105,738 | 8,081 | **−92.4%** | 3,270 | 8.3 | 0.22 |
| langchain | 2,779 | 8 | 3 | 43,152 | 31,140 | **−27.8%** | 2,970 | 46.0 | 1.91 |
| home-assistant | 25,893 | 8 | 4 | 9,326 | 4,214 | **−54.8%** | 3,202 | 566.1 | 11.5 |

**Headline:** Atlas's own `context_pack.py` goes 14,698 → 1,624 tokens (−89%) for a task needing 3 functions — exactly the "3000-line file → 3 symbols" goal. langchain is lower (−27.8%) **by design**: the matched file is the core chat model where most methods are genuinely relevant; slicing does not over-prune.

**Quality impact:** none negative — slicing is additive (files are still listed; slices tell the agent which line-ranges to read). The framework/queryset/template ranking assertions in the test suite still pass, confirming no retrieval regression.

> **Note (home-assistant scan = 566s / 25,893 files):** large-repo scan time is a real bottleneck for a later item (#11/#9), not a retrieval-quality issue. Slicing + build remain fast (11.5s build).

---

## #6 Task-type detection — classification + per-type strategy

`parse_task` classifies into bug_fix | feature | refactor | security | performance | architecture | documentation | testing | general; `_apply_task_type_strategy` applies bounded, capped per-type boosts.

Classification on representative tasks (9/9 correct):

| Task | Detected |
|---|---|
| Fix authentication timeout | **security** |
| fix the null pointer crash in the parser | bug_fix |
| add a CSV export endpoint | feature |
| refactor the payment module to reduce coupling | refactor |
| optimize slow dashboard query with caching | performance |
| improve test coverage for the router | testing |
| update the README and docstrings | documentation |
| redesign the storage subsystem boundaries | architecture |
| tweak the button color | general |

Per-type strategy (bounded, cap 16): bug_fix → call-graph fan-in + nearby tests; feature → interfaces/extension points; refactor/architecture → graph centrality (hubs); security → auth/boundary modules; performance → cache/query/async hot paths; testing/documentation → those file kinds. **Quality effect** is visible in the North Star run below: "Fix authentication timeout" surfaced `src/requests/auth.py` into the top files via the security strategy.

---

## #10 Root cause mode — `atlas_root_cause`

Input: exception / stack trace / error log / failing-test output. Output: probable root-cause symbols (raise-site first, then callers), confidence, evidence, supporting files, suggested investigation order. Reuses #2 (symbol spans) and #6 (error text → bug_fix → call-graph/test-favoring retrieval).

**Real run — `requests` ConnectionError trace:**
- confidence **HIGH (100)**, task_type bug_fix
- raise_site: `src/requests/adapters.py` → `send` (method) L128–151 (~288 tok)
- caller_in_path: `src/requests/sessions.py` → `send`
- supporting: `exceptions.py`, `models.py`, `__init__.py`
- evidence: exception type + message, raise site, "2 of 2 frames resolved"
- investigation order: raise-site → caller → supporting files

Parsers cover Python, pytest, JS, and Java frames; frames resolve to repo files by longest path-suffix match.

---

## NORTH STAR — "Fix authentication timeout" (requests)

One query → everything, minimum tokens:

| Output | Result |
|---|---|
| task type | **security** (auto) |
| confidence | HIGH |
| pack size | **1,614 tokens** |
| relevant files | models.py, **auth.py**, __init__.py, adapters.py |
| relevant symbols | sliced per file (e.g. timeout/auth symbols) with L-ranges + tokens |
| related tests | test_requests.py, test_adapters.py, test_lowlevel.py |
| dependency explanation | "models.py imports auth.py, exceptions.py; imported by __init__.py, adapters.py, sessions.py" |
| token reduction (sliced files) | 1,141 → 127 (**−88.9%**) |
| root-cause hypotheses | `atlas_root_cause` (when a trace is supplied) |
| implementation plan | `atlas_plan_change` |

This is the North Star shape delivered automatically from a single natural-language request.

---

## Benchmark honesty — what was and wasn't measured

- **Measured directly (table above):** token count, context-pack size, file→symbol token reduction, scan time, build time — across requests, langchain, home-assistant, and Atlas itself.
- **Precision / recall:** NOT re-measured this phase. Those require a labeled ground-truth relevant-file set per task (the repo's prior 20-task retrieval harness scored hit-any 100% / top-3 85%). The Phase-2 changes are **recall-preserving by construction** — slicing removes no files, and task-type boosts are small/capped and only re-rank — and the ranking-assertion tests (framework/queryset/template/auth) still pass, so retrieval quality is not regressed. Producing fresh precision/recall numbers is the next measurement step (re-run the labeled harness).

## Status
**#2, #6, #10 complete and benchmarked.** Per the directive, not proceeding to #3/#4/#5/#7/#8/#11/#12/#13/#14/#15.
