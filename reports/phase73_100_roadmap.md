# JARVIS Roadmap — Phases 73–100
**Date:** 2026-05-29
**Status:** Design only (no code).
**Basis:** `reports/jarvis_codebase_audit_phase73_100.md` (honest baseline ≈ 62% readiness; 507 intents / 487 handlers; single-process file-based desktop app; Phase 71/72 real bounded tool-use shipped; autonomy stack v1 = uncommitted WIP).

---

## Operating principles (apply to every phase)

1. **No fake success.** Every capability keeps the Phase 71/72 contracts: real-provider-required, verify-after-act, honest failure, never report success when a step failed.
2. **Read-only first.** Payments, orders, bookings, logins, form submits, downloads, deletes, sends, account changes, and autonomous desktop control stay **blocked**. Reversible *gated* actions appear only at Phase 95, behind double-confirmation + reversibility + audit. **No autonomous irreversible actions, ever.**
3. **Trust before reach before intelligence-at-scale.** Fix what lies (mock paths, inflated scores), then make it reachable and safe, then make it smart broadly.
4. **Every phase has a testable exit criterion** with deterministic tests + an honest live smoke where external systems are involved.
5. **Shrink while you grow.** Net intent/handler count should *fall* as the tool protocol + LLM router replace bespoke handlers.

Effort key: **S** <1 dev-wk · **M** 1–2 · **L** 3–4 · **XL** 5+. Impact: **Critical / High / Med**.

---

## Milestone map (what's shippable when)

| Milestone | Phases | Theme | "Done" means |
|-----------|--------|-------|--------------|
| **M1 — Trustworthy** | 73–77 | Foundation & trust | No fake success anywhere; encrypted state; the agent loop is finished, audited, evaluated, observable; one memory. |
| **M2 — Real brain** | 78–84 | LLM reasoning core | LLM routes/plans over a typed tool catalog; semantic memory; the 507-intent surface is cut hard. |
| **M3 — Connected** | 85–91 | Reach & connectors | API + web/mobile surface; identity; Gmail/Calendar/Files read-only; document understanding. |
| **M4 — Anticipatory** | 92–96 | Proactive assistant | Briefings/watchers; personalization; multimodal; gated *reversible* drafts; sharing. |
| **M5 — Platform** | 97–100 | Moat & scale | Third-party tool SDK; cross-platform; enterprise; monetization. |

Critical path (longest dependency chain): **73 → 77 → 78 → 79 → 80 → 81 → 84 → 85 → 86 → 87 → 90**. Everything else hangs off these.

---

## WAVE A — Trust & Foundation (M1)

### Phase 73 — Trust repair & data-at-rest security
**Goal:** Eliminate every fake-success path and stop storing secrets in plaintext.
**Deliverables:** Route all browsing through `tooluse/`; delete the mock-success branches in `actions/phase62_browser_actions.py`; mark legacy `browser/runtime.py` mock as explicit-unavailable (never SUCCESS). Encrypt `data/` at rest; move secrets/tokens to OS keychain (DPAPI on Windows).
**Dependencies:** Phase 71/72 (done).
**Effort:** M · **Impact:** Critical (trust + S-1/S-2 security).
**Exit criteria:** No code path returns SUCCESS on a mock/unavailable provider (test-proven); secrets never appear in plaintext on disk (test scans `data/`); legacy mock browser returns BLOCKED_UNAVAILABLE.

### Phase 74 — Finish & merge the Autonomous Agent Stack v1
**Goal:** Land the bounded research agent (the current WIP branch) production-clean.
**Deliverables:** Complete tests (planner rejects forbidden goals; pinned-plan hash gating; no-mock-success; per-step verification; bounded recovery; audit written; report generated; router exposes only the 6 allowed commands; read-only displays); 3 smokes (fake/real/forbidden); `reports/autonomous_agent_stack_v1.md`.
**Dependencies:** 73.
**Effort:** M · **Impact:** High.
**Exit criteria:** All new tests pass; fake + forbidden smokes pass; real smoke passes or fails honestly with a clear external reason; sourced structured report produced.

### Phase 75 — Eval harness + CI + repo hygiene
**Goal:** Make "is it actually working" measurable and repeatable.
**Deliverables:** A fixed prompt/task eval set with task-success scoring; CI pipeline (lint + tests + evals); dependency lockfile + packaging (`pyproject.toml`); delete/quarantine `tests_tmp/` (231 files) and declare `tests/` authoritative.
**Dependencies:** 74.
**Effort:** M · **Impact:** High (prevents regressions for all later phases).
**Exit criteria:** CI green on a clean checkout; eval score is recorded as a number per run; one authoritative test dir.

### Phase 76 — Observability & honest status
**Goal:** See latency, errors, and task success over time.
**Deliverables:** Metrics (per-intent latency, success/fail, recovery counts) emitted from the router; structured run traces; a `show system telemetry` read-only view; surface degraded-mode clearly.
**Dependencies:** 75 (so metrics feed evals).
**Effort:** M · **Impact:** Med-High.
**Exit criteria:** Latency + success metrics queryable for the last N runs; degraded state visible to the user.

### Phase 77 — Memory unification
**Goal:** One memory, ranked, with a migration off the two-store split.
**Deliverables:** Merge `session_memory` into `PersonalMemoryStore`; migrate + delete the old file; rank by importance×recency×confidence; size/TTL guards retained.
**Dependencies:** 73 (encryption applies to memory).
**Effort:** L · **Impact:** Critical (foundation for the brain).
**Exit criteria:** Single store; old file migrated then removed; `search_memory` returns ranked results; no data loss in migration test.

---

## WAVE B — The Brain (M2)

### Phase 78 — Typed tool/skill protocol
**Goal:** Replace bespoke handlers with a uniform, typed, safety-classed tool interface (function-calling / MCP-style).
**Deliverables:** A `Tool` spec (name, JSON schema, safety_class read-only/reversible/forbidden, handler); adapters for the top ~40 high-value handlers; a tool registry separate from the legacy ActionRegistry.
**Dependencies:** 77.
**Effort:** XL · **Impact:** Critical (unlocks the LLM router and kills sprawl).
**Exit criteria:** ≥40 capabilities callable via the typed protocol with schemas; safety_class enforced centrally; parity tests vs legacy handlers.

### Phase 79 — LLM-as-router / planner
**Goal:** The LLM becomes the front door; the rule classifier becomes a fast-path cache.
**Deliverables:** LLM function-calling over the Phase 78 tool catalog; the rule classifier only short-circuits high-confidence exact matches (latency); fallback + safety guard intact.
**Dependencies:** 78.
**Effort:** XL · **Impact:** Critical (the single biggest UX leap).
**Exit criteria:** Novel phrasings route correctly without new phrase rules; eval task-success up vs Phase 75 baseline; forbidden actions still blocked centrally.

### Phase 80 — Semantic memory + user profile
**Goal:** Real recall and a (non-sensitive) profile.
**Deliverables:** Embedding-backed retrieval; entity/fact extraction; a structured user profile (domains, preferences, routines); injected as context to the LLM router.
**Dependencies:** 77, 79.
**Effort:** L · **Impact:** Critical ("it remembers me").
**Exit criteria:** Recall@k on an eval set beats keyword baseline; profile demonstrably personalizes answers; no secrets/PII stored beyond policy.

### Phase 81 — Generalized plan→act→reflect loop
**Goal:** Promote the autonomy executor into the default engine for open-ended requests.
**Deliverables:** A general agent loop (decompose → tool calls → observe → verify → reflect → continue/stop) bounded by limits; reuses Phase 71/72/74 verification + recovery; sourced structured output.
**Dependencies:** 79, 80.
**Effort:** L · **Impact:** Critical.
**Exit criteria:** Multi-step open-ended tasks complete with verification and honest stop conditions; no autonomous irreversible actions reachable.

### Phase 82 — Prompt-injection & egress defenses
**Goal:** Make web-fed reasoning safe.
**Deliverables:** Instruction/content separation for web text; SSRF/private-range egress blocking; the forbidden-action guard as the non-negotiable backstop; injection eval suite.
**Dependencies:** 81.
**Effort:** M · **Impact:** High (security S-5/S-8).
**Exit criteria:** Injection eval set: agent never executes page-embedded instructions to take forbidden/unapproved actions; private IPs blocked.

### Phase 83 — Conversational state & multi-turn continuity
**Goal:** Natural follow-ups ("the third one", "compare those").
**Deliverables:** In-process conversation context feeding the router/planner; reference resolution to prior results.
**Dependencies:** 79.
**Effort:** M · **Impact:** High.
**Exit criteria:** Follow-up eval set resolves references correctly across turns.

### Phase 84 — Surface reduction
**Goal:** Cut the 507-intent / 487-handler sprawl now that tools+LLM cover it.
**Deliverables:** Migrate remaining valuable handlers to tools; deprecate dead/duplicate intents; trading/investigation domain moved behind an optional plugin (see Phase 97 SDK).
**Dependencies:** 78, 79.
**Effort:** L · **Impact:** High (maintainability + product clarity).
**Exit criteria:** Net intent count materially reduced; startup import cost down; no capability regression in evals.

---

## WAVE C — Reach & Connectors (M3)

### Phase 85 — Service/API boundary
**Goal:** Turn the in-process app into a local daemon with a typed API.
**Deliverables:** A local service exposing the router/agent over a typed API; voice/overlay/CLI become clients; clean process separation.
**Dependencies:** 79 (stable brain to expose).
**Effort:** XL · **Impact:** High (breaks the single-box ceiling).
**Exit criteria:** Two clients drive the same backend; backend survives a client crash.

### Phase 86 — Identity + datastore migration
**Goal:** Accounts and a real database.
**Deliverables:** User identity/accounts; migrate memory/audit/state from JSON files to SQLite (then optionally server DB); encrypted per-user store.
**Dependencies:** 85, 77.
**Effort:** L · **Impact:** High (scale + multi-device prerequisite).
**Exit criteria:** Concurrent sessions don't corrupt state; queries replace full-file scans; migration is lossless.

### Phase 87 — Web client with rich, sourced answers
**Goal:** Output that matches modern AI products.
**Deliverables:** Web UI rendering citations, tables, cards, step traces, and confidence; live progress for agent runs.
**Dependencies:** 85.
**Effort:** XL · **Impact:** High (perceived intelligence + daily use).
**Exit criteria:** Answers show sources + confidence; agent progress visible; usable on desktop browser.

### Phase 88 — Gmail (read-only) connector
**Goal:** Make "summarize my inbox" real.
**Deliverables:** OAuth (keychain-stored), read-only scope; tool exposed via Phase 78; consent + audit.
**Dependencies:** 73 (secrets), 78 (tool protocol), 86 (identity).
**Effort:** L · **Impact:** High.
**Exit criteria:** Real inbox summary with citations to messages; PASS when authorized, SKIP when not; no write scope present.

### Phase 89 — Google Calendar (read-only) connector
**Goal:** Real "summarize my day / find conflicts."
**Deliverables:** Same pattern as 88, calendar.readonly.
**Dependencies:** 88.
**Effort:** M · **Impact:** High.
**Exit criteria:** Real calendar summary + conflict detection; read-only enforced.

### Phase 90 — Files/Drive + document & PDF understanding
**Goal:** "Read this and answer."
**Deliverables:** Local files + Drive (read-only); PDF/spreadsheet/screenshot ingestion → embeddings → grounded answers with citations.
**Dependencies:** 80 (embeddings), 87 (rich output).
**Effort:** L · **Impact:** High (core knowledge-worker need).
**Exit criteria:** Q&A over a supplied document returns cited, grounded answers; refuses to answer beyond the document.

### Phase 91 — Mobile-reachable surface
**Goal:** Reach the assistant from a phone.
**Deliverables:** PWA or thin client over the Phase 85 API; push notifications for proactivity (Wave D).
**Dependencies:** 85, 86, 87.
**Effort:** L · **Impact:** High (daily-use ceiling).
**Exit criteria:** Authenticated remote access; push delivery works.

---

## WAVE D — Assistant That Anticipates (M4)

### Phase 92 — Proactivity engine
**Goal:** It acts before you ask (safely).
**Deliverables:** Scheduled briefings (morning digest), "tell me when X" watchers, suggestion surfacing; built on the existing scheduler + connectors + memory.
**Dependencies:** 80, 88/89, 91.
**Effort:** L · **Impact:** High.
**Exit criteria:** A scheduled briefing delivers real, sourced content; watchers fire on real conditions; all proactive output is read-only.

### Phase 93 — Personalization & learning
**Goal:** It adapts to you.
**Deliverables:** Safe learning of domains/tone/routines feeding the planner; lessons memory generalized from the autonomy memory (non-sensitive).
**Dependencies:** 80.
**Effort:** M · **Impact:** Med-High.
**Exit criteria:** Demonstrable personalization on an eval; no sensitive data retained beyond policy.

### Phase 94 — Multimodal output
**Goal:** Charts/images/audio summaries, not just text.
**Deliverables:** Chart/table generation; optional spoken summaries; image rendering in the web client.
**Dependencies:** 87.
**Effort:** M · **Impact:** Med.
**Exit criteria:** A data answer renders a correct chart; audio summary plays.

### Phase 95 — Gated *reversible* actions
**Goal:** Carefully cross from read-only to reversible — never irreversible.
**Deliverables:** Draft email (not send), create calendar event, create a note — each behind **double confirmation + reversibility check + full audit**; explicit per-action allowlist.
**Dependencies:** 82 (injection safety), 88/89, 96-style review.
**Effort:** L · **Impact:** High (but highest-risk — gate hard).
**Exit criteria:** Only reversible, allowlisted actions reachable; every action double-confirmed, reversible, and audited; irreversible actions provably impossible to plan or execute.

### Phase 96 — Collaboration & sharing
**Goal:** Knowledge work is shared.
**Deliverables:** Shareable reports/findings; export; optional team visibility.
**Dependencies:** 86, 87.
**Effort:** M · **Impact:** Med.
**Exit criteria:** A report is shareable via link/export with access control.

---

## WAVE E — Platform & Moat (M5)

### Phase 97 — Third-party tool/skill SDK
**Goal:** Others extend JARVIS via the Phase 78 protocol.
**Deliverables:** SDK + docs + safety-class review process; the trading/investigation domain becomes the first first-party plugin.
**Dependencies:** 78, 84.
**Effort:** L · **Impact:** High (moat).
**Exit criteria:** A sample third-party tool installs and runs under the same safety/audit contract.

### Phase 98 — Cross-platform core
**Goal:** Escape Windows-only.
**Deliverables:** Decouple win32/Tesseract/pyttsx3 behind interfaces; macOS/Linux support for the core (voice/desktop optional per-OS).
**Dependencies:** 85 (service boundary makes this tractable).
**Effort:** XL · **Impact:** Med-High (TAM).
**Exit criteria:** Core runs headless on macOS/Linux with parity on non-desktop features.

### Phase 99 — Team / enterprise
**Goal:** Sellable to organizations.
**Deliverables:** Workspaces, roles, admin policy, audit export, data-retention controls, SSO.
**Dependencies:** 86, 96.
**Effort:** XL · **Impact:** High (revenue).
**Exit criteria:** Multi-user workspace with role-based permissions and exportable audit.

### Phase 100 — Marketplace & monetization
**Goal:** Sustainable business surface.
**Deliverables:** Subscription tiers, connector/tool packs, enterprise plan; usage metering.
**Dependencies:** 97, 99.
**Effort:** L · **Impact:** High.
**Exit criteria:** A paid tier gates premium connectors/tools; metering accurate.

---

## Parallelization (tracks that can run concurrently)

- **Track 1 (critical path):** 73 → 77 → 78 → 79 → 80 → 81 → 84 → 85 → 86 → 87 → 90.
- **Track 2 (reliability, parallel to B):** 75, 76 can run alongside 78–80.
- **Track 3 (connectors, after 78+86):** 88 → 89 → 90 in series; can overlap 87.
- **Track 4 (safety, gates B/D):** 82 must precede 95; 73's guards persist throughout.
- **Track 5 (platform, last):** 97–100 after the brain (B) and reach (C) are stable.

---

## Risk register (top risks + mitigation)

| Risk | Mitigation |
|------|-----------|
| LLM router increases cost/latency | Rule fast-path cache (79); per-intent latency budget from 76 |
| Tool-protocol migration breaks parity | Parity tests vs legacy handlers (78); migrate incrementally |
| Prompt injection via web/email content | Phase 82 before any reversible action (95); forbidden guard backstop |
| Memory migration data loss | Lossless migration tests (77, 86) before deleting old stores |
| Scope creep re-grows intent sprawl | Phase 84 net-reduction gate; tools-only for new capabilities |
| Connectors leak PII into logs/memory | Read-only scopes; policy-enforced redaction; audit review (88–90) |
| "Reversible" actions drift toward irreversible | Hard allowlist + reversibility check + double-confirm (95); never autonomous |

---

## Definition of done for the whole program (by milestone)
- **M1:** zero fake-success paths; encrypted state; finished agent loop; CI + evals + observability; one memory.
- **M2:** LLM routes/plans over typed tools; semantic memory + profile; intent surface materially reduced; injection-safe.
- **M3:** reachable via API + web + mobile; identity + DB; Gmail/Calendar/Files read-only + document Q&A.
- **M4:** proactive briefings/watchers; personalization; multimodal; gated reversible drafts; sharing.
- **M5:** third-party SDK; cross-platform core; enterprise; monetization.

Throughout: **no autonomous irreversible actions; no fake success; honest failure always.**

*End of roadmap — design only, no code.*
