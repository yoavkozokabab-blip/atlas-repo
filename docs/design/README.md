# Atlas Premium Experience Design Checkpoint

Branch: `design/atlas-premium-experience`

This packet completes the audit, strategy, information architecture, token system, screen specifications, and isolated static prototypes. Production desktop and website UI files are unchanged.

## Documents

- [Design strategy](ATLAS_DESIGN_STRATEGY.md)
- [Information architecture](ATLAS_INFORMATION_ARCHITECTURE.md)
- [Design tokens](ATLAS_DESIGN_TOKENS.md)
- [Screen specification](ATLAS_SCREEN_SPEC.md)

## Prototype

Open [`prototypes/atlas-premium-experience/index.html`](../../prototypes/atlas-premium-experience/index.html) in a browser. The prototype is static and has no API calls, repository writes, authentication changes, MCP changes, or production behavior.

Review controls switch between desktop and website. Desktop controls cover all three Home states plus Ask, Impact, Debug, Plan, and Map. The required Phase 2 proof surfaces are:

- Desktop Home states
- Ask Atlas answer
- Impact result
- Website hero
- Website persistence proof

## Before and proposed screenshots

| Surface | Current | Proposed prototype |
| --- | --- | --- |
| Desktop first launch | [Account choices](screenshots/before/desktop-auth-choices.png) | Specified in [Screen specification](ATLAS_SCREEN_SPEC.md#first-launch-and-local-mode) |
| Desktop Home | [Current Home](screenshots/before/desktop-home.png) | [No repository](screenshots/prototypes/desktop-home-empty.png), [ready](screenshots/prototypes/desktop-home-productive.png), and [small window](screenshots/prototypes/desktop-home-mobile.png) |
| Ask Atlas | Existing implementation in `view-ask` | [Analysis document](screenshots/prototypes/desktop-ask.png) |
| Impact | Existing implementation in `view-impact` | [Risk summary](screenshots/prototypes/desktop-impact.png) and [blast radius](screenshots/prototypes/desktop-impact-graph.png) |
| Website Home | [Current hero](screenshots/before/website-home-viewport.png) | [Persistence-led hero](screenshots/prototypes/website-hero.png) and [mobile hero](screenshots/prototypes/website-hero-mobile.png) |
| Website product proof | Current answer preview | [Cited answer](screenshots/prototypes/website-proof.png) and [scoped restore proof](screenshots/prototypes/website-persistence-proof.png) |

## Exact flow improvements

1. First launch changes from sign-in-first plus a second welcome modal to one account choice with Continue locally as the primary action.
2. Home changes from simultaneous repository, feature, and MCP promotion to one state-specific next action.
3. Scan moves from permanent top navigation to a repository action.
4. Ask changes from a generic answer card to an analysis document led by direct answer and evidence.
5. Impact changes from a dense report stack to an explicit origin, direct, likely, tests, and unknown-risk path.
6. Debug changes from a generic form and result card to ranked, falsifiable hypotheses.
7. Plan changes from a report container to a numbered implementation path with tests and compatibility risk.
8. Map changes from graph instrumentation as the default to an architecture overview with task presets.
9. Agent setup moves from Home cards into one global connection sheet while preserving per-tool states and real handlers.
10. Website Home changes from a feature-card sequence to a persistent-session claim, controlled proof, Impact, and visible data flow.

## Production implementation plan

### Checkpoint 1: shared foundation

- Add shared token names to desktop and website.
- Add focus, reduced-motion, status-label, and stable-control primitives.
- Do not restyle functional screens yet.
- Verify contrast and existing screenshots.

### Checkpoint 2: desktop shell and Home

- Restructure the desktop app bar and Home state containers in `atlas_desktop/static/index.html`.
- Map current state from `app.js`, persistence status, and MCP status into the three Home states.
- Make Continue locally primary without changing its endpoint or persistence behavior.
- Preserve existing IDs used by account and MCP scripts or add a tested adapter.
- Remove superseded Home CSS after focused tests pass.

### Checkpoint 3: Ask Atlas

- Reorder existing `answer`, `evidence`, `files`, `confidence`, and `limitations` fields.
- Keep current Ask endpoint and copy targets.
- Add file interaction only where the current runtime supports it.
- Verify sample and real repository answers.

### Checkpoint 4: agent connections and scan

- Move per-tool controls into a global connection sheet.
- Keep real Claude, Cursor, and Codex handlers and status IDs.
- Present existing scan phases honestly; do not invent backend detail.
- Verify config backups, unrelated MCP servers, cancellation, repeat scan, and persistence.

### Checkpoint 5: Impact, Debug, Plan, and Map

- Render existing Impact fields into the blast-radius hierarchy.
- Render existing Debug hypotheses as ranked and falsifiable.
- Render existing Plan fields as a numbered implementation path.
- Reframe Map around architecture and selection; preserve graph controls through disclosure.
- Verify cross-navigation among Ask, Impact, Plan, and Map.

### Checkpoint 6: website

- Replace the Home hierarchy with persistence-led product proof.
- Add controlled benchmark scope next to every measured restore claim.
- Add the local-first data flow and factual comparison.
- Redesign HN and Download as separate technical and trust surfaces.
- Keep public routes free of build-time network requirements.

### Checkpoint 7: release verification

- Focused desktop UX, MCP, persistence, and local-mode suites
- Full desktop test suite
- TypeScript and website production build
- Responsive screenshots
- Installed-app click-through
- No installer rebuild, deployment, or asset replacement until explicit final approval

## Screens changed

Production screens changed: none.

Prototype screens created: three Desktop Home states, Ask, Impact, Debug, Plan, Map, website hero, website product and persistence proof, website Impact, local-first data flow, and download CTA.

## Verification completed

- Prototype JavaScript syntax check
- Live browser interaction across Home, Ask, Impact, and website proof
- Ctrl/Cmd+K command palette and Escape close
- Ctrl/Cmd+Enter analysis submission
- Visible keyboard focus: 2 px solid focus outline with 3 px offset
- Duplicate ID, unlabeled control, unnamed button, and broken hash-target audit
- Desktop viewport overflow audit
- 390 x 844 website and desktop layout-context audit
- Mobile CTA visibility and horizontal-overflow checks
- WCAG contrast calculations for text, primary action, focus-supporting accents, and semantic colors
- Direct prototype page console: no warnings or errors

The in-app browser injects its own iframe observer into responsive harness pages and logs a `MutationObserver` parameter error with no source URL. The prototype source contains no `MutationObserver`, and the direct prototype page is clean. Treat this as screenshot-harness tooling noise, not a product-console pass for a future production implementation.

## Remaining risks

- The desktop HTML and CSS are historically layered. Appending another override layer would preserve debt and increase regression risk.
- MCP controls depend on current DOM IDs and script handlers.
- Some desired file and symbol interactions lack line-level data in every response.
- Scan phase granularity is lower than the ideal five-stage presentation.
- Map presets such as Recent changes require verified data support.
- Public analytics claims need a source and policy audit before publication.
- The current Windows environment has previously produced permission failures and Next.js worker restrictions; final gates require a clean verification environment.

## Recommendation

Iterate once on the isolated prototype with stakeholder feedback, then implement Desktop Home as the first production checkpoint. Do not ship the redesign or rewrite all screens in one pass yet.
