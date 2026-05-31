# RU-3 — Architectural Question Understanding (Design Only)

**Status:** Design only. No implementation, no code, no detector changes, no LLM.
**Date:** 2026-05-31
**Builds on:** RU-2 (role-aware retrieval + subsystem map), Phase 94A (dependency
graph), Phase 94B (impact analysis design).
**Principle:** deterministic classification; **unknown beats guessing**; every
classification is explainable (it reports which rule/terms fired).

---

## 0. The precise gap

RU-2 fixed *retrieval* — architecture questions now pull production code and
architecture docs, not benchmark/report noise. What is still weak is
*interpretation*: the system understands **which files** are relevant but not
**what repository-level question** is being asked.

Today `builder_core/ask.py::classify()` is monolithic:

```
risk?            -> "risk"
architecture?    -> "architecture"     # one giant bucket
else             -> "retrieval"
(+ file named + bug word -> python_analysis)
```

So everything architectural collapses into a single "architecture" answer that
lists subsystems. That is why:

| Example | Today | Should be |
|---|---|---|
| "What is the execution path when a user speaks a voice command?" | architecture (works by luck — subsystem list mentions voice) | **execution_path** (a call chain) |
| "Which directories contain the highest concentration of production code?" | architecture (lists folders, **unranked**) | **production_layout** (a ranked density answer) |
| "Which production subsystems are most central to the architecture?" | architecture (lists subsystems, **no centrality**) | **subsystem** + centrality (ranked by dependency fan-in) |

The retrieval is correct; the **question category** is not. RU-3 inserts a
deterministic **question-understanding layer** in front of the existing handlers
that maps a question to exactly one of eleven categories and routes it to the
handler (and graph inputs) that category actually needs.

**Scope guard:** RU-3 adds a *routing/interpretation* layer only. It does not
change detectors, the benchmark harness, promotion, retrieval ranking (RU-2), the
dependency graph (94A), or the impact engine (94B). It selects among existing and
already-designed handlers; it never invents answers.

---

## 1. Repository question taxonomy

Eleven categories. Each is defined by its **answer unit** (what the answer is
*about*), its **strong (anchored) signals** (high-precision phrases/regex), and
the **handler** it routes to. Strong signals are deterministic phrases; the full
routing (including weak-signal scoring and tie-breaks) is in §2.

| Category | Answer unit | Canonical question | Strong signals (anchored) | Handler |
|---|---|---|---|---|
| **architecture** | the system as a whole | "What is the architecture / how is the system structured?" | `architecture`, `overall structure`, `high level`, `overview of the system` | RU-2 architecture/subsystem-map answer |
| **subsystem** | subsystems as units (incl. centrality/importance) | "Which production subsystems are most central / most important?" | `subsystem(s)`, `most central`, `most important … subsystem`, `core subsystem` | RU-2 subsystem map + **subsystem-centrality** (depgraph roll-up) |
| **entrypoint** | where execution begins | "What are the entry points / where does the app start?" | `entry point`, `entrypoint`, `where does … start`, `main entry`, `how is it launched` | repository_understanding entry files + `main.py`/`cli.py` |
| **execution_path** | an ordered call chain | "What is the execution path when a user speaks a voice command?" | `execution path`, `what happens when`, `flow when`, `path … reaches`, `how does … reach` | 94B path query (entrypoint → … → target over resolved `calls`) |
| **dependency** | who-depends-on-what (specific module/file) | "What does X import / what does Y depend on?" | `depend(s) on`, `import(s)`, `uses … module`, `coupled to`, `dependencies of` | depgraph `imports`/`calls` edges (forward) |
| **impact** | blast radius of a change | "What breaks if I change X / what depends on X?" | `what breaks`, `impact of changing`, `what depends on`, `affected if … change`, `safe to change` | 94B impact engine (reverse closure + risk/confidence) |
| **production_layout** | where code of a role lives | "Which directories have the highest concentration of production code?" | `concentration of production`, `where is the production code`, `which folders/directories … production`, `density`, `production vs test layout` | RU-2 `roles`/`subsystems` ranked by production count/density |
| **ownership** | who owns/maintains code | "Who owns / maintains the voice module?" | `who owns`, `who maintains`, `owner of`, `maintainer`, `codeowners` | CODEOWNERS → git authorship → maintainer tags (degrade to unknown) |
| **security** | security exposure | "Where are the security vulnerabilities / injection risks?" | `vulnerab*`, `injection`, `taint`, `security risk`, `unsafe input`, `CWE` | `engine.security_findings` (existing, read-only) |
| **bug_analysis** | a specific file's correctness | "Is there a bug in X / analyze X for logic errors" | `bug`, `logic error`, `analyze <file>`, `is … broken`, `review <file>` | existing `_answer_python_analysis` (`_BUG_RE` + named file) |
| **unknown** | (no confident category) | "Tell me about the code." | — (no anchor, low lexicon margin) | RU-2 plain retrieval, labeled low-confidence |

**Closed set.** These eleven are the canonical *question* categories. Note two
pre-existing *handlers* that are not separate categories: the legacy `risk`
handler (`risk.compute_risks`) and the generic `retrieval` fallback. Their
reconciliation is in Appendix B — in short, architectural-risk phrasing
("biggest architectural risks", "fragile hotspots") classifies as **architecture**
with a risk facet and routes to the risk handler; security-vulnerability phrasing
classifies as **security**.

---

## 2. Routing rules

A two-tier deterministic classifier. No LLM, no learned weights — fixed lexicons
and a published precedence. The classifier emits `(category, confidence,
fired_rule, alternatives)` so the choice is auditable (evidence-quality, per RU-2).

### 2.1 Tier 1 — anchored phrase rules (high precision)

An **ordered** list of anchored patterns (the "strong signals" column of §1),
each tagged with a **specificity weight**. The classifier scans the question for
all anchors and selects the **single highest-weight matched anchor**; its category
wins. Specificity weights (higher = more specific intent) resolve cross-category
overlaps without a brittle category precedence:

```
weight 5 (intent-defining):  "what breaks", "impact of changing"            -> impact
                             "execution path", "what happens when"          -> execution_path
                             "concentration of production", "density"       -> production_layout
                             "who owns", "who maintains"                    -> ownership
                             "entry point", "entrypoint"                    -> entrypoint
weight 4 (strong subject+intent): "vulnerab*/injection/taint"              -> security
                             "most central", "most important subsystem"     -> subsystem(centrality)
                             "bug/logic error/analyze <file>"               -> bug_analysis
weight 3 (subject anchors):  "depends on / imports / coupled to"            -> dependency
                             "subsystem(s)"                                 -> subsystem
weight 2 (generic):          "architecture / overall structure / overview" -> architecture
```

**Why specificity weight, not category precedence:** "What breaks if I change the
**security** scanner?" matches both `security` (w4) and `impact` ("what breaks",
w5). Max-weight wins → **impact** (correct: the intent is blast radius; security
is just the subject). Likewise "execution path through the auth module" → w5
execution_path beats w3 dependency. The weights encode that *intent verbs*
("what breaks", "execution path") are more category-defining than *subject nouns*
("security", "module").

### 2.2 Tier 2 — lexicon scoring (recall, for unanchored questions)

If no anchor fires, score each category by weighted overlap of its **weak-signal
lexicon** (synonyms/morphological variants) against the tokenized question
(reusing RU-2 `retrieval.tokenize`). The category with the **highest score** wins
**only if** it clears two gates:

1. `score >= MIN_SCORE` (absolute floor), and
2. `top_score - second_score >= MIN_MARGIN` (separation).

Otherwise → **unknown** (route to RU-2 retrieval, low confidence). This is the
"unknown beats guessing" gate: a question that is merely *near* two categories is
never force-fit into one.

### 2.3 Category → handler routing

| Category | Routed handler | Output shape |
|---|---|---|
| architecture | RU-2 architecture answer | subsystem overview + sources |
| subsystem | RU-2 subsystem map; **centrality** computed from depgraph (§4) | ranked subsystems + evidence |
| entrypoint | repository_understanding entry files | entry file list + roles |
| execution_path | 94B path query | ordered call chain or "no resolved path (partial coverage)" |
| dependency | depgraph forward edges | imports/calls of the named target |
| impact | 94B impact engine | asserted/possible/unanalyzed + risk + confidence |
| production_layout | RU-2 `roles`/`subsystems` ranking | ranked dirs by production count **and** density |
| ownership | CODEOWNERS / git authorship | owner(s) per path or "no ownership signal" |
| security | `engine.security_findings` | ranked security findings (read-only) |
| bug_analysis | `_answer_python_analysis` | per-file findings |
| unknown | RU-2 retrieval | best-effort passages, low confidence |

The classifier never *produces* answers — it only selects the handler and the
graph inputs that handler requires (§4).

---

## 3. Expected evidence sources for each category

Every answer must cite evidence whose **role** (RU-2 `classify_file_role`) and
**source** are appropriate to the category. This is the cross-check that keeps a
category from answering out of the wrong corpus (the original RU-1 failure).

| Category | Expected evidence (roles / artifacts) | Must NOT rely on |
|---|---|---|
| architecture | `README_ARCHITECTURE.md`, `README.md`, top production subsystems | reports/*, benchmark/dataset |
| subsystem | subsystem map (`index["subsystems"]`) + depgraph import roll-up | report_history, datasets |
| entrypoint | entry files (`main.py`, `cli.py`, `__init__.py`, `voice_loop.py`, …) | generic prod files that aren't entries |
| execution_path | resolved `calls` edges + entry functions (94A/94B) | name-only guesses, unresolved calls as if resolved |
| dependency | `imports`/`calls` edges incident to the named node | textual mentions in docs/reports |
| impact | reverse closure over resolved edges (94B) + roles for weighting | unresolved edges presented as asserted |
| production_layout | `index["roles"]` + per-subsystem `role_counts` | doc prose, reports |
| ownership | CODEOWNERS, git `log/blame` authorship, explicit maintainer tags | author *guesses*, docstring tone |
| security | `engine.security_findings` (taint/security AST signals) | risk prose, generic "looks unsafe" |
| bug_analysis | per-file `python_analysis` findings (AST signals) | repo-wide speculation |
| unknown | RU-2 retrieval passages | any confident specialized claim |

Determinism rule: each cited item carries `path` (+ `line` where applicable) and
`role`, sorted by stable keys — identical repo ⇒ identical evidence list.

---

## 4. Required graph inputs

What each category must read. **If a required input is absent or degraded, the
category fails closed** (§5), it does not fall back to prose guessing.

| Category | repository_understanding | depgraph (94A) | impact (94B) | other |
|---|---|---|---|---|
| architecture | `production_subsystems`, roles | — (optional: `statistics`) | — | — |
| subsystem | `discover_subsystems`, `role_counts` | `imports` edges → subsystem fan-in; `import_cycles`, `largest_components` | — | — |
| entrypoint | entry-file detection (`_ENTRY_NAMES`) | `contains` edges (module→functions) | — | — |
| execution_path | entry files (path roots) | resolved `calls` edges (`scope` intra/cross) | reverse/forward path traversal | — |
| dependency | role of endpoints | `imports`+`calls` edges (forward), `resolved` flag | — | `module_map` for name→path |
| impact | roles (risk weighting) | full graph (reverse indices) | the 94B engine | — |
| production_layout | `index["roles"]`, per-subsystem `role_counts` | — | — | — |
| ownership | path→subsystem (grouping) | — | — | CODEOWNERS, git history |
| security | role (focus on production_code) | — (optional: file list) | — | `engine.security_findings` |
| bug_analysis | role of the named file | — | — | `python_analysis` for that file |
| unknown | — | — | — | RU-2 retrieval index |

**Subsystem centrality (the metric behind "most central"):** deterministic, no
guessing. For each subsystem S, **fan-in = number of *distinct other subsystems*
that contain at least one module with a resolved `imports` edge into S**
(depgraph `imports` edge → `to` module `path` → subsystem via
`discover_subsystems`). Rank by `(fan-in desc, fan-out asc, name)`. Optionally
annotate membership in `statistics.import_cycles` / `largest_components`. Every
ranked subsystem reports the importing subsystems as evidence. This answers
"most central to the architecture" with a real, reproducible measure rather than a
subsystem dump.

**Production layout (the metric behind "highest concentration"):** for each
top-level directory/subsystem, read `role_counts["production_code"]` and total
files; report **both** absolute production count **and** density
`production_code / indexable_files`, ranked `(density desc, count desc, name)`.
This distinguishes "biggest" from "purest" and answers the BAD example directly.

---

## 5. Failure handling

The layer must fail *legibly*, never silently mis-answer. Five failure modes:

1. **No confident category (Tier-2 gates not met)** → `unknown`. Route to RU-2
   retrieval, label the answer "interpreted as general retrieval (low
   confidence)", and list the top-2 candidate categories so the user can rephrase.

2. **Ambiguous (two anchors of equal weight, different categories)** → pick the
   one earliest in the published order, **reduce interpretation confidence to at
   most `medium`**, and surface the alternative in `alternatives`. (Equal-weight
   collisions are rare by construction; the weight ladder is designed to avoid
   ties.)

3. **Required input missing / degraded** → category-specific "cannot compute,"
   confidence `unknown`, no fallback to prose. Examples: centrality or
   dependency/impact on a `degraded` graph → "dependency graph degraded — cannot
   compute"; execution_path with no resolved call chain → "no resolved execution
   path found (call-graph coverage is partial)" (inherited 94B wording).

4. **Empty evidence after routing** → distinguish **"no evidence found"** (the
   handler ran, found nothing — e.g. security scan returned zero findings) from
   **"wrong interpretation"** (offer the next-best category). Never report empty
   as a confident "none exist" unless the handler is authoritative for that claim.

5. **Ownership with no signal** → since this repo has no CODEOWNERS and may have
   shallow/limited git history, ownership commonly degrades to
   **`unknown: no ownership signal available`** rather than inferring an owner
   from authorship noise. This is the canonical "unknown beats guessing" case.

A misclassification must be *recoverable*: because the layer only selects a
handler, a wrong guess wastes a query but cannot corrupt state, detectors, or the
benchmark.

---

## 6. Confidence model

**Two orthogonal layers**, reported separately (never multiplied into one
misleading number):

### 6.1 Interpretation confidence — "did we understand the question?"

Driven by classifier signals:

- **Anchor strength:** a fired Tier-1 anchor (esp. weight ≥ 4) → `high`.
- **Margin:** Tier-2 win with large `top - second` margin → `medium`/`high`;
  thin margin → `low`.
- **Collisions:** equal-weight anchor collision → capped at `medium` (§5.2).
- **No anchor + gates barely met** → `low`; gates failed → `unknown`.

Buckets: `high` / `medium` / `low` / `unknown`. `low`/`unknown` ⇒ the layer
prefers the RU-2 retrieval fallback over a specialized answer.

### 6.2 Answer-support confidence — "is the routed answer well-grounded?"

Inherited from the handler:

- impact/dependency/execution_path → the **94B confidence** (resolved_ratio,
  unresolved/star/dynamic caveats, degraded → unknown).
- subsystem-centrality/production_layout → fraction of the relevant edges/files
  that are `resolved`/indexable; presence of `parse_errors` lowers it.
- security/bug_analysis → these are AST *signals*, never proofs (existing
  wording: "review leads, not automatic proof of a bug").
- ownership → `high` only with CODEOWNERS; git-authorship-only → `medium`;
  nothing → `unknown`.

**Reporting rule:** the answer states both, e.g. *"Interpreted as
**production_layout** (interpretation: high). Ranked by density (support: high)."*
A high-interpretation / low-support answer is explicitly flagged so the user
knows the question was understood but the data is thin — and vice-versa.

---

## 7. Acceptance tests

Design-level; to be authored with the implementation. No code now.

**Classification correctness (the motivating cases)**

1. "What is the execution path when a user speaks a voice command?" → **execution_path** (not architecture).
2. "Which directories contain the highest concentration of production code?" → **production_layout** (ranked by density, not an unranked folder list).
3. "Which production subsystems are most central to the architecture?" → **subsystem** with centrality (ranked by dependency fan-in, not a subsystem dump).

**One-per-category battery** (each classifies to its own category):

4. "What is the overall architecture?" → architecture.
5. "What are the entry points of the app?" → entrypoint.
6. "What does `voice/router.py` import?" → dependency.
7. "What breaks if I change `core/app.py`?" → impact.
8. "Who maintains the voice subsystem?" → ownership (likely `unknown: no signal` here — see §5.5).
9. "Where are the injection vulnerabilities?" → security.
10. "Is there a logic bug in `memory/store.py`?" → bug_analysis.
11. "Tell me about the code." → unknown → retrieval fallback, low confidence.

**Precedence / disambiguation**

12. "What breaks if I change the security scanner?" → **impact** (w5 beats w4 security).
13. "Execution path through the auth module?" → **execution_path** (w5 beats w3 dependency).
14. "Which folder has the most production code and who owns it?" → ownership **or** production_layout by the weight ladder, with the other surfaced in `alternatives`, interpretation ≤ medium.

**Robustness / invariants**

15. **Determinism:** every question above classifies identically across repeated runs (same category, same confidence, same fired_rule).
16. **Degraded inputs:** Q3 (centrality) / Q7 (impact) on a `degraded` graph → "cannot compute," confidence `unknown` — never a guess.
17. **Unknown floor:** a question matching two weak lexicons within `MIN_MARGIN` → unknown (not force-fit).
18. **No-regression / no-detector-change:** routing `security`→`engine.security_findings` and `bug_analysis`→`python_analysis` uses the existing read-only handlers unchanged; the full Builder Core suite still passes and QuixBugs 12 TP / 0 FP, holdout 2 TP / 0 FP are unchanged (the layer does not touch the benchmark path).
19. **Evidence-role guard:** an architecture/subsystem/production_layout answer cites **zero** `benchmark`/`dataset`/`report_history` sources (re-asserts the RU-2 guarantee through the new categories).

---

## 8. Rollback plan

Purely additive interpretation layer; trivial, behavior-neutral removal (matching
the RU-2 / 94B patterns).

- **Footprint:** one new classifier module (e.g.
  `builder_core/question_understanding.py`) consumed by `ask.classify()`, plus
  per-category routing in `ask.answer()`, plus tests. **No** changes to detectors,
  the benchmark harness, promotion, retrieval ranking, depgraph, or the impact
  engine.
- **Feature flag:** `QUESTION_UNDERSTANDING_ENABLED` (default on). When **off**,
  `classify()` reverts to the exact RU-2 behavior (`risk` / `architecture` /
  `retrieval` + file-scoped `bug_analysis`) — i.e. the eleven categories collapse
  back to the current four with no other change.
- **Hard rollback:** delete the module, the routing block, and the tests. Because
  the layer only **selects** existing/already-designed handlers and writes nothing
  into any analysis or index path, removal cannot alter findings, benchmark
  verdicts, promotion, or `ask`/`graph`/`impact` outputs.
- **No migrations / no state:** no persisted classifier state, no index schema
  change. Classification is a pure function of the question string plus read-only
  graph/index inputs.
- **Staged enablement:** categories can be turned on incrementally — unimplemented
  categories simply route to `unknown`→retrieval (current behavior), so partial
  rollout is safe and observable.

---

## Appendix A — Worked classification traces

- **"What is the execution path when a user speaks a voice command?"**
  Tier-1 anchor `execution path` (w5) fires → **execution_path**, interpretation
  `high`. Routes to 94B path query rooted at `voice/voice_loop.py` entry function;
  answer is a resolved call chain or the explicit partial-coverage message.

- **"Which directories contain the highest concentration of production code?"**
  Anchor `concentration of production` (w5) → **production_layout**, `high`.
  Reads `index["roles"]` + per-subsystem `role_counts`; ranks by density and
  count; cites the directories (role = production_code). No benchmark/report
  sources.

- **"Which production subsystems are most central to the architecture?"**
  Anchor `most central` + `subsystem` (w4) → **subsystem** (centrality), `high`.
  Requires depgraph; rolls `imports` edges up to subsystems; ranks by fan-in;
  cites the importing subsystems as evidence. On a degraded graph → "cannot
  compute," confidence `unknown`.

## Appendix B — Reconciling the legacy `risk` and `retrieval` handlers

The required taxonomy is a closed set of eleven **question** categories;
`risk.compute_risks` and the plain `retrieval` fallback are **handlers**, not
categories.

- **Security vs risk:** vulnerability/injection/taint phrasing → **security**
  (→ `engine.security_findings`). General "biggest architectural risks / fragile /
  technical debt / hotspots" phrasing → **architecture** with a *risk facet* that
  routes to the existing `risk` handler. This removes the current overlap where
  `_RISK_RE` swallows `vulnerab*` (which should be security).
- **Retrieval:** reachable only via **unknown** (low-confidence fallback). It is
  never a first-choice category — preventing the RU-2-era behavior where genuinely
  architectural questions silently became generic text search.

## Appendix C — Open design questions (for review, not blockers)

1. **Centrality measure:** subsystem fan-in only, or fan-in + cycle/component
   membership weighting? (Leaning: fan-in primary, cycle membership as an
   annotation, to keep it explainable.)
2. **Multi-intent questions** (Q14): answer the top category and *offer* the
   second, or answer both? (Leaning: answer top, surface second in `alternatives`
   — single deterministic answer, no fan-out.)
3. **Ownership data source priority** when both CODEOWNERS and git exist:
   CODEOWNERS authoritative (`high`), git authorship advisory (`medium`).
   (Leaning: yes — declared ownership beats inferred authorship.)
