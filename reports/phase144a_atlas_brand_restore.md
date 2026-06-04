# Phase 144A — Restore Atlas Branding

Reverts the product brand **Syron → Atlas** (branding only). Exact inverse of the
earlier Atlas → Syron migration, using the same curated file set and the same
word-boundary technique, so no application behavior, route, package, identifier,
or stored data changes.

## Method

`scripts/restore_atlas_brand.py` reuses the target set from
`scripts/rebrand_atlas_to_syron.py` and applies the reverse substitutions:

- `SyronDesktop` → `AtlasDesktop`
- `\bSYRON\b` → `ATLAS`
- `\bSyron\b` → `Atlas`
- `\bsyron\b` → `atlas`

Because the forward migration never created any `syron_*` identifier, the only
`Syron`/`SYRON`/`syron` tokens in the tree were user-facing brand words — so the
revert touches branding only.

## Files changed

**168 replacements across 38 files** (symmetric with the 169 forward; the 1-token
difference is an intervening edit to `server.py`):

| Group | Files | Examples |
|---|---:|---|
| `static/*.html` | 16 | index, landing, about, contact, docs, pricing, usage, billing_admin, privacy, security, terms, roadmap, changelog, graph_smoke |
| `static/*.js` | 6 | app.js, atlas_beta.js, universe.js, marketing.js, feedback.js, billing.js |
| `static/*.css` | 1 | styles.css |
| User-facing code | 9 | server.py (title/version), api.py (product + demo label), planning_engine.py, domain_knowledge.py, reliability.py, impact_engine/{concept_lexicon,__init__}, architecture/__init__ |
| Billing/usage copy | 5 | usage/{estimator,plans,tracker}.py, billing/models.py |
| Brand tests | 5 | test_phase119/118b/122/110/141 |

Restored user-facing surfaces: window/app titles ("Atlas — Repository
Intelligence Platform", `AtlasDesktop/119`), landing pages, onboarding & welcome
screens, about/support pages, marketing copy, pricing/usage/admin pages, and the
in-app planning output ("Atlas confidence:", "Atlas's most likely root cause").

## Preserved internal identifiers (unchanged, as before)

`atlas_knowledge` package, `atlas://catalog/…` URIs, `atlas_self` benchmark id,
`ATLAS_*` environment variables (11 refs intact), `atlas_recent_repos` /
`atlas_onboarding_*` localStorage keys, `atlas_beta.js` filename, and
`showAboutAtlas()` JS ids. None were ever renamed to Syron, so none required
restoring.

## Validation results

| Check | Result |
|---|---|
| Remaining user-facing `Syron`/`SYRON` in product | **0** |
| Imports (`server`, `api`, `planning_engine`, `reliability`, `concept_lexicon`) | **OK** |
| Routes | **Unchanged by this revert** (no route paths touched) |
| `api.health()["product"]` | **`ATLAS`** |
| `atlas_knowledge` package + `ATLAS_*` env vars | **Intact** |

The product again presents as **Atlas** across the desktop window, website,
onboarding, exports, and marketing copy, while all internal wiring is identical.
