---
name: atlas-desktop-design-qa
description: Audit, redesign, implement, and visually verify the Atlas browser-hosted Windows desktop application in atlas-rc1-clean. Use for atlas_desktop/static, launch/auth/local mode, repository scan and memory, Ask/Impact/Debug/Plan/Graph, MCP agents, diagnostics, settings, accessibility, desktop responsiveness, or installed-app visual QA. Do not use for websites/atlas-web.
---

# Atlas desktop design and QA

## Boundaries

- Work only in `C:\J.A.R.V.I.S\atlas-rc1-clean` unless the user names another repo.
- Never redesign `websites/atlas-web`.
- Treat Atlas as a Python loopback server plus browser-hosted UI, not Electron/Tauri.
- Preserve APIs, stored data, persistence, MCP semantics, account gates, installer/updater, and loopback security.
- Do not invent data, scan phases, confidence, files, symbols, or relationships.
- Preserve dirty-worktree changes. Stage explicit paths only; never `git add .` or `git add -A`.

## Required sequence

1. Prove the entry and branch: `atlas_desktop_entry.py`, `run_atlas.py`, `atlas_desktop/server.py`, `atlas_desktop/static/index.html`.
2. Read `docs/design/desktop-redesign/` and relevant checkpoint documents.
3. Run source mode with isolated `ATLAS_DESKTOP_DATA`.
4. Capture the current state with Browser or Computer Use before changing it.
5. Map changed DOM IDs to JavaScript and test consumers.
6. Implement coherent primitives; do not add another unbounded override layer.
7. Verify every changed workflow at 900x650, 1280x720, 1440x900, and 1920x1080.
8. Run focused tests, JS syntax, accessibility checks, then the relevant full suite.
9. For release claims, verify installed app and fresh-process persistence. Source-only success is insufficient.

## Visual rules

- Use graphite surfaces, mineral teal active state, warm off-white text, restrained indigo, thin borders, and 3-7 px radii.
- Use interface typography for operations; monospace only for paths, symbols, commands, evidence, hashes, and measured values.
- Prefer rows, split panes, inspectors, and tables over card grids.
- Keep repository, readiness, memory freshness, and agent connection visible.
- No cyan glow, marketing hero, gaming HUD, decorative graph, fake metric, hover-only meaning, icon-only critical state, or continuous motion.

## Accessibility and desktop behavior

- Maintain visible focus, semantic landmarks, accessible names, logical tab order, and focus return.
- Never encode state by color alone.
- Provide a list/table equivalent for every graph mode.
- Respect reduced motion, 200% zoom, compact windows, high DPI, long paths, and keyboard-only operation.
- Keep the rail and core status stable; secondary panels become drawers before the workspace collapses.

## Product-truth gate

Compare every UI claim to the exact API field that supports it. If absent or partial, label the limitation or omit the claim. Verify MCP writes preserve unrelated servers and expected backups. Verify persisted memory from a fresh process before claiming restoration.

## Reference

Read `references/checklist.md` for the workflow regression and screenshot checklist.
