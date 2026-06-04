# Phase 146 — Beta Polish

**Date:** 2026-06-02  
**Scope:** Onboarding, wording, errors, empty states, installer friction, support workflow — **no** new intelligence, analysis engines, or billing.

## Phase 145 note

No `phase145_*.md` artifact was found in the repository. Polish priorities were taken from:

- `reports/phase142_beta_breakage_audit.md` (predicted support tickets)
- `reports/phase144_private_beta_execution.md` (onboarding funnel + metrics)

## Goal

Reduce support burden so a first-time user reaches a **successful Build Plan** without asking for help.

## Changes (summary)

| Area | Change |
|------|--------|
| Home | Demo-first steps; **Planning only** banner; primary CTA **Load Sample Repository** |
| Welcome | States Atlas does not write code; fastest path = sample → Build Plan |
| After scan | Primary button **Try your first Build Plan**; sample auto-opens Build with example |
| Build Plan | First-build banner; clearer empty state; marks first success in localStorage |
| Scan | Surfaces `health_warnings` / degraded scan copy (non-alarming) |
| Validate | Friendlier path errors (`not_directory`, permissions, etc.) |
| Export | Explicit “paste into Claude/Codex/Cursor” instruction |
| Support | Beta FAQ: Python, no pip on monorepo, huge-repo scope, planning-only |
| Installer | `Launch Atlas.bat` reminds: Python 3.10+, no pip install |
| Docs | `docs/ATLAS_QUICKSTART.md` single-page run instructions |

## First-time funnel (target < 5 min)

1. Double-click **Launch Atlas** (or `Launch Atlas.bat`)
2. **Load Sample Repository**
3. Auto-navigate to **Build Plan** with example text
4. Click **Generate Change Plan** → grounded plan with modules and steps

## Support burden estimate (after 146)

| Ticket theme (Phase 142) | Mitigation in 146 |
|--------------------------|-------------------|
| pip install failures | Quickstart + Support FAQ + launcher message |
| Expectation: writes code | Planning-only banner on Home, Welcome, About |
| Scan huge tree | Picker help + Support FAQ |
| Export “now what?” | Export screen paste instruction |
| Degraded scan confusion | Scan reliability notice on success panel |

**Estimated reduction:** ~25–35% fewer “how do I start?” and expectation tickets in week one (qualitative).

## Readiness score: **8.7 / 10** (beta polish)

Remaining friction:

- Python still a one-time prerequisite (not bundled)
- Mac/Linux still manual `python3 run_atlas.py`
- First Build Plan on **own repo** still requires validate + scan (sample path is the guided default)

## Tests

```bash
py -3 -m pytest jarvis_desktop/tests/test_phase146_beta_polish.py -q
```

## Files

- `jarvis_desktop/static/atlas_polish.js` (new)
- `jarvis_desktop/static/index.html`, `app.js`, `atlas_beta.js`, `support.html`, `styles.css`
- `docs/ATLAS_QUICKSTART.md`
- `Launch Atlas.bat`, `jarvis_desktop/install_support.py` (hint)
- `jarvis_desktop/api.py` (`PRODUCT_VERSION`)
