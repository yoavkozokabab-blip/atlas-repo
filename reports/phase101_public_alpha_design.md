# Phase 101 — Repository Intelligence Platform: Public Alpha Design

**Status:** Design only. No code.
**Date:** 2026-05-31
**Premise (assumed proven):** the Phase 100B context-compression benchmark
**succeeds** (Claude+JARVIS ≥2× token compression, ≥40% cost reduction, equal-or-
better quality, zero fabrication) and the Phase 99/100 historical confirmation
**succeeds** (a measured `confirmed_defect` tier at 100% precision with directional
buggy→fixed clearance).
**This phase designs the first public alpha** of that platform.

---

## 0. What the platform is, and how it must be sold

**One-line positioning:**

> JARVIS is a **deterministic repository-intelligence layer**. It makes your coding
> agent **cheaper and sharper** (answers architecture/impact/bug questions from a
> precomputed map instead of raw-file dumps) and it **confirms real defects with
> proof** — locally, with no guessing.

**Two proven value props, sold in order of proof:**

| Lead | Value prop | Proof | Risk posture |
|---|---|---|---|
| **Primary** | **Context compression** — cut agent tokens/cost on repo questions | 100B (broad, measured) | Low — broadly applicable, hard to over-claim |
| **Differentiator (guarded)** | **Confirmed defects with evidence** | 99/100 (narrow, measured precision) | High — one false "this is broken" destroys trust; ship under-claimed |

**The governing product principle (inherited from the whole program):** *under-claim.*
The fastest way to kill this product is a confident wrong answer. Every surface
leads with what is measured, labels certainty explicitly, and says "unknown" rather
than guessing.

---

## 1. Installation flow

**Design goals:** local-first, zero code upload by default, < 2 minutes to value,
plugs into the user's existing agent.

| Step | Command / action | Notes |
|---|---|---|
| 1. Install | `pipx install jarvis-repo-intel` (also Homebrew / standalone binary) | Single dependency-isolated install; Python-repo target in alpha |
| 2. Index | `jarvis init` (run in the repo root) | Builds the deterministic index + subsystem map + dependency graph **locally**; writes only to `./.jarvis/` |
| 3. Connect agent | `jarvis mcp install` | Registers the JARVIS **MCP server** with Claude Code / Cursor / compatible agents so `ask`/`graph`/`impact` become agent tools |
| 4. (Optional) Account | `jarvis login` | Only for metered/Pro features; **core analysis needs no account and no network** |

**Privacy stated at install (trust front-loading):**
> "Your code is analyzed **on your machine**. JARVIS uploads nothing by default.
> Telemetry is opt-in. The `.jarvis/` index never leaves your repo."

**Prerequisites:** git repo, Python codebase (alpha scope), local Python/runtime for
the CLI. No API key required for deterministic analysis (no LLM in the core).

**Uninstall is one command** (`pipx uninstall` + `rm -rf .jarvis/`) — reversibility
is part of trust.

---

## 2. First-run experience

The first run must produce **verifiable value with zero LLM and zero upload**,
then make the agent-compression win tangible.

**Stage 1 — Repository Snapshot (instant, deterministic).**
`jarvis init` finishes with a snapshot the user can immediately verify (grounded in
the RU-2 output shape):
```
Repository Snapshot  (4,060 files · 665 production · built locally in 6s)
Top subsystems:   voice (133) · actions (65) · builder_core (47) · brain · core
Entry points:     main.py · builder_core/cli.py · voice/voice_loop.py
Dependency graph: 1,410 modules · 3 import cycles · top-imported: core.app
Roles:            production 665 · tests 152 · benchmarks 1,873 · docs 4
```
Every line is checkable. This is the "it understands my repo" moment — before any
question is asked.

**Stage 2 — Three guided questions.**
Prompt the user to run three `ask` queries (one architecture, one impact, one
bug-lead), each returning a **compact, evidence-cited** answer plus the **ASK
QUALITY** panel (production% / reports% / benchmark%). Establishes: answers cite
real files; nothing fabricated.

**Stage 3 — The compression moment (the hook).**
> "Now ask Claude the same question. Watch the token counter."
Side-by-side: Claude alone (reads many files) vs Claude+JARVIS (one `ask`). The live
token/cost delta is the 100B value made personal. This is the conversion event.

**Stage 4 — Opt-in confirmed-defect scan (guarded).**
`jarvis confirm` (default-off gate, explicit opt-in) returns the **small** confirmed
tier + review leads, each labeled and evidence-backed:
> "We only call something a **Confirmed Defect** when we can prove it. Most findings
> are **Review Leads** — places worth inspecting, not bugs."

**Time-to-first-value target:** Repository Snapshot < 2 min; compression "aha" < 5 min.

---

## 3. Trust surface

The trust surface is the product's moat **and** its single largest risk. It is
engineered, not assumed.

| Trust pillar | How it shows up in-product |
|---|---|
| **Evidence on every claim** | Every answer/finding cites real `file:line`; confirmed defects ship the full proof packet (contract → feasible path → consequence → witness → unknowns). Nothing is asserted without a clickable source. |
| **Determinism** | Same repo → same answer, byte-stable. No randomness, no LLM in the core. Users can diff two runs. |
| **"Unknown beats guessing"** | Dynamic dispatch / degraded graph → JARVIS says **"unresolved"**, never invents a callee. The hallucination floor: a fabricated path is a product bug, not a quirk. |
| **Tiered certainty, never blurred** | `Confirmed Defect` → `Strong Suspect` → `Review Lead` → `Refuted`. A lead is **never** called a bug. The word "broken" is reserved for the confirmed tier. |
| **Published, measured precision** | The confirmed-tier precision (99B/100) and the compression numbers (100B) are shown openly, with the corpus and method. "Here is our measured precision and how to reproduce it." |
| **0-FP discipline** | The confirmed gate is calibrated to **zero false positives** in evaluation; when proof is incomplete it **stays silent**. Silence is a feature. |
| **Local & auditable** | Code stays local; the data boundary is explicit and inspectable; telemetry opt-in; `.jarvis/` is plain, readable JSON. |
| **Honest scope in-product** | The UI states the alpha limits (Python; confirmed = `inconsistent_return`; size caps; degraded disclosure) wherever they bite, not buried in docs. |

**The trust contract, stated to users:**
> "If JARVIS says **Confirmed Defect**, we can prove it broke and the fix clears it.
> If JARVIS isn't sure, it says so. It will never invent a file, a dependency, or a
> bug."

---

## 4. Demo workflow

A scripted, **reproducible** ~6-minute demo (pinned repo + recorded numbers tied to
the 100B manifest and 100A corpus), structured as three acts:

**Act 1 — Compression (the broad win).**
On a real repo, ask *"What breaks if I change `core/app.py`?"* in Claude alone →
show tokens/cost/time. Then Claude+JARVIS (`impact-file`) → token counter drops ≥2×,
same-or-better answer. Repeat for *"What are the main subsystems?"*. **The hook:
JARVIS pays for itself in agent tokens.**

**Act 2 — Confirmed defect (the trust differentiator).**
Run `jarvis confirm` → surface a **Historically Proven Confirmed Defect**: show its
packet (violated return contract, feasible path, the failing trigger test, and the
buggy→fixed differential that clears on the fix). Then show a **Review Lead** right
next to it, explicitly labeled *not a bug*. **The trust moment: proof, not vibes.**

**Act 3 — Honesty (the differentiator vs LLM-only tools).**
Ask about a dynamically-dispatched call. JARVIS answers **"unresolved — this call is
dynamic; here's what I *can* prove."** **The clincher: it doesn't hallucinate.**

The demo ends on the dashboard: measured compression ratio, confirmed-tier precision,
and "reproduce this yourself" — closing on verifiability.

---

## 5. Pricing candidates

Core analysis is **local and deterministic** (near-zero marginal compute), so pricing
is **value-anchored**, not compute-metered. The ROI anchor is the 100B token savings.

| Tier | Candidate price | What's included | Rationale |
|---|---|---|---|
| **Free / OSS** | $0 | Local CLI; `ask`/`graph`/`impact` on personal + public repos; capped repo size; community support | Adoption + trust; the compression value is best experienced, not pitched |
| **Pro (individual)** | candidate **$15–25 / seat / mo** | MCP agent integration with metering; confirmed-defect scanning; private repos; larger size caps | Priced **below** measured monthly agent-token savings → ROI-positive ("pays for itself") |
| **Team** | candidate **$30–50 / seat / mo** | Pro + CI integration (confirmed-defect gate as a PR check), shared config, audit log, SSO | Confirmed-defect-in-CI is the premium differentiator |
| **Design-partner (alpha)** | **free / deeply discounted** | Pro features in exchange for consented usage data + feedback | Alpha is for learning, not revenue |

**Pricing logic:** anchor the Pro price to the **measured** agent-cost reduction from
100B — if JARVIS saves a heavy agent user more in tokens than the subscription, the
purchase is rational on compression alone, and confirmed-defects are upside. Prices
above are **candidates to validate in alpha**, not commitments.

---

## 6. Usage limits

Alpha limits are simultaneously **scale controls** and **trust controls** — they keep
the product inside its proven envelope and degrade honestly beyond it.

| Limit | Alpha value | Why |
|---|---|---|
| **Language** | Python only | Where compression + confirmation are measured (100B/100A) |
| **Repo size** | ≤ the depgraph proven range (≈5,000 Python files); beyond → **degraded/unknown**, not a wrong answer | Honesty over coverage; inherits `_MAX_FILES` degradation |
| **Confirmed-defect scope** | `inconsistent_return` only; all other rules → **Review Lead** | Phase 99 first gate; never over-promise the confirmed tier |
| **Confirmed gate default** | **OFF**, opt-in, with the precision disclaimer | The catastrophic-FP surface is gated and consented |
| **Cohort** | Invite-only / design partners, capped N | Limits blast radius of any trust failure during alpha |
| **Rate** | Per-tier query/scan caps; agent-integration token metering | Fair use + cost control |
| **Network** | Core fully offline; only opt-in telemetry/metering leaves the machine | Privacy contract |

**Limits-as-trust:** the product is loud about *where it is proven* and refuses to
bluff outside it. A capped, honest alpha beats a broad, over-claiming one.

---

## 7. Alpha scope, graduation, and risks

**Explicitly OUT of the alpha:** automated repair / fix generation; multi-language;
repos beyond the proven size; autonomous actions on the codebase; any confirmed-defect
rule beyond `inconsistent_return`; any cloud analysis of private code.

**Graduation to GA requires (measured, not assumed):**
- 100B verdict **SUCCESS** sustained on ≥2 external repos (not just `local_jarvis`).
- Confirmed-defect precision **100% / 0 FP** held across the alpha cohort (Phase 99B
  7/10 gate), with ≥10 human-accepted confirmed defects across ≥5 repos.
- Alpha retention / would-use-again above a preregistered bar.
- Zero confirmed-tier false positives reported by any alpha user.

**Top risks and guardrails:**

| Risk | Guardrail |
|---|---|
| A confident **false "this is broken"** | Confirmed gate default-off, opt-in, 0-FP-calibrated, scope-limited; review-lead labeling; published precision; one FP → pause the tier |
| Over-claiming the compression number | Publish the method + per-repo variance; let users measure their own delta in first-run |
| Privacy concern blocks adoption | Local-first, no-upload-by-default, auditable `.jarvis/`, opt-in telemetry stated at install |
| Scope creep (repair, multi-lang) eroding focus | Hard out-of-scope list; alpha stays a *measurement and trust* exercise |
| Degraded/large repos producing junk | Degrade to "unknown," never to a wrong answer |

---

## 8. Acceptance (definition of done for this design)

| Requirement | Section |
|---|---|
| Installation flow | §1 |
| First-run experience | §2 |
| Trust surface | §3 |
| Demo workflow | §4 |
| Pricing candidates | §5 |
| Usage limits | §6 |
| Scope / graduation / risk guardrails | §7 |
| No code; product design only; under-claim discipline throughout | whole doc |

---

## 9. Bottom line

The first public alpha ships JARVIS as a **local, deterministic repository-
intelligence layer** that leads with the **broadly-proven compression win** (cheaper,
sharper coding agents) and offers a **guarded, evidence-backed confirmed-defect tier**
as the differentiator. Installation is local and upload-free; the first run delivers a
verifiable repository snapshot in under two minutes and a live token-savings "aha";
the trust surface is engineered around evidence, determinism, tiered certainty, and
"unknown beats guessing"; pricing is anchored to measured agent-token savings; and
every usage limit doubles as a promise to operate only where the product is proven.
The alpha's job is not scale — it is to **earn trust at small blast radius** and graduate
on measured precision and compression, not on claims.
