# Phase 89 — Value-Aware Data Flow & Taint Core

**Status:** Implemented and verified
**Date:** 2026-05-30
**Scope:** First value-aware intraprocedural analysis core + a local taint-based
security MVP. Additive; no rule rewire of the benchmark path; no recall chasing.

---

## 0. TL;DR

- Built `valueflow.py`: an intraprocedural, value-aware data-flow core that emits
  **facts** (CFG, reaching definitions, branch conditions, returns, container
  state, nullability, integer intervals, taint) for one Python function.
- Built `security.py`: turns taint/sink facts into **findings** with a full
  review schema (id, severity, confidence, category, file, line, explanation,
  evidence, why-this-might-be-wrong, next-verification-step). Six security
  categories + null-dereference.
- Added CLI `security-scan` and enriched `analyze-file` with
  SUMMARY / FINDINGS / EVIDENCE / SOURCES / NEXT VERIFICATION STEPS.
- **No regression:** QuixBugs 100% / 30% and Holdout 100% / 16.7% unchanged
  (the security/value core is a separate path and does not touch the semantic
  benchmark). Synthetic security precision 100%.

---

## 1. Architecture

```
text ──▶ valueflow.analyze_source ──▶ per-function FACTS
                                       (cfg, reaching defs, branch conds,
                                        returns, container state, nullability,
                                        intervals, taint, sink/source obs,
                                        null-deref value findings)
                                              │
                          ┌───────────────────┴───────────────────┐
                          ▼                                        ▼
            security.analyze_source                       (future) rule rewire
            (taint/sink facts ──▶ Finding89)              consumers of value facts
                          │
              CLI: security-scan / analyze-file
```

**Two analyzers, one model.** `valueflow.py` is the single value-fact provider.
`security.py` is the first consumer. The existing bug detectors and the
QuixBugs/holdout benchmark path (`python_analysis` + `semantic_reasoning`) are
**untouched**, which is why precision/recall are unchanged — the value core is
purely additive in this phase. (Folding the older detectors onto this core is
the planned next step; doing it here would risk the benchmark.)

**How the facts are produced.**
- **Reaching definitions** — a structured walk over the function body that
  threads a per-variable def-set through assignments, joining at branch merges
  and over-approximating loops (union with the back-edge). Keyed by use-site.
- **Minimal CFG** — a best-effort basic-block builder (entry / branch / merge /
  loop-header / sequential blocks with edges); degrades to a single block on
  anything it cannot model, never crashing.
- **Value lattices** — a flow-sensitive forward pass with an abstract
  environment `AV{null, taint, interval, container}` per variable. Branch
  conditions **narrow** the environment (`if x is not None:` makes `x`
  not-None inside the true branch; `if x:` likewise). Paths **join** at merges
  (least-upper-bound → "maybe"/"unknown" when paths disagree). Loops are
  analyzed once for finding detection (conservative).

---

## 2. Facts emitted (per function)

| # | Fact | Values / shape |
|---|---|---|
| 1 | `cfg_blocks` | basic blocks `{id, kind, lines, succ}` |
| 2 | `definitions` | assignments + params `{name, line, kind}` |
| 3 | `reaching_definitions` | `{use_line: {var: [def_lines]}}` |
| 4 | `uses` | `{name, line}` |
| 5 | `branch_conditions` | `{line, test, vars}` |
| 6 | `returns` | `{line, expr, kind, is_constant}` |
| 7 | `container_state` | per var: `state ∈ {maybe_empty, non_empty, unknown}` + `grows / shrinks / consumed` |
| 8 | `nullability` | per var: `definitely_none / definitely_not_none / maybe_none / unknown` (+ flagged derefs) |
| 9 | `intervals` | per var: `exact / lower / upper / upper_expr / unknown` (e.g. `range(len(x))` → `lower 0, upper_expr "len(x) - 1"`) |
| 10 | `taint` | per var summary `source / propagated / sanitized / untainted`; plus `source_observations` and `sink_observations` |

Taint model:
- **Sources:** function parameters (untrusted by default), `input()`,
  `os.getenv` / `os.environ[...]`, `sys.argv`, `request.*`, and IO reads
  (`.read()/.recv()`).
- **Propagation:** assignment, `BinOp`, f-strings, `.format`/`%`, container
  literals, attribute/subscript of a tainted base, and `open(tainted)` →
  tainted file object.
- **Sanitizers (obvious):** `int()/float()/len()/bool()`, `shlex.quote`,
  `html.escape`, `os.path.basename`.

---

## 3. Security findings supported

Detected as **facts first**, promoted to findings only at high confidence.

| Category | Trigger | Severity / Confidence |
|---|---|---|
| `code_injection` | `eval` / `exec` on tainted value | critical / high |
| `command_injection` | `subprocess.*` / `os.system` tainted **or** `shell=True` | high / high |
| `sql_injection` | tainted string built (concat / f-string / %) then `execute()` | high / high |
| `path_traversal` | `open()` on tainted, unsanitized path | medium / medium |
| `unsafe_deserialization` | `pickle/marshal.load*` on tainted; `yaml.load` without safe Loader | high / high–medium |
| `weak_crypto` | `hashlib.md5` / `sha1` / `hashlib.new("md5"/"sha1")` | medium / medium |
| `null_dereference` (value) | dereference of a `maybe_none` / `definitely_none` value with no guard | medium |

Safe patterns deliberately **not** flagged: parameterized SQL
(`execute(sql, params)`), `os.path.basename`-sanitized paths, `yaml.safe_load`,
SHA-256+, and `None`-guarded dereferences.

**Security is local code review only:** no execution of analyzed code, no
payloads, no network, no remote scanning.

Every finding includes: `id, severity, confidence, category, file, line,
explanation, evidence, why_might_be_wrong, next_verification_step`.

---

## 4. CLI examples

```
py -3 -m builder_core.cli security-scan --project <repo> --top 20
py -3 -m builder_core.cli analyze-file  --project <repo> <file>
```

`security-scan` on a synthetic vulnerable repo (abridged):
```
SECURITY SCAN
SUMMARY
7 finding(s) across 1 file(s). code_injection=1, command_injection=1, ...
FINDINGS
1. [HIGH/HIGH] command_injection  id=SEC-COMM-f5f59c79
   vulnerable.py:6
   `subprocess.call` runs an OS command with shell=True using a value traced from untrusted input.
   evidence: subprocess.call(user_cmd, shell=True)
   why this might be wrong: ... shell=True is occasionally required ...
EVIDENCE
- vulnerable.py:6: subprocess.call(user_cmd, shell=True)
SOURCES
- vulnerable.py
NEXT VERIFICATION STEPS
- [SEC-COMM-f5f59c79] Prefer a list argv with shell=False; if a shell is required, shlex.quote untrusted parts.
```

`analyze-file` integrates bug findings with the value/taint sections
(SUMMARY / FINDINGS / EVIDENCE / CONFIDENCE / SOURCES / NEXT VERIFICATION STEPS),
listing untrusted-input sources and per-finding verification steps.

---

## 5. Tests run

```
py -3 -m pytest builder_core/tests/test_phase89_value_dataflow_taint.py -q   # 18 passed
py -3 -m pytest builder_core/tests/ -q                                       # 78 passed (60 prior + 18)
py -3 builder_core/scripts/smoke_phase89_value_dataflow_taint.py             # SMOKE PASSED
```

Phase 89 test coverage: reaching defs through assignment, minimal CFG blocks,
branch-condition facts, container empty/non-empty state, interval from
`range(len(x))`, None-check before deref (not flagged) vs missing check
(flagged), tainted→eval, tainted→subprocess `shell=True`, SQL concat with taint,
safe parameterized SQL (not flagged), tainted path `open`, sanitized path (not
flagged), `pickle.load` on tainted file, `md5` flagged, full finding-schema
completeness, and clean function (no findings).

---

## 6. Benchmarks — before / after

The value/security core is a **separate path**; the semantic benchmark path is
untouched, so the numbers are unchanged (no regression — the acceptance bar).

| Benchmark | Metric | Before | After |
|---|---|---|---|
| QuixBugs | precision | 100% | **100%** |
| QuixBugs | recall | 30% | **30%** |
| Holdout | precision | 100% | **100%** |
| Holdout | recall | 16.7% | **16.7%** |
| Holdout | FP on fixed | 0 | **0** |
| Synthetic security | precision | — | **100%** (6 seeded vulns detected, 0 FP on the safe file) |

| Acceptance criterion | Target | Result |
|---|---|---|
| QuixBugs recall | ≥ 25% | 30% ✅ |
| Holdout precision | ≥ 85% | 100% ✅ |
| Holdout recall | ≥ 16.7% | 16.7% ✅ |
| Synthetic security precision | ≥ 85% | 100% ✅ |
| No target-repo modification | required | honored ✅ |
| No unsafe execution | required | honored ✅ |

---

## 7. Limitations (honest)

- **Intraprocedural only.** Taint does not cross function boundaries; a source
  in one function reaching a sink in another is invisible. This is the single
  biggest recall limit and is the next phase.
- **Parameters are treated as taint sources.** This is the standard SAST default
  and keeps recall up, but it means the model leans on the *sink* (eval, execute,
  shell=True, pickle, open, md5) for precision. Pure-computation code with no
  dangerous sink is never flagged; that is why the safe file stays clean.
- **Loops analyzed once; no fixpoint** on the value lattices (reaching defs do
  use a back-edge union). Interval reasoning is "hints", not a solver — good for
  `range(len(x))`-style bounds, not arbitrary arithmetic.
- **CFG is minimal/best-effort.** `try/with` flow is approximated; exotic control
  flow degrades to a single block (facts still emitted, never a crash).
- **Sanitizer list is small and syntactic.** Custom validators are not
  recognized, so some findings carry a deliberate "why this might be wrong."
- **Not wired into the bug benchmark.** By design this phase — the value core is
  available but the older detectors were not rewired onto it (that rewrite is
  where the QuixBugs/holdout *recall* will actually move).

---

## 8. Next recommended phase

**Phase 90 — Interprocedural propagation + the rule rewrite onto the value core.**
Two coupled moves, in order:
1. **Call graph + function summaries** (the "widen" axis): propagate taint and
   nullability across function boundaries so cross-function injection and
   null-deref become visible — the largest remaining recall lever.
2. **Rewire the existing bug detectors onto `valueflow` facts** and retire the
   matching name-bound rules, finally lifting QuixBugs/holdout recall through
   value reasoning instead of names (the deferred Phase 88 work, now that the
   substrate exists and is proven).

Everything after (full Security Intelligence Engine, Invariant Engine, Test
Reasoning Engine) plugs into this same value core.
