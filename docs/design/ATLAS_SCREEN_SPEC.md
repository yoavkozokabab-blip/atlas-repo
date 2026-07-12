# Atlas Screen Specification

Status: Phase 1 design checkpoint

Prototype: [`prototypes/atlas-premium-experience/index.html`](../../prototypes/atlas-premium-experience/index.html)

## Shared desktop shell

### App bar

The app bar contains Atlas Home, repository switcher, task navigation, agent status, command palette, and Local mode or account. It remains visible while tool output scrolls.

Repository switcher content:

- Repository name
- Fresh, stale, scanning, or no-repository state
- Branch and commit when available
- Up to four recent repositories in the expanded menu
- Scan another repository action

Agent status opens one connection sheet. It does not show three configuration cards on Home after the user is productive.

### Navigation

Primary: Home, Ask, Impact, Debug, Plan, Map.

Scan opens contextually from Home, repository switcher, and stale-state messages.

Settings and account are global. Admin and billing do not appear in the primary product navigation.

### Accessibility

- App bar uses a banner landmark and named primary navigation.
- Selected tool has `aria-current="page"`.
- Repository and connection statuses include text.
- Small-window navigation remains keyboard reachable.
- Focus is moved to the new page heading after route changes.

## First launch and Local mode

### Hierarchy

1. Continue locally
2. Create free account
3. Sign in

Required explanation:

> Atlas works locally without an account. Sign in only for account, billing, and future sync features.

After local entry, the app uses "Local mode" in the global status. It does not repeatedly label the user as Guest.

### Existing behavior mapping

- Continue locally calls the existing `POST /api/accounts/guest/start` path.
- Persisted account state remains owned by `accounts_client.py`.
- Protected workflows continue through `server._account_gate_failure()` and `has_local_workflow_access()`.
- Signing in later must change identity state without clearing repository persistence.

### Remove from the flow

- A second welcome modal after local entry
- Sign-in-first visual priority
- Repeated Guest labels
- Account-plan language on local product screens

## Desktop Home

### State 1: no repository

Purpose: get one repository indexed.

Headline:

> Give your coding agents persistent repo context.

Support:

> Scan once. Atlas restores the repository graph, evidence, and memory in every fresh Claude Code, Cursor, or Codex session.

Actions:

- Primary: Scan a local repository
- Secondary: Try the sample repository

Trust line:

> Local-first | No signup required | Your repository stays on this machine

Below the fold is one connected sequence: Scan, Connect, Start with context. It uses repository files, relationship evidence, and an agent handoff as visual material. It is not three generic feature cards.

MCP setup, recent activity, and tool marketing remain hidden.

### State 2: repository indexed, no agent connected

Purpose: prove readiness and route to connection.

Headline:

> Atlas already knows this repository.

Show:

- Repository name
- Files indexed
- Nodes and edges
- Last indexed
- Fresh-session restore status
- Local storage status

Actions:

- Primary: Connect an agent
- Secondary: Ask Atlas now

Agent choices are Claude Code, Cursor, and Codex. Raw config is hidden until Advanced or View config diff.

### State 3: repository ready and agent connected

Purpose: start productive work.

Headline:

> What do you want to understand or change?

The Ask input is the dominant element. Suggestions are task-oriented and route to the appropriate workspace. Below the input, show useful activity and current repository state. Remove launch copy and setup explanation.

### Error and stale variants

No repository access:

> Atlas cannot read this folder. Nothing was indexed. Choose a folder your Windows account can read.

Cancelled scan:

> Scan stopped. Your previous index is unchanged. Retry or choose another folder.

Stale repository:

> Repository changed since the last index. Refresh before relying on impact paths.

## Repository scan

### Initial

The selected path is the focal field. Show ignored folders and scope through disclosure, not as a large configuration form.

Actions:

- Primary: Scan repository
- Secondary: Cancel or return to Home

### Progress

Show only measured states. Existing backend labels may initially map to:

| Existing label | Presented phase |
| --- | --- |
| Indexing files | Discovering files and building symbols |
| Building dependency graph | Mapping dependencies |
| Preparing Ask Atlas | Writing persistent index |
| Complete | Ready |

Do not present a more granular phase until the backend reports it. Preserve the existing cancel route.

### Complete

Message:

> Repository indexed and ready for fresh agent sessions.

Show cold scan time, file count, graph size, and persistence status. Then route to Home State 2 or 3.

## Ask Atlas

### Header

- Repository name
- Fresh or stale state
- Switch repository
- Question input

### Answer document

The answer is a reading surface, not a chat bubble.

Order:

1. Direct answer
2. Evidence rows
3. Relevant files and symbols
4. Why Atlas believes this
5. Caveats
6. Confidence
7. Continue actions

Evidence row contents:

- Direct, related, or inferred label
- File path
- Exact symbol when available
- Line when available
- Relevance reason
- Open action only when supported

Existing `files` entries may be plain strings. Until line and symbol data are present, omit those fields rather than generating them.

### Actions

- Ask follow-up
- Copy answer
- Run Impact
- Show in Map
- Open in editor only when an existing supported editor target is detected

Agent-specific copy targets remain available behind an Export or Send to agent control. Four equal copy buttons do not lead the answer.

### Empty and weak evidence

If Atlas has no precise match, say what is missing and offer narrower suggestions. Do not render an authoritative answer shell with low-content output.

## Impact

### Input

Modes:

- File
- Symbol, only when symbol lookup is backed by current data
- Describe change, only when current impact routing supports the text

The first production pass should ship File mode and retain current supported target parsing. Other modes stay out until verified.

### Result

Top summary answers:

- Risk level
- Why the target matters
- Direct dependent count
- Transitive dependent count
- Affected test count
- Confidence
- Manual verification count

### Blast-radius representation

Columns:

1. Origin
2. Directly affected
3. Likely affected

Relationship encoding:

- Solid blue: selected origin
- Solid teal: direct static relationship
- Dashed amber: indirect static relationship
- Dotted red: unknown or dynamic risk

The representation is a technical relationship view. It must not animate continuously or place unrelated nodes for spectacle.

### Detail

- Direct dependents
- Indirect dependents
- Tests affected
- Recommended verification
- Unknown and dynamic risk
- Probably safe when no import path exists
- Evidence and limitations

Primary next action: Create change plan.

Secondary: Open in Map.

## Debug

### Input

One field accepts an error, stack trace, or symptom. The UI does not imply that a stack trace is required.

### Result

1. Most likely root cause
2. Why it fits
3. First files to inspect
4. Ranked competing hypotheses
5. What should be true for each hypothesis
6. How to confirm or rule it out
7. Minimal fix direction
8. Risk of the wrong fix

The backend already distinguishes confidence and provides hypotheses. Visual ranking must preserve uncertainty.

### Timeline option

Use an investigation timeline only when a real call path or ordered verification sequence exists. Otherwise use a hypothesis stack. Do not invent a call graph from file ranking alone.

## Plan

### Input

Prompt:

> What should change?

Examples may appear as compact suggestions, not a large instruction panel.

### Result

1. Goal
2. Files to change and why
3. Numbered implementation order
4. Tests
5. Compatibility and behavior risks
6. Rollback considerations
7. Agent handoff

Existing fields map directly to goal, affected systems, entry points, implementation order, what may break, tests, risk, confidence, and prompts.

Rollback considerations must remain a clearly labeled manual check unless the backend adds grounded rollback data.

## Map

### Default

Show repository architecture overview, major modules, entry points, and important dependency directions. System health remains accessible but does not occupy the primary left column.

### Controls

- Search file or symbol
- Architecture preset
- Authentication preset
- Request-flow preset
- High-risk preset
- Recent-changes preset only when supported
- Inbound and outbound relationship toggle

### Selection

The inspector shows:

- File or symbol
- Module role
- Inbound relationships
- Outbound relationships
- Risk and evidence
- Ask about this
- Run Impact

Graph controls use stable dimensions. Selecting or hovering a node must not shift the map layout.

## Agent connections

### Connection sheet

One sheet lists Claude Code, Cursor, and Codex. Each row owns its status, primary action, test action, and advanced disclosure.

Before write:

- State the config file
- State that Atlas preserves unrelated MCP servers
- State that a backup will be created
- Show a concise diff summary

After write:

- Connected
- Restart the named tool to activate Atlas, when required
- Test connection
- View config diff
- Restore backup

### Required handler preservation

Production markup must retain or explicitly remap the IDs currently used by `atlas_mcp_setup.js`. Focused tests must verify clicks call real endpoints and update only the selected tool state.

## Website Home

### Hero

Headline:

> Persistent repository context for Claude Code, Cursor, and Codex.

Support:

> Your coding agent should not rediscover the same repository every session. Atlas indexes locally, restores its graph and evidence in fresh sessions, and returns cited files for questions, debugging, and change planning.

Actions:

- Primary: Download Atlas
- Secondary: See the 30-second flow

Trust:

> Windows v1.0 | No signup required | Local-first

The hero uses a full-bleed product scene as its background. It shows Session 1 indexing, a fresh-session restore, and a connected agent receiving cited context. Hero copy overlays the scene; it is not a split text-and-card layout.

The first viewport leaves a visible hint of Product proof.

### Product proof

One example leads:

Question: "Where is authentication implemented?"

Answer cites implementation, route wiring, and supporting test from the controlled repository. The section labels its 27-file scope and displays the existing controlled restore result only with the exact benchmark caveat.

### Persistent-session proof

Show:

- Fresh agent session
- Restore: 8-12 ms
- Graph rebuilt: No
- Scope: controlled 27-file repository

Do not convert this into a general performance claim.

### Impact

Headline:

> See the blast radius before the edit.

The visual shows selected symbol, direct dependents, likely affected tests, and uncertainty. It explains that Atlas uses repository relationships rather than a static context file alone.

### Remaining homepage order

How it works, integrations, local-first data flow, factual comparison, pricing, FAQ, founder note, download.

## Local-first trust section

Data flow:

1. Repository
2. Atlas local index
3. Selected evidence
4. Connected agent
5. Model provider under that tool's terms

Required statements:

- Indexing is local.
- Atlas does not upload repository contents to Atlas servers.
- Selected context may be sent by Claude, Cursor, or Codex to its model provider.
- Atlas analytics exclude code, prompts, secrets, and raw file paths only if current telemetry implementation and policy verification support the statement.
- Paddle handles payment data when paid plans launch.

Links: View data flow, Delete local data, Security details.

## Download page

One primary action: Download Atlas.

Show:

- Version
- File size
- SHA256
- Release commit
- Windows support
- SmartScreen guidance
- Install steps
- What Atlas reads
- What Atlas writes
- Uninstall and local-data behavior
- Support contact

Values must come from the current release artifact or build metadata. No hard-coded stale SHA or version.

## HN page

Use plain technical typography and minimal decoration. Avoid homepage sections and feature-card repetition.

Order:

1. What I built
2. The problem
3. How persistence works
4. What is local
5. What leaves the machine
6. What Atlas does better
7. What Atlas does not solve
8. Known limitations
9. Download
10. Source and release
11. Founder note
12. Feedback requested

## Pricing

Free leads and lists all capabilities available today.

Pro is Coming soon at a planned `$19/month`. It lists only committed future capabilities.

Team is Coming later with Contact. There is no fake checkout or purchasable-state styling before billing is live.

## Responsive requirements

### Desktop application

- 900 x 650 minimum design target
- No clipped primary navigation
- No hidden primary CTA
- Analysis rails move below documents
- Blast radius changes from columns to ordered groups
- Modals and sheets stay within viewport and scroll internally

### Website

- 360 px minimum width
- Download CTA visible in the first viewport
- Product scene remains legible as a background, not a horizontal overflow source
- Code paths wrap or scroll within their own row
- Product proof becomes one reading column
- Data flow becomes a numbered vertical sequence

## Interaction requirements

- Keyboard navigation for every control
- Visible focus
- Command palette opens with Ctrl/Cmd+K
- Ctrl/Cmd+Enter submits analysis forms
- Escape closes overlays
- Copy actions announce success in a polite live region
- Operations longer than one second show text describing the phase
- Retry appears with errors
- Undo appears only for actions with a safe reversal path
- Reduced-motion preference removes nonessential animation

The keyboard behavior may exist without adding instructional shortcut copy to every screen.

## Implementation order and gates

1. Shared tokens and accessibility primitives
2. Desktop shell and Home states
3. Ask Atlas document layout
4. Agent connection sheet
5. Scan flow
6. Impact
7. Debug
8. Plan
9. Map
10. Website Home
11. HN
12. Download
13. Remaining website pages

Each screen gate requires:

- Existing behavior preserved
- Focused UX tests
- Real handler tests for all functional controls
- Guest/local-mode tests where applicable
- MCP tests for connection surfaces
- Persistence tests for repository-state surfaces
- Desktop screenshots at standard and small-window sizes
- Website screenshots at desktop and mobile widths
- Console free of new JavaScript errors

Full desktop suite, TypeScript, website production build, and installed-app verification occur only after the complete approved implementation. The design branch does not rebuild or publish the installer.
