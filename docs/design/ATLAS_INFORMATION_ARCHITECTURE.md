# Atlas Information Architecture

Status: Phase 1 design checkpoint

## Product model

Atlas has four concepts. The navigation exposes tasks, while repository and agent state remain global context.

| Concept | Contents | UI role |
| --- | --- | --- |
| Repository | Current path, index freshness, branch or commit, persistence state | Global repository switcher and Home state |
| Understand | Ask Atlas, Map | Primary task navigation |
| Change safely | Impact, Debug, Plan | Primary task navigation |
| Agents | Claude Code, Cursor, Codex connection state | Global connection sheet |

## Desktop navigation

### Persistent app bar

Left to right:

1. Atlas Home
2. Compact repository switcher
3. Home, Ask, Impact, Debug, Plan, Map
4. Agent connection status
5. Command palette
6. Settings and account or Local mode

Scan is not a permanent top-level destination. It is a repository action opened from Home, the repository switcher, stale-state messages, and empty states. This reduces top-level choices without removing the workflow.

### Small-window behavior

At widths below 860 px:

- Repository context stays in the top bar.
- Tool navigation moves to one horizontally scrollable row.
- Agent, account, and settings actions move behind a single global menu.
- The primary screen action remains visible.
- Tool output becomes one reading column; evidence and metadata move below the answer.

## Desktop state model

### First launch

1. Show the unsigned-app notice only when required.
2. Present "Continue locally" as the primary action.
3. Present "Create free account" as secondary.
4. Present "Sign in" as tertiary.
5. State that account, billing, and future sync features are the only reasons to sign in.
6. Continue directly to the correct Home state. Do not add a second welcome modal.

### Home state A: no repository

Visible:

- Persistent-repository-context promise
- Scan a local repository
- Try the sample repository
- Local-first trust line
- Compact Scan -> Connect -> Fresh session context sequence

Hidden:

- Full tool navigation on the first pass
- Agent config detail
- Recent activity
- Repository metrics
- Feature grid

### Home state B: repository indexed, no agent connected

Visible:

- Repository ready
- Repository name, file count, graph size, indexed time, persistence status
- Connect an agent
- Claude Code, Cursor, and Codex choices
- Ask Atlas now

The message is: Atlas already knows the repository. Connection is the next setup step, but Ask Atlas is already useful.

### Home state C: repository indexed and agent connected

Visible:

- Dominant Ask input
- Task-oriented suggestions
- Fresh or stale state
- Connected agent count
- Recent useful activity
- Latest repository state

Marketing and onboarding copy disappear after the user becomes productive.

### Stale repository state

The app bar and each analysis surface show the same stale state. Results may remain readable, but actions that depend on current graph evidence lead with Refresh index.

## Task workspaces

### Ask

Reading order:

1. Repository identity and freshness
2. Question input
3. Direct answer
4. Evidence
5. Relevant files and symbols
6. Why Atlas believes this
7. Caveats and confidence
8. Follow-up actions

Ask is an analysis document, not a chronological chat transcript. Follow-up questions reuse the current result context but do not turn every response into a speech bubble.

Existing data contract:

- `answer`
- `report`
- `evidence`
- `files`
- `confidence`
- `limitations`
- `suggested_action`
- `graph_highlight`

### Impact

Reading order:

1. Target and input mode
2. Risk summary
3. Direct dependents
4. Indirect or likely dependents
5. Tests affected
6. Unknown and dynamic risk
7. Confidence and evidence
8. Create change plan

Existing data contract:

- `target`
- `risk_level`
- `confidence`
- `direct_impact`
- `indirect_impact`
- `tests_likely_affected`
- `recommended_verification`
- `risks_of_incorrect_fix`
- `what_probably_wont_break`
- `evidence`
- `target_node_id` and `affected_node_ids`

### Debug

Reading order:

1. Symptom or stack trace
2. Likely root cause
3. Ranked hypotheses
4. Files involved and call-path evidence
5. How to confirm or rule out each hypothesis
6. Minimal fix direction
7. Risks of the wrong fix

Existing fields support this structure: `most_likely_root_cause`, `hypotheses`, `verification_checklist`, `minimal_fix_strategy`, `risks_of_incorrect_fix`, evidence, and confidence.

### Plan

Reading order:

1. Goal
2. Files to change and why
3. Numbered implementation sequence
4. Tests
5. Compatibility risk
6. Rollback boundary
7. Export or agent handoff

The current plan response supports goal, files, order, affected systems, tests, what may break, risk, confidence, and prompts. Rollback should be derived only when the backend provides grounded information; otherwise the UI labels it as a manual consideration.

### Map

Default view:

- Major repository clusters
- Entry points
- Important dependency directions
- Search for file or symbol
- Architecture preset

Presets:

- Architecture
- Authentication
- Request flow
- High-risk modules
- Recent changes, only when the data exists

Selection opens a compact inspector with inbound and outbound relationships and two primary actions: Ask about this and Run Impact.

## Repository scan flow

### Before scan

- Selected path
- Scope summary
- Ignored folders disclosure
- Validate and Scan actions

### During scan

Use backend-provided phases and progress only. The preferred labels are:

1. Discovering files
2. Building symbols
3. Mapping dependencies
4. Writing persistent index
5. Ready

If the backend cannot distinguish all five, group the existing stages honestly. Do not invent percentages or phase transitions.

Visible runtime information:

- Current phase
- Files considered when available
- Ignored folders
- Elapsed time
- Cancel action

### Completion

Primary message:

> Repository indexed and ready for fresh agent sessions.

Show cold scan time, file count, graph size, persistence state, and the next action. Route to Home state B or C rather than dropping the user into a dense metrics dashboard.

## Agent connection flow

Each tool owns one state:

| State | Primary action | Required message |
| --- | --- | --- |
| Not connected | Connect | What Atlas will add |
| Connecting | None | Which config is being checked or written |
| Connected | Test connection | Atlas is present in config |
| Needs restart | Acknowledge | Restart the named tool to activate Atlas |
| Needs manual setup | View steps | Why auto-write is unavailable |
| Error | Retry | What failed and the next safe step |

Before a config write, show a concise summary. Preserve unrelated MCP servers and create a backup. Keep raw JSON or TOML behind "View config diff" or "Manual setup."

Production wiring that must remain real:

- Claude and Cursor continue through the existing integration handlers.
- Codex continues to call `POST /api/integrations/codex/write-config`.
- Primary Connect never degrades into copy-to-clipboard behavior.
- Existing per-tool status elements keep an explicit DOM contract or receive a tested adapter.

## Global interactions

### Command palette

The palette searches tools, recent repositories, files, and symbols. It can route to existing actions but must not invent editor or repository operations.

### Error pattern

Every error has three lines of meaning:

1. What happened
2. What Atlas preserved or did in response
3. What the user can do next

Example:

> Scan stopped. Your previous index is unchanged. Choose a smaller folder or retry.

### Status pattern

No state relies on color alone. Each dot or semantic color is paired with text such as Ready, Stale, Needs restart, or Error.

## Website architecture

Homepage order:

1. Hero
2. Real product proof
3. Persistent-session proof
4. Impact analysis
5. How it works
6. Claude Code, Cursor, and Codex integrations
7. Local-first data flow
8. Factual comparison and context
9. Pricing
10. FAQ
11. Founder note
12. Download CTA

The first viewport contains the Atlas offer, one download action, the local-first trust line, and a visible hint of product proof.

### Download page

The download page is a single-action trust surface. It shows version, size, SHA256, release commit, Windows support, SmartScreen guidance, install steps, read and write behavior, uninstall behavior, and support contact.

### HN page

The HN page is a plain technical launch note, not a duplicate homepage. Its order is: what was built, problem, persistence implementation, local data boundary, what leaves the machine, strengths, non-goals, limitations, download, source and release, founder note, feedback request.

### Docs

Task-based order:

1. Install Atlas
2. Start locally without an account
3. Scan a repository
4. Connect Claude Code
5. Connect Cursor
6. Connect Codex
7. Ask Atlas
8. Run Impact
9. Troubleshoot MCP
10. Delete local data
11. Verify installer checksum

## Current-to-proposed route map

| Current desktop view | Proposed destination | Change type |
| --- | --- | --- |
| `view-home` | Home state router | Presentation and state hierarchy |
| `view-scan` | Repository scan flow | Presentation only |
| `view-ask` | Ask analysis document | Presentation only |
| `view-impact` | Impact blast-radius workspace | Presentation only |
| `view-investigate` | Debug investigation workspace | Presentation only |
| `view-build` | Plan implementation path | Presentation only |
| `view-center` | Map architecture workspace | Presentation and control grouping |
| Home MCP cards | Global Agent connection sheet | Presentation; preserve handlers |
| Account chip and modal | Global Local mode/account menu | Presentation; preserve state logic |

## Checkpoint rule

Implement one production screen at a time. A screen advances only after focused UX tests, keyboard review, responsive screenshots, and functional handler checks pass. Desktop Home is first because it defines every subsequent route and state transition.
