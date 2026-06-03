# Generalization Report — VS Code

**Language:** typescript · **Framework:** Electron IDE · **Category:** typescript
**Path:** `C:\J.A.R.V.I.S\vscode`
**Status:** ok

## Repository Summary

- Modules: **7551** · Edges: **13224** · Subsystems: 226 · Files: 14871
- Massive mode: True · graph detail: imports · scan time: 78.8s

## Final Score

| Understanding | Impact | Investigation | Build Plan | **Overall** |
|---:|---:|---:|---:|---:|
| 100.0 | 62.0 | 100.0 | 100.0 | **88.6** |

## Repository Understanding Results

Score **100.0** / 100. Components: graph_built 20.0, explanation 15.0, subsystems 15.0, entry_points 10.0, runtime_boundaries 15.0, top_risks 10.0, hubs_vs_risks_separated 15.0

## Impact Results

Score **62.0** / 100 · resolution rate 0.667 · fallback rate 0.333 (6/9 concepts resolved).

- `what breaks if I remove authentication` → label='authentication' modules=['extensions/copilot/src/extension/completions-core/vscode-node/lib/src/auth/copilotTokenManager.ts', 'extensions/copilot/src/extension/completions-core/vscode-node/lib/src/auth/copilotTokenNotifier.ts'] direct=17 indirect=75
- `what breaks if I remove caching` → label='architecture symbol `caching`' modules=['extensions/copilot/src/platform/parser/node/parserWithCaching.ts'] direct=4 indirect=34
- `what breaks if I remove configuration` → label='architecture symbol `configuration`' modules=['extensions/configuration-editing/src/browser/net.ts', 'extensions/configuration-editing/src/configurationEditingMain.ts'] direct=0 indirect=0
- `what breaks if I remove the logging layer` → label=None modules=[] direct=0 indirect=0

## Investigation Results

Score **100.0** / 100 · grounded 1.0 · clean (no dotfiles) 1.0 · avg modules/symptom 5.4.

- `duplicate events are being fired` → ['extensions/copilot/test/simulation/fixtures/fixing/python/pyright_no_to_string_member.py', 'src/vs/platform/agentHost/node/claude/claudeMapSessionEvents.ts', 'extensions/copilot/src/extension/prompts/node/base/promptRenderer.ts']
- `websocket connections keep disconnecting` → ['src/vs/platform/agentHost/browser/webSocketClientTransport.ts', 'src/vs/sessions/contrib/tunnelHost/electron-browser/toggleRemoteConnectionsActionViewItem.ts', 'src/vs/platform/meteredConnection/browser/meteredConnectionService.ts']
- `authentication fails intermittently` → ['extensions/copilot/src/platform/parser/test/node/fixtures/try.py', 'extensions/copilot/src/extension/completions-core/vscode-node/lib/src/auth/copilotTokenManager.ts', 'extensions/copilot/src/extension/completions-core/vscode-node/lib/src/auth/copilotTokenNotifier.ts']

## Build Plan Results

Score **100.0** / 100 · plans with affected modules 4/4.

- `add distributed tracing` → ['extensions/copilot/src/extension/completions-core/vscode-node/prompt/src/test/testdata/example.py']
- `add rate limiting` → ['extensions/copilot/src/platform/parser/test/node/fixtures/try.py', 'src/vs/workbench/contrib/chat/browser/widget/chatContentParts/chatAnonymousRateLimitedPart.ts']

## Failure Analysis

| Scenario | Expected | Actual | Root cause | Subsystem | Category |
|---|---|---|---|---|---|
| what breaks if I remove the logging layer | concept resolves to modules | fallback / no target | concept absent from repo or not in resolver map | target_resolver / impact_engine | semantic_routing_failure |
| what breaks if I remove the extension host | concept resolves to modules | fallback / no target | concept absent from repo or not in resolver map | target_resolver / impact_engine | semantic_routing_failure |
| what breaks if I remove the command registry | concept resolves to modules | fallback / no target | concept absent from repo or not in resolver map | target_resolver / impact_engine | semantic_routing_failure |

## Top 5 Failures

### 1. Concept "the logging layer" not resolved (fallback)

- **Failure:** Concept "the logging layer" not resolved (fallback)
- **Frequency:** 6 repositories (this repo: 1 scenario)
- **Root Cause:** concept absent from repo or not in resolver map
- **Suggested Future Phase:** Phase 137 — Semantic Generalization (universal concept inference beyond the HA-tuned map)

### 2. Concept "the extension host" not resolved (fallback)

- **Failure:** Concept "the extension host" not resolved (fallback)
- **Frequency:** 1 repository (this repo: 1 scenario)
- **Root Cause:** concept absent from repo or not in resolver map
- **Suggested Future Phase:** Phase 137 — Semantic Generalization (universal concept inference beyond the HA-tuned map)

### 3. Concept "the command registry" not resolved (fallback)

- **Failure:** Concept "the command registry" not resolved (fallback)
- **Frequency:** 1 repository (this repo: 1 scenario)
- **Root Cause:** concept absent from repo or not in resolver map
- **Suggested Future Phase:** Phase 137 — Semantic Generalization (universal concept inference beyond the HA-tuned map)
