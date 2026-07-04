# Hacker News — Show HN

## Title (keep it plain; HN hates hype)
**Show HN: JARVIS – Prepare your codebase for AI before Claude/Codex/Cursor read it**

(Alt: *Show HN: Repository intelligence so your AI agent stops re-reading the whole repo*)

## Body (the text post)
> Hi HN. I kept watching AI coding agents burn context re-reading a repository just to
> orient themselves — and then confidently describe wiring that didn't exist.
>
> JARVIS analyzes a repository locally and builds the structures an AI actually needs:
> a subsystem map, a deterministic dependency graph, an architectural-risk ranking
> (fan-in, size, cycles, coverage, with the evidence behind each score), and
> change-impact analysis. It then exports a compact, structured context packet you paste
> into Claude/Codex/Cursor so they start informed.
>
> It's deliberately not an LLM wrapper: the graph and risk engine are deterministic, run
> fully on your machine, need no API keys, and the same repo always produces the same output.
> It doesn't replace your AI tool — it makes the one you already use cheaper and better grounded.
>
> Honest status: early, Python-first, and there are rough edges in the product shell. The core
> analysis is real and runs today. I'd value scrutiny of the approach and the risk model
> especially. Demo + waitlist in the first comment.

## First comment (you post it immediately)
> Technical notes: the dependency graph is a static, production-scoped import/call graph;
> the risk score combines fan-in, module size, cycle membership and test presence; the AI
> export is structured facts with file citations and an explicit "uncertainty" section
> (e.g. fan-in is a static lower bound). Happy to go deep on any of it. [demo] [waitlist]

## Launch-day checklist
- [ ] Post 8–10am ET on a weekday (avoid Fri/weekend).
- [ ] Title is plain, accurate, no superlatives ("blazingly", "revolutionary" = death).
- [ ] First comment posted within 60s with demo + technical notes.
- [ ] Be present for 4+ hours; answer every top-level comment substantively.
- [ ] Lead with limitations when asked; never get defensive.
- [ ] Have a 60-sec demo (no audio needed) and one architecture screenshot ready.
- [ ] Don't ask for upvotes anywhere (instant flag).
- [ ] If it stalls, that's fine — repost as a different angle in a few weeks.
