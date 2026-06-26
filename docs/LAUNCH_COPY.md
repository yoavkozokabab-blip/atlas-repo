# Launch Copy (technical, non-hype)

> Honest constraints baked in: retrieval is measured, outcomes are not; Windows beta;
> unsigned installer; payments not enabled. Do not add claims beyond these.

## Homepage headline
**The shared memory your AI coding agents are missing.**
_Sub:_ Atlas maps your codebase locally and gives Claude, Cursor, and Codex the exact
files, impact, and reasons — from one source of truth. Your code stays on your machine.

## One-line pitch
Atlas is a local, vendor-neutral code-context engine that gives any AI agent
evidence-ranked files + blast-radius for a task — your code never leaves your machine.

## 30-second pitch
AI agents drown in large repos — they open the wrong files and burn your context window.
Atlas scans your repo into a dependency + symbol graph and serves any agent a compact,
evidence-ranked context pack: the right files, exact symbols, what breaks if you change
them, with confidence. Local-first; ~90% fewer tokens than naive search in our benchmark.

## 2-minute pitch
The cost of AI coding on a real codebase isn't the model — it's managing what it knows;
`CLAUDE.md` drifts, RAG goes stale, each tool is a silo. Atlas makes context a shared,
structured layer: it maps your code locally and exposes, over MCP, the files/symbols that
matter, impact analysis, and root-cause — to Claude, Cursor, and Codex alike. In an
independent retrieval benchmark it put the right file first 55% of the time vs ~30% for
keyword search, with 0 fabrications and ~90–97% fewer tokens. Honestly, that's retrieval
quality — outcome studies are next. Free beta, Windows today.

## GitHub README intro
Atlas — a local, agent-agnostic code-context engine over MCP. Scan a repo; ask any agent
for the exact files, impact (`what_breaks`), and root-cause, with evidence and confidence.
Local-first; your code stays on your machine. Windows beta.

## LinkedIn post
I kept watching my AI agent open the wrong files in a 500k-LOC repo. So I built Atlas: a
local context layer that gives Claude/Cursor/Codex the right files + impact analysis, with
evidence. Benchmark: right-file-first 55% vs ~30% for keyword search, 0 fabrications, ~90%
fewer tokens. Free beta (Windows), feedback wanted. [link]

## Reddit post (r/ChatGPTCoding)
**Built a local context layer for AI agents that works on big repos.** Short problem, a
2-min demo + benchmark (including where it loses), Windows beta, brutal feedback welcome.

## Show HN draft
**Show HN: Atlas – local, agent-neutral code context for Claude/Cursor/Codex.**
Body: the problem (agents flail on large repos), the approach (import+symbol graph,
evidence-ranked packs, `what_breaks`/`root_cause`, local/private over MCP), the honest
benchmark (decisive vs BM25; not significant vs grep on top-5; outcome A/B not yet run),
what's NOT done (Windows-only, unsigned beta), and a request for feedback.

## Cold DM
You work on [big repo] with [Cursor/Claude] — do you hit the "agent opens the wrong files"
problem? I built a local tool that fixes the context part (benchmark: 55% right-file-first
vs ~30%). 10-min look? No deck.

## Follow-up DM
No worries if busy — here's a 2-min demo [link] and the benchmark [link]. If it's not
relevant to your repo size, ignore me; if it is, I'll hand-set-it-up for you.

## Demo video script (2 min)
(0:00) big repo, agent greps and flails. (0:20) connect Atlas (one-time). (0:35) "where is
auth handled / what breaks if I change it." (0:55) show evidence pack: ranked files +
exact symbols + blast radius + confidence. (1:20) token count 3k vs 100k+. (1:35) same
engine, switch from Claude to Cursor. (1:50) "local — your code stays here. Free beta,
link below."
