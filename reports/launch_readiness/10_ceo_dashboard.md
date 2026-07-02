# 10 — CEO Dashboard (one screen, every morning)

**Date:** 2026-06-20. What Yoav should see in 60 seconds, with action thresholds. Sourced from `/api/health`, Supabase, the accounts analytics, and the support inbox.

## Top row — is it alive?
| Tile | Source | Green | 🔴 Trigger action |
|---|---|---|---|
| Production health | `/api/health` | `ok:true`, `persistence:"ok"`, hostname = wggjguqcxmskhjznexum | anything else → fix env/Supabase **now** |
| Errors (last 24h) | logs / (future) remote reporting | 0 unhandled | spike → investigate |
| Support queue | shared inbox | 0 unanswered >24h | >0 → respond today |

## Funnel (last 7 days) — the heart of the dashboard
| Stage | Metric | Watch |
|---|---|---|
| Visitors → Downloads | count + % | low % → landing/CTA problem |
| Downloads → Registrations | % | low → signup friction |
| Registrations → Installed | % | low → SmartScreen/installer |
| Installed → MCP configured | % | **biggest expected drop** → config-step friction |
| MCP configured → **First answer** (ACTIVATION) | % + count | the number that matters most |

## Engagement
| KPI | Definition | Threshold |
|---|---|---|
| **WAU (activated)** | ≥1 MCP call/scan in 7d | trend must be flat-or-up week/week |
| D7 retention | % returning day 7 | <20% → product/onboarding problem |
| NPS (rolling) | from in-app | <0 → stop acquiring, fix product |

## Pipeline
| KPI | Source |
|---|---|
| Waitlist size + invites sent / accepted | Supabase |
| New signups (24h / 7d) | Supabase `users` |
| (post-paid) Trials → Paid, MRR | Stripe |

## The 5 numbers Yoav should know cold
1. **Activation rate** (installed → first answer).
2. **WAU (activated).**
3. **New signups this week.**
4. **Open support items.**
5. **Prod health (green/red).**

## Action thresholds (rules, not vibes)
- Activation <50% → **stop recruiting, fix onboarding** (the funnel says where).
- D7 <20% → product isn't sticky → interview churned users before scaling.
- Prod red → drop everything, fix; post to status/beta channel.
- NPS <0 → pause growth; the highest-frequency complaint is the roadmap.
- Support backlog >5 → triage before any new outreach.

> Build it cheap: a single static page (or even a daily script) that reads `/api/health` + the Supabase counts + the analytics rollup. Don't build a BI stack for 10 users.
