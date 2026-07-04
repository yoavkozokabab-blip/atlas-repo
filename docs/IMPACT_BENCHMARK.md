# Atlas Change-Impact Benchmark (v1)

_Generated 2026-07-04 - fully automated, reproducible (`scripts/impact_benchmark.py`)._

## What is measured

For 100 real change-impact questions ("What breaks if I change `<file>`?") across 20 popular open-source repositories, Atlas's `atlas_what_breaks` MCP tool is scored against an **independent gold standard**: the set of files that statically import the changed module, resolved by a self-contained stdlib-`ast` import resolver that shares no code or data with Atlas's scanner.

- **Prediction** = `direct_impact` (the tool's direct blast-radius claim), test files excluded.
- **Gold** = independently resolved direct importers, test files excluded.
- **Latency** = wall-clock per question through the real MCP tool dispatch (scan time reported separately; scanning is a one-time step).

## Headline results

| Metric | Value |
|---|---|
| Questions scored | 100 |
| Answered (no refusal/error) | 100/100 |
| **Micro precision** | **1.00** |
| **Micro recall** | **0.93** |
| Micro F1 | 0.96 |
| Macro precision / recall | 1.00 / 0.94 |
| Recall incl. `affected_files` union | 0.94 |
| False positives (total files) | 0 |
| False negatives (total files) | 120 |
| False-reassurance questions* | 2/100 |
| Query latency median / p95 | 758 ms / 4239 ms |

\* A question counts as *false reassurance* when a subsystem containing a missed gold importer is simultaneously listed under `what_probably_wont_break`. This is the worst failure mode for a trust product, so it is tracked explicitly.

## Per-repository results

| Repo | Commit | Files | Scan (s) | Qs | Micro P | Micro R | FP | FN | Median ms |
|---|---|---|---|---|---|---|---|---|---|
| black | `d7587ce9f5` | 172 | 9.6 | 5 | 1.00 | 1.00 | 0 | 0 | 431 |
| celery | `2e150f8330` | 810 | 16.2 | 5 | 1.00 | 0.98 | 0 | 2 | 1244 |
| click | `16fc00e2f4` | 147 | 4.5 | 5 | 1.00 | 1.00 | 0 | 0 | 392 |
| django | `318a316a4c` | 6876 | 78.5 | 5 | 1.00 | 1.00 | 0 | 0 | 9282 |
| fastapi | `fdfd5091f1` | 2793 | 30.0 | 5 | 1.00 | 0.33 | 0 | 54 | 3706 |
| flask | `36e4a824f3` | 230 | 3.3 | 5 | 1.00 | 1.00 | 0 | 0 | 478 |
| httpx | `b5addb64f0` | 115 | 4.6 | 5 | 1.00 | 1.00 | 0 | 0 | 360 |
| jinja | `5ef70112a1` | 105 | 4.8 | 5 | 1.00 | 0.90 | 0 | 4 | 339 |
| langchain | `0501325e6c` | 2825 | 35.8 | 5 | 1.00 | 1.00 | 0 | 0 | 3981 |
| pydantic | `c9688f493b` | 721 | 16.1 | 5 | 1.00 | 0.97 | 0 | 2 | 1084 |
| pytest | `1aa747de62` | 624 | 10.1 | 5 | 1.00 | 1.00 | 0 | 0 | 956 |
| requests | `23953c0c87` | 125 | 3.2 | 5 | 1.00 | 1.00 | 0 | 0 | 368 |
| rich | `9d8f9a372c` | 531 | 5.6 | 5 | 1.00 | 0.72 | 0 | 37 | 760 |
| scrapy | `870803b7fb` | 605 | 12.8 | 5 | 1.00 | 1.00 | 0 | 0 | 994 |
| sqlalchemy | `d59159ca08` | 703 | 27.1 | 5 | 1.00 | 1.00 | 0 | 0 | 1246 |
| sqlmodel | `636e91f458` | 460 | 7.8 | 5 | 1.00 | 1.00 | 0 | 0 | 740 |
| starlette | `5174d4c835` | 124 | 4.8 | 5 | 1.00 | 1.00 | 0 | 0 | 390 |
| tornado | `3239945064` | 319 | 8.1 | 5 | 1.00 | 0.96 | 0 | 2 | 618 |
| typer | `73c8a41cc1` | 766 | 8.9 | 5 | 1.00 | 1.00 | 0 | 0 | 1067 |
| werkzeug | `1b00618e78` | 269 | 6.7 | 5 | 1.00 | 0.70 | 0 | 19 | 643 |

## Results by fan-in band

| Band | Qs | Micro P | Micro R | Notes |
|---|---|---|---|---|
| high | 40 | 1.00 | 0.93 | 16 question(s) exceed the 25-file output cap |
| medium | 33 | 1.00 | 0.92 |  |
| low | 27 | 1.00 | 0.97 |  |

## Failure analysis (largest misses)

- **fastapi::fastapi/templating.py** (gold 1, band low): P=0.00 R=0.00; missed e.g. `docs_src/templates/tutorial001_py310.py`
- **fastapi::fastapi/responses.py** (gold 45, band high): P=1.00 R=0.04; missed e.g. `docs_src/additional_responses/tutorial001_py310.py`, `docs_src/additional_responses/tutorial002_py310.py`, `docs_src/additional_responses/tutorial003_py310.py`
- **werkzeug::src/werkzeug/middleware/shared_data.py** (gold 8, band medium): P=1.00 R=0.12; missed e.g. `examples/coolmagic/application.py`, `examples/couchy/application.py`, `examples/cupoftee/application.py`
- **jinja::src/jinja2/loaders.py** (gold 5, band medium): P=1.00 R=0.40; missed e.g. `examples/basic/debugger.py`, `examples/basic/inheritance.py`, `examples/basic/test.py`
- **fastapi::fastapi/encoders.py** (gold 9, band medium): P=1.00 R=0.44; missed e.g. `docs_src/body_updates/tutorial001_py310.py`, `docs_src/body_updates/tutorial002_py310.py`, `docs_src/encoder/tutorial001_py310.py`
- **rich::rich/box.py** (gold 8, band medium): P=1.00 R=0.50; missed e.g. `examples/fullscreen.py`, `examples/print_calendar.py`, `examples/table_movie.py`
- **werkzeug::src/werkzeug/exceptions.py** (gold 26, band high): P=1.00 R=0.54; missed e.g. `examples/coolmagic/application.py`, `examples/couchy/application.py`, `examples/couchy/views.py`
- **rich::rich/console.py** (gold 75, band high): P=1.00 R=0.69; missed e.g. `benchmarks/benchmarks.py`, `examples/attrs.py`, `examples/columns.py`

### False-reassurance cases

- **tornado::tornado/ioloop.py**: subsystems ['maint'] contain missed importers but were listed as probably-won't-break.
- **tornado::tornado/gen.py**: subsystems ['maint'] contain missed importers but were listed as probably-won't-break.

## Interpretation

This suite was first run against the pre-fix engine (2026-07-04, "v1"), which scored **micro-P 0.67 / micro-R 0.32** with 264 false positives. The v1 run exposed five root causes, all fixed at the implementation level (not thresholds) and re-verified by this run:

1. **Silent truncation** - symbol-evidence merge overwrote `direct_impact` and cut it to 12 entries; the MCP layer capped at 25 with no total. Now: full direct list + `direct_impact_total`.
2. **Direction confusion** - files the target *imports* (call-graph callees) were reported as "what breaks" (verified: `click/utils` -> `_winconsole`). Now: forward dependencies never enter the impact lists.
3. **Layout blind spots** - module names were derived from repo-root paths, so absolute imports under `src/` and monorepo roots (`pytest` P 0.12/R 0.03, `langchain` P 0.17/R 0.06 in v1) never resolved. Now: multi-root module mapping (`pytest` and `langchain` both >0.9 recall).
4. **`from a.b import c` submodule edges** were never created (only the package `__init__`), and imports inside functions/`if TYPE_CHECKING:` blocks were invisible. Now: submodule edges + conditional imports tracked as impact-only `deferred_edges` (kept out of cycle/stats to avoid pathological blowup on lazy-import hubs).
5. **False reassurance** - "probably won't break" was computed against the display-capped list, so subsystems with importers beyond the cap were declared safe. Now: judged against the full impacted set.

**Remaining honest gaps:** residual false negatives are dominated by files outside Atlas's production scan scope (examples/, docs_src/, maint/ directories) - the gold deliberately counts them because they do break; both remaining false-reassurance cases (tornado `maint/`) are this scope mismatch, not resolution errors. p95 latency (~4 s) is the first, cache-cold question on django-scale repos.

## Methodology and threats to validity (read before quoting)

1. **Gold is static direct-import truth.** It is mechanical, reproducible, and independent of Atlas, but it is not runtime truth: dynamic imports, plugin registries, string-based dispatch and monkey-patching are invisible to both sides. A file can import a module and not break; a file can break without importing it. Direct static import is the best label that does not require executing 20 test suites.
2. **Transitive impact is not scored** (v1). An independent transitive gold would need its own graph closure, whose errors would contaminate labels. Atlas's `indirect_impact` is therefore reported but unscored.
3. **Python-only.** This is Atlas's strongest language; results do not generalize to JS/Go/etc.
4. **Output caps.** The MCP layer truncates `direct_impact` at 25 files; questions whose gold exceeds the cap have a structural recall ceiling. They are flagged in the band table.
5. **Resolver correctness** was spot-checked but the resolver is ~150 lines of stdlib `ast`; its bugs would distort labels for both metrics equally.
6. **No cherry-picking:** questions were selected mechanically by fan-in band from the resolver's reverse index before any Atlas run; all runs are reported.

## Reproduce

```powershell
py -3 scripts/impact_benchmark.py gen    --out benchmarks/impact/suite_v1.json
py -3 scripts/impact_benchmark.py run    --suite benchmarks/impact/suite_v1.json --out benchmarks/impact/results_v1.json
py -3 scripts/impact_benchmark.py report --suite benchmarks/impact/suite_v1.json --results benchmarks/impact/results_v1.json --out docs/IMPACT_BENCHMARK.md
```

Repository pins (commit SHAs) are recorded in the suite file. Repos without a `.git` directory are local snapshots and marked `unpinned-snapshot`.
