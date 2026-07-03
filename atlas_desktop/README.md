# Atlas Desktop

Local **Repository Intelligence Platform** — scan a codebase, explore its dependency graph, ask grounded Copilot questions, and export AI context packets for Claude, Codex, or Cursor.

No external APIs. No API keys. Analysis runs on your machine via Builder Core.

## Quick start

From the repository root:

```bash
py run_atlas.py
```

Optional flags:

```bash
py run_atlas.py --port 8777 --host 127.0.0.1 --no-browser
```

Your browser opens to `http://127.0.0.1:8777/`.

## First-time flow

1. **Read onboarding** — explains what Atlas does (shown once).
2. **Choose repository** — paste the full path to your project root, click **Validate**, then **Scan Repository**.
   - Or click **Try Demo Mode** to explore with a bundled sample repo.
3. **Scan completes** — review files, modules, edges, top risk, and suggested next steps.
4. **Command Center** — 3D dependency graph + Copilot panel.
5. **Export** — copy compact context for Claude/Codex/Cursor.

## Scan a repository

1. Paste path (examples):
   - Windows: `C:\dev\my-project`
   - Linux/macOS: `/home/you/projects/my-project`
2. Click **Validate** — confirms folder exists, is readable, and contains source files.
3. Click **Scan Repository** — Builder Core builds the production-scope dependency graph and risk ranking.

### Validation errors

| Message | Fix |
|---|---|
| Path does not exist | Check spelling and drive letter |
| No source code files | Choose a project root with `.py`, `.js`, etc. |
| Permission denied | Pick a folder your user can read |

## Demo Mode

**Try Demo Mode** loads a bundled mini repository (`atlas_desktop/demo/sample_repo/`) without choosing a path. The header shows a **Demo Mode** badge. All features work the same; data is labeled as demo.

## Features

| Screen | Purpose |
|---|---|
| Home | Pick repo, Demo Mode, recent paths |
| Scan | Progress, success, or failure |
| Command Center | Graph + Copilot |
| Intelligence | Plain-English repo summary |
| Impact | Blast radius for a file change |
| Bug Hunt | Heuristic localization from traces |
| AI Export | Token-estimated context packets |

## Copilot (grounded, local)

Ask questions like:

- What does this repository do?
- What are the top architectural risks?
- What breaks if I change `config.py`?
- Show import cycles.
- Generate a Claude prompt for this repo.

Answers use scan data only — not a cloud LLM.

## Known limitations

- **Path input** — Browsers cannot pick full filesystem paths natively; paste the path manually.
- **Impact analysis** — Direct importers only (transitive Phase 94B not wired in UI).
- **Bug Hunt** — Heuristic path matching, not semantic defect analysis.
- **3D graph** — Loaded from CDN (`3d-force-graph`); offline falls back to text hubs.
- **Large repos** — Graph display capped at 5000 modules; scan still indexes full graph.
- **Copilot** — Deterministic summaries, not generative chat prose.

## Screenshots checklist (for demos)

Capture these before an external user test:

1. [ ] Onboarding welcome screen
2. [ ] Home with validated path + recent repos
3. [ ] Scan success screen (metrics + next steps)
4. [ ] Command Center graph (module view)
5. [ ] Copilot answer card with evidence
6. [ ] Demo Mode badge in header
7. [ ] AI Export preview with token estimate
8. [ ] Scan failed screen (optional — use invalid path)

## Tests

```bash
py -m pytest atlas_desktop/tests -q
```

## Architecture

- `atlas_desktop/api.py` — product logic (scan, graph, copilot, validation)
- `atlas_desktop/server.py` — stdlib HTTP server + optional FastAPI
- `atlas_desktop/static/` — SPA (HTML/CSS/JS)
- `builder_core/` — dependency graph, architectural risk (unchanged by Desktop UI)
