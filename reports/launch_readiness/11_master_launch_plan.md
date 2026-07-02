# 11 — Master Launch Plan (now → first paying customer)

**Date:** 2026-06-20. The single playbook. Sequenced phases + a daily routine. Grounded in Atlas's real state: engineering substantially done; the path is **ops → first users → harden → distribution → paid.** Detail lives in docs 01–10.

## Operating principle
Do **not** chase scale before activation works. The gate at every phase is the **activation rate** (installed → first Atlas answer in Claude). Fix that with 10 users before touching 100.

---

## PHASE 0 — GO LIVE (this week · owner-only · ~half a day)
Nothing ships to a user until these are green. (From `01_launch_blockers` A.)
1. Apply Supabase migrations `0001`+`0002` to atlas-prod; verify `select count(*) from public.waitlist`.
2. Set Vercel `SUPABASE_URL` + `SUPABASE_SERVICE_ROLE_KEY` (new project) + `AUTH_SECRET`; redeploy.
3. Confirm `/api/health` → `persistence:"ok"`, hostname = wggjguqcxmskhjznexum.
4. Point `useatlas.dev` → Vercel.
5. GitHub release the installer; set `ATLAS_INSTALLER_URL`; verify `/download/atlas` + SHA.
6. Set `NEXT_PUBLIC_SUPPORT_EMAIL` to a **real monitored inbox** (fix the personal-gmail value).
7. Run `scripts/website_smoke_test.py` against the live URL → all green.
8. On your own machine: install → add `Atlas.exe --mcp` to Claude Desktop → ask the auth question → confirm a tool call. (Last-mile; de-risked by `mcp_install_proof.py`.)
**Exit:** you personally completed the full journey on the live site.

## PHASE 1 — FIRST 10 (weeks 1–2 · supervised learning)
- Recruit per `02_first_10_users`: warm intros → Claude/Cursor power users → IndieHackers. Personal, screen-shared installs.
- Record the 90s value-moment video (`03_onboarding`) and the "Connect to Claude in 3 steps" page.
- Instrument the activation funnel (`05_metrics`); stand up the CEO dashboard (`10`).
- Run 5 beta interviews (`09`).
- **Engineering (Claude/Codex, in parallel):** hide the stale desktop beta-form in website mode; wire password-reset email.
**Exit:** ≥7/10 reach first answer; top-3 friction points known and being fixed; activation ≥50%.

## PHASE 2 — NEXT ~40 + HARDEN (weeks 3–6)
- Open to ~50 via r/ClaudeAI + r/cursor (value-first; `07` days 8–21).
- Fix the #1 funnel drop revealed in Phase 1 (likely the MCP-config step → better copy/screenshots).
- Add code signing (EV cert) + opt-in remote crash reporting (`01` C tier).
- Publish the honest benchmark write-up (Atlas vs grep, method + raw data).
**Exit:** activation ≥60%, D7 ≥20%, NPS ≥0, signed installer, 50+ users.

## PHASE 3 — DISTRIBUTION WAVE (weeks 7–10)
- Reddit demo + benchmark posts (`07` days 15–30); a single X demo thread.
- Only if HN-ready (`06`: signed/mac + demo + public benchmark + honest answer-quality framing) → consider HN. Otherwise hold HN for after paid.
- Decide macOS build (the biggest reach unlock + HN de-risk).
**Exit:** ~100 activated users, stable retention, a reproducible public benchmark, demand signal for Pro.

## PHASE 4 — PAID (month 3+, when demand is proven)
- Implement real Stripe (checkout + webhook + entitlements) per `billing_architecture.md`; flip `PAID_PLANS_ENABLED` on only after test-mode passes.
- Tie Pro entitlement to desktop features; finalize ToS/refund/cancel.
- Convert the most-engaged free users first (they told you they'd pay in interviews).
**Exit / GOAL:** **first paying customer.**

---

## DAILY ROUTINE (every morning, ~30 min)
1. **Open the CEO dashboard** (`10`): prod health green? activation rate? WAU? new signups? open support?
2. **Clear the support queue** — respond to every beta user same/next day (you are support right now).
3. **Watch one activation funnel** — where did users drop yesterday? Note it.
4. **Talk to one user** — a quick message or a scheduled interview; "what almost made you quit?"
5. **Ship one friction fix** (or hand it to Claude/Codex) — the single highest-frequency complaint.
6. **One acquisition action** appropriate to the phase (a warm intro, a helpful Reddit comment, a DM to a power user) — *only if* activation is healthy; if activation is broken, fix it instead.
7. **Log the 5 numbers** (activation, WAU, signups, support, health) so you see the trend.

## Weekly (Friday)
- Review NPS + feedback + funnel; pick next week's single biggest fix.
- Post "this week in the Atlas beta" to the beta channel (closes the loop, builds loyalty).
- Re-check the phase exit criteria — only advance phases when the gate is met.

## The one rule
**Activation before acquisition.** Every time you're tempted to chase more users, first ask: "do the users I have reach first value?" If not, that's today's job.
