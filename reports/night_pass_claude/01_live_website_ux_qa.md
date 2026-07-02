# 01 — Website UX QA

**Date:** 2026-06-20. **Live Vercel URL: NOT available to me** (no URL provided, no external egress). QA'd the **deployed code** locally (`next dev/build`), which is what Vercel serves. Re-run against the live URL after the owner deploys.

| Page | Loads | Copy honest | Paid clearly stub/beta | CTA clear | Explains next step | Feels production-worthy |
|---|---|---|---|---|---|---|
| `/` | ✓ 200 | ✓ | ✓ (no paid) | ✓ Download/Join beta | ✓ | yes |
| `/features` | ✓ | ✓ | n/a | ✓ | ✓ | yes |
| `/pricing` | ✓ | ✓ "Free in beta" | ✓ no checkout | ✓ Join the beta | ✓ | yes |
| `/docs` | ✓ | ✓ | n/a | ✓ | ✓ | yes |
| `/faq` | ✓ | ✓ (beta-aware answers) | ✓ | ✓ | ✓ | yes |
| `/download` | ✓ | ✓ | ✓ | ✓ + **MCP connect/verify block** (added) | ✓ | yes |
| `/login` | ✓ | ✓ | n/a | ✓ | ✓ | yes |
| `/account` | ✓ 307→login when anon | ✓ | ✓ | ✓ | ✓ | yes |
| `/account/downloads` | ✓ (authed) | ✓ | ✓ | ✓ | ✓ | yes |
| `/account/billing` | ✓ (authed) | ✓ "Free beta — nothing will ever be charged" | ✓ | ✓ | ✓ | yes |
| `/contact` | ✓ | ✓ | n/a | ✓ category mailtos | ✓ | yes (but support email — see below) |
| `/privacy` | ✓ | ✓ | n/a | — | ✓ | yes |
| `/terms` | ✓ | ⚠ mentions "converts to paid only if you subscribe" (forward-looking; fine for beta) | n/a | — | ✓ | yes |
| `/billing/success` | ✓ (stub path) | ✓ (only reached via stub; checkout is gated off) | ✓ | ✓ | ✓ | yes |
| `/download/atlas` | ✓ 302 (authed + URL) / →/login (anon) | ✓ | n/a | n/a (redirect) | n/a | yes |

## Findings
- **Honest + production-worthy.** No fake/paid CTAs; paid is clearly hidden behind the free-beta flag; "code never leaves your machine" is stated on download.
- **Support email** (footer + contact): a personal Gmail (`yoavkozlovski@gmail.com`, env-driven) whose spelling differs from the owner's address — **verify it's monitored** (env, not code).
- `/terms` has forward-looking paid language — acceptable for beta but worth a one-line "currently free beta" note someday (not a blocker).

## Fixes this pass
None on the website (already clean; the download-page MCP copy + doc support-email were fixed in the prior pass). Live-URL re-QA pending owner deploy.
