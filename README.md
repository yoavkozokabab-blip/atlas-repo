# Atlas

**A local, agent-agnostic code-context engine for AI coding agents.**

Atlas scans your repository into a real dependency graph and symbol index, then
serves any MCP-compatible AI agent — Claude Desktop, Cursor, Codex — a compact,
**evidence-ranked context pack**: the exact files and symbols that matter for a
task, what breaks if you change them, and the likely root cause of a stack trace.

Your code never leaves your machine. Atlas runs locally over stdio (MCP), and
tool output is secret-redacted by default.

> Status: **0.1.0-beta**, Windows. macOS/Linux are not yet supported.

---

## Why Atlas

On a large or unfamiliar codebase, an AI agent either burns its context window
opening the wrong files, or leans on a hand-maintained `CLAUDE.md` / `AGENTS.md`
that drifts out of date. Atlas gives the agent a precise, continuously-scanned
map instead of a guess.

In an independent retrieval benchmark (gold = where a symbol is actually defined,
resolved by grep, independent of Atlas; 62 tasks across 11 repos):

- **Hit@1 0.55** vs 0.27–0.32 for keyword / BM25 search
- **MRR 0.68**, **Recall@5 0.77**, **0 fabricated files**
- **~90–97% fewer tokens** than opening a naive search's top files

Honest scope: this measures *retrieval quality*, not end-to-end task outcomes.
The advantage is largest on big/complex repositories and on behavioural ("no
symbol named") queries; on small repos your IDE's built-in search may be enough.

---

## What it does

| Capability | Tool |
|---|---|
| Scan a repo into a dependency graph + symbol index | `atlas_scan_repo` |
| Compact, evidence-ranked context pack for a task | `atlas_build_context_pack` |
| Rank task-relevant files with reasons + confidence | `atlas_find_relevant_files` |
| Impact analysis — "what breaks if I change X" | `atlas_what_breaks` |
| Root-cause analysis from a stack trace / failing test | `atlas_root_cause` |
| Repository summary, architecture, dependency graph, health | `atlas_repo_summary`, … |
| Export context for Claude / Cursor / Codex | `atlas_export_for_*` |

Privacy and safety are built in: local stdio transport, local-path-only
enforcement, secret redaction on output, and every tool gated behind a
successful scan.

---

## Install & connect (Windows beta)

1. Download and run the installer (`Atlas_Setup.exe`).
2. Connect your agent — Atlas can write the MCP config for Claude Desktop, or
   you add it manually. Full steps: [`README_MCP.md`](README_MCP.md) and
   [`docs/MCP_CLIENT_SETUP.md`](docs/MCP_CLIENT_SETUP.md).
3. In your agent, scan a repository, then ask a question:
   > "Where is authentication handled, and what breaks if I change it?"

First scan on a very large monorepo can take up to a minute; results are cached
afterwards.

---

## Documentation

- [`README_MCP.md`](README_MCP.md) — MCP server setup
- [`docs/MCP_CLIENT_SETUP.md`](docs/MCP_CLIENT_SETUP.md) — per-client config
- [`README_ARCHITECTURE.md`](README_ARCHITECTURE.md) — architecture overview

---

## License

Proprietary. See [`LICENSE`](LICENSE).
