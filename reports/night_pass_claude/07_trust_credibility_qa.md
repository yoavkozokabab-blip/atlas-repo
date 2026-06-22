# 07 — Trust + Credibility QA

**Date:** 2026-06-20.

| Question | Verdict |
|---|---|
| Does Atlas look like a real product? | **Yes** — coherent site, real desktop app, working MCP server, honest pages. |
| Is beta status honest? | **Yes** — "free invite beta", "unsigned beta build" stated plainly. |
| Is the local-first claim supported? | **Yes** — MCP runtime is stdio-local, read-only, secret-redacting; scan skips `.env`/`.git`/`node_modules`. |
| Is "no code leaves your machine" stated carefully? | **Mostly** — download page says "your code never leaves your machine". Accurate for local scan; the *context pack you paste* does leave when you paste it. The FAQ already nuances this ("only the compact context you choose to copy"). Consider mirroring that nuance on the download page. |
| Is paid/pro/trial copy honest given Stripe is stubbed? | **Yes** — paid CTAs hidden (`PAID_PLANS_ENABLED` off), `/api/checkout`→403, account/billing says "Free beta — nothing will ever be charged". No way to be charged. |
| Are privacy/terms sufficient for beta? | **Adequate** — both present. `/terms` has forward-looking paid language (fine for beta). |
| Is support contact credible? | **Risk** — a personal Gmail (spelling differs from owner) as the support address undermines credibility and may be a typo. Use a branded `support@useatlas.dev` (matches the desktop default). Env/owner fix. |
| Any benchmark overclaims? | **No** — the committed benchmark reports are deliberately narrow: "better *retrieval* (−40% tokens, higher recall vs grep), NOT proven better *answers*; agent A/B designed but unrun." The website does **not** cite benchmark numbers, so there's no public overclaim. |

## Net
Credibility is **good for a beta**. The two dents are both **non-code**: the personal-Gmail support address (verify/replace) and the unsigned installer (SmartScreen). No overpromising in public copy.

## Fix this pass
None (the "code never leaves" nuance is already covered in FAQ; the support email is env/owner). No copy overclaim found to fix.
