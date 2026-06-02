# Phase 122 — Metric Truth Audit

| Metric | Source | Calculation | Verified? | Stale/cache? | UI visibility |
|--------|--------|-------------|-----------|--------------|---------------|
| Module count | `scan_repository` → `module_count` | Production-scope modules indexed | Yes (per scan) | Per scan session | Cockpit, graph headers |
| Dependency edges | Graph build | Resolved import edges in production graph | Yes | Per scan | Graph mode metrics |
| Risk score | Risk engine on graph | Aggregated module risk scores | Heuristic | Per scan | Cockpit |
| Graph health label | `_graph_health()` | healthy / degraded from unresolved ratio + cycles | Heuristic | Per scan | Cockpit |
| Import cycles | Cycle detection on graph | Count of import cycles | Yes (static) | Per scan | Cockpit |
| Resolved imports | Edge filter | `resolved=True` internal edges | Yes | Per scan | Cockpit |
| Unresolved imports | Edge filter | Internal unresolved only | Yes | Per scan | Cockpit (tooltip: internal only) |
| External package imports | Edge metadata | External deps; **excluded** from unresolved ratio | Yes | Per scan | Cockpit (tooltip) |
| Unresolved ratio | `unresolved / (resolved+unresolved)` internal | **Not** inflated by external | Yes | Per scan | Cockpit + `unresolved_ratio_note` |
| Token savings % | `_token_savings()` | `module_count×600` vs compact packet estimate | **No** | Per scan | **Hidden** (`show_in_cockpit: false`) |
| Top hubs / risks | Risk ranking | fan-in + coupling heuristics | Heuristic | Per scan | Cockpit lists |
| Scan time | Scan pipeline | Wall clock for scan stages | Yes | Per scan | Scan UI progress |
| Graph visible nodes | `current_graph` payload | May be subset in architecture/hierarchy/massive mode | Yes | Per view switch | Entity summary + badge |
| Impact fan-in | `impact()` | Count of direct importers (resolved) | Yes (direct only) | Per request | Impact page |
| Planning confidence | `planning_engine` | Keyword + graph match scores | Heuristic | Per request | Build / Investigate |

## Actions taken

1. **Token savings** — removed from cockpit unless `verified` and `show_in_cockpit` (both false by default).
2. **Unresolved ratio** — explanatory note in API and UI tooltip.
3. **External imports** — labeled as separate from unresolved internal failures.
4. **Impact** — `direct_only` scope; no transitive pretense.

## Misleading metrics removed from default UI

- `99.9%` token savings (and any unverified reduction %)
