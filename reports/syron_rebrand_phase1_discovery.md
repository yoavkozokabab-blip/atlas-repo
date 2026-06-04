# Syron Rebrand — Phase 1: Discovery & Migration Report

**Scope:** rename the product brand **Atlas → Syron**. Branding only — no change
to behavior, architecture, APIs, data models, algorithms, routes, or stored data.

## Where the brand lives

The "Atlas" brand is **entirely contained in `jarvis_desktop/`**. The rest of the
J.A.R.V.I.S repository does not use it:

| Area | Files with `atlas` refs |
|---|---:|
| `jarvis_desktop/` | 233 |
| `marketing/`, `websites/`, `installer/`, `apps/`, root `README*.md` | **0** |
| `external_repos/` (vendored 3rd-party) | excluded (not ours) |

Of the 233 files in `jarvis_desktop`, the large majority are the
`atlas_knowledge/` data package, which is **not product branding** (see exclusions).

## Reference classification

| Type | Examples | User-facing? | Action |
|---|---|---|---|
| Page/UI brand text | `<title>ATLAS …</title>`, "Welcome to Atlas", "Atlas scans…" | **Yes** | **Rename** |
| Marketing copy | landing/about/contact/docs/pricing HTML | **Yes** | **Rename** |
| App strings in code | "Atlas Demo — …" (`api.py`), planning output ("Atlas confidence:", "Atlas's most likely root cause") | **Yes** | **Rename** |
| Server/app title | "Atlas — Repository Intelligence Platform", `AtlasDesktop/119` (`server.py`) | **Yes** | **Rename** |
| Code comments/docstrings | "Atlas's impact concept resolution…" | No (dev-facing) | Rename (cheap, consistent) |
| Brand UI tests | `test_phase119_atlas_product_polish.py` assertions | No | Rename assertions to match |
| **`atlas_knowledge/` package** | package name + imports | No | **Exclude — internal identifier** |
| **`atlas://` catalog URIs** | `atlas://catalog/databases/…` (600+ in packs) | No | **Exclude — internal data scheme** |
| **Knowledge content** | packs/concepts mentioning real products (e.g. *MongoDB Atlas*) | content | **Exclude — 3rd-party references** |
| **`atlas_self` benchmark id** | registry id for the self-scan | No | **Exclude — internal identifier** |
| **`atlas_recent_repos` etc.** | `localStorage` keys (`app.js`) | No | **Exclude — stored user data** |
| **`atlas_beta.js`, `showAboutAtlas()`** | asset filename, JS function/element ids | No | **Exclude — internal identifiers** |

## Migration method (safe by construction)

Replacement uses **word boundaries** so only standalone brand tokens change:

- `AtlasDesktop` → `SyronDesktop`
- `\bATLAS\b` → `SYRON`
- `\bAtlas\b` → `Syron`
- `\batlas\b` → `syron`

Because `_`, `:` and adjacent letters are word characters, this **cannot** touch
`atlas_knowledge`, `atlas_self`, `atlas_beta`, `atlas_recent_repos`,
`showAboutAtlas`, or `atlas://…` — every "do not rename" item is preserved
automatically. Applied only to a curated file set (UI + a short list of
user-facing code files + brand tests); `atlas_knowledge/`, `external_repos/`,
benchmark data, and historical phase reports are excluded.

## Excluded (intentional exceptions)

1. `jarvis_desktop/atlas_knowledge/**` — internal package name, `atlas://` URI
   scheme, and third-party knowledge content. Renaming would change data and
   behavior (forbidden).
2. `atlas_self` benchmark id and other internal identifiers.
3. `localStorage` keys (`atlas_recent_repos`, `atlas_onboarding_v2_done`, …) —
   stored user data; renaming would silently drop users' local state.
4. `external_repos/**` and vendored benchmark data — not ours.
5. Historical execution reports (`reports/phase1xx_*.md`) — describe past states
   when the product was named Atlas; preserved for historical accuracy.
6. Binary assets (favicons, app icons, raster logos, screenshots) — cannot be
   regenerated without design tooling; flagged for follow-up.
