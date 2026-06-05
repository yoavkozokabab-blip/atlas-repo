# Phase 157 — Installer, Trust, and User-Experience Hardening

Date: 2026-06-05

Scope: installer reliability, SmartScreen guidance, trust signals, beginner/advanced
output, scan-reliability reporting, and support UX. **No changes** to intelligence,
the semantic resolver, benchmarks, the marketing site, or billing.

Success criteria: a stranger can install Atlas and trust its output without help.

---

## 1. Installer reliability + self-test

- New **installer self-test** (`install_support.installer_self_test`) verifies:
  - **Atlas.exe / launcher** exists (frozen vs. source mode),
  - required assets/data directories are present and writable,
  - **Start menu / desktop shortcuts** exist (Windows; optional in source mode),
  - **browser auto-open** capability (a default browser is registered).
  Optional checks (shortcuts in source mode, browser) never fail the overall result.
- Exposed at `GET /api/system/self-test` (stdlib + FastAPI mirror) and `api.installer_self_test()`.
- `run_atlas.py --self-test` runs it, writes `self_test.json` to the data dir, and returns
  a non-zero exit code on critical failure (usable by installer scripts/CI).
- The launcher now runs the self-test on every start and logs the result locally.
- `installer_build.ps1` gained **`Test-StagedInstaller`** — a pre-compile self-test that
  fails the build if the staged `Atlas.exe`, Start-menu/desktop shortcut declarations,
  beta install notes, or `support.html` are missing.
- **Browser auto-open failures** are now handled explicitly in `server.run`: logged
  locally, and (in source mode) the URL is printed so the user can open it manually.
- Shortcut / registry permission issues surface as plain-language self-test warnings
  rather than silent failures, with hints to relaunch from the install folder or re-run setup.

## 2. SmartScreen guidance

- First-launch detection (localStorage) shows a one-time modal:
  **"Atlas is an unsigned beta application."** It explains *why* Windows shows the
  SmartScreen warning (no code-signing certificate yet) and *how to continue safely*
  (downloaded from official source → **More info → Run anyway**; analysis stays local).
- Same guidance added to the installer's `install_notes.txt` (shown before install)
  and to the Quickstart page.

## 3. Trust improvements

Every **Change Plan**, **Investigation**, and **What breaks?** now renders a consistent
**"Why Atlas believes this"** block (`atlas_trust.js` → `trustBlock(kind)`):

- **Evidence** — files, symbols, and references, derived from the existing plan/impact
  data (`files_to_inspect_first`, repository-evidence `matching_symbols`, importers, etc.).
- **Confidence** — normalized to **high / medium / low** with a colored badge.
- **Reason** — a plain-English sentence explaining how Atlas reached the result and why
  the confidence is what it is (impact reuses the existing architectural summary).

The engine already produced confidence + evidence; Phase 157 surfaces it uniformly.
Tests confirm `plan_change` and `change_impact_simulation` expose `confidence` and
grounded evidence.

## 4. Output simplification (Beginner / Advanced)

- A **Beginner / Advanced** toggle in the top bar, persisted in localStorage,
  toggles `body.mode-beginner` / `body.mode-advanced`.
- **Beginner** shows plain English: the confidence badge, the reason, and the core
  result. **Advanced** additionally reveals `.advanced-only` blocks — raw plan markdown,
  prompt previews, domain-knowledge panels, deep impact details, and the full evidence
  lists (files/symbols/references).
- Default is Beginner (set on `<body>` to avoid a flash before JS runs).

## 5. Scan reliability

- Degraded-scan detection, the failure taxonomy, and the safe single retry
  (`reliability.classify_scan`, zero-module retry) remain in place and are now
  **surfaced in health reporting**: `beta_diagnostics` and `beta_system_health`
  include the `reliability` assessment (category, severity, signals, retried/recovered).
- The support page renders the self-test and the existing scan-health summary.

## 6. Support

- One-click **Copy diagnostics** and **Open/Create support bundle** (saved to the
  browser's **Downloads** folder — the location is now stated explicitly in the UI and
  in the post-action message).
- New **Installer self-test** card on the Support page with a **Re-run self-test** button.
- Report Issue continues to save **locally only** (carried over from Phase 155).

---

## Files changed

Backend / launcher:
- `jarvis_desktop/install_support.py` — `installer_self_test` + executable/shortcut/browser checks.
- `jarvis_desktop/api.py` — `installer_self_test()` wrapper; `reliability` in diagnostics + health.
- `jarvis_desktop/server.py` — `/api/system/self-test` route (both servers); browser-open failure logging.
- `run_atlas.py` — `--self-test` CLI, startup self-test logging.
- `packaging/installer/installer_build.ps1` — `Test-StagedInstaller` build self-test.
- `packaging/installer/install_notes.txt` — SmartScreen guidance.

UI:
- `jarvis_desktop/static/atlas_trust.js` (new) — trust block, beginner/advanced mode, SmartScreen notice.
- `jarvis_desktop/static/index.html` — mode toggle, default beginner mode, script include.
- `jarvis_desktop/static/app.js` — `trustBlock` in all three workflows; advanced-only tagging.
- `jarvis_desktop/static/styles.css` — trust block, confidence badges, mode toggle, visibility rules.
- `jarvis_desktop/static/support.html` / `support.js` — self-test card, Downloads-location wording.
- `jarvis_desktop/static/quickstart.html` — SmartScreen note.

Tests / report:
- `jarvis_desktop/tests/test_phase157_installer_hardening.py` (10 tests)
- `jarvis_desktop/tests/test_phase157_trust_signals.py` (7 tests)
- `jarvis_desktop/tests/test_phase157_beginner_mode.py` (6 tests)
- `jarvis_desktop/tests/test_phase107_desktop_api.py` — route count 46 → 47 (added self-test route).
- `reports/phase157_installer_and_trust_hardening.md` (this file).

---

## Verification

```
py -3 run_atlas.py --self-test                 # READY (source mode)
py -3 -m pytest jarvis_desktop/tests/test_phase157_installer_hardening.py \
                jarvis_desktop/tests/test_phase157_trust_signals.py \
                jarvis_desktop/tests/test_phase157_beginner_mode.py -q   # 23 passed
py -3 -m pytest jarvis_desktop/tests/test_phase107_desktop_api.py -q     # passes
```

Pre-existing unrelated failure: `test_phase122_product_hardening.test_product_version_atlas_hardening_lineage`
(expects `phase12` in `PRODUCT_VERSION`, currently `phase146b-...`) — out of scope and untouched.

---

## Remaining friction

- **Code signing.** SmartScreen guidance reduces confusion, but a signed installer
  (EV/standard certificate) is still required to remove the warning entirely for a public beta.
- **Native shortcut verification.** The self-test checks well-known shortcut paths; a
  custom install directory with relocated shortcuts may report a benign warning.
- **Browser detection** is best-effort; headless/locked-down environments still require
  opening `http://127.0.0.1:8777/` manually (the URL is now logged and printed).

## Beta readiness verdict

**Ready for self-serve supervised beta.** Installs verify themselves, first-launch
SmartScreen confusion is pre-empted, every result explains its evidence/confidence/reason,
and beginners get plain-English output with a one-click path to full detail. The single
remaining gate for a fully unsupervised public beta is installer code-signing.
