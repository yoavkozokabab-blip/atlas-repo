# Workflow map

```mermaid
flowchart LR
  L["Launch"] --> T["Startup checks"]
  T -->|ready| A["Account choice"]
  T -->|failure| D["Diagnostics and recovery"]
  A -->|local mode or signed in| R["Repository workbench"]
  R -->|no repository| S["Select or resume"]
  S --> V["Validate path and scope"]
  V --> Q["Scan"]
  Q -->|cancel or fail| S
  Q -->|complete| M["Persist graph, evidence, and memory"]
  M --> H["Repository ready"]
  H --> X["Connect Claude Code, Cursor, or Codex"]
  H --> I["Investigate"]
  I --> ASK["Ask"]
  I --> IMP["Impact"]
  I --> DBG["Debug"]
  I --> PLN["Plan"]
  I --> G["Graph and files"]
  ASK --> E["Cited evidence and next action"]
  IMP --> E
  DBG --> E
  PLN --> E
  E --> HAND["Agent handoff or MCP"]
  M -->|stale, moved, invalid| S
```

## Fragile handoffs

- Account/local-mode state controls protected repository and analysis routes.
- Scan completion populates `STATE.summary`, graph, recents, persistence state, and target pickers.
- Home agent cards depend on exact MCP IDs and real config-write/test handlers.
- Ask/Impact/Debug/Plan share DOM targets, history, and cross-navigation.
- Map selection feeds module inspection, Ask context, Impact, and copied paths.
- Diagnostics rebuild/cache actions mutate local state and require explicit explanation and confirmation.
