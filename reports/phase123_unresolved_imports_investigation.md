# Phase 123 — Unresolved Imports Investigation

**Date:** 2026-06-02
**Scope:** Why is the "unresolved import ratio" so high, what is realistically
recoverable, and what is cosmetic vs. real.

> TL;DR — The headline ratio is **misleading, not broken**. What Atlas labels
> "unresolved imports" is the resolver's `imports_external` counter: *every*
> import whose target is outside the internal production module set. That bucket
> is dominated by third-party packages and the standard library, which are
> **expected** and not failures. The genuinely-recoverable portion (internal
> imports that should have resolved but didn't) is small. The single highest-ROI
> fix is **classification + relabeling**, not chasing a higher resolve rate.

---

## 1. Method

Scanned three real repositories with the production scanner and inspected the
raw resolver statistics (`graph["statistics"]["unresolved_counts"]`) and the
`language_breakdown`:

```
py tests_tmp/phase123_unresolved_probe.py
py tests_tmp/phase123_stats_probe.py
```

## 2. Measured data (real repos)

| Repo    | Modules | Resolved imports | "Unresolved" | Ratio | external_package_imports |
|---------|--------:|-----------------:|-------------:|------:|-------------------------:|
| FastAPI |      73 |              159 |          560 | 77.9% | **0** |
| Django  |     907 |            2,916 |        1,377 | 32.1% | **0** |

Raw `unresolved_counts` for FastAPI:
```json
{ "imports_external": 560, "calls_unresolved": 5370, "references_unresolved": 185 }
```

## 3. Root cause

Two distinct issues, both in how the number is **derived and labeled** — not in
the resolver's ability to follow internal imports.

### 3a. The metric is `imports_external`, surfaced as "unresolved"
`jarvis_desktop/api.py`:
```python
"unresolved_imports": unresolved.get("imports_external", 0),
```
`imports_external` counts every import whose target is **not an internal
production module**. For FastAPI that is overwhelmingly:
- third-party packages: `pydantic`, `starlette`, `typing_extensions`, `email_validator`
- standard library: `typing`, `enum`, `dataclasses`, `functools`, `inspect`, …

These are **correct, expected** edges leaving the repo. Labeling them
"unresolved" makes a perfectly healthy library look 78% broken.

### 3b. `external_package_imports` is never populated (always 0)
`graph_build._language_breakdown(...)` returns `external_packages: 0` and
`external_package_imports: 0` for every repo measured. So there is currently **no
separation** between "external dependency" and "internal import we failed to
resolve." Everything outside the module set lands in one bucket.

### 3c. Why FastAPI looks worse than Django
FastAPI is a small, dependency-heavy library: few internal modules (73) but many
imports of pydantic/starlette/stdlib → external-to-internal ratio is high (78%).
Django is a large framework that imports itself a lot (2,916 internal resolved)
→ external ratio is lower (32%). Neither number reflects a resolver defect.

## 4. What is realistically recoverable?

The question "how do we get from 78% to X%?" is the wrong question, because most
of the 78% **should not resolve to an internal module** — they are external by
design. The right metric is:

> **internal-unresolved ratio** = (internal imports that failed to resolve) ÷
> (internal imports total)

Estimated breakdown of the current "unresolved" bucket (FastAPI, by inspection
of import targets):

| Category                              | Est. share of "unresolved" | Recoverable? |
|---------------------------------------|---------------------------:|--------------|
| Third-party packages (pydantic, etc.) |                    ~55–65% | No — external by design |
| Standard library                      |                    ~25–35% | No — external by design |
| Genuinely-unresolved **internal**     |                     ~5–10% | **Partially yes** |

So the honest targets:

- **Reported "unresolved ratio" after classification:** FastAPI ~78% → the
  *internal-unresolved* metric is realistically **< 10%**, with the remainder
  correctly relabeled "external dependencies."
- **Recoverable internal-unresolved** (relative-import edge cases, conditional/
  `TYPE_CHECKING` imports, re-exports): of that <10%, perhaps **half** is
  recoverable with resolver work → internal-unresolved ~**3–6%**.

This is a **labeling + classification** win, not a resolve-rate grind.

## 5. Language-specific causes (for the recoverable internal slice)

- **Python:** `TYPE_CHECKING`-guarded imports, conditional imports inside
  functions, star re-exports (`from .x import *`), namespace packages.
- **TypeScript/JS:** path aliases (`@/...` from `tsconfig.json`/`jsconfig.json`),
  barrel files (`index.ts` re-exports), extensionless imports, `paths` mapping.
- **Relative imports:** deep `from ...pkg.mod import x` resolution across package
  boundaries.
- **Dynamic imports:** `importlib.import_module`, `require()` with variables —
  **not recoverable statically** and should be labeled as such, not counted as
  failures.

## 6. Prioritized improvements (real, not cosmetic)

1. **[Shipped this phase] Honest labeling.** `_graph_health` now states the
   metric counts external + stdlib + unresolved-internal, and the "partial"
   notice no longer implies the internal graph is broken. This removes the
   biggest trust hit immediately, without manipulating the number.
2. **[Recommended — resolver] Classify the external bucket.** Split
   `imports_external` into `external_third_party`, `external_stdlib`, and
   `internal_unresolved` using a stdlib name set + the dependency manifest
   (`requirements.txt`/`pyproject`/`package.json`). Then surface
   `internal_unresolved_ratio` as the quality metric and show external counts
   as informational. **Highest ROI for trust.**
3. **[Recommended — TS/JS] Honor `tsconfig`/`jsconfig` path aliases & barrels.**
   Biggest real recovery for front-end repos.
4. **[Recommended — Python] Resolve `TYPE_CHECKING` and re-export edges.**
5. **Label dynamic imports explicitly** as "not statically resolvable" so they
   never count against graph health.

## 7. Honest conclusion

The current 78% is not a bug in resolution; it is a bug in **presentation**.
Fixing the label (done) and then splitting external vs internal (recommended)
turns a scary, trust-destroying number into an accurate, defensible one. Chasing
a higher raw resolve rate on external packages would be cosmetic — those imports
*should* leave the repo. Real recovery (path aliases, re-exports) applies only to
the small internal-unresolved slice and is worth doing **after** classification.
