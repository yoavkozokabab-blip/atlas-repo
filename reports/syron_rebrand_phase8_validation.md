# Syron Rebrand — Phase 8: Validation Report

## 1. Files changed

**38 files rebranded** (160 + 9 = **169 replacements**) across the product brand
surface, plus 3 reports and 1 migration script:

| Group | Files | Notes |
|---|---:|---|
| `jarvis_desktop/static/*.html` | 16 | landing, index, about, contact, docs, pricing, usage, billing_admin, privacy, security, terms, roadmap, changelog, graph_smoke, … |
| `jarvis_desktop/static/*.js` | 6 | app.js, atlas_beta.js (content), universe.js, marketing.js, feedback.js, billing.js |
| `jarvis_desktop/static/*.css` | 1 | styles.css |
| User-facing code | 9 | server.py (title/version), api.py (product name + demo label), planning_engine.py (investigation/build output), domain_knowledge.py, reliability.py, impact_engine/concept_lexicon.py + __init__, architecture/__init__, evidence_builder.py |
| Billing/usage user copy | 5 | usage/{estimator,plans,tracker}.py, billing/models.py |
| Brand tests | 5 | test_phase119/118b/122/110/141 (assertions updated to match) |

Validation:
- **Imports OK** (`server`, `api`, `planning_engine`, `reliability`, `concept_lexicon`).
- **Routes unchanged**: 42 routes, none renamed.
- **`api.health()["product"]` → `SYRON`.**
- Window/app title → "Syron — Repository Intelligence Platform";
  server header → `SyronDesktop/119`.

## 2. Remaining Atlas references

**Zero** user-facing brand references remain in the product
(`grep -E "\bAtlas\b|\bATLAS\b"` over `static/**` and product code, excluding the
intentional exceptions below = 0).

## 3. Intentional exceptions (must NOT be renamed)

| Item | Why preserved |
|---|---|
| `atlas_knowledge/` package + `atlas://catalog/…` URIs (600+) | Internal package + data-key scheme; renaming changes data/behavior. |
| Knowledge content referencing real products (e.g. *MongoDB Atlas*) | Third-party names, not our brand. |
| `ATLAS_ADMIN`, `ATLAS_BILLING_UI_ENABLED`, `ATLAS_USAGE_*` env vars (8) | Configuration identifiers; renaming breaks existing setups. |
| `atlas_recent_repos`, `atlas_onboarding_*` `localStorage` keys | Stored user data; renaming silently drops local state. |
| `atlas_self` benchmark id, `atlas_beta.js` filename, `showAboutAtlas()` JS ids | Internal identifiers; not user-visible. |
| `external_repos/**`, vendored benchmark data | Not ours. |
| Historical execution reports (`reports/phase1xx_*.md`) | Describe past states when the product was named Atlas. |
| Binary assets (favicons, app icons, raster logos, screenshots) | Cannot be regenerated without design tooling — **follow-up required**. |

## 4. Branding consistency score

**Text/code surface: 100%** — every user-facing string now reads "Syron"; no
mixed Atlas/Syron branding remains in HTML, JS, CSS, or user-facing code.

**Overall product readiness: ~95%** — the residual 5% is:
- Binary assets (icons/favicons/screenshots) still show the old mark (need design
  regeneration; flagged).
- Internal identifiers intentionally retain `atlas_*` names (invisible to users).

## 5. Known unrelated test drift (NOT caused by the rebrand)

Three assertions fail due to concurrent `phase141` launch work, not this rebrand
(none reference an "Atlas" token, so the brand replacement could not have changed
their pass/fail state):
- `test_phase122::test_product_version_atlas_hardening_lineage` — `PRODUCT_VERSION`
  was bumped to `phase141-private-beta-launch` (asserts `phase12`).
- `test_phase119::test_home_actions_present` — home action button labels changed.
- `test_phase119::test_js_uses_atlas_keys` — onboarding `localStorage` key was
  renamed to `…_v2_done`.

These belong to the concurrent launch effort and should be reconciled there.

## Goal check

On launch, the desktop window, website, in-app copy, exports, and marketing text
all read **Syron**. Internal wiring (routes, packages, stored data, env vars,
knowledge URIs) is untouched, so behavior is identical. The product now presents
as if it was always called Syron.
