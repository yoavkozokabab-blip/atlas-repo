# Information architecture

## Stable application rail

### Repository

- Home
- Memory
- Files
- Graph

### Investigate

- Ask
- Impact
- Debug
- Plan

### Operate

- Agents
- Diagnostics

Settings is pinned at the bottom. Repository selection remains visible in the status bar from every workspace.

## Global status bar

It answers without opening a menu:

1. Which repository is active?
2. Is its index and memory current?
3. Is Atlas ready?
4. Is an agent connected?

It also exposes command/search and account/local-mode state. Status text accompanies color.

## Current-to-target mapping

| Current | Target |
| --- | --- |
| `view-home` | Home state router |
| `view-scan` | Repository selector/scan operation |
| `view-hn` | First-run sample action only |
| `view-ask` | Ask |
| `view-impact` | Impact |
| `view-investigate` | Debug |
| `view-build` | Plan |
| `view-center` | Graph; system health moves to Diagnostics |
| Map list/inspector | Files and Graph inspectors |
| Home MCP cards | Agents |
| `view-export` | Agents and result-level Handoff |
| support/startup checks | Diagnostics |
| account/status/usage | Settings/Account |

Scan is contextual, not permanent primary navigation. HN demo is acquisition/onboarding, not a recurring developer task. Memory and Files become inspectable because they are core product objects.

## Compact behavior

Below 1100 px the rail collapses to 72 px while active state and labelled tooltips remain. Below 820 px secondary inspectors become drawers and tables hide lower-priority columns. The app does not become a mobile tab bar.
