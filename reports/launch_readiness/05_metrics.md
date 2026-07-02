# 05 — Analytics & Metrics

**Date:** 2026-06-20. Atlas already emits privacy-safe desktop counters (launches, scans, change_plans, what_breaks, exports, tokens_saved) to the accounts service, plus website waitlist + an admin dashboard. Use those; add the gaps.

## North Star
**Weekly Activated Users** = users who got ≥1 successful Atlas answer in their agent in the last 7 days. (Everything else is upstream or downstream of this.)

## Acquisition
| Metric | Source |
|---|---|
| Unique visitors (`/`, `/download`) | Vercel analytics / a lightweight page beacon |
| Downloads (installer fetched) | `/download/atlas` redirect count |
| Registrations | Supabase `users` count (new/day) |
| Waitlist signups | Supabase `waitlist` |

## Activation (the funnel that matters — instrument every step)
| Step | Signal | Source |
|---|---|---|
| Installer launched | desktop `launch` event | accounts analytics |
| MCP configured | first `--mcp` spawn / first `tools/list` | desktop launcher log / a one-time event |
| First scan | `scan` counter > 0 | accounts analytics |
| **First successful Atlas answer** (activation) | first `atlas_build_context_pack`/`export` via MCP | desktop analytics event |
**Report the conversion at each arrow** (download→install→config→scan→answer). The biggest drop will reveal the onboarding fix.

## Retention
| Metric | Definition |
|---|---|
| D1 / D7 / D30 | % of activated users who return (launch or MCP call) on day 1/7/30 |
| WAU / MAU | active = ≥1 MCP tool call or scan in the window |
| Stickiness | WAU/MAU |

## Product
| Metric | Source |
|---|---|
| Context packs generated | desktop counter |
| Exports (Claude/Cursor/Codex) | desktop counter |
| MCP tool calls (by tool) | add a per-tool counter in analytics |
| Est. tokens saved | existing `estimated_tokens_saved` |

## Business
| Metric | Source |
|---|---|
| Waitlist size + invite→signup rate | Supabase |
| Active users (WAU) | analytics |
| Paying users / MRR | Stripe (post-paid-launch) |
| Free→Pro conversion | Stripe + users.plan |

## Instrumentation gaps to close (P1)
- **MCP-side event** for "first answer" (the activation moment) — the MCP runtime is read-only/local; emit a privacy-safe local counter the desktop forwards (no new product feature, just a counter).
- A simple **per-tool call counter**.
- Wire visitor/download analytics on the website (privacy-light).

## Honesty note
Do **not** publish "tokens saved" or retrieval numbers as marketing without the method (the committed benchmarks are honest and narrow — keep them that way). Internal metrics ≠ public claims.
