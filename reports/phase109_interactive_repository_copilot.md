# Phase 109 — Interactive Repository Copilot

**Product version:** `phase109-copilot`  
**Verdict:** Grounded local copilot **implemented** (no external APIs)

## Goal

Turn the Command Center right panel into a real repository assistant that answers from existing Builder Core scan outputs.

## Backend

### Endpoint

`POST /api/copilot/ask`

**Input**

```json
{
  "question": "...",
  "target": "claude|codex|cursor|none",
  "packet": "compact|verbose",
  "node_context": { "path": "...", "label": "...", "fan_in": 0 }
}
```

**Output**

Deterministic envelope with `mode`, `answer`, `evidence`, `files`, `risk_level`, `suggested_prompt`, `suggested_action`, `copy_targets`, `confidence`, `limitations`.

### Routing

| Question cues | Mode | Source |
|---|---|---|
| repo purpose, start here, subsystem | `repository_understanding` | `current_summary()` |
| risk, bottleneck | `risk` | `current_risks()` |
| what breaks, change file, tests | `impact` | `impact()` |
| cycles, circular | `cycles` | depgraph `import_cycles` |
| who imports, dependency | `dependency` | resolved import edges |
| Claude/Codex/Cursor/prompt | `context_export` | `_render_context()` |
| no match | `unknown` | suggested questions |

No external LLM calls. Partial answers are explicit when a capability is not wired (e.g. transitive impact).

## Frontend

Command Center copilot panel:

- Question input + Send button
- Suggested questions (repo-wide or node-specific)
- Loading state
- Answer card with mode badge + risk badge
- Evidence list + file chips
- Suggested next action
- Copy answer / Claude / Codex / Cursor prompts

### Graph integration

- Selected node card in copilot when a graph node is clicked
- Node-specific suggested prompts (explain, impact, importers, Claude prompt)
- Edge visibility toggle (Show edges on/off)
- Hover + selected-node neighbor highlighting with stronger edges
- Risk coloring by percentile: top 1% red, top 5% orange, cycle purple, normal blue

## Example questions tested

| Question | Mode |
|---|---|
| What does this repository do? | repository_understanding |
| What are the top architectural risks? | risk |
| What breaks if I change core/util.py? | impact |
| Show import cycles | cycles |
| Generate a Claude prompt for this repo | context_export |
| xyzzy plugh | unknown |

## How to run

```bash
cd local_jarvis
py run_jarvis_desktop.py
```

1. Scan a repository (or `local_jarvis`).
2. Command Center opens automatically.
3. Ask questions in the right copilot panel or click suggested prompts.
4. Click graph nodes for module-specific suggestions.

### Screenshots

Run the desktop app locally and capture:

1. Command Center with copilot answer card visible
2. Graph node selected with node-specific suggestions
3. Subsystem vs module graph toggle with edge visibility off/on

## Tests

```bash
py -m pytest jarvis_desktop/tests/test_phase109_interactive_repository_copilot.py \
              jarvis_desktop/tests/test_phase108_real_dependency_graph.py \
              jarvis_desktop/tests/test_phase107_desktop_api.py -q
```

**Result:** 27 passed (Phase 107 + 108 + 109)

## Files modified

- `jarvis_desktop/api.py` — `copilot_ask()`, routing, node prompts
- `jarvis_desktop/server.py` — route + FastAPI handler
- `jarvis_desktop/static/app.js` — copilot UI, graph integration
- `jarvis_desktop/static/index.html` — copilot panel markup
- `jarvis_desktop/static/styles.css` — copilot + graph controls
- `jarvis_desktop/tests/test_phase107_desktop_api.py` — route count
- `jarvis_desktop/tests/test_phase109_interactive_repository_copilot.py` — new

## Known limitations

- Answers are deterministic summaries, not generative prose from an LLM
- Impact uses direct importers only (Phase 94B transitive engine not wired)
- Subsystem explain requires subsystem name to appear in the scan index
- Copilot requires a completed scan (`POST /api/repositories/scan`)
- 3D graph library still loaded from CDN

## Unchanged

- Builder Core analysis logic (`depgraph`, `architectural_risk`, `ask`)
- Phase 107/108 scan and graph pipeline
