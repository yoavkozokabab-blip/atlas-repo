# Phase 176 — First Impression Sprint

**Goal:** Optimize the first 10 minutes of Atlas for new users — perception and demo quality only.

**Out of scope (unchanged):** `trust_integrity.py`, graph generation, `repository_memory.py` core, `impact_engine`.

## Delivered

### 1. Demo quality

Audited `small`, `medium`, and `large` demo packs with pack-specific first-run examples:

| Pack | Build | Investigate | Impact |
|------|-------|-------------|--------|
| small | Improve error handling in core/hub.py | API requests fail intermittently under load | core/hub.py |
| medium | Add structured logging to API handlers | API requests fail intermittently under load | api/handlers.py |
| large | Improve error handling in gateway/entry.py | API gateway returns 500 under load | gateway/entry.py |

When a demo workflow cannot answer (empty files, empty order, low confidence, empty impact), API returns `demo_limited` with:

> Try a real repository for best results.

Implemented in `jarvis_desktop/first_impression.py` and wired through `api.py`.

### 2. Clipboard cleanup (beginner)

`atlas_zero_friction.js` strips from beginner copy only (kept internally / advanced):

- `scan_id`, `scan_signature`, `memory_ref`, `generated_at`, `replay_warning`, `freshness_status`, `ref:`

### 3. Output cleanup

Empty `MUST inspect` / `LIKELY modify` / `VERIFY only` sections are omitted from markdown (`planning_engine.py`) and from the domain-knowledge UI (`app.js`).

### 4. Evidence score

`cap_evidence_score()` enforces 0–100 in `first_impression.py`, markdown export, and UI (`fiCapScore`).

### 5. Status wording

Feature requests no longer show **Implemented** — replaced with **Proposed** in API polish, markdown, and `renderRepositoryEvidence`.

### 6. Investigate cleanup

Removed trading-era placeholder text from `index.html` investigate textarea.

### 7. Beginner mode

Beginner view shows only **Goal**, **Files**, **Order**, **Copy for Claude** via `beginnerPlanHero`, `beginnerInvestigateHero`, and `beginnerImpactHero`. Full reports, trust blocks, and repository evidence panels are behind **Advanced**.

## Tests

`jarvis_desktop/tests/test_phase176_first_impression.py` — demo first-run audit, score cap, status wording, empty-section omission, static asset checks.

## Files touched

- `jarvis_desktop/first_impression.py` (new)
- `jarvis_desktop/api.py`
- `jarvis_desktop/planning_engine.py`
- `jarvis_desktop/static/atlas_zero_friction.js`
- `jarvis_desktop/static/app.js`
- `jarvis_desktop/static/index.html`
- `jarvis_desktop/tests/test_phase176_first_impression.py`
- `reports/phase176_first_impression_sprint.md`
