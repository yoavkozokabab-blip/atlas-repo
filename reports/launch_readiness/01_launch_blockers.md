# 01 — Launch Blocker Inventory

**Date:** 2026-06-20. Grounded in Atlas's real state (free invite beta; website+Supabase+auth+MCP work; installer unsigned; paid stubbed/hidden; Windows-only; useatlas.dev DNS + real-Claude-Desktop confirmation pending).
Severity: 🔴 blocker · 🟠 high · 🟡 medium · ⚪ nice-to-have.

## A) 1 external beta user
| Blocker | Type | Sev | Prob | Impact | Owner | Fix |
|---|---|---|---|---|---|---|
| Supabase migrations 0001+0002 applied to atlas-prod | operational | 🔴 | done? confirm | signup/waitlist 500 | Yoav | 5 min |
| Vercel `SUPABASE_URL`/`SERVICE_ROLE_KEY`/`AUTH_SECRET` correct | operational | 🔴 | med | auth fails / logouts | Yoav | 5 min |
| `useatlas.dev` → Vercel (desktop's baked auth target) | operational | 🔴 | high | desktop GUI login dead-ends | Yoav | 15 min + DNS |
| GitHub release + `ATLAS_INSTALLER_URL` | operational | 🔴 | high | download dead | Yoav | 15 min |
| One real Claude-Desktop tool call confirmed | technical | 🟠 | low (proven on frozen exe) | last-mile risk | Yoav | 15 min |
| Support email is real/monitored (not the personal-gmail typo) | support | 🟠 | med | user can't get help | Yoav | 2 min |
| Unsigned installer → SmartScreen | onboarding | 🟡 | certain | friction (mitigated by forewarning) | Yoav | hours+cert (defer) |

## B) 10 external beta users
| Blocker | Type | Sev | Owner | Fix |
|---|---|---|---|---|
| Stale desktop beta-application form (conflicts w/ website signup) → hide in website mode | onboarding | 🟠 | Claude/Codex | 1–2 h |
| Password-reset emails nothing (no provider) — now shows honest "not enabled in beta" copy; wire real email | support | 🟠 | Yoav | 1–2 h |
| "Connect to Claude in 3 steps" page + 90s demo video | onboarding | 🟠 | Yoav | half-day |
| Basic activation analytics (download→install→MCP→first answer) | analytics | 🟠 | Claude/Yoav | 0.5–1 day |
| Lightweight support loop (shared inbox + Discord/channel) | support | 🟡 | Yoav | 1 h |

## C) 100 external beta users
| Blocker | Type | Sev | Owner | Fix |
|---|---|---|---|---|
| Code-signing certificate (SmartScreen at scale) | operational | 🟠 | Yoav | days (EV cert) |
| Remote crash/error reporting (opt-in) | technical | 🟠 | Claude/Yoav | 1–2 days |
| Rate-limit verified under load (Supabase RPC) | technical | 🟡 | Yoav | hours |
| Status page + incident comms | operational | 🟡 | Yoav | hours |
| Scalable support (tags/FAQ/office hours) | support | 🟡 | Yoav | ongoing |

## D) Hacker News launch
| Blocker | Type | Sev | Why |
|---|---|---|---|
| Code-signed installer **or** macOS/Linux build | onboarding/technical | 🔴 | "Windows-only + unsigned" is an instant HN dogpile |
| Public, reproducible benchmark page (Atlas vs grep, honest) | marketing | 🟠 | HN demands numbers + method |
| Hosted demo / GIF of the value moment | marketing | 🟠 | "show, don't tell" |
| Agent answer-quality A/B run (or explicitly framed as retrieval-only) | marketing | 🟠 | HN attacks unproven "makes Claude better" claims |
| Load capacity (Vercel + Supabase) | technical | 🟡 | front-page spike |

## E) Paid launch
| Blocker | Type | Sev | Why |
|---|---|---|---|
| Real Stripe (checkout + webhook + entitlements) | technical | 🔴 | currently stubbed; cannot charge |
| Refund/cancel/dunning + billing support | operational/legal | 🟠 | consumer expectations |
| ToS/pricing/refund policy finalized for paid | legal | 🟠 | currently beta-framed |
| Entitlement enforcement (plan → desktop features) | technical | 🟠 | gate Pro features |
| Code signing + macOS (paid users expect polish) | operational | 🟠 | trust |

**Bottom line:** the path to **1 user is purely owner ops** (no engineering blocker). 10 users adds onboarding polish + email + analytics. 100/HN/paid each add a real engineering/operational tier (signing, telemetry, Stripe).
