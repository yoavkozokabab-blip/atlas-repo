# Phase 116 — TypeScript/JavaScript Dependency Graph Support

## Summary

JARVIS Desktop now builds **import-level dependency graphs** for JavaScript and TypeScript repositories, merged with the existing Python `depgraph` output. VS Code scans are no longer empty.

## VS Code before / after

| Metric | Before (115C) | After (116) |
|---|---:|---:|
| Scan time | ~30s (empty graph) | **9.07s** |
| `module_count` | **0** | **8144** |
| `dependency_edges` | **0** | **13224** |
| TypeScript modules | 0 | **8108** |
| JavaScript modules | 0 | **36** |
| Python modules | 0 | 0 |
| External package refs | — | **232** (unique packages) |
| JS files in graph | 0 | **8144** kept / 8147 candidates |

Artifacts: `reports/phase116_vscode_before.json`, `reports/phase116_vscode_after.json`

Subsystem view (massive mode default) shows **6 subsystem hubs** / **2 cross-links** — module-level graph has 8144 nodes when forced.

## Architecture (additive)

| Component | Path | Role |
|---|---|---|
| JS/TS graph builder | `builder_core/bug_intelligence/jsdepgraph.py` | Discovery, import regex extraction, resolution, depgraph-shaped JSON |
| Multilang merge | `jarvis_desktop/graph_build.py` | `merge_graphs()`, `build_scan_graph()` runs Python + JS |
| Desktop API | `jarvis_desktop/api.py` | `language_breakdown`, multilang risk signal availability |
| UI | `jarvis_desktop/static/app.js` | Language metrics + empty-graph message |

Python `depgraph` / `architectural_risk` core logic unchanged; TS modules use import fan-in/out, cycles, LOC; Python-only signals marked `unavailable`.

## Features delivered

1. **Extensions:** `.js`, `.jsx`, `.ts`, `.tsx`, `.mjs`, `.cjs`
2. **Import forms:** ESM import/export-from, `require()`, literal `import()`
3. **Relative resolution:** `./`, `../`, extension/index variants
4. **Path aliases:** `tsconfig.json` / `jsconfig.json` `baseUrl` + `paths` (incl. `@scope/*`)
5. **Production scope:** skips `node_modules`, `dist`, `test`/`tests` segments, `__tests__`, `fixtures`, `testdata`, `*.test.ts`, `*.spec.ts` — **keeps** `contrib/testing` (segment `testing` ≠ `test`)
6. **Module IDs:** `module:src/vs/workbench/...` (extensionless path key)
7. **Metadata:** `language`, `extension`, `external_package_count`, `unresolved_import_count`
8. **Cap:** `JS_MAX_FILES = 12000` (VS Code ~8147 fits; avoids empty degraded graph at Python’s 5000 cap)

## Tests

- `builder_core/tests/test_phase116_jsdepgraph.py`
- `jarvis_desktop/tests/test_phase116_typescript_graph.py`
- Fixture: `jarvis_desktop/demo/ts_sample_repo/`

## Known limits (documented, not hidden)

- Import-only graph (no call/type edges for JS/TS)
- Regex extraction (not full TypeScript compiler)
- Unresolved internal alias/relative paths counted in `unresolved_imports` (~69k for VS Code — mostly external/npm)
- Massive repos default to **subsystem** graph view in Command Center

## Verification

```bash
cd local_jarvis
py -m pytest builder_core/tests/test_phase116_jsdepgraph.py jarvis_desktop/tests/test_phase116_typescript_graph.py -q
py -c "from jarvis_desktop import api; r=api.scan_repository(r'C:\\J.A.R.V.I.S\\vscode'); print(r['module_count'], r['dependency_edges'])"
```

Expected: `8144 13224` (approximate).
