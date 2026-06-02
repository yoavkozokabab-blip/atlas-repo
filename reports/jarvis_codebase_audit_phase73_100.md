# JARVIS Codebase Audit — Technical + Product + Phase 73–100 Plan
**Date:** 2026-05-29
**Scope:** Whole-project audit (analysis only — no code written).
**Lens:** Production readiness, architecture, scalability, security, and "is this a real AI OS."
**Grounding facts (measured):** 929 Python files, ~113,000 LOC, 116 `tests/` files (+231 in `tests_tmp/`), **507 `Intent` enum members**, **487 registered action handlers**, ~40 top-level packages, **no web server / API** (single-process Windows desktop app), `voice/` is the largest package (134 files), packaging = `requirements.txt` only.

> Honest baseline from this session's prior audits: composite production readiness ≈ **62%** (not the ~76% the roadmap projected). This audit explains *why* and what to do about it.

---

## 0. One-paragraph verdict

JARVIS is an unusually broad, single-user Windows voice assistant with a real command pipeline (classify → validate → confirm → execute → log), a genuine Phase 71/72 read-only browser tool-use loop, and strong safety instincts (confirmation gates, forbidden-action guards, no-mock-success contracts in the new layers). But it carries the weight of **507 intents / 487 handlers** of mostly trading/investigation surface that dwarfs the "assistant" core, **two parallel memory systems**, a **keyword classifier doing an LLM's job**, **mock paths still counted as success in legacy browser actions**, and **file-based single-process state** that caps it at one user on one machine. It is a powerful prototype, not yet a product, and not yet an "AI OS."

---

## 1. Top 20 Technical Weaknesses (ranked)

| # | Weakness | Evidence | Impact |
|---|----------|----------|--------|
| T1 | **Intent/handler sprawl: 507 intents, 487 handlers** hand-registered in one 1,000+ line `actions/registry.py` | `core/types.py` (507), `actions/registry.py` `_register_defaults` | Unmaintainable; every feature is a bespoke handler; no generalization |
| T2 | **Rule/keyword classifier is the primary brain** (~1,950-line phrase table); LLM is only a fallback | `brain/intent_classifier.py` | Brittle phrasing match; can't handle novel requests; the opposite of how ChatGPT/Claude work |
| T3 | **Legacy browser still mock-by-default and counts mock as success** | `browser/runtime.py:23` `provider="mock"`; `actions/phase62_browser_actions.py:27,83` return `result_success` when `provider=="mock"` | Fake success in a user-facing path (the new `tooluse/` layer avoids this, but legacy remains) |
| T4 | **Two memory systems** (`memory/store.py` PersonalMemoryStore + `memory/session_memory.py`) never unified | both exist; session entries not searchable via `search_memory` | Fragmented recall; "memory" feels unreliable |
| T5 | **"Semantic" search is bag-of-words cosine**, not embeddings | `memory/semantic_runtime.py` token-frequency vectors | Misleading capability; recall quality low |
| T6 | **File-based JSON/JSONL state, single process** | `data/*.json`, rotating `*.jsonl`, in-process singletons everywhere | No concurrency, no multi-device, race-prone, doesn't scale |
| T7 | **No service/API boundary** | no FastAPI/Flask/server; everything in-process | Can't expose to web/mobile, can't run headless as a daemon cleanly, no remote control |
| T8 | **Agent architecture is ownership metadata, not orchestration** | `agents/runtime_wiring.py` gates health + stamps `agent_id`, but `ActionRegistry.execute` is still a string lookup | "12 agents" don't actually plan/cooperate; no real multi-agent reasoning |
| T9 | **Voice stack over-built and fragile** (134 files; many `test_*`, `force_*`, `*_hotfix` paths) | `voice/` package | Enormous surface for a feature most users won't rely on; maintenance sink |
| T10 | **`tests_tmp/` (231 files) > `tests/` (116)** | repo listing | Test hygiene problem; unclear which tests are authoritative; CI signal diluted |
| T11 | **No CI/CD, no packaging, no lockfile** | only `requirements.txt`; no `pyproject.toml`, no CI config seen | No reproducible builds; "works on my machine" risk |
| T12 | **Startup imports the world** (`actions/registry.py` imports ~60 modules eagerly) | top of `actions/registry.py` | Slow cold start; one bad import breaks all commands |
| T13 | **Confirmation is a single global slot** | `core/confirmation.py` `_store: PendingConfirmation \| None` | Only one pending action at a time; no concurrent/queued approvals; not multi-user safe |
| T14 | **Config monolith** (`config.py` 1,450+ lines, env-driven, dozens of flags) | `config.py` | Behavior depends on a large implicit flag matrix; hard to reason about |
| T15 | **Real LLM reasoning absent from the execution core** | classifier-only routing; no plan/act/reflect loop except the new bounded `tooluse`/`autonomy` layers | The product can't "think"; it pattern-matches |
| T16 | **Windows-only, hard dependency on win32/pywin32/Tesseract/pyttsx3** | `desktop/`, `vision/`, `voice/` | No cross-platform path; narrows TAM and CI options |
| T17 | **Observability is JSONL files, no metrics/tracing/dashboards** | `services/observability.py`, rotating jsonl | Can't see latency/error trends; debugging is grep |
| T18 | **Recovery/watchdog only recently wired to CLI** and threads partially registered | Sprint 3.2 watchdog; voice/TTS thread registration partial | Silent thread death still possible in some paths |
| T19 | **Huge trading/investigation domain bolted into a personal assistant** | `investigation/`, `operational/`, `alpha/`, `task_agent/`, Intents phases 45–55 | Product identity confusion; most code serves a niche the "assistant" framing hides |
| T20 | **No dependency injection / global singletons everywhere** | `get_*()` singletons across `core/`, `agents/`, `voice/`, `tooluse/` | Hard to test in isolation, hard to run two contexts, hidden coupling |

---

## 2. Top 20 Product Weaknesses (ranked)

| # | Weakness | Why it hurts |
|---|----------|--------------|
| P1 | **No real conversational intelligence** — it matches commands, it doesn't converse or reason | Users expect ChatGPT-level understanding; this feels like a 2015 voice macro engine |
| P2 | **Discoverability is near-zero** — 507 intents, but the user must know magic phrases | Power is invisible; "what can you do" can't convey 487 handlers usefully |
| P3 | **Memory doesn't feel persistent or smart** (fragmented, keyword recall, TTLs) | The #1 thing users want from a personal AI is "it remembers me" |
| P4 | **Integrations are stubs** — Gmail/Calendar/Telegram ~12% | "Summarize my inbox" implies a product that doesn't exist yet |
| P5 | **Browser/research only just became real and bounded** | Can't yet do the "agent" things users now expect (book, buy intentionally excluded — but even multi-step research is brand new) |
| P6 | **No mobile, no web, no remote** — tied to one Windows box | A personal AI you can't reach from your phone has a low daily-use ceiling |discriminator
| P7 | **Output is plain text in a console/overlay** — no rich UI, citations, cards, tables | Perplexity/ChatGPT set the bar for sourced, structured answers |
| P8 | **No proactivity** — it only reacts to commands | "AI OS" implies anticipation (briefings, reminders, watching things) |
| P9 | **Trust is fragile** — historical inflated scores, mock-success paths | Once a user catches a fake "done," they stop trusting all of it |
| P10 | **Latency unknown/uninstrumented for the user** | No sense of speed; voice round-trips feel laggy without feedback |
| P11 | **No multi-turn task continuity** that feels natural | Each command is mostly standalone; "the third one" context is limited |
| P12 | **No personalization** beyond aliases/preferences | Doesn't learn your domains, tone, routines |
| P13 | **No file/document intelligence** — can't "read this PDF and answer" | A core knowledge-worker need is missing |
| P14 | **No multimodal output** (images, charts, audio summaries) | Text-only limits perceived intelligence |
| P15 | **Onboarding is nonexistent** | A new user has no guided path to value |
| P16 | **Error UX is technical** ("not_implemented", stack-ish messages) | Breaks the illusion of an assistant |
| P17 | **No collaboration/sharing** (reports stay local) | Knowledge work is shared; local-only md files don't fit workflows |
| P18 | **No account/identity** | Can't follow the user across devices/sessions meaningfully |
| P19 | **Voice-first bias** where most durable value is text/agentic | Heavy investment in a modality with high failure rate, low daily reliance |
| P20 | **No clear "job to be done"** — assistant + trader + investigator + coder | Tries to be everything; users can't form a one-line mental model |

---

## 3. Missing capabilities for a *true* AI Operating System

An "AI OS" mediates a user's digital life with memory, reasoning, tools, and proactivity. JARVIS is missing:

1. **A reasoning core (LLM-in-the-loop planning)** — plan→act→reflect over tools, not phrase-matching. *(Phase 71/72/autonomy is the seed; it needs to become the default brain.)*
2. **Durable, unified, semantic memory** — one store, real embeddings, entities, recency+importance ranking, user profile.
3. **A real tool/skill protocol** — a uniform, typed tool interface (à la MCP / function-calling) instead of 487 bespoke handlers; tools register capabilities, schemas, safety class.
4. **Connectors** — email, calendar, files, drive, messaging, notes — read first, then gated write.
5. **Persistent context & identity** — accounts, cross-device sync, session continuity.
6. **Proactivity engine** — scheduled briefings, watchers ("tell me when X"), suggestions.
7. **Document & data understanding** — PDFs, spreadsheets, screenshots → answers with citations.
8. **A real UI surface** — rich answers (citations, tables, cards), and a web/mobile client.
9. **Multi-agent orchestration that actually executes** — a planner that decomposes and dispatches to specialist agents with verification.
10. **Permissioned action layer** — a single capability/consent model spanning read-only → reversible → gated-irreversible, with audit. *(The Phase 71/72 forbidden-action model is the right nucleus.)*
11. **Trust & transparency surface** — every answer shows sources, confidence, what was tried/failed (autonomy report does this — generalize it).
12. **Observability & evals** — task success metrics, regression evals on real prompts.

---

## 4. Architecture bottlenecks

- **B-A1: The monolithic ActionRegistry** is the central chokepoint — 487 handlers, eager imports, string dispatch. Everything routes through one object; it's the single biggest scaling and maintainability bottleneck.
- **B-A2: Rule classifier as the front door** — caps understanding; the LLM is bolted on as fallback rather than being the router.
- **B-A3: Global singletons + in-process state** — `get_*()` everywhere prevents concurrency, multi-session, and clean testing.
- **B-A4: Single global confirmation slot** — serializes all human-in-the-loop actions; incompatible with concurrent agent work.
- **B-A5: File-based persistence** — JSON/JSONL with locks; no transactions, no queries, no concurrency.
- **B-A6: No process/service boundary** — voice loop, overlay (Qt), watchdog, health monitor, agents all share one Python process; one crash risks all.
- **B-A7: Config-flag combinatorics** — runtime behavior is an implicit matrix of ~dozens of env flags.

---

## 5. Scalability risks

1. **Single user / single machine** — no multi-tenant story; file state and singletons make it a 1:1 deployment.
2. **Cold start cost** — importing ~60 action modules + voice stack on launch.
3. **Unbounded domain growth** — adding capability = adding an intent + handler + phrases; O(N) human work per feature, already at 507.
4. **Memory file growth** — JSON store loaded fully into memory on each `_load()`; linear scans; will degrade with size.
5. **Browser concurrency** — one Playwright session; no pooling; autonomous multi-source is serial.
6. **No horizontal scaling path** without a service/API + datastore refactor.
7. **Thread-based concurrency in one GIL process** — voice/TTS/overlay/watchdog contend; CPU-bound work blocks.

---

## 6. Security risks

1. **S-1 Local plaintext state** — `data/*.json` (memory, preferences, approvals) unencrypted; anyone with disk access reads it.
2. **S-2 OAuth/token handling for future connectors** — plan stores tokens in `data/oauth_tokens/*.json` (Sprint 6); needs OS keychain / encryption, not flat files.
3. **S-3 Desktop control + clipboard + screen OCR** — powerful capabilities; confirmation-gated but a compromised process has broad reach (window control, clipboard read/write, screenshots).
4. **S-4 Command injection surface via PowerShell/app launch** — `actions/powershell.py`, app launcher; allowlists exist but must be airtight.
5. **S-5 Browser visits arbitrary URLs** — SSRF-like exposure (internal IPs), drive-by content; the autonomy layer should enforce an egress policy / block private ranges.
6. **S-6 Audit logs may capture page text** — must guarantee no secrets/PII; the autonomy memory is careful (hostnames only) but full audit md/json store page excerpts — review for sensitive capture.
7. **S-7 No authn/authz** — any local caller can issue any command; no user identity, no per-capability permission beyond confirmation.
8. **S-8 LLM prompt-injection** (as soon as web content feeds an LLM planner) — a visited page could instruct the agent; needs content/instruction separation and the forbidden-action guard as the backstop.
9. **S-9 Dependency supply chain** — large native dep set (pywin32, playwright, tesseract, torch-ish STT) with no lockfile/SCA.

---

## 7. Features that appear implemented but are NOT production-ready

| Feature | Appears | Reality |
|---------|---------|---------|
| Web browsing / "search the web" | Intent + handlers exist | Legacy path is **mock**; real path (Phase 71/72) is new, read-only, single-flow |
| "Summarize my inbox / calendar / day" | Intents + actions exist | **Stubs** — no real Gmail/Calendar provider (~12%) |
| Telegram notifications | `integrations/telegram_client.py` | **2-line stub** |
| Semantic memory search | `search_memory`, "semantic" module | **Keyword cosine**, not semantic |
| 12-agent architecture | `agents/registry.py`, runtime_wiring | **Ownership/health metadata**, not real orchestration |
| Investigation/auto-fix/patch phases (45–55) | ~hundreds of intents | Trading-domain, **unverified for general users**, acceptance historically inflated |
| Voice barge-in / adaptive silence | referenced | **Not implemented** (Sprint 5 scope) |
| Desktop "do things on screen" (click/type) | intents exist, confirmation-gated | Real but **narrow/fragile**; OCR-dependent |
| Autonomous research agent (this session) | branch `autonomous-agent-stack-v1` | **WIP, uncommitted** — core loop works in fake/real tests, router wiring partially done; not finished |

---

## 8. Highest-ROI improvements (the short list)

1. **Make the LLM the router/planner; keep handlers as tools.** Collapse 507-intent matching into LLM function-calling over a curated tool catalog. *Massive UX leap, shrinks maintenance.*
2. **Unify memory + add real embeddings + a user profile.** The single biggest "feels intelligent" win.
3. **Finish + generalize the bounded agent loop (Phase 71/72/autonomy) as the default for open-ended requests** with sourced, structured answers.
4. **Ship 2–3 real read-only connectors (Gmail, Calendar, Files)** behind the existing consent model. Turns stubs into the headline feature.
5. **Add a thin service/API + a simple web client** so it's reachable and answers are rich (citations/cards). Breaks the single-box ceiling.
6. **Kill the mock-success leak and quarantine the legacy browser path.** Trust repair.
7. **Encrypt local state + add a real secrets store.** Table stakes before connectors.

---

## 9. Ranked roadmap (impact × effort × dependencies)

Effort: S(<1d) · M(2–5d) · L(1–2wk) · XL(>2wk). Impact: Critical/High/Med.

| Rank | Initiative | Impact | Effort | Dependencies |
|------|------------|--------|--------|--------------|
| 1 | LLM-as-router/planner over a typed tool catalog | Critical | XL | Tool catalog refactor (#3); eval harness |
| 2 | Unified semantic memory + user profile | Critical | L | Embeddings provider; migration from 2 stores |
| 3 | Tool/skill protocol (typed, safety-classed) replacing bespoke handlers | Critical | XL | Inventory of 487 handlers; adapter layer |
| 4 | Finish autonomous research agent + structured sourced answers | High | M | Phase 71/72 (done); WIP branch |
| 5 | Real read-only connectors: Gmail, Calendar, Files | High | L each | OAuth + secrets store (#8) |
| 6 | Service/API boundary + minimal web client (rich answers) | High | XL | Auth/identity; datastore |
| 7 | Quarantine legacy mock browser; remove mock-success | High | S | Route all browser via `tooluse/` |
| 8 | Encrypt local state + OS keychain secrets | High | M | — |
| 9 | Proactivity engine (briefings, watchers, scheduled tasks) | High | L | Memory (#2); connectors (#5); scheduler exists |
| 10 | Datastore migration (SQLite first) for memory/audit/state | Med-High | L | Touches many singletons |
| 11 | Observability: metrics + task-success evals | Med-High | M | — |
| 12 | Document/PDF understanding ("read this and answer") | High | M | Memory (#2); LLM core (#1) |
| 13 | Onboarding + capability discovery UX | Med | M | Web/UI (#6) |
| 14 | Test hygiene: delete/quarantine `tests_tmp/`, add CI + lockfile | Med | M | — |
| 15 | Decompose `config.py` + reduce flag matrix | Med | M | — |
| 16 | Egress policy / SSRF guard for browser | Med | S | autonomy layer |
| 17 | Cross-platform path (decouple win32/tesseract) | Med | XL | Large; defer |
| 18 | Trading/investigation domain → optional plugin | Med | L | Tool protocol (#3) |

---

## 10. Recommended Phase 73–100 plan (themed waves)

**Wave A — Trust & Foundation (Phase 73–77)**
- **73** Quarantine legacy mock browser; route all browsing through `tooluse/`; delete mock-success. Encrypt `data/` at rest + OS keychain for secrets.
- **74** Finish & merge the Autonomous Agent Stack v1 (research/compare, sourced reports, full audit) — *the WIP branch.*
- **75** Eval harness: a fixed prompt set with task-success scoring; wire into CI. Lockfile + CI + delete `tests_tmp/`.
- **76** Observability: latency/error/task-success metrics; structured run traces; a status surface.
- **77** Memory unification (one store) + migration; importance×recency ranking.

**Wave B — The Brain (Phase 78–84)**
- **78** Typed tool/skill protocol (schema + safety class + capability); adapter for top ~40 high-value handlers.
- **79** LLM-as-router: function-calling over the tool catalog; rule classifier becomes a fast-path cache, not the brain.
- **80** Real embeddings + semantic recall; entity/profile extraction (non-sensitive).
- **81** Plan→act→reflect loop generalized from the autonomy executor; verification + recovery as first-class.
- **82** Prompt-injection defenses for web-fed content; egress/SSRF policy; forbidden-action guard as backstop.
- **83** Multi-step task continuity + conversational state across turns.
- **84** Migrate the remaining valuable handlers to tools; deprecate dead intents (cut the 507 surface hard).

**Wave C — Reach & Connectors (Phase 85–91)**
- **85** Service/API boundary (local daemon + typed API).
- **86** Identity/accounts + encrypted per-user store; SQLite/datastore migration.
- **87** Web client with rich, sourced answers (citations, tables, cards).
- **88** Gmail (read-only) connector behind consent + audit.
- **89** Google Calendar (read-only) connector.
- **90** Files/Drive + **document/PDF understanding** ("read this and answer").
- **91** Mobile-reachable surface (PWA or thin app) + push.

**Wave D — Assistant That Anticipates (Phase 92–96)**
- **92** Proactivity engine: scheduled briefings, "tell me when X" watchers.
- **93** Personalization: domains, tone, routines learned safely.
- **94** Multimodal output (charts/images/audio summaries).
- **95** Gated reversible actions (draft email, create calendar event) behind double-confirm + reversibility checks — still no autonomous irreversible actions.
- **96** Collaboration/sharing of reports & findings.

**Wave E — Platform & Moat (Phase 97–100)**
- **97** Third-party tool/skill SDK (others add capabilities via the tool protocol).
- **98** Cross-platform core (decouple win32/tesseract; macOS/Linux).
- **99** Team/enterprise: workspaces, roles, audit export, admin policy.
- **100** Marketplace + monetization surface (subscription tiers, connector packs, enterprise).

---

## 11. What this does NOT change
- The safety posture stays: read-only first; payments/orders/bookings/logins/submits/downloads/deletes/sends remain blocked and only ever reachable (much later, Phase 95) behind explicit double-confirmation + reversibility + audit. No autonomous irreversible actions.
- No "fake success": every wave keeps the Phase 71/72 contracts (real-provider-required, verify-after-act, honest failure).

---

## 12. Note on current working tree
Branch `autonomous-agent-stack-v1` holds **uncommitted WIP**: the autonomy package (`autonomy/*`), router actions, classifier wiring, and config/intent additions are implemented and pass an inline fake+real sanity check, but the full test suite, smokes, and docs for that sprint were not finished (the build was interrupted for this audit). It is Phase 74 above. Nothing was committed during this audit.

*End of audit — analysis only, no code written.*
