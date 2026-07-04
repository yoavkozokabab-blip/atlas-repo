# Reddit Launch Templates

> Reddit punishes marketing and rewards usefulness + candor. Lead with the problem,
> share freely, disclose you built it, invite criticism. No hype words.

## r/programming  /  r/ExperiencedDevs
**Title:** I got tired of my AI agent re-reading my whole repo, so I built a tool that maps it first

**Body:**
> Every time I ask Claude/Codex/Cursor something about a non-trivial codebase, it spends
> a chunk of the context window just re-reading files to figure out where things are —
> and still occasionally invents structure that isn't there.
>
> I built **JARVIS**: it scans a repo locally and builds the things an AI actually needs to
> orient — a subsystem map, a real dependency graph, an architectural-risk ranking, and
> change-impact analysis. Then it exports a compact context packet you paste into your AI tool.
>
> It's local-first (no upload, no API keys) and deterministic (it's a real dependency-graph +
> risk engine, not an LLM wrapper). Python-first for now.
>
> It does **not** replace your AI — it makes the one you already use understand your repo faster.
>
> Early and rough in places. I'd genuinely like to hear where the architecture summary or risk
> ranking is *wrong* on your repos. Demo + waitlist: [link]

## r/ChatGPTCoding  /  r/cursor
**Title:** Cut the tokens your AI wastes re-reading your codebase (local repo-intelligence tool)

**Body:**
> If you've watched Cursor/Codex/Claude read 20 files just to answer one architecture question,
> this is for you. JARVIS pre-computes your repo's structure (3D dependency graph, risk, impact)
> and gives you a compact context packet to paste in. Your agent starts informed instead of
> re-deriving everything. Local, deterministic, no keys. Feedback wanted: [link]

## Comment-readiness (have these ready)
- "Is this just RAG?" → No — it's a deterministic static dependency graph + architectural-risk
  engine. The export is structured facts with citations, not retrieved text chunks.
- "Does my code leave my machine?" → Never. Fully local.
- "Languages?" → Python-first today; more on the roadmap (beta users vote).
- "Why not just paste files?" → You can — and you'll spend tokens and still miss structure.
  JARVIS gives the map in a fraction of the tokens.

**Rules:** post once per subreddit, reply to every comment for the first 3 hours, disclose
authorship in the body, never argue — thank critics and note what you'll fix.
