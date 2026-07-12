# Desktop Home Checkpoint Review

Date: 2026-07-12

Branch: `design/atlas-premium-experience`

Scope: production Desktop Home only. No persistence, indexing, graph, account, billing, website, installer, or release behavior changed.

## Decision summary

The state-led Home is materially clearer within five seconds. First launch has one dominant choice, repository readiness uses measured local state, and the productive state leads with Ask rather than launch marketing. All three states were exercised against the running source app with isolated Atlas data and agent configuration directories.

## Problems in the previous Home

- First launch presented repository setup, MCP setup, feature cards, and historical onboarding layers at once.
- Equal-weight cards obscured the one useful next action.
- Signed-in or Local-mode account copy could replace repository-focused Home copy.
- Agent configuration controls remained prominent after the user became productive.
- The old one-time welcome screen covered the new first-run hierarchy after Local-mode entry.
- The app shell had a small-window overflow when navigation and output-detail controls shared one row.

The before reference is [home-before-current-production.png](screenshots/home-checkpoint/home-before-current-production.png).

## New Home improvements

- One product state is visible at a time.
- First launch leads with **Scan a local repository**, then **Try the sample repository**.
- The local-first/no-signup trust line is visible without opening account UI.
- Repository readiness shows only production values and hides any unavailable fact.
- Raw MCP configuration remains behind an Advanced disclosure.
- Once an agent is connected, launch copy and setup cards disappear in favor of one Ask input.
- Real stale status changes the supporting copy so Atlas never calls stale graph evidence ready.
- Below 860 px, controls and task navigation use separate app-bar rows and the document has no horizontal overflow.

## State mapping

| Home state | Production condition | Live result |
| --- | --- | --- |
| No repository | `STATE.summary?.ok` is false | First-run Scan/Sample hierarchy; no inactive agent cards |
| Repository ready, no agent | Summary is valid and no MCP status has `atlas_configured` | Repository facts plus Claude Code, Cursor, and Codex choices |
| Productive | Summary is valid and at least one MCP status has `atlas_configured` | Dominant Ask input, task suggestions, compact repository/activity detail |

The no-agent state used empty isolated `APPDATA`, `HOME`, and `CODEX_HOME` directories. State 3 was produced by clicking the real **Connect to Codex** control, which called the existing local config-write endpoint and caused the real MCP status response to change.

## Real data sources

| Visible value | Existing source |
| --- | --- |
| Repository name | `/api/repositories/current/summary` -> `repo_name` |
| Files indexed | current summary -> `file_count` |
| Graph nodes | current summary -> `module_count` (module graph nodes) |
| Graph edges | current summary -> `dependency_edges` |
| Last indexed | matching item from `/api/repositories/recent` -> `last_scan_at` |
| Fresh/stale | `/api/repositories/current/trust-status` -> `user_trust_label` |
| Restored state | `/api/health` -> `persistence.restored` |
| Agent connections | `/api/integrations/mcp/status` -> per-agent `atlas_configured` |
| Recent useful activity | existing local-only `atlas_activity_v1` event list |

No restore latency is shown because the Home payload does not expose one. Empty or unavailable metrics are hidden, not replaced with invented values.

## Existing handlers reused

- Scan: `goToScanStart()`
- Sample: `loadDemoMode('medium')`
- Home Ask: `go('ask')` + existing `sendCopilotQuestion()`
- Claude Code: `atlasMcpSetup.connectClaude()`
- Cursor: `atlasMcpSetup.connectCursor()`
- Codex: `atlasMcpSetup.connectCodex()`
- Impact: existing `go('impact')`, focused on `impactTarget`
- Debug: existing `go('investigate')`, focused on `investigateSymptom`
- Plan Change: existing `go('build')`, focused on `buildRequest`

No endpoint behavior or business logic was duplicated.

## Live review

- State 1: exact headline, primary/secondary CTA, trust line, Local guest mode, and locked pre-repository navigation verified.
- State 2: 18 files, 17 graph nodes, 24 graph edges, real timestamp, `Fresh`, `Repository restored`, and three genuinely disconnected agents verified.
- State 3: real Codex config write changed Home to the productive state; connected status and local activity were real.
- Home Ask preserved `Where is authentication implemented?`, opened Ask Atlas, and returned a cited `services/auth.py` answer.
- Impact suggestion opened `view-impact` and focused `impactTarget`.
- A copied isolated repository was changed after indexing; the real trust endpoint produced `Full rescan required`, and Home changed to refresh-first language.
- At 720 px, document `scrollWidth` equaled `clientWidth`; the primary CTA remained in the viewport.
- At the 1152 x 720 CSS-pixel equivalent of a 1440 x 900 display at 125% scaling, there was no horizontal overflow and the primary CTA remained visible.

## Screenshots

- [No repository, 1440 x 900](screenshots/home-checkpoint/home-no-repository-1440x900.png)
- [Repository ready, no agent, 1440 x 900](screenshots/home-checkpoint/home-repository-ready-no-agent-1440x900.png)
- [Repository plus connected agent, 1920 x 1080](screenshots/home-checkpoint/home-repository-agent-connected-1920x1080.png)
- [Small desktop, 720 x 900](screenshots/home-checkpoint/home-repository-ready-small-720x900.png)
- [Previous production Home](screenshots/home-checkpoint/home-before-current-production.png)

Browser screenshots exclude the native scrollbar width, so recorded bitmap dimensions are 1425 x 914, 1425 x 891, 1905 x 1072, and 705 x 881 respectively.

## Accessibility and interaction

- DOM order follows the visual hierarchy: primary input/action, suggestions, repository detail, activity.
- Native buttons and inputs remain keyboard reachable.
- Keyboard focus produced a 2 px `--atlas-focus` outline.
- `Ctrl+K` opened the existing command palette; `Escape` closed it.
- No visible Home control lacked an accessible name.
- Fresh, disconnected, connected, and stale states all include text labels; none rely on color alone.
- Reduced-motion CSS collapses Home transitions and smooth scrolling.
- HTML parsing found zero duplicate IDs.
- Small-window task navigation remains keyboard reachable on its own row.

## Tests

- Home, navigation, real-repository Home, and auth UX: **25 passed, 8 skipped**.
- Guest Mode: **5 passed**.
- MCP setup, alias resolution, and MCP server: **25 passed**.
- Persistence and fresh-process MCP: **43 passed**.
- JavaScript syntax: `app.js`, `atlas_mcp_setup.js`, and `atlas_workflows.js` passed `node --check`.
- `git diff --check`: passed for the intended Home/design/test files.

The eight skips are existing dev-only account-service tests when that optional service is unavailable. MCP and persistence were rerun successfully in stable writable temp roots after sandboxed pytest roots reproduced the known Windows ACL failure. A redundant final MCP rerun was denied by the external approval service after its usage limit was reached; no MCP source or IDs changed after the passing 25-test run.

## Remaining weaknesses

- The running app emits two pre-existing vendor warnings: Three.js legacy-build deprecation and multiple Three.js instances. There were no Home JavaScript errors. The warnings are outside this Home-only checkpoint.
- The source app's repository chip retains the raw directory name while Home cleans underscores/hyphens for display. The chip belongs to the shared shell and was not redesigned here.
- Browser safety policy stopped the final live Debug/Plan click-through after Impact routing had been verified. Their exact existing routes and focus targets remain covered by the focused Home test contract.
- Isolated runtime/temp directories created during review remain untracked because the external approval service denied the cleanup command after reaching its usage limit. They are excluded from staging.

## Deliberately deferred

- Ask, Impact, Debug, Plan Change, Map, Scan, account, and website redesigns.
- A global agent connection sheet.
- Restore latency until a real frontend payload exposes it.
- Shared-shell repository-name cleanup.
- Third-party Three.js warning cleanup.

## Production behavior

No backend production behavior changed. The implementation reads existing responses and routes controls into existing handlers. Presentation behavior changed only on Home: real state selects the visible panel, stale copy is truthful, the legacy second welcome overlay no longer covers the state-led Home, and small-window navigation gets its approved second row.

## Recommendation

**A. APPROVE HOME AND CONTINUE TO ASK**
