# Show HN post — final draft

## Title (pick one)

1. Show HN: Atlas – Persistent repository memory for Claude Code, Cursor, and Codex
2. Show HN: Atlas – Persistent repo context and impact analysis for coding agents

URL: `https://<prod-url>/hn`

## Post body

I built Atlas because I was tired of re-explaining my codebase to coding agents. Every fresh Claude Code or Cursor session started from zero, and the usual fix — hand-maintained CLAUDE.md / AGENTS.md files — drifted the moment the code changed.

Atlas is a local Windows app that scans a repository into a resolved import graph, subsystem map, and per-file evidence, and serves that to Claude Code, Cursor, and Codex over MCP (18 tools). The part I care most about: the index persists. Scans are written to disk with a sorted, content-hashed manifest signature. A fresh agent session validates that signature against the live repo — unchanged means instant restore, changed means Atlas refuses the stale context and asks for a rescan. It never silently serves an outdated map.

The 30-second version: install → load the bundled sample repo (or scan your own) → ask "Where is authentication implemented?" → get an answer with cited file paths → one click writes the MCP config for your agent (with a timestamped backup that preserves your other MCP servers).

What it is not: Atlas is not an agent and calls no LLM — answers are deterministic lookups against the local index, so they cite files rather than hallucinate. It never modifies your code. Indexing is fully local; nothing is uploaded to any Atlas server (there isn't a hosted indexing service to upload to). The only network path for your code remains the one you already have: whatever your agent sends to its own model provider. Full data-flow breakdown is on the site.

One measured number, narrowly scoped: on the controlled 27-file benchmark repo that ships in the source, a cold scan takes ~2.2 s and a fresh installed MCP process restores the persisted index in 8–11 ms without rebuilding the graph. I am not claiming agent-accuracy or token-savings numbers — I haven't run a study that would justify them.

Honest limitations: Windows-only installer for now, and it's unsigned, so SmartScreen warns on first run (SHA256 is published on the release; verify it). Deep dependency analysis covers Python and JS/TS; Go/Rust/Java/C#/Ruby are file-level scanned. Impact analysis sees statically resolved imports only — dynamic dispatch is invisible to it. Large monorepos index slowly today.

Pricing: the core app is free, no account required. A $19/mo Pro tier (sync, snapshots, unlimited repos) exists on the pricing page but checkout is deliberately disabled until billing is verified end-to-end — I'd rather ship "coming soon" than a checkout I haven't tested with real money.

Solo project. The thing I most want from HN: tell me where the model breaks — repos where indexing fails, wrong impact results, MCP setups that don't connect. I'll be in the thread all day.

## First founder comment (post immediately)

Some technical detail that didn't fit the post:

Persistence was the hard part to get honest. The failure mode of every "memory" tool is silently serving stale context. Atlas signs each scan with a manifest of every tracked file (path, size, mtime, 256KB-capped content hash), sorted before hashing so directory-traversal order can't produce false staleness. A fresh MCP process validates that signature before restoring; there's an explicit active-repo pointer, and if several repos are persisted with no active one it returns a "selection required" response instead of guessing. Stale scans come back as errors that say why.

The MCP config writes were the part I was most nervous about shipping — nobody wants a tool that eats their config. Connect creates a timestamped backup first, merges only the `atlas` entry, preserves every other server, and validates the resulting JSON/TOML before atomically replacing the file. If your config is malformed it refuses to touch it and shows you a paste-ready snippet instead.

Happy to go into the graph construction, the staleness model, or why answers are deterministic lookups instead of an LLM.
