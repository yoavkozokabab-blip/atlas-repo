# Atlas Website — Conversion Audit (Phase 5 / P5)

**Date:** 2026-06-16
**Scope:** landing (`app/page.tsx`), download (`app/download/page.tsx`), pricing teaser,
features, waitlist. Goal: increase waitlist signups, beta signups, downloads. No redesign —
targeted, high-leverage fixes only.

## Top findings (ranked by impact)

### 🔴 HIGH

1. **The waitlist has no UI — the form doesn't exist.**
   `/api/waitlist` (now durable via Supabase, P1) is **not surfaced anywhere**. The only
   "waitlist" text on the site is an FAQ line ("macOS and Linux are on the waitlist"). Every
   visitor who isn't ready to install — Mac/Linux users, evaluators, mobile visitors — has
   **no way to leave an email.** This nullifies the entire waitlist feature and the #1
   top-of-funnel capture.
   **Fix:** add a `WaitlistForm` (email + optional role) to (a) a hero secondary path /
   dedicated section, and (b) the download page for non-Windows users. *(Implemented this
   session — see below.)*

2. **Primary CTA leads to a signup wall, not a download.**
   "Download for Windows" → `/download` → non-authenticated users must **create an account**
   before any download. Forced signup before first value is a classic dev-tool drop-off.
   **Fix options:** allow an anonymous download (capture email *after*, or make it optional),
   or reframe the wall as "Get your beta invite" with the waitlist so the click still
   converts to a lead instead of a bounce. At minimum, set expectations on the button
   ("Create free account to download") — already done — and add the waitlist as the softer
   alternative for those who won't sign up.

3. **Mac/Linux demand is discarded.**
   Download page sends non-Windows users to `/contact` ("Tell us"). That's a dead end vs. a
   one-field waitlist capture. **Fix:** replace with the `WaitlistForm` (role/platform
   captured) — same component as #1.

### 🟡 MEDIUM

4. **No real product proof / screenshots.** "See it work" uses a hand-written terminal block
   and a synthetic SVG graph — not a real Atlas screenshot. Devs want to see the actual UI.
   **Fix:** add 1–2 real screenshots (codebase map, context-pack "Copy for Claude") to the
   landing and download page. (Asset needed from product.)

5. **Positioning is inconsistent.** Hero eyebrow = "Repository intelligence"; download page =
   "repository memory"; strategy = "persistent memory layer for AI coding agents." Pick one
   spine and use it everywhere. The "memory" framing is the differentiated one and should
   lead. **Fix:** align hero eyebrow/headline to the memory positioning.

6. **MCP is invisible on the site.** The biggest agent-native differentiator ("Claude can
   query Atlas directly") isn't mentioned. **Fix:** one feature card / short section on MCP
   (label it experimental, per the readiness reports — no false claims).

7. **No explicit "private beta" framing or trust signals.** The site reads as a finished
   product; there's no beta honesty line, user count, or social proof beyond a "WORKS WITH"
   row. **Fix:** a small "Private beta" badge + an honest one-liner; add proof as it exists.

### 🟢 LOW

8. **Pricing "Start 7-day trial" → stub checkout.** Payments are stub (no real Stripe);
   clicking grants a local trial. Fine for beta, but ensure the success page doesn't imply a
   real charge. Revisit when Stripe is live.
9. **"Free to start" vs forced account.** Microcopy could clarify that "free" still needs a
   free account.
10. **FAQ is solid** (local-first, not-a-replacement, no-hallucination, platforms) — keep.

## What was implemented this session

A reusable, accessible **`WaitlistForm`** client component (`app/_components/waitlist.tsx`)
posting to the durable `/api/waitlist`, with success/duplicate/error states, added to:
- the landing page (a dedicated "Not on Windows yet? / Get your beta invite" section), and
- the download page (replacing the `/contact` dead-end for Mac/Linux).

This turns the now-persistent waitlist backend into an actual conversion surface (closes
findings #1 and #3, softens #2).

## Recommended next (needs product/owner input)
- Real screenshots (finding #4) — single highest remaining trust lever.
- Decide the download gate policy (finding #2): anonymous download vs. invite-gated.
- Positioning pass to the "memory" spine (finding #5) across hero + meta.
