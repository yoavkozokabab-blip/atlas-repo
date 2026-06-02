# Phase 122 — Button Audit

Legend: **PASS** = wired endpoint or client action works; **HIDE** = moved out of primary flow; **REMOVE** = UI removed.

| Button | Expected | Actual | Result |
|--------|----------|--------|--------|
| Browse (Home/Scan) | Native folder picker | `/api/browse` | PASS |
| Validate | Path validation | `/api/repositories/validate` | PASS |
| Scan | Full scan | `/api/scan` stream | PASS |
| Try Demo | Demo pack load | `/api/demo/load` | PASS |
| Watch Product Tour | Client tour | Client-only | PASS (Home) |
| Reset View | Camera reset | `resetGraphView()` | PASS (Advanced) |
| Tour Repository | Graph tour | Client | PASS (Advanced) |
| Export Bundle | Demo zip | `/api/demo/export-bundle` | PASS (Advanced) |
| PNG / SVG / Screenshot | Graph export | Client canvas | PASS (Advanced) |
| Ask Copilot / Send | Q&A | `/api/copilot/ask` | PASS |
| Suggested questions | Fill + send | Copilot | PASS |
| Generate Change Plan | Plan | `/api/planning/change` | PASS |
| Generate Investigation Plan | Investigate | `/api/planning/investigate` | PASS |
| Simulate Impact (Build) | Impact sim | `/api/planning/impact` | PASS |
| Simulate Impact (Impact tab) | Impact | `/api/impact` | PASS |
| Copy Claude/Codex/Cursor | Clipboard | Client | PASS |
| Export copy/save | Context | `/api/context/export` | PASS |
| Recent repo chips | Fill path | Client | PASS |
| Module graph toggles | Graph view | `/api/graph` | PASS |
| Bug Hunt Investigate | — | **REMOVED** | MERGE → Investigate |
| Start Product Tour (graph toolbar) | — | **HIDE** | Removed from primary toolbar |

## Failures fixed this phase

- None requiring code removal beyond duplicate Bug Hunt screen (merged into Investigate).

## Notes

- Advanced toolbar collapsed by default so beta users are not exposed to half-finished “wow” controls.
- `/api/bug-investigation` remains for API compatibility; UI uses planning investigate endpoint.
