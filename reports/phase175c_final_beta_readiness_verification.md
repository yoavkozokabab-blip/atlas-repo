# Phase 175C Final Beta Readiness Verification

Date: 2026-06-06
Scope: verification only. No Atlas production code was modified.

## Executive Verdict

NO-GO for 5 supervised beta users.

NO-GO for 20 supervised beta users.

NO-GO for public self-serve beta.

Reason: the main first-user and repository workflows are usable, but two beta blockers remain:

1. Port fallback does not work for the reproduced occupied-port case.
2. Trust-integrity attack A10 still fails because support bundles preserve raw secret key patterns such as `api_key=` and `token=`, even though the values are redacted.

Additional concern: source-mode startup failure can print a raw traceback in a redirected CP1252 console before reaching the startup failure page.

## Pass / Fail Summary

| Area | Result | Evidence |
| --- | --- | --- |
| Install / launch | FAIL | Normal temp-backed launch works, browser self-test passes, startup failure page works under UTF-8, but occupied-port fallback fails with `PermissionError: [WinError 10013]`. |
| First-user path | PASS | Sample repo -> Change Plan -> Copy for Claude completed in 0.455s, export ~294 tokens. |
| Real repo path | PASS | Small and medium synthetic repos scanned; Change Plan, Impact, Investigation, and Claude/Cursor/Codex exports all returned `ok=true`. |
| Trust integrity | FAIL | 9/10 attacks passed; A10 support bundle redaction still failed. |
| Billing honesty | PASS | `billing_enabled=false`, `payments_active=false`, pricing copy says no checkout/payment collection, usage tracking populated. |
| Feedback / support | FAIL | Local feedback and configured remote feedback behaved honestly; support bundle still failed strict redaction pattern check. |
| User-facing polish | FAIL | Main app is Atlas-branded, but static assets still contain JARVIS references in JS/console/demo text and source-mode startup can emit a raw traceback. |

## Install / Launch

Checks run:

- Start `py -3 run_atlas.py --host 127.0.0.1 --port 8811 --no-browser` with temp-backed `JARVIS_DESKTOP_DATA`.
- Request `http://127.0.0.1:8811/api/health`.
- Request `http://127.0.0.1:8811/`.
- Run installer browser self-test.
- Occupy requested port and start Atlas on that port.
- Force startup failure with `JARVIS_DESKTOP_DATA` pointing to a file and request `startup-error.html`.

Results:

| Check | Result | Evidence |
| --- | --- | --- |
| Atlas starts | PASS | `/api/health` returned `ok=true` with temp data dir. |
| Home page serves | PASS | `/` returned ATLAS page. |
| Browser availability | PASS | Installer self-test reported `Browser auto-open: ok=true`. |
| Browser visible sanity | PASS | In-app browser loaded `http://127.0.0.1:8835/`; title was `ATLAS - Repository Intelligence Platform`; visible copy included ATLAS, Load Sample Repository, Change Plan, and Claude export language. |
| Startup failure page | PASS | `startup-error.html` returned "Startup check failed"; `/api/system/startup-status` returned `ready=false`. |
| Port fallback | FAIL | Occupied port repro returned `PermissionError: [WinError 10013]`; no fallback port answered. |

Port fallback reproduction:

```text
1. Bind a listener on 127.0.0.1:8822.
2. Run:
   py -3 run_atlas.py --host 127.0.0.1 --port 8822 --no-browser
3. Probe ports 8822-8831.
4. No fallback port responds.
5. stderr shows PermissionError [WinError 10013].
```

Captured error:

```text
PermissionError: [WinError 10013] An attempt was made to access a socket in a way forbidden by its access permissions
```

Startup failure caveat:

An earlier source-mode startup failure with redirected CP1252 output crashed while printing a Unicode cross mark:

```text
UnicodeEncodeError: 'charmap' codec can't encode character '\u2717'
```

That means the support/startup failure path is not fully traceback-proof in source mode under non-UTF-8 redirected consoles.

## First-User Path

Workflow:

```text
Welcome/Home -> Load Sample Repository -> Change Plan -> Copy for Claude
```

API verification:

| Step | Result |
| --- | --- |
| Load sample repo | PASS, `demo_ok=true`, `module_count=5` |
| Generate Change Plan | PASS, `status=ok` |
| Copy for Claude | PASS, `status=ok`, estimated tokens `294` |
| Time to value | PASS, `0.455s` |

This path is comfortably under the 5-minute target.

## Real Repo Path

Two non-demo synthetic repositories were scanned: a small Python app and a medium multi-module Python service.

| Repo | Files | Modules | Edges | Scan time | Change Plan | Impact | Investigation | Exports |
| --- | ---: | ---: | ---: | ---: | --- | --- | --- | --- |
| Small | 4 | 3 | 2 | 0.053s | PASS | PASS | PASS | Claude/Cursor/Codex PASS |
| Medium | 17 | 16 | 14 | 0.081s | PASS | PASS | PASS | Claude/Cursor/Codex PASS |

Export token estimates:

| Repo | Claude | Cursor | Codex |
| --- | ---: | ---: | ---: |
| Small | 252 | 242 | 246 |
| Medium | 354 | 344 | 347 |

## Trust Integrity

The exact Phase 174C attack set was rerun.

Result: 9/10 PASS.

| Attack | Result | Actual |
| --- | --- | --- |
| A1 repo switch without rescan | PASS | Build/Investigation/Impact/Export returned `requires_rescan`; no repo A leak. |
| A2 edit scanned file export | PASS | Export/session returned `stale_outside_plan`. |
| A3 git HEAD changed export | PASS | Export returned `stale_git_head_changed`. |
| A4 late file outside 2500 cap | PASS | Export returned `stale_outside_plan`. |
| A5 tampered memory JSON reload | PASS | Poison marker not visible. |
| A6 forced memory write failure | PASS | `memory_persistence_status=failed`; no persistent memory claim. |
| A7 unsupported Go/shallow graph | PASS | Build and Investigation returned `insufficient_evidence`; no helper-file fake success. |
| A8 concurrent scan/select/export | PASS | 12 iterations, `leak_count=0`. |
| A9 export replay after repo change | PASS | New export blocked; old packet had `scan_id`, `scan_signature`, `replay_warning`. |
| A10 support bundle redaction | FAIL | Values redacted, but raw key patterns remain. |

A10 exact reproduction:

```text
1. Scan support repo.
2. Write launcher.log with:
   api_key=LEAK_ME
   token=TOKEN_LEAK_ME
   Authorization: Bearer BEARER_LEAK_ME
3. Run api.export_support_bundle().
4. Decode support zip.
5. Inspect logs/launcher.log.
```

Actual support bundle excerpt:

```text
Failure at [path-redacted] with [secret-redacted] and api_key=[REDACTED] and token=[REDACTED] and Authorization: [REDACTED] [REDACTED]
```

Failure reason:

`raw_key_pattern_leak=true` because raw labels/patterns such as `api_key=` and `token=` remain visible in the support bundle. The secret values themselves are redacted.

## Billing Honesty

Result: PASS.

Evidence:

- `/api/health`: `billing_enabled=false`, `payments_active=false`.
- Pricing API returned: "Billing is not enabled in beta - no checkout, no payment collection."
- Static pricing copy says: "No checkout, no fake payments, no subscription activation."
- Usage tracking populated from scans/workflows:
  - scans used: 3
  - exports used: 7
  - repositories used: 3
  - build plans: 3
  - investigations: 2
  - impacts: 2
  - token-equivalent total: 5887
  - Atlas compute units: 6.92
- Admin usage summary returned `ok=true` with usage data.

No real checkout or payment collection was observed.

## Feedback / Support

Result: FAIL because support-bundle redaction is still incomplete under the strict Phase 174C attack definition.

What passed:

- Product config with no `ATLAS_FEEDBACK_URL`: `feedback_url_configured=false`.
- Local feedback returned `destination=local`, `remote_sent=false`.
- Configured local feedback URL was used only when `ATLAS_FEEDBACK_URL` was set.
- Remote feedback payload was sent once to the configured URL.
- Remote feedback redacted token values.
- Support email `support@useatlas.dev` is visible in support UI.
- Support bundle includes trust-integrity status.
- Support bundle redacts absolute paths and secret values.

What failed:

- Support bundle still preserves raw key labels/patterns in logs, including `api_key=` and `token=`.

## User-Facing Polish

Result: FAIL.

What passed:

- Main app browser-visible Home page is Atlas-branded.
- API product config exposes `version=0.1.0-beta`, not an internal phase version.
- Unknown API route did not return a stack trace.
- Legacy bug investigation did not return `ok=true` with `mock=true`.

What failed or remains risky:

- Static assets still contain JARVIS references:
  - `jarvis_desktop/static/studio.js` has user-visible demo text: `JARVIS shows exactly what a change touches...`
  - JS globals and console messages still use `JARVIS_UNIVERSE` / `[JARVIS graph]`.
  - CSS and JS comments still reference JARVIS and internal phases. Comments are not visible in normal UI, but they are still shipped static assets.
- Source-mode startup failure can emit a raw Python traceback in a redirected CP1252 console before the startup page is reached.

## Final Verdicts

| Audience | Verdict | Reason |
| --- | --- | --- |
| 5 supervised beta users | NO-GO | Trust attack A10 still fails; port fallback fails; source-mode startup failure can emit traceback. |
| 20 supervised beta users | NO-GO | Same blockers become more likely at larger sample size. |
| Public self-serve beta | NO-GO | Installation/launch fallback and support-bundle trust are not clean enough for self-serve users. |

## Required Fixes Before GO

1. Treat `PermissionError [WinError 10013]` during bind as an occupied/blocked port fallback case, or otherwise recover cleanly.
2. Make startup failure printing safe under non-UTF-8 redirected consoles, or avoid console Unicode before opening the failure page.
3. Decide the strict support redaction contract:
   - If raw labels like `api_key=` are forbidden, redact key labels too.
   - If labels are allowed, update the trust attack definition explicitly.
4. Remove or rename remaining user-facing JARVIS demo strings in shipped static assets.

## Commit Scope

Report-only verification. No Atlas code was modified.
