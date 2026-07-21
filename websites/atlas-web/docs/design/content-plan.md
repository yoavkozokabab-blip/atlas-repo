# Content Plan — real facts only

Single source of truth = `app/lib/content/facts.ts`. No page or scene may hardcode a product
number outside this file. Nothing below is invented; each is verifiable in-repo.

## Verified facts (safe to publish)

**What it is:** Local-first, persistent repository memory for AI coding agents. Indexes a repo
locally into a **dependency graph + evidence store**; serves **cited context** to coding agents
over **MCP**. Windows desktop app. No signup required (guest mode).

**Agents:** Claude Code, Cursor, Codex — via the Atlas MCP server (**18 tools** in current
build). Config-write hardening verified.

**Persistence:** Scans persist across fresh MCP sessions and are validated against the live repo
before reuse (stale scans are refused, never silently served). Cold scan ~2–4s; **restore
8–11ms** on the installed build (dev ~87ms).

**Capabilities:** Ask Atlas (cited answers, evidence-centric packs with relevance scores +
selection/dependency/impact reasons), Impact (direct-import blast radius), Debug / root-cause
(parses tracebacks → repo files → symbol spans), comparison + general-analysis modes. No LLM in
the retrieval loop — deterministic lookups; answers are evidence-only, never fabricated.

**Benchmarks (harness ships in-repo, reproducible):**
- Sample/demo repo: 18 files / 17 production modules; index ~4s end-to-end; Ask Atlas 1–30ms.
- 50-scenario suite (feature / bug / impact): file recall **0.95 / 0.98 / 0.97**; file precision
  0.80 / 0.30 / 0.88 (bug intentionally casts a wide hypothesis net); all 50 execute without
  error; mean score 86.3. Reproduce: `py -3 benchmarks/generate_suite.py` then
  `py -3 benchmarks/runner.py`.
- Impact engine (separate suite, 20 OSS repos / 100 questions): P 1.00 / R 0.93 on strict gold;
  median ~758ms / p95 ~4.2s. Present with its scope caveats.

**Privacy/security:** Repository indexing runs locally; source is not uploaded to a hosted
analysis service. User decides what context to send to an agent. Installer is currently
**unsigned** (SmartScreen warning) — state this honestly on /download and /security. SHA256 of
the published installer is shown for verification (`INSTALLER_SHA256` in `_config.ts`).

**Distribution:** GitHub `yoavkozokabab-blip/atlas-repo`, **v1.0.1** released; download via
`/download/atlas` redirects to the verified GitHub Release asset. Canonical production site:
atlas-repo-wu76.vercel.app. Current installer SHA256:
`B2531078FC814B9D2AA454FAFD31711AE353AAFCD336C6E39D21B4645A9573EF`.

**Pricing:** Free (local, no signup) / **Pro $19/mo** (7-day trial, no card up front) / Team —
coming soon. Payments run through Paddle (MoR); live charging is not yet wired (Team + Pro
checkout may show "coming soon" states) — do not imply billing is live beyond what ships.

## Honest limitations (state them — they build trust)

- Numbers are self-measured on one Windows dev machine; hardware varies.
- The 50-scenario suite uses a reference repo we built, not a random OSS sample.
- Large-monorepo indexing is slower (active work item; see /roadmap).
- Retrieval quality ≠ end-to-end agent task success — that study isn't published yet.
- Windows only today. Installer unsigned today.

## Forbidden

No invented user counts, enterprise logos, testimonials, security certifications, or
performance claims. No "supercharge/revolutionize/unlock the power/build faster than ever/the
future of coding is here." No fake terminals, chats, or code that doesn't match Atlas.

## Copy deck (home)

- H1: **Your codebase, remembered.**
- Support: *Atlas maps your repository into a persistent memory and serves cited context to
  Claude Code, Cursor and Codex — locally, across every session.*
- Act titles: *Every AI session starts from zero.* / *Atlas maps your repository.* / *Memory
  that survives across sessions.* / *Your agent asks; Atlas answers with citations.* / final:
  *Give your coding agent a persistent understanding of your project.*
