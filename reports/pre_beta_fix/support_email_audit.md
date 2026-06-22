# TASK 3 — Support Email Consistency Audit

**Date:** 2026-06-20.

## Every support/contact email reference found
| Location | Value | Type |
|---|---|---|
| `jarvis_desktop/product_info.py:14` | `support@useatlas.dev` (`DEFAULT_SUPPORT_EMAIL`, overridable by `ATLAS_SUPPORT_EMAIL`) | desktop default — **branded** |
| `websites/jarvis-landing/app/_config.ts:5` | `process.env.NEXT_PUBLIC_SUPPORT_EMAIL ?? ""` (→ `/contact` if unset) | **env-driven (correct pattern)** |
| `websites/jarvis-landing/.env.example:6` | `you@example.com` | generic placeholder (fine) |
| `websites/jarvis-landing/.env.local:` (gitignored) | `yoavkozlovski@gmail.com` | **personal Gmail; live-rendered value; spelling differs from owner** |
| `docs/VERCEL_DEPLOYMENT_CLICK_BY_CLICK.md:44` (before fix) | `yoavkozokabab@gmail.com` | personal Gmail in a tracked doc |
| `docs/*_CLICK_BY_CLICK.md` `ADMIN_EMAILS` | `yoavkozokabab@gmail.com` | owner's address — **correct for ADMIN** (left as-is) |

## Inconsistencies
Three different "support" addresses were in play: branded `support@useatlas.dev` (desktop), `yoavkozokabab@gmail.com` (docs), and `yoavkozlovski@gmail.com` (live web env). The web env value's spelling (**yoavkozlovski**) differs from the owner's git address (**yoavkozokabab**) — likely a typo; a wrong support email silently drops first-user help.

## Fixes applied (code/docs only)
- **Aligned the doc example** `NEXT_PUBLIC_SUPPORT_EMAIL` → `support@useatlas.dev` (matching the desktop's existing branded default) in `docs/VERCEL_DEPLOYMENT_CLICK_BY_CLICK.md`, with a note "a monitored support inbox (not a personal address)". This is alignment to the existing brand address, **not a guess**.
- Left `ADMIN_EMAILS` examples as the owner's address (admin = owner is correct).
- **No code change** to the website — it already uses the env-driven source-of-truth (`NEXT_PUBLIC_SUPPORT_EMAIL`). **No personal Gmail is hardcoded in source.**
- **Did NOT edit `.env.local`** (gitignored, operator-owned, secret-bearing) — the live value is the owner's to set.

## Owner action (cannot be done in-repo)
Set `NEXT_PUBLIC_SUPPORT_EMAIL` (Vercel + local `.env.local`) to a **real, monitored** inbox — recommended `support@useatlas.dev` (consistent with the desktop) or a confirmed address. **Verify the current `yoavkozlovski@gmail.com` is intentional; it looks like a typo.**
