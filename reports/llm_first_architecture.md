# JARVIS — LLM-First Architecture (design only)
**Date:** 2026-05-29
**From:** 507 intents · 487 hand-registered handlers · rule/keyword classifier as the brain.
**To:** an LLM-first agent OS where the model *reasons over a typed tool catalog*, grounded in unified memory, with planning, gated execution, and verification — preserving every existing safety contract (read-only-first, no-mock-success, verify-after-act, forbidden-action guard, audited).

No code. This is the architecture and the migration path.

---

## 0. The core inversion

**Today:** `text → keyword match → 1 of 507 intents → 1 of 487 handlers → execute`.
The classifier *is* the intelligence; every capability is a bespoke handler; novelty fails.

**LLM-first:** `text + memory → LLM router/planner → typed tool calls → gated execution → verification → grounded answer`.
The LLM *is* the intelligence; capabilities are **tools** described by schemas; the 487 handlers become tool adapters; the keyword classifier becomes a **latency cache**, not the brain.

---

## 1. Request lifecycle (the spine)

```
                 ┌─────────────────────────────────────────────────────────────┐
 user text/voice │                        ORCHESTRATOR                          │
 ───────────────►│                                                              │
                 │  1. Fast-path cache ── exact/high-conf rule hit? ──► tool call│
                 │       (old classifier, demoted)                              │
                 │                                                              │
                 │  2. Context assembly ◄── MEMORY (working/episodic/semantic/  │
                 │                              profile) + conversation state    │
                 │                                                              │
                 │  3. Tool retrieval ◄── TOOL REGISTRY (embedding shortlist     │
                 │                          of top-K candidate tools)            │
                 │                                                              │
                 │  4. ROUTER/PLANNER (LLM) ─► structured output:               │
                 │        • single tool call,  OR                               │
                 │        • multi-step PLAN (typed, hashed)                     │
                 │                                                              │
                 │  5. SAFETY PRE-SCREEN ── forbidden? unsafe? ──► BLOCK/clarify │
                 │                                                              │
                 │  6. APPROVAL ── plan/irreversible? ──► preview + pinned hash  │
                 │                                                              │
                 │  7. EXECUTOR ── per step: observe → call tool → observe →     │
                 │        VERIFY → reflect → continue/recover/stop              │
                 │                                                              │
                 │  8. SYNTHESIS ─► grounded answer (sources, confidence)       │
                 │                                                              │
                 │  9. MEMORY WRITE-BACK + AUDIT                                 │
                 └─────────────────────────────────────────────────────────────┘
```

Every numbered stage maps to a component below.

---

## 2. Tool Registry (the foundation)

The single most important abstraction. Replaces ad-hoc `ActionRegistry` string lookup.

### 2.1 Tool specification (fields, not code)
- `name` — namespaced, e.g. `web.search`, `memory.recall`, `mail.summarize`, `calendar.read`.
- `description` — natural-language, written *for the LLM* (this is what selection retrieves on).
- `input_schema` — JSON Schema (typed params, required/optional, enums).
- `output_schema` — typed result shape (so verification and synthesis are structured).
- `safety_class` — `READ_ONLY` | `REVERSIBLE` | `IRREVERSIBLE_FORBIDDEN`.
- `side_effects` — `none` | `local_write(reports/audit only)` | `external_reversible` | `external_irreversible`.
- `idempotent` — bool (affects retry/recovery).
- `requires_approval` — derived from safety_class (READ_ONLY = none; REVERSIBLE = double-confirm; FORBIDDEN = never planned/executed).
- `verification` — declared post-condition contract (see §7): how to confirm the tool *actually* did its job.
- `cost_hint` / `latency_hint` — for planner budgeting.
- `auth` — none | connector-token (keychain-backed).
- `version` — for parity/rollback.
- `handler_ref` — the adapter that performs the work (existing handler, browser provider, connector).

### 2.2 How the 487 handlers fold in
- An **adapter layer** wraps each existing handler as a tool with a schema + safety_class. No big-bang rewrite.
- Group the 507 intents into **~40–60 tools** (many intents are variants of one capability, e.g. dozens of trading/investigation intents → a few parameterized tools). Net surface **shrinks**.
- Legacy/dead intents are deprecated; trading/investigation becomes a **plugin namespace** (`trading.*`).

### 2.3 Selection at scale (you cannot put 487 tools in one prompt)
Two-stage routing:
1. **Retrieve** top-K candidate tools by embedding similarity between the (memory-enriched) request and tool `description`s. (Tool descriptions are embedded once; cached.)
2. **Decide** — the LLM sees only the shortlist (K≈8–15) as function-calling schemas and picks/parameterizes.
- Namespacing + a small always-present "core" toolset (search, recall, answer, clarify) guarantees baseline capability even on retrieval miss.

### 2.4 Registry guarantees
- Central enforcement point for `safety_class` (a FORBIDDEN tool is never exposed to the planner — defense in depth even if the LLM "asks").
- Schema validation on every call (reject malformed LLM args before execution).
- Versioned; tools can be A/B'd and rolled back.

---

## 3. Routing (LLM-as-router, classifier demoted)

### 3.1 Three tiers, fastest-first
1. **Fast-path cache** — the existing rule/keyword classifier becomes a *cache*: an exact/high-confidence phrase hit dispatches a known tool directly (sub-ms, no LLM cost). Misses fall through.
2. **Single-shot tool call** — for clear, single-capability requests the LLM emits one function call.
3. **Plan** — for open-ended/multi-step requests the LLM emits a typed multi-step plan (→ Planner, §4).

The LLM decides between (2) and (3); a complexity heuristic can bias the prompt.

### 3.2 Inputs to the router
- User text + conversation state (multi-turn references resolved).
- Retrieved memory (profile + relevant episodic/semantic facts).
- Tool shortlist (schemas).
- The **safety policy** (what classes are allowed this turn).

### 3.3 Output (structured, never free-form actions)
- Either `{tool, args}` or `{plan: [steps...]}` or `{clarify: question}` or `{answer: ...}` (no tool needed).
- All tool args are schema-validated before anything runs.

### 3.4 Why keep the classifier at all
Latency + cost + determinism for the common case ("open chrome", "show last errors"). It is a cache, not the authority — the LLM owns anything it doesn't confidently match.

---

## 4. Planner

### 4.1 Plan as a typed, bounded artifact
- A **plan** = ordered (or DAG) list of **PlanSteps**, each = `{tool, args, expected_verification, recovery_strategy, depends_on}`.
- Carries **limits**: `max_steps`, `max_sources`, `max_runtime`, `max_cost`, `allowed_domains`.
- Carries `safety_class` of the whole plan = max of its steps.
- **Dry-run:** building a plan executes nothing.
- **Hash:** canonical form (normalized goal + step templates + limits + allowed/forbidden) → `plan_hash`. (Reuses the Phase 71/72/autonomy pattern already in the repo.)

### 4.2 Planning modes
- **Deterministic templates** for known shapes (e.g. research = search→open→extract→summarize→synthesize) — cheap, predictable.
- **LLM-generated plans** for novel goals — *validated against the contract*: every step's tool must exist, be allowed, and be schema-valid; forbidden tools cause rejection before preview.
- **Hybrid:** LLM fills parameters of a vetted template skeleton (safest middle ground; recommended default).

### 4.3 Approval & pinning
- READ_ONLY single-step → run directly.
- Multi-step or REVERSIBLE → **preview the full plan + safety class + limits + plan_hash**, require confirmation, **pin** the exact plan, and execute *only* the pinned plan (hash-checked). If the plan changes → re-approve. (This is exactly the Phase 72/autonomy mechanism, generalized.)

### 4.4 Replanning
- The executor may request a bounded replan on repeated verification failure (e.g., rewrite query, choose different sources) — within the approved capability/limit envelope, never escalating safety_class. Replans are logged.

---

## 5. Memory integration

A single, unified store (post Phase 77) with four *views*, assembled into the LLM context each turn.

| View | Contents | Role |
|------|----------|------|
| **Working memory** | current conversation turns, last results, active plan/task | reference resolution, continuity |
| **Episodic** | past runs: goals, tools used, outcomes, sources, what failed | "you asked this before"; provider/domain lessons |
| **Semantic** | embedded facts/notes/documents | grounded recall (replaces keyword search) |
| **Profile** | durable, non-sensitive: domains, preferences, routines, aliases | personalization injected as system context |

### 5.1 Context assembly (the retrieval policy)
- Each turn: profile (always) + top-N semantic hits for the query + relevant episodic summaries + working memory, **budgeted to a token cap** with importance×recency×confidence ranking.
- Tool retrieval (§2.3) runs over the same enriched query.

### 5.2 Write-back
- After execution: persist an episodic record (goal, plan_hash, steps, sources, status, confidence) and extract durable facts/profile updates (policy-filtered, **no secrets/PII/cookies**).
- Lessons (useful/failed domains, query rewrites that worked) feed future planning — generalize the autonomy memory already built.

### 5.3 Safety
- Memory is encrypted at rest (Phase 73); write-back is policy-gated; nothing sensitive from web/email pages is stored beyond extractive snippets explicitly needed for a report.

---

## 6. Execution

### 6.1 The executor loop (per step)
```
observe(state) → call tool(args) → observe(state') → verify(expected, state')
   ├─ ok      → record success, advance
   ├─ fail    → recovery (bounded, non-escalating) → retry/skip/replan
   └─ blocked → stop honestly (safety/limit/unavailable)
```
Generalized from the Phase 71 `tooluse` and Phase 74 `autonomy` executors.

### 6.2 Guarantees enforced *in the executor* (defense in depth)
- **Real capability required** — a tool that needs a real provider/connector and finds it unavailable returns `BLOCKED_UNAVAILABLE`, never SUCCESS. **No mock-success, no hidden fallback to mock.**
- **Safety gate** — a step whose tool is FORBIDDEN aborts the run (the planner shouldn't emit it; the executor refuses anyway).
- **Approval integrity** — the executed plan's hash must equal the approved hash.
- **Limits** — every external action counts against `max_steps`/`max_runtime`/`max_cost`; exceeding → honest stop.
- **Per-step audit** — tool, args (redacted), result, verification, recovery, URLs — to `*_audit.jsonl` + per-run report (existing pattern).

### 6.3 Concurrency & isolation
- A **session/agent context** object replaces global singletons (no shared mutable state), enabling concurrent tasks and clean tests.
- Confirmation becomes **per-session keyed** (replacing the single global slot) so concurrent approvals don't collide.
- Tool execution is sandboxed by capability: browser tools through the isolated Playwright provider; connector tools read-only-scoped; local writes restricted to `reports/`/audit.

---

## 7. Verification (why "no fake success" is structural)

Verification is a **first-class, declared contract per tool**, not an afterthought.

### 7.1 Verifier types (declared in the tool spec)
- **State-change** — observed state matches expected post-condition (e.g., browser navigated off the search engine; page title non-empty).
- **Content** — output satisfies a shape/threshold (e.g., ≥N chars extracted; ≥1 organic result; schema-valid result).
- **Provider-reality** — the action ran on a real provider/connector (mock/unavailable ⇒ not verified).
- **Cross-source** — for synthesis/compare, ≥K independent sources corroborate.

### 7.2 Confidence
- A transparent function of: verified-step ratio, sources-corroborated, provider reality, recency. Surfaced to the user with every answer. Zero sources ⇒ zero confidence (never asserted).

### 7.3 Synthesis is grounded
- Final answers cite the tool outputs/sources that produced them; the synthesizer is constrained to observed content (extractive-first), reducing hallucination. Disagreements and uncertainty are reported, not hidden.

---

## 8. Safety & permission model (cross-cutting)

- **Capability tiers:** `READ_ONLY` (default, no approval) → `REVERSIBLE` (double-confirm + reversibility check + audit, Phase 95) → `IRREVERSIBLE_FORBIDDEN` (never planned/executed). Payments/orders/bookings/logins/submits/downloads/deletes/sends/account-changes/autonomous-desktop-control = FORBIDDEN.
- **Forbidden-action guard** at three layers: goal classification (reject), planner (won't emit), executor (refuses) — the existing `scan_forbidden`/capability model generalized.
- **Prompt-injection isolation (Phase 82):** web/email content is *data*, never instructions; the planner never takes a forbidden/unapproved action because a page told it to; egress policy blocks private IP ranges (SSRF).
- **Consent + identity (Phase 86):** per-user, per-connector scopes; tokens in OS keychain.
- **Everything audited:** every external action and every blocked attempt logged; runs reproducible.

---

## 9. Observability & evals (make "smart" measurable)

- **Metrics:** per-tool latency/success/recovery; router cache-hit rate; plan length; confidence distribution.
- **Eval harness (Phase 75):** a fixed task set scored for success; gates the router/tool migration so quality is a number, not a vibe.
- **Traces:** structured per-run traces (router decision, tool shortlist, plan, step verifications) for debugging and trust.

---

## 10. Component map (new ↔ existing)

| LLM-first component | Built on / replaces |
|---------------------|---------------------|
| Orchestrator | new thin layer over `brain/router.py` |
| Fast-path cache | demoted `brain/intent_classifier.py` |
| Tool Registry + adapters | wraps `actions/registry.py` handlers; new `Tool` spec |
| Tool retrieval (embeddings) | new; reuses memory embedding stack (Phase 80) |
| Router/Planner (LLM) | new; uses `brain/llm_intent_classifier.py` plumbing + function-calling |
| Plan + pinned approval | generalize `tooluse`/`autonomy` plan-hash + `core/confirmation.py` (per-session) |
| Executor loop | generalize `tooluse/executor.py` + `autonomy/executor.py` |
| Verification contracts | generalize `tooluse/verifier.py` + autonomy verifiers |
| Memory views + write-back | unified `memory/store.py` (Phase 77) + embeddings (Phase 80) + autonomy lessons memory |
| Audit | existing rotating JSONL + per-run reports |
| Safety/forbidden guard | `tooluse.contracts.scan_forbidden` + `autonomy.capabilities` generalized |

---

## 11. Migration path (incremental, parity-gated — no big bang)

1. **Define the Tool spec + registry** (Phase 78). Adapt the top ~40 handlers as tools with schemas + safety_class + verification. Parity tests vs legacy.
2. **Stand up tool retrieval** over tool descriptions (cache embeddings).
3. **Introduce the LLM router** behind a flag: classifier stays as fast-path cache; LLM handles misses. Measure on the eval set (Phase 79).
4. **Generalize the planner/executor/verifier** from `tooluse`/`autonomy` into the shared engine (Phase 81).
5. **Wire unified semantic memory** into context assembly + write-back (Phase 80).
6. **Migrate remaining handlers → tools; deprecate dead intents; trading → plugin** (Phase 84). Net intent surface falls.
7. **Throughout:** safety guards, no-mock-success, audit, and the eval gate stay green; each step is reversible/rollback-able by tool version + flag.

---

## 12. What the user experiences after this
- Speak naturally; no magic phrases. Novel requests work.
- Answers are grounded, sourced, with confidence — and honest when they fail.
- It remembers you (profile + semantic recall).
- Multi-step research/compare "just works" within bounded, previewed, approved plans.
- Still cannot pay/order/book/login/submit/download/delete/send — and never acts irreversibly on its own.

*End — architecture only, no code.*
