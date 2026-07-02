# 06 — Hacker News Preparation (not the post — the readiness)

**Date:** 2026-06-20. HN is high-variance and high-scrutiny. Launching too early on a Windows-only, unsigned beta with unproven answer-quality would be a dogpile. Determine readiness first.

## When Atlas is ready for HN (all must be true)
1. **Installer is code-signed OR there's a macOS/Linux build** (HN skews mac/Linux; "Windows-only + unsigned" is fatal).
2. **A 60–90s demo video/GIF** of the real value moment (auth question → ranked files in Claude).
3. **A public benchmark page** (Atlas vs naive grep) with **method + raw data** — not marketing numbers.
4. **The answer-quality story is honest** — either the blind Claude-vs-Claude+Atlas A/B is run, or the post explicitly claims "better *retrieval/context*, measured" and not "better answers."
5. **Capacity:** Vercel + Supabase can take a front-page spike; `/api/health` green.
6. **No embarrassing first-5-minute bug** (the stale desktop beta-form is hidden; install→connect→answer is smooth).

## What evidence is still missing (today)
- Code signing / mac build.
- Hosted demo or video.
- Public benchmark page (the data exists in `reports/`; needs a clean public write-up).
- The agent A/B (designed, not run).

## What HN will attack
- **"Windows-only and unsigned"** → ship signed and/or mac.
- **"Isn't this just grep / RAG / Cursor's index?"** → lead with the benchmark: grep returns tests/docs/.ambr on big repos (Hit@k=0 on langchain/home-assistant) while Atlas ranks the real file; ~40× fewer tokens; 0 fabrications.
- **"You're a wrapper / where's the moat?"** → evidence-centric + impact-aware + self-maintaining repo memory over MCP; complements (not competes with) Cursor/Claude.
- **"Show me it makes Claude *better*, not just smaller context"** → be honest: retrieval is proven; answer-quality A/B is the next proof (don't overclaim).
- **"Privacy — what leaves my machine?"** → "scanning is local; only the compact context you paste leaves." State precisely.
- **"Benchmarks are cherry-picked"** → publish method, repos, gold labels, raw JSON; invite reproduction.

## Questions they'll ask
- macOS/Linux? Pricing? Open source? What model/heuristics power retrieval (LLM or static)? How is "memory" maintained/refreshed? Multi-repo? Monorepo scale? Does it edit code? Telemetry/privacy? How is it different from Sourcegraph/Continue/mem0?

## Proof they'll demand
- Reproducible benchmark + raw data.
- A live/recorded demo on a *real* repo (not a toy).
- A clear privacy statement.
- Honest limitations (Windows-only beta, retrieval-not-answer-quality-proven).

**Verdict:** Atlas is **not HN-ready yet**. HN comes *after* the 100-user tier (signed/mac + demo + public benchmark + honest answer-quality framing). Use the first-10 and Reddit phases to harden first.
