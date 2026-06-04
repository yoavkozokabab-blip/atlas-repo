# Phase 155 — Zero-Friction First User Experience

Date: 2026-06-05

Scope: first-use UX only. Changes are limited to installation/launch friction,
the first-run flow, the export-to-AI workflow, and product clarity. **No changes**
were made to the semantic resolver, knowledge engine, evidence engine, impact
algorithms, billing, benchmarks, or the marketing website.

Success criteria: a new developer can go from opening Atlas to copying a useful
prompt into Claude / Cursor / Codex in **under 5 minutes** without help.

---

## Goal

Make Atlas easy enough for a new developer to use without explanation:

> Install → open → browser opens → Load Sample (or Scan) → Change Plan →
> Send to AI → know what to do next.

---

## Before / after flow

| Step | Before | After |
|------|--------|-------|
| Launch | Console-less Atlas.exe; on failure could surface a raw error | Clean loading splash; on failure opens **Support** with plain-language message, **Copy diagnostics**, **Open support bundle** — never a raw traceback |
| First screen | 3 primary buttons + a wall of "explore by task" cards, scope settings, recent list, diagnostics in the top bar | **Three** clear actions: **Load Sample Repository** (primary), **Scan My Repository** (secondary), **Open Quickstart** (tertiary). Advanced options, diagnostics, support, and "explore by task" are collapsed/de-emphasized |
| Sample load | Auto-jumped to Build Plan ~0.9s after scan; success screen barely seen | Lands on a clear success screen: **"Atlas understood the sample repository."** with files indexed, modules, dependency edges, and a primary CTA **"Generate your first Change Plan"** (no fast auto-jump) |
| Scan own repo | Path box + terse "skip node_modules" hint | Explicit **✓ Recommended / ✗ Avoid** guidance, plus a **broad-folder warning** modal (node_modules, multiple sub-projects, huge file count, drive root, Desktop/Downloads, external_repos) offering **Continue anyway** or **Choose a smaller folder** |
| After a plan | Small "Export implementation prompts" copy row with terse buttons | Prominent **"Send this to your AI coding tool"** panel on Change Plan / Investigation / What breaks?, with **Copy for Claude / Cursor / Codex** + **Download Markdown**, and the next step: *"Paste this into Claude, Cursor, or Codex and ask it to implement the plan."* |
| First success | (none) | **"You're ready."** recognition card with Copy to Claude/Cursor/Codex + "Try on your own repository" |
| Empty pages | Mixed ("Build Plan needs a scan", blank panels) | Every locked/empty page says **"Scan a repository first."** with one **Scan Repository** button |
| Vocabulary | Build Plan, Impact, Repository Map, Export, Graph health, Unresolved imports | Change Plan, What breaks?, Codebase Map, Send to AI — technical detail preserved in expandable sections |
| Report Issue | Implied submission | Clearly **saved locally** ("Saved on this device only", "Save locally"); nothing uploaded unless a support URL is configured |

---

## Screens / files changed

UI (static, no intelligence):
- `jarvis_desktop/static/index.html` — three-action home, jargon rename, boot splash,
  Help menu, folder guidance, collapsed advanced scope, standardized empty states,
  scan-success recognition + CTA, "You're ready" mount.
- `jarvis_desktop/static/atlas_zero_friction.js` (new) — boot-splash teardown,
  **Send-to-AI panel**, safe-to-implement prompt builders for Change Plan /
  Investigation / What breaks?, "You're ready" recognition, broad-folder modal.
- `jarvis_desktop/static/app.js` — wired Send-to-AI panel into all three workflows,
  dynamic Copy-for-target label, standardized empty states, scan-success title,
  broad-folder gate in `scanFlow`.
- `jarvis_desktop/static/atlas_polish.js` — removed the too-fast post-sample auto-jump.
- `jarvis_desktop/static/styles.css` — boot splash, help menu, folder guidance,
  Send-to-AI panel, ready-state styles.
- `jarvis_desktop/static/quickstart.html` (new) — the 5-minute path, folder guidance,
  vocabulary, install notes.
- `jarvis_desktop/static/support.html` / `support.js` — install notes, "Copy
  diagnostics" / "Open support bundle" wording, saved-locally reassurance.

Launcher / installer (friction only):
- `run_atlas.py` — documented install modes (Windows beta, no Python with installer,
  source mode Python 3.10+); reaffirms support fallback, no raw traceback.
- `packaging/installer/Atlas.iss` + `install_notes.txt` (new) — beta install notes shown
  before install; `AppComments` clarifying "no Python required".
- `installer/README.md` — install notes + under-5-minute first-run path.

Backend (UX helper only, additive):
- `jarvis_desktop/api.py` — `broad_folder_warnings(...)` pure helper; `validate_repository_path`
  now returns a `broad_warnings` field. No engine logic changed.

Tests / report:
- `jarvis_desktop/tests/test_phase155_first_user_experience.py` (new, 20 tests, all pass).
- `jarvis_desktop/tests/test_phase122_product_hardening.py` — nav-label assertions updated
  to the de-jargoned labels (the rename is the Phase 155 directive).
- `reports/phase155_zero_friction_first_user_experience.md` (this file).

---

## Verification

```
py -3 -m pytest jarvis_desktop/tests/test_phase155_first_user_experience.py -v   # 20 passed
py -3 -m pytest jarvis_desktop/tests/test_phase122_product_hardening.py \
                jarvis_desktop/tests/test_phase146_beta_polish.py \
                jarvis_desktop/tests/test_phase124_repository_map_visual.py -q
```

The Send-to-AI prompts are built entirely from existing plan data (repository
context, files to inspect, implementation order, what may break, tests, rollback)
and append an explicit **"How to work safely"** section (implement in order, do not
break public interfaces without updating importers, run the listed tests, keep
changes reversible, trust the code over the plan).

---

## Remaining friction

- **SmartScreen / unsigned installer.** First-launch Windows SmartScreen warning still
  applies until the build is code-signed (tracked from Phase 152).
- **Native loading splash gap.** The clean loading screen is in-app; the brief moment
  between process start and the browser opening is still OS-default. A small native
  splash could close it but adds packaging weight.
- **Scan time on large own-repos.** The broad-folder warning mitigates accidental
  whole-drive scans, but very large monorepos still benefit from a narrower scan scope.
- **Prompt verbs.** Send-to-AI prompts now invite safe implementation, while the
  underlying planning engine intentionally remains "planning only"; the two are
  reconciled in the client prompt wrapper rather than in the engine.

---

## Beta readiness verdict

**Ready for a supervised external beta.** The end-to-end happy path — open →
Load Sample → "Atlas understood the sample repository" → Generate your first
Change Plan → Copy for Claude/Cursor/Codex → "You're ready." — is achievable in
well under 5 minutes with no explanation, no terminal, and no Python (installer
mode). Failure paths route to a friendly Support page instead of a traceback, and
every empty state guides the user to scan. The main outstanding item for a *public*
beta is installer code-signing.
