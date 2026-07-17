# Claude UX Merge Audit — v1.0.5 Integration

Audited commit: `526519c715e6f819cb14e88e5f1eddb72c5c345f` (launch/atlas-v105-final-integration)
Original UX commits: `c46b409c` (pass 1), `57137ebc` (pass 2) — cherry-picked into the
integration branch as `004fab5a` / `fb33da96`.
Method: file diffs, behavioral-marker greps, my regression test suites run at the
integration commit, and a live source-run audit (headless Chrome via CDP, guest →
demo → all screens → all workflows).

## Per-area verdicts

| Area | Verdict | Evidence |
|---|---|---|
| Four-step onboarding (progress, Back/Next/Skip) | **Preserved correctly** | Markers in app.js/index.html; live run: step 1 + demo step render, stepper advances |
| Escape closes tour | **Preserved correctly** | Live run: `esc-closed: true` |
| Reopen from Settings | **Preserved correctly** | "Reopen welcome tour" present in index.html |
| Home primary "Analyze impact" CTA | **Preserved correctly** | index.html: sole `btn primary` in `repo-command-actions` |
| Connected vs Configured semantics | **Changed intentionally by Codex — improved** | `agentVerificationState` now returns a real `"connected"` state from live backend connection tracking (`data.connected` / `connections.clients[key].connected`) instead of my `last_handshake` heuristic. Labels preserved: "Connected"/"Not connected" primary, "Configuration: Installed", "MCP configuration installed. Restart {client} to connect." Home chip shows "No agent configured" until truly connected. |
| Impact states (loading / not-found / no-dependents / failure / success) | **Preserved correctly** | Live run: success renders visible result; target-not-found state renders; loading/failed classes present. No-dependents wording verified in source + tests; visual proof deferred to installed acceptance. |
| Ask / Debug / Plan differentiation | **Preserved correctly** | Distinct placeholders/examples/empty states; live run: all three complete with visible results |
| A11y labels / live regions | **Preserved correctly** | Live audit: 0 unnamed buttons, 0 unlabeled inputs, 10 aria-live regions |
| Reduced motion | **Preserved correctly** | `prefers-reduced-motion` in all stylesheets incl. ui-polish-v105.css (byte-identical) |
| Responsive fixes | **Preserved correctly** | 22-route web audit: zero horizontal overflow at 375–1920px; download CTA visible everywhere |
| Website hero (truthful Impact-led) | **Preserved correctly** | HeroCine.tsx: "Know what may break / before the code changes." |
| Windows / unsigned-installer disclosures | **Preserved correctly** | /download intro + SmartScreen warning present |
| Pro coming soon / no live checkout | **Preserved correctly** | Pricing gated on `proCheckoutReady()`; page audit found zero live-checkout copy; `_config.ts` notes paid plans suspended |
| Analytics event contract doc | **Preserved correctly** | `docs/analytics/ATLAS_ANALYTICS_EVENT_CONTRACT.md` byte-identical |

## Accidental regressions found (for Codex to fix — no source changes made by me)

1. **BLOCKER — changelog syntax error breaks the site build.**
   `websites/atlas-web/app/changelog/page.tsx`, v1.0.4 entry: the `items` array is
   closed twice (`],` on two consecutive lines, around lines 19–21). This is a parse
   error; `next build` will fail. Fix: delete the duplicated `],`.
   (I patched it *locally, uncommitted* so the source audit could run; the committed
   tree still contains the error.)

2. **IMPORTANT — historical v1.0.3 changelog entry was dropped.**
   The integration replaced my v1.0.3 entry with the new v1.0.4 entry instead of
   adding to it. v1.0.3 was a real public release (GitHub: 2026-07-15). Historical
   versions must remain. Fix: reinsert a v1.0.3 entry between v1.0.4 and v1.0.2.

3. **POLISH — two of my regression tests assert superseded implementation
   expressions.** `test_v105_ux_polish.py::test_connected_requires_verified_handshake`
   and `::test_agents_summary_leads_with_connection` fail at the integration commit
   because Codex (correctly) refactored the expressions. The *behavior* they guard is
   intact. Fix when convenient:
   - assert `verification === "connected"`-driven labels instead of
     `verification === "verified" ? "Connected"`;
   - assert `Connected clients: ${connected.length}` in desktop-shell.js instead of
     `${verified.length}`.
   All 17 other tests pass at the integration commit.

## Unresolved ambiguities

- **Top-bar account chip** reads "Account" during a guest session in one audit state
  (previously "Local guest mode"). If intentional rewording, fine; if it implies a
  signed-in account for guests, revisit. Needs a quick Codex confirmation.
- **Footer version vs download target**: footer/facts now say `1.0.5` (candidate)
  while `/download` correctly targets the public `v1.0.4` release via `_config.ts`
  defaults. Correct for a candidate build, but the deploy that publishes this site
  must either ship together with the v1.0.5 release (and set
  `NEXT_PUBLIC_GITHUB_RELEASE_URL`/`NEXT_PUBLIC_INSTALLER_SHA256` to v1.0.5) or hold
  the footer at the version actually served. See §Version audit in the acceptance
  report.

## Source-run note (not a regression)

The new runtime-transport hardening (loopback authority + `atlas_runtime_token`
cookie delivered via the launch URL, handshake exempt) initially blocked my audit
browser until I used the tokened launch URL from `runtime.json`. Behavior is correct
and the packaged launcher does this automatically; recorded here so future source
audits know to use the launch URL, not the bare origin.
