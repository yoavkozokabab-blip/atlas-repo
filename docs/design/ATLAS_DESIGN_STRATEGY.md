# Atlas Design Strategy

Status: Phase 1 design checkpoint

Branch: `design/atlas-premium-experience`

Baseline commit: `8ebcf2ce83f5c94a9c46dafc2ea55b7edd5fc017`

## Product thesis

Atlas is a persistent local repository intelligence layer for Claude Code, Cursor, and Codex.

The product story, in order, is:

1. Atlas knows the repository.
2. Atlas remembers it across fresh sessions.
3. Atlas gives connected agents selected, cited repository context.
4. Atlas helps a developer understand impact, investigate failures, and plan changes.
5. Repository indexing remains local.

The shortest expression of that story is:

> Scan once. Every new coding-agent session starts with the repository context it needs.

This sequence is the hierarchy for both desktop and website. A screen should not introduce lower-level tools before its current step is understood.

## Current UX audit

### Evidence captured

- [Desktop first-launch notice](screenshots/before/desktop-first-launch-auth.png)
- [Desktop account choices](screenshots/before/desktop-auth-choices.png)
- [Desktop first-run Home](screenshots/before/desktop-home.png)
- [Website Home viewport](screenshots/before/website-home-viewport.png)
- Existing product evidence: [Map](../media/atlas_map.png) and [Change Plan](../media/atlas_change_plan.png)

The new screenshots were captured from the local development app with an isolated Atlas data directory. No production user state was used.

### Desktop findings

1. First launch asks the user to resolve three layers before becoming productive: unsigned-app notice, account choice, and a second welcome modal. Each layer has a different hierarchy and CTA order.
2. The account screen visually makes sign-in primary even though local mode is the default launch path. "Continue without an account" reads as a bypass rather than an intentional mode.
3. The no-repository Home screen promotes repository setup and three agent-connection cards simultaneously. The user has not yet indexed a repository, so connection detail competes with the only meaningful next action.
4. The top navigation exposes Home, Scan, Ask Atlas, Debug, Impact, Plan Change, Map, and additional account/global actions. Their visual weight becomes too similar after a scan.
5. The current Home implementation contains several historical presentation layers in one file: first-run hero, return-user hero, dashboard cards, launch-first UX, zero-friction UX, and onboarding overlays. `styles.css` is 1,079 lines and `index.html` is 1,126 lines. The layering is a maintenance risk even before a visual redesign.
6. Ask Atlas already returns a direct answer, evidence, files, suggested action, confidence, limitations, and graph highlight. The UI fragments these fields across a chat-like answer card, output area, tags, and four copy actions. The evidence is present but does not lead the reading order.
7. Impact already exposes direct impact, indirect impact, affected tests, verification steps, confidence, dynamic-risk caveats, and a map highlight. It is one of the strongest product surfaces, but the current dense report gives its visual emphasis to containers rather than the dependency path.
8. Debug and Plan have useful structured output fields. Their current forms and report cards resemble each other, which makes two different reasoning tasks feel interchangeable.
9. Map has substantial capability, but the default view is instrumentation-heavy. Health metrics, graph controls, graph, inspector, and Ask actions all compete in the initial viewport.
10. Existing MCP controls call real endpoints and preserve per-tool status. Their selectors and handlers are sensitive to markup changes, so production implementation must preserve IDs or move to an explicit adapter contract with tests.

### Website findings

1. The hero says "Persistent repo memory for Claude Code and Cursor" and omits Codex from the primary claim even though Codex is a supported connection.
2. The hero explains local indexing and cited files, but persistent restoration across fresh sessions is not demonstrated. The current product preview proves an answer, not the unique persistence claim.
3. The first three sections repeat equal three-card layouts for flow, integrations, and features. This creates a generic SaaS rhythm and makes Impact look no more important than any other item.
4. The visual system uses a useful near-black base and readable type, but much of the hierarchy comes from bordered cards, a decorative hero pattern, and soft blue styling. Product proof should carry more visual weight than decoration.
5. The local-first section is directionally correct, but it stops at "you choose." The data flow should state what Atlas keeps local and what a connected agent may send to its own model provider.
6. The current homepage has one clear download action, which should be preserved. The redesign should make the product claim sharper without multiplying CTAs.

### Strengths to preserve

- Repository workflows are backed by real local API routes.
- Ask Atlas exposes cited evidence and limitations.
- Impact distinguishes direct and transitive relationships.
- Scan state, stale state, and MCP connection state already exist.
- Guest/local mode is implemented below the UI gate.
- Existing regression tests cover critical desktop wiring.
- Public copy already includes "No signup required" and local-first language.

## Strategic hierarchy

### Desktop

The desktop app is a stateful workflow, not a dashboard.

| State | User question | Dominant action | Supporting information |
| --- | --- | --- | --- |
| No repository | What should I do first? | Scan a local repository | Sample repository and local-first trust |
| Indexed, no agent | What is ready, and what is next? | Connect an agent | Repository facts and Ask Atlas fallback |
| Indexed and connected | What do I want to understand or change? | Ask about the repository | Impact, Debug, Plan, Map, recent activity |
| Stale index | Can I trust this result? | Refresh index | Last indexed time and changed files |

Ask, Impact, Debug, Plan, and Map are workspaces. Home routes the user into the right workspace; it does not explain every feature.

### Website

The website sells one idea, then proves it:

1. Persistent repository context for Claude Code, Cursor, and Codex.
2. A real cited answer from a controlled repository.
3. A fresh-session restore result with explicit scope.
4. Change impact as the distinctive technical capability.
5. A visible local-first data flow.
6. Integrations, comparison, pricing, FAQ, founder note, and download confidence.

## Experience principles

### One focal point per state

Each screen gets one dominant question and one primary action. Secondary actions remain available but do not share the same visual weight.

### Evidence before decoration

Code paths, symbols, relationship paths, tests, confidence, and caveats are the primary visual material. Abstract AI imagery, decorative graphs, and random metrics are excluded.

### Progressive technical depth

The first reading layer answers the user's question. The next layer proves it. Detailed reports and config diffs remain available through disclosure controls.

### Local mode is a product mode

Use "Local mode" in the application. Reserve "guest" for internal state and implementation. First launch should make "Continue locally" primary and explain accounts in one sentence.

### State language is operational

Status must answer what happened and what comes next:

- Repository ready. Connect an agent or ask Atlas now.
- Cursor connected. Restart Cursor to activate Atlas.
- Index stale. Refresh before relying on impact paths.
- Scan stopped. The previous index is unchanged.

### Motion communicates state

Motion is limited to navigation, progress, focus, and state changes. Durations stay between 120 and 220 ms. Reduced-motion preference removes nonessential movement.

## Visual direction

- Near-black canvas with distinct neutral surfaces, not blue-tinted panels everywhere.
- Atlas blue only for primary actions, focus, and selected navigation.
- Teal for direct evidence and verified relationships.
- Amber for stale, uncertain, and manual-verification states.
- A light technical summary surface is allowed when it creates a deliberate reading break.
- Editorial heading scale paired with compact technical output.
- Modest 4 to 7 px radii. Pills are reserved for compact statuses.
- Hairline borders communicate grouping; page sections do not float as cards.

## Scope controls

This phase does not authorize changes to:

- repository persistence
- indexing or graph construction
- MCP route behavior or config writing
- account, billing, admin, or license behavior
- installer behavior
- production deployment

Production implementation should map the new presentation to existing response fields and handlers. Any missing capability must remain absent or be labeled as a future design dependency, not simulated in the product.

## Success measures

### Five-second website test

A new visitor can answer:

- Atlas gives coding agents persistent repository context.
- It works with Claude Code, Cursor, and Codex.
- Indexing is local-first.
- Download Atlas is the next action.

### Thirty-second desktop test

A new user can:

1. Continue locally.
2. Load the sample or select a repository.
3. See that indexing completed and persistence is ready.
4. Ask where authentication is implemented.
5. Identify the cited files and next actions.

### Design quality gates

- One primary action in each product state.
- No unlabeled color-only statuses.
- Normal text meets WCAG AA contrast.
- All controls are keyboard reachable with a visible focus state.
- The desktop remains usable at 900 px wide and 650 px tall.
- Website content remains readable at 360 px wide without horizontal overflow.
- Reduced motion removes nonessential animation.

## Recommendation at this checkpoint

Proceed to isolated prototypes, then review screenshots before touching production UI. The product has enough real evidence and workflow structure to support a distinctive redesign, but a broad CSS rewrite without state-by-state checkpoints would carry unnecessary regression risk.
