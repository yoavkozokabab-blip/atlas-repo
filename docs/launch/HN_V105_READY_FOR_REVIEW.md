# Show HN Package — Atlas v1.0.5 (READY FOR REVIEW — do not auto-publish)

Fact-checked against the released v1.0.5 build on 2026-07-18. Remaining author
TODO: paste the demo video link, choose a title, and post manually.

## A. Title options

1. **Show HN: Atlas – see what may break before your coding agent changes a file**
2. Show HN: I built a dependency map so coding agents can see what they might break
3. Show HN: Atlas, a local repository memory and impact map for coding agents

**Recommendation: title 1.** It leads with the user's fear (breakage), names the
actor (your coding agent), and stays inside what the product actually does
("may break", not "will break"). Title 2 is warmer but buries the product name;
title 3 describes architecture, not pain.

## B. Post (final)

I kept hitting the same problem with coding agents: every session starts from
zero. The agent edits a file confidently, and neither of us knows what depends on
it — so the breakage shows up two files away, after the change.

Atlas is my attempt to fix that. It's a local Windows app that scans a repository
into a dependency graph with persistent memory, and its main trick is Impact:
pick a file (or let your agent ask over MCP) and see the likely blast radius —
direct dependents, transitive reach, affected subsystems and tests, with the
evidence it used. Results are evidence-backed estimates from resolved imports and
symbols, not guarantees, and it says so when it isn't confident.

How it works: indexing runs entirely on your machine and the index stays in a
local folder you can delete. Atlas exposes 18 MCP tools, so Claude Code, Cursor,
or Codex can ask "what breaks if I change services/billing.py?" against the same
graph you see in the UI, and the memory survives across sessions — no re-explaining
the codebase every morning.

Honest caveats: Windows-only today. The installer is unsigned for now, so
SmartScreen will warn (checksum is on the download page). It's free to use — a Pro
plan is planned but there's nothing to buy yet. Pseudonymous usage analytics can be turned off in Settings and never
includes code, paths, file names, prompts, or answers.

There's a bundled demo repo, so you can try Impact in under a minute without
pointing it at your own code.

Site: https://atlas-repo-wu76.vercel.app · GitHub:
https://github.com/yoavkozokabab-blip/atlas-repo · 60-second demo: [video link]

I'd genuinely value skepticism about the impact-analysis approach — what would
make you trust (or distrust) a blast-radius estimate?

## C. First comment (post immediately, from the author)

A few clarifications up front, since these always come up:

**Data flow.** Indexing and analysis are local; Atlas doesn't upload repository
contents to any Atlas service. If you connect an MCP client (Claude Code, Cursor,
Codex), that client sends whatever context you request to *its* model provider —
same as using that agent normally. Atlas itself talks to the network for update
checks and (if enabled) pseudonymous analytics; analytics never includes code, paths,
file names, prompts, or answers, and there's a Settings toggle to turn it off.

**MCP.** Atlas runs as a local stdio MCP server exposing 18 tools (repo summary,
find-relevant-files, what-breaks, plan-change, etc.). The Agents screen only shows
"Connected" after a real MCP handshake — a written config file shows
"Not connected" with a restart hint, because config ≠ connection.

**Unsigned installer.** Code signing is in progress; until then SmartScreen will
warn. The SHA-256 is published on the download page — verify before running.

**Verification status, honestly:** the Cursor integration is what I've verified
end-to-end (handshake + tools grounded in the loaded repo). Claude Code and Codex
configs are written by the same mechanism and expose the same tools, but I haven't
run full end-to-end verification with them yet, so I won't claim it.

**Security note:** v1.0.5 replaced a shared local-service secret from earlier
releases with per-installation protected keys; v1.0.0–v1.0.4 are marked
superseded on GitHub and upgrading signs old local sessions out. The service
only listens on localhost, but I'd rather say it than hide it.

**Known limitations:** Python-first analysis depth (JS/TS is shallower), resolved
static imports only — dynamic/string imports and runtime dispatch aren't traced,
and Impact is an estimate with confidence labels, not a proof. Windows-only today;
macOS/Linux are on the roadmap page.

## D. Response templates

**Why not Cursor's native context?**
Cursor's context is per-session and retrieval-shaped. Atlas builds a persistent
dependency graph that survives sessions and answers structural questions (fan-in,
blast radius) that similarity search doesn't. They compose: Cursor for editing,
Atlas as the memory/impact layer over MCP.

**Why not Claude Code memory?**
CLAUDE.md/memory files are great for conventions and decisions, but they're prose
you maintain by hand. Atlas maintains a *computed* graph of what actually imports
what, and re-derives it from the code on each scan. Different layer; I use both.

**Why not codebase-memory-mcp / vexp / similar tools?**
Same problem space, different bets — I wanted (1) impact analysis as the headline
workflow, not just retrieval, (2) a local UI a human can use without an agent, and
(3) verified-connection truthfulness in the MCP setup. If another tool fits your
flow better, use it; the space is young. I don't claim to be the only one here.

**Why Windows only?**
Solo dev; Windows is where I could ship a verified installer and test the full
MCP flow properly. The core is Python + a local web UI, so macOS/Linux are
portability work, not a rewrite. Roadmap has them.

**Why is the installer unsigned?**
Certificate acquisition is in progress; I chose shipping with a published SHA-256
and a SmartScreen explanation over waiting. The app tells you this on first run
instead of pretending it's fine.

**What data leaves my machine?**
From Atlas: update checks and (if enabled) pseudonymous analytics events — never
code, paths, file names, prompts, or answers. From your MCP client: whatever
context you ask it to send to its own model provider, exactly as when using that
agent without Atlas.

**Why does Atlas need analytics?**
To see which workflows fail or get abandoned (e.g., "Impact started but no visible
result"), which directly catches bugs like invisible-success states. It's
event-name + timing level, opt-out in Settings, and the app works identically with
it off.

**How accurate is Impact?**
It's built from resolved static imports and a symbol index, so precision is high on
those edges and it labels confidence. It will miss dynamic imports, reflection,
string-based dispatch, and cross-service boundaries — the result panel lists
unresolved/limitation notes rather than hiding them. Treat it as a pre-change
checklist, not a proof.

**Is Atlas open source?**
The repository with the website and release assets is public on GitHub; the app
itself ships as a free binary while I decide licensing. If that changes I'll say so
plainly.

**How is this different from a dependency visualizer?**
Visualizers draw the graph; Atlas answers questions against it (what breaks, what
to read first, plan a change), keeps that memory across sessions, and hands it to
your agent over MCP. The graph is the substrate, not the product.
