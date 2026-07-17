# Installed-Candidate Acceptance Checklist — v1.0.5

For the installed candidate Codex delivers. **No item may be marked PASS from
source inspection, API responses alone, or config files.** Evidence = what a user
sees. Installed PASS is *not* claimed by this document.

Environment per run: fresh isolated install dir + fresh isolated data root
(`ATLAS_DESKTOP_DATA` override), port >8799 (never 8777), canonical
`%USERPROFILE%\.atlas_desktop` untouched (fingerprint before/after).

| # | Check | Procedure | PASS evidence required |
|---|---|---|---|
| 1 | Onboarding | Fresh install, first launch | Screenshot of step 1 + demo step; Back/Next/Skip work; Esc skips; Settings → "Reopen welcome tour" reopens |
| 2 | Home CTA | Load any repo | Screenshot: "Analyze impact" is the single primary header action |
| 3 | Guest mode | Click "Continue without an account" | Full workbench usable; no signup wall reappears; screenshot |
| 4 | Medium demo | Load demo | Title "Atlas Demo — Medium" in sidebar+topbar; 18 files; screenshot |
| 5 | Ask | Type question, run | Visible evidence-backed answer panel; screenshot |
| 6 | Impact success | `services/billing.py` → Analyze | Visible result: target, 8 direct dependents, risk+confidence; screenshot |
| 7 | Impact not found | `no/such_file.py` | Distinct "Target not found in this repository" panel (not generic error); screenshot |
| 8 | Impact no dependents | A leaf file (e.g. `workers/job_1.py`) | Visible result with explicit "No indexed dependents found."; screenshot |
| 9 | Debug | Symptom text → run | Visible ranked hypotheses with evidence; screenshot |
| 10 | Plan | Change brief → run | Visible ordered plan with file tiers; screenshot |
| 11 | Agents disconnected | Before any client connects | All cards "Not connected"; configured cards show restart hint; "Connected clients: 0"; screenshot |
| 12 | Cursor connected | Configure + fully restart Cursor | Card flips to **Connected** only after real handshake; screenshot; run 4 MCP tools grounded in loaded repo |
| 13 | Cursor exit/reconnect | Quit Cursor entirely (verify no process), relaunch | Status returns to Not connected while down (or shows honest last-seen), reconnects cleanly; no reconnect loop |
| 14 | Free-limit messages | Exhaust the configured allowance (or set test allowance) | Inline message matches FREE_PLAN_UX_V105.md verbatim incl. reset time; demo exempt; screenshot |
| 15 | Analytics opt-out | Settings toggle off | Confirmation copy per ANALYTICS_DISCLOSURE doc; no further analytics requests in network log |
| 16 | Analytics offline | Block analytics endpoint | "unavailable" state, no error banner, features unaffected |
| 17 | Pro coming soon | Pricing/limit surfaces | No actionable payment control anywhere; screenshot |
| 18 | No checkout | Attempt every plan-related CTA | None routes to checkout or external payment |
| 19 | Accessibility | Keyboard-only pass of onboarding + one workflow; zoom 200% | Focus visible throughout; all controls reachable; no critical control lost at 200% |
| 20 | Responsive | 1280×720, 1440×900, 1920×1080, narrow (~1000px), display scaling 125%/150% | No horizontal overflow; primary actions visible; screenshots at each |
| 21 | Screenshots | Full manifest | Every FINAL_SCREENSHOT_MANIFEST.md item captured and clean |

Also record: installer SHA-256 + installed exe SHA-256 (must match the published
candidate), footer reads "Atlas 1.0.5", and zero requests to port 8777 during the
whole session.
