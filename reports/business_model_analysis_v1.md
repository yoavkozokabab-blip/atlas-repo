# Business Model Analysis v1

Date: 2026-06-01

## Executive Answer

If JARVIS proves:

- `50-80%` token reduction; and
- `3-5x` faster repository understanding and change-impact work;

the most valuable near-term business model is:

```text
Claude companion
  sold as a team subscription
```

The product should be positioned as a local repository-intelligence layer that
makes coding agents faster, cheaper, and more grounded:

```text
JARVIS indexes the repository once,
then gives Claude compact architecture, dependency, impact,
and evidence-backed review context on demand.
```

The best initial buyer is a Python engineering team already paying for Claude,
Cursor, or another coding assistant. The best initial pricing unit is a
per-developer team seat with workspace administration, not raw API usage.

Do not lead with:

- autonomous bug finding;
- enterprise governance;
- a general API platform; or
- an attempt to replace Claude.

The proven economic wedge is **context compression**, not model competition.

## Evidence Base

### Phase 95E: Review Value Exists, Bug-Finder Positioning Does Not

| Metric | Result |
| --- | ---: |
| Grounded findings reviewed | `202` |
| Confirmed actionable defects | `0` |
| Useful review leads | `148` (`73.3%`) |
| Misleading findings | `15` (`7.4%`) |

Phase 95E supports:

```text
JARVIS helps developers decide where to look.
```

It does not support:

```text
JARVIS reliably tells developers which code is broken.
```

### Phase 98A: Repository Breadth Exists

| Metric | Result |
| --- | ---: |
| Public repositories scanned | `24` |
| Successful scans | `22` |
| Degraded scans | `2` |
| Unsafe scans | `0` |
| Findings exported | `16,110` |
| Blinded review packets | `300` |

The system can process real repositories safely. The Phase 98A human labels and
repository-usefulness scores remain open.

### Phase 99F: Trust Infrastructure Is Real but Default-Off

Phase 99F repaired the confirmed-defect gate:

- C1-C6 confirmation contract;
- mandatory test or runtime witness;
- observable consequence;
- empty proof obligations;
- evidence bundle;
- shadow mode;
- double default-off flags;
- `371` passing tests.

This is commercially useful as a trust foundation. It is not yet a validated
market claim.

### Phase 100A and 100C: Historical Confirmation Remains Early

Phase 100A defines a `30`-case v1 historical corpus plan.

Phase 100C executed the first zero-setup slice:

| Metric | Result |
| --- | ---: |
| Cases materialized | `10` |
| Confirmed-eligible positives | `0` |
| Predicted confirmations | `0` |
| Confirmed precision | unavailable |
| Confirmed recall | unavailable |
| Confirmed on fixed revision | `0` |

This is a safe result, but not a positive-oracle result. BugsInPy-backed
confirmed-eligible cases still need materialization.

### Phase 100B: The Commercial Wedge

Phase 100B defines the most commercially promising claim:

```text
Claude + JARVIS
  reaches equal-or-better answer quality
  with substantially fewer tokens, less time, and lower cost
  than Claude alone.
```

The benchmark is designed correctly:

- same model;
- same prompts;
- same repository snapshot;
- same generic tools;
- JARVIS tools added only in the companion arm;
- answer quality held constant;
- hallucination and honesty traps included;
- index-build amortization disclosed.

The user-supplied assumption of `50-80%` token reduction and `3-5x` speedup
would clear the Phase 100B success bar materially.

### Phase 100D: Product Shell Is the Remaining Delivery Constraint

The current CLI is not yet self-serve:

- no installable `jarvis-builder` command;
- no package metadata;
- raw traceback on routine invalid-path errors;
- no visible progress or cancellation flow;
- incomplete current documentation;
- limited JSON/SARIF editor and CI workflow support.

This matters commercially: the intelligence wedge is stronger than the current
delivery shell.

## The Value Proposition

The highest-value promise is:

> JARVIS is a local repository-intelligence companion for Claude and coding
> agents. It reduces how much code an agent must read, shortens time to a
> grounded answer, and exposes uncertainty instead of guessing.

The product creates value in four ways:

| Value driver | Why teams care |
| --- | --- |
| Lower token usage | Reduces AI spend and context-window pressure |
| Faster answers | Saves developer time during review, onboarding, and refactor planning |
| Better grounding | Reduces wasted exploration and fabricated dependency claims |
| Local repository boundary | Makes adoption easier for sensitive codebases |

The initial product should focus on:

```text
understand repository
  -> inspect dependencies
  -> assess impact
  -> compress context for Claude
  -> investigate review leads honestly
```

Confirmed-defect functionality should remain a controlled trust layer until
historical validation earns broader surfacing.

## Business Model Ranking

| Rank | Model | Near-term fit | Long-term value | Recommendation |
| ---: | --- | --- | --- | --- |
| 1 | Claude companion + team subscription | Excellent | High | Launch wedge |
| 2 | Developer subscription | Good | Medium | Offer as a simple individual tier |
| 3 | Enterprise | Premature now | Very high later | Expand after team adoption and governance work |
| 4 | API platform | Weak now | Potentially high later | Defer until stable schemas and repeated integrator demand |
| 5 | Standalone Claude companion sold only to individuals | Useful acquisition wedge | Limited capture | Use as positioning, not the only revenue model |

The comparison below evaluates the five requested options separately.

## 1. Developer Subscription

### Product Shape

```text
one developer
  + local repository index
  + CLI or editor workflow
  + Claude companion context
```

### Strengths

- Easy to understand.
- Low-friction entry point after productization.
- Works for freelancers, maintainers, and senior engineers.
- Token savings are personally visible.
- Can be sold without enterprise procurement.
- Good path for early design partners.

### Weaknesses

- Individual willingness to pay is capped.
- Value is partly shared: architecture maps and impact context help the whole
  team, not only one person.
- Token savings may accrue to an employer's AI account rather than the
  individual purchaser.
- Supporting many individuals creates more onboarding burden per dollar.
- Churn risk is higher if the user works mainly in small or familiar
  repositories.

### Best Use

Offer a developer tier as the entry product:

| Tier concept | Suitable scope |
| --- | --- |
| Individual | Local CLI, limited repositories, Claude companion workflow, no team administration |

### Verdict

**Good acquisition model, not the highest-value primary model.**

## 2. Team Subscription

### Product Shape

```text
engineering team
  + shared repository configuration
  + local indexing
  + Claude/Cursor companion workflows
  + consistent architecture and impact answers
  + workflow exports
```

### Strengths

- Aligns value with the group receiving the benefit.
- Teams can measure saved engineering time, reduced AI spend, and faster review.
- Architecture, dependency, and impact intelligence are naturally shared
  workflow assets.
- The buyer can justify spend from both productivity and AI-cost budgets.
- Easier upsell path from individual alpha users.
- Fits PR review, onboarding, regression investigation, and refactor planning.
- Supports a land-and-expand motion without enterprise complexity on day one.

### Why the Economics Are Attractive

Assume:

- a developer asks repository-heavy questions several times per week;
- JARVIS reduces tokens by `50-80%`;
- JARVIS reduces task time by `3-5x`;
- answer quality remains equal or better.

The time saving is likely worth more than the token saving:

```text
developer time saved
  + AI usage saved
  + fewer wrong turns
  + faster onboarding and review
```

Token reduction is a crisp proof point. Developer throughput is the budget
justification.

### Recommended Initial Packaging

| Tier concept | Suitable scope |
| --- | --- |
| Team | Per-developer seats, shared repo configuration, workspace policy, JSON/SARIF, CI examples, usage and savings summary |

Pricing should be seat-based initially. Avoid complicated token pass-through.
The buyer is purchasing saved engineering time and reliable context, not a
discounted token broker.

### Risks

- Requires the P0 product shell from Phase 100D.
- Team admins will expect predictable installation and upgrades.
- Shared workflows need revision freshness and coverage transparency.
- CI and editor integration become more important.

### Verdict

**Best primary business model.**

## 3. Enterprise

### Product Shape

```text
larger organization
  + private deployment
  + policy controls
  + auditability
  + support
  + procurement
```

### Strengths

- Highest contract values.
- Local and read-only architecture is attractive for sensitive repositories.
- Explicit unknowns, unresolved-edge reporting, and deterministic exports fit
  governance needs.
- Token and time reduction can matter at large scale.
- Potential for private VPC, air-gapped, or self-hosted deployments.

### Weaknesses

- Too early as the first model.
- Current shell lacks installability, support matrix, admin controls, release
  management, and troubleshooting bundle.
- Confirmation validation remains incomplete.
- Phase 98A human review and first-ten-user workflow evidence remain open.
- Enterprise buyers will demand evidence across many repository shapes,
  languages, and environments.
- Procurement and security review slow learning.

### What Must Exist First

- Team usage evidence.
- Versioned packaging and upgrade path.
- Authentication and workspace policy only if needed by deployment shape.
- Data retention controls.
- Audit logs.
- Supported environment matrix.
- SLA and support path.
- Admin visibility into revision freshness and coverage.
- Clear statement of local execution and data boundaries.

### Verdict

**High-value expansion model after team product-market signal, not the opening
move.**

## 4. API Platform

### Product Shape

```text
repository intelligence API
  -> ask
  -> graph
  -> impact
  -> evidence packets
  -> context compression for other agents
```

### Strengths

- Could become infrastructure for multiple coding agents.
- Makes JARVIS model-agnostic.
- Attractive if external integrators want repository context without building
  their own index and graph layer.
- Can monetize usage across agent ecosystems.
- Context compression is naturally API-shaped.

### Weaknesses

- Premature before one product workflow is proven.
- Public APIs freeze schemas and support obligations early.
- Hosted API raises sensitive-code and data-residency concerns.
- Self-hosted API adds deployment complexity.
- Usage-based pricing captures token volume, but the product's economic value
  is developer time saved.
- Current external demand is unmeasured.
- The existing product shell and docs are not ready for integrators.

### Appropriate Trigger to Revisit

Revisit an API platform when:

- team users repeatedly ask to connect non-Claude agents;
- schemas are stable across product iterations;
- at least `3-5` external integrations request the same surfaces;
- hosted versus self-hosted demand is understood;
- authentication, rate limits, versioning, and support expectations are clear.

### Verdict

**Strategically plausible second product line. Defer as the primary model.**

## 5. Claude Companion

### Product Shape

```text
Claude
  + deterministic local repository intelligence
  + compact evidence-backed context
```

### Strengths

- Directly matches the Phase 100B benchmark.
- Explains token reduction in one sentence.
- Avoids competing with frontier-model vendors.
- Makes Claude more effective on large repositories.
- Uses JARVIS's strongest existing capabilities: RU-3, graph, impact, and
  explicit unknown handling.
- Supports a clear demo:

```text
Claude alone reads many files.
Claude + JARVIS asks a few grounded questions and answers faster.
```

- Can start narrow with Python and local repositories.
- Fits the current review-intelligence truth better than a bug-finder pitch.

### Weaknesses

- Positioning tied too tightly to one model vendor could limit optionality.
- Users may expect a one-click integration that does not exist yet.
- Companion value must be measured at equal-or-better answer quality.
- Index-build cost and break-even query count must be disclosed honestly.

### Recommended Positioning

Use:

> A local repository-intelligence companion for Claude and coding agents.

Lead with Claude in the demo because it is concrete. Keep the architecture
model-agnostic in the product:

```text
Claude companion today
coding-agent repository intelligence layer over time
```

### Verdict

**Best product wedge. Pair it with team subscription pricing.**

## Recommended Commercial Sequence

### Stage 1: Concierge Design Partners

Target:

- `5-10` Python engineering teams;
- teams already using Claude, Cursor, or Copilot;
- repositories where unfamiliar-code review, onboarding, or change impact is
  expensive.

Sell:

```text
local Claude companion
for faster, cheaper, grounded repository work
```

Measure:

- token reduction;
- wall-clock speedup;
- answer-quality delta;
- index-build break-even query count;
- weekly active developers;
- repeat repository queries;
- developer time saved;
- whether teams ask to keep it installed.

### Stage 2: Paid Team Subscription

Ship after the Phase 100D P0 shell:

- installable `jarvis-builder`;
- first-run preflight;
- progress and cancellation;
- state recovery;
- freshness and coverage;
- JSON/SARIF;
- VS Code and CI examples;
- privacy and local-state docs.

Sell:

```text
team seats
  + shared repository workflow
  + Claude companion context
  + savings and usage summary
```

### Stage 3: Enterprise Expansion

Add only after repeat team usage proves pull:

- self-hosted or private deployment options;
- policy controls;
- admin reporting;
- auditability;
- supported-environment matrix;
- support and SLA;
- procurement-ready security documentation.

### Stage 4: API Platform

Add only if integration demand appears repeatedly:

- stable repository-intelligence API;
- versioned schemas;
- authentication;
- usage governance;
- hosted or self-hosted deployment options.

## Pricing Recommendation

### Initial Pricing Unit

Use:

```text
per active developer seat per month
```

with a team minimum.

Why:

- seat pricing is familiar;
- value maps to developer throughput;
- token savings remain a proof point rather than a billing complication;
- teams can forecast spend;
- it avoids punishing heavy use of a productivity tool.

### Suggested Packaging Shape

| Tier | Buyer | Pricing shape | Purpose |
| --- | --- | --- | --- |
| Individual | Developer | Low-friction monthly seat | Adoption and design-partner funnel |
| Team | Engineering team | Per-seat monthly or annual, team minimum | Primary revenue model |
| Enterprise | Larger organization | Annual contract | Later expansion |
| API | Integrator | Usage-based plus platform minimum | Later, only after demand |

Exact price points should be tested with design partners after measuring:

- weekly tasks per user;
- minutes saved per task;
- model-token cost saved;
- break-even query count;
- willingness to keep the tool installed;
- whether the budget owner is engineering productivity, developer tools, or AI
  platform.

## Claims That Are Safe If the Assumption Is Proven

Safe:

- "Reduce repository-context tokens by `50-80%` on the measured task suite."
- "Answer measured repository tasks `3-5x` faster with equal-or-better quality."
- "Local, read-only repository intelligence for Claude and coding agents."
- "Understand architecture and change impact without loading the whole
  repository into model context."
- "See unresolved relationships instead of fabricated certainty."

Only with qualifiers:

- "Lower AI cost" - include model, task suite, index amortization, and
  break-even count.
- "Faster code review" - only after external workflow sessions measure it.
- "Confirmed defects" - only after historical positive-oracle and manual gates
  pass.

Not safe yet:

- "Finds bugs automatically."
- "Zero false positives."
- "Replaces code review."
- "Production security scanner."
- "Works across all languages."
- "Enterprise ready."

## Decision Matrix

Scores: `1` weak to `5` strong for the current product state.

| Model | Matches proven wedge | Speed to revenue | Value capture | Product readiness fit | Long-term upside | Overall |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Developer subscription | `4` | `4` | `2` | `4` | `3` | `17 / 25` |
| Team subscription | `5` | `4` | `5` | `4` | `5` | **`23 / 25`** |
| Enterprise | `4` | `1` | `5` | `1` | `5` | `16 / 25` |
| API platform | `4` | `2` | `4` | `2` | `5` | `17 / 25` |
| Claude companion positioning | `5` | `5` | `3` | `4` | `4` | **`21 / 25`** |

The two strongest answers serve different roles:

```text
Claude companion = product wedge
team subscription = business model
```

## Risks

| Risk | Consequence | Mitigation |
| --- | --- | --- |
| Compression claim measured only on one repository | Weak generalization | Repeat Phase 100B on multiple pinned repositories and task mixes |
| Speedup comes from lower answer quality | Commercially hollow win | Keep quality non-inferiority as a hard gate |
| Token savings are smaller after index-build cost | Misleading ROI | Publish amortized and steady-state views plus break-even queries |
| Users expect bug-finder behavior | Trust failure | Lead with repository intelligence and review acceleration |
| Claude-specific integration limits market | Dependency risk | Keep interfaces agent-agnostic while demoing Claude first |
| Team shell is not ready | Adoption friction | Finish Phase 100D P0 productization before broad self-serve |
| Enterprise requests arrive early | Delivery distraction | Run design-partner pilots; avoid bespoke platform commitments |

## Bottom Line

If JARVIS proves `50-80%` token reduction and `3-5x` speedup at equal-or-better
quality, the most valuable business is:

```text
a team subscription
for a local Claude companion
that compresses repository context
and accelerates grounded engineering work
```

The first dollars should come from teams that already feel the pain and already
pay for coding agents. Individual subscriptions can feed adoption. Enterprise
should follow repeat team pull. API platform work should wait until integration
demand appears repeatedly.

The commercial story is pleasantly simple:

```text
Do not replace Claude.
Make Claude dramatically better at repositories.
```
