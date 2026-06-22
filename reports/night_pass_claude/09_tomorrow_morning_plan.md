# 09 — Tomorrow Morning Plan

**Date:** 2026-06-20. Ranked next tasks. Owner = Yoav unless noted.

## P0 — before the FIRST external beta user
| Task | Owner | Est | Why | Success criteria |
|---|---|---|---|---|
| Apply Supabase migrations 0001+0002 to atlas-prod | Yoav | 5 min | prod health was "table public.waitlist not found"; auth/waitlist fail without it | `/api/health` `persistence:"ok"`; `select count(*) from public.waitlist` works |
| Set Vercel `SUPABASE_URL`/`SERVICE_ROLE_KEY` to wggjguqcxmskhjznexum + `AUTH_SECRET` | Yoav | 5 min | stale env → 500s; ephemeral secret → logouts | `/api/health` hostname = wggjguqcxmskhjznexum; signup works |
| Point `useatlas.dev` → Vercel | Yoav | 15 min + DNS | frozen desktop's auth target is useatlas.dev; GUI login dead-ends otherwise | site loads at useatlas.dev |
| GitHub release installer + set `ATLAS_INSTALLER_URL` | Yoav | 15 min | `/download` is dead without it | `/download/atlas` 302→asset; SHA matches |
| Verify support email (`NEXT_PUBLIC_SUPPORT_EMAIL`) is real/monitored | Yoav | 2 min | current value looks like a personal-gmail typo → support black hole | a test email arrives |
| One real Claude Desktop tool call (atlas_health + atlas_repo_summary) on a clean install | Yoav | 30 min | frozen-exe MCP proven via script; the real-client UI is the last mile | tools visible + calls return |

## P1 — before ~10 external users
| Task | Owner | Est | Why | Success criteria |
|---|---|---|---|---|
| Hide the stale desktop beta-application form in website mode (sign-in only) | Claude/Codex | 1–2 h | conflicts with website signup; produces confusing errors | website-mode desktop shows only "Sign in"; no beta questionnaire |
| Wire transactional email (password reset + waitlist/invite) | Yoav | 1–2 h | "forgot password" currently emails nothing | reset email delivered |
| Code-sign the installer | Yoav | hours + cert | SmartScreen scares users at scale | no "unknown publisher" |
| Add the literal "where is auth implemented?" example to MCP docs | Claude/Codex | 10 min | tighten first-value moment | doc lists it |
| Run the blind Claude-vs-Claude+Atlas A/B (harness ready) | Yoav + graders | hours | prove answer-quality value | scored result |

## P2 — before public launch
| Task | Owner | Why |
|---|---|---|
| Real Stripe (checkout + webhook + entitlements) | Yoav/Claude | enable paid |
| Live security red-team on the deployed build | Yoav | forged JWT/replay/leak |
| Server-side session revocation | Claude | kill stolen cookies |
| Remote crash/error reporting | Claude/Yoav | diagnose prod issues |
| Delete legacy surfaces (old `~/jarvis_landing`, `installer/jarvis.iss`) | Claude | provenance clarity |
