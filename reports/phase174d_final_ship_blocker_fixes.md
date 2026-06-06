# Phase 174D — Final Trust-Integrity Ship Blocker Fixes

**Date:** 2026-06-06  
**Verdict:** Clears 174C-SB1, 174C-SB2, 174C-SB3

## Blockers Fixed

### SB1 — Unsupported / shallow graph false success (P0)

**Problem:** Build/Investigation returned `ok=true` on Go/Kubernetes repos with incidental `hack/boilerplate.py` helper only.

**Fix (`trust_integrity.py`):**

- Extended `gate_weak_graph_workflow()` beyond label-only check:
  - `graph_health=unsupported_language_limited`
  - `files > 1000` AND `modules < 25`
  - Shallow unsupported coverage: non-Python production dominates, `edges == 0`, tiny module count (174C A7)
- Removed Python path-list fallback — requires **real graph/symbol evidence** (`matching_symbols`, `evidence_score ≥ 50`, resolved edges or calls)
- Returns `ok=false`, `confidence=low`, `status=unsupported_language_limited` or `insufficient_evidence`

### SB2 — Memory packet replay metadata (P1)

**Problem:** `ATLAS_REPOSITORY_MEMORY v1` had `scan_id` but no signature, freshness, or replay warning.

**Fix (`repository_memory.py`):**

Every memory packet/export now includes:

| Field | Example |
|-------|---------|
| `scan_id` | `aa95e61f` |
| `scan_signature` | first 12 chars of signature hash |
| `generated_at` | ISO scan timestamp |
| `freshness_status` | `fresh` / `stale_outside_plan` / etc. |
| `replay_warning` | "This context is only valid for the scanned repository state…" |

`freshness_status` computed from `trust_integrity.assess_staleness()` at packet generation.

### SB3 — Support bundle secret leak (P0)

**Problem:** `api_key=LEAK_ME` passed through support bundle redaction.

**Fix (`install_support.py`):**

`_redact_secret_values()` redacts:

- `key=value` / `key: value` for api_key, token, password, secret, bearer, etc.
- JSON `"key": "value"` fields
- `Authorization:` / `Bearer` headers
- Token prefixes: `sk-ant-`, `sk-`, `ghp_`, `github_pat_`, `xoxb-`, JWT `eyJ…`

Existing path and `SECRET_*` redaction preserved.

## Files Changed

| File | Change |
|------|--------|
| `jarvis_desktop/trust_integrity.py` | Shallow-graph gate + strict symbol evidence |
| `jarvis_desktop/repository_memory.py` | Replay metadata on memory text/packet |
| `jarvis_desktop/install_support.py` | Secret pattern redaction |
| `jarvis_desktop/tests/test_phase174d_final_ship_blockers.py` | **New** — 12 blocker tests |

## Test Results

```
py -3 -m pytest jarvis_desktop/tests/test_phase174d_final_ship_blockers.py -q  # 12 passed
py -3 -m pytest jarvis_desktop/tests/test_phase174b_trust_integrity.py -q       # 17 passed
py -3 -m pytest jarvis_desktop/tests/test_phase172a_memory_attack_surface.py -q # 6 passed
py -3 -m pytest jarvis_desktop/tests/test_phase172_memory_engine.py -q          # 49 passed
```

**Total: 84 passed**

## Remaining Limitations

- Shallow-graph detection uses index role/ext heuristics; exotic languages may still need manual file targeting.
- Memory replay warning is textual — external LLMs must honor it; Atlas cannot revoke already-copied packets.
- Secret redaction is pattern-based; novel credential formats may need future patterns.
