# Atlas

**A local, agent-agnostic code-context engine for AI coding agents.**

Atlas scans your repository into a real dependency graph and symbol index, then serves any
MCP-compatible AI agent — Claude Desktop, Cursor, Codex — a compact, **evidence-ranked
context pack**: the exact files and symbols that matter for a task, what breaks if you
change them, and the likely root cause of a stack trace.

Your code stays on your machine. Atlas runs locally over stdio (MCP), tool output is
secret-redacted, and **no source code is uploaded to Atlas servers** to provide the
product (verified by source inspection — see [Security & Local-First](docs/LOCAL_FIRST.md)).

> Status: **1.0.0, Windows only.**

---

## Why Atlas

On a large or unfamiliar codebase, an AI agent either burns its context window opening the
wrong files, or leans on a hand-maintained `CLAUDE.md` / `AGENTS.md` that drifts. Atlas
gives the agent a precise, continuously-scanned map instead of a guess.

In an independent retrieval benchmark (gold = where a symbol is actually defined, resolved
by grep, independent of Atlas; 62 tasks across 11 repos):

- **Hit@1 0.55** vs 0.27–0.32 for keyword / BM25 search
- **MRR 0.68**, **Recall@5 0.77**, **0 fabricated files**
- **~90–97% fewer tokens** than opening a naive search's top files

Honest scope: this measures *retrieval quality*, not end-to-end task outcomes. The
advantage is largest on big/complex repos and on behavioural ("no symbol named") queries;
it is decisive vs BM25 but not statistically significant vs naive grep on top-5 hit. On
small repos your IDE's built-in search may be enough. See
[Differentiation](docs/DIFFERENTIATION.md).

---

## What it does

| Capability | Tool |
|---|---|
| Scan a repo into a dependency graph + symbol index | `atlas_scan_repo` |
| Compact, evidence-ranked context pack for a task | `atlas_build_context_pack` |
| Rank task-relevant files with reasons + confidence | `atlas_find_relevant_files` |
| Impact analysis — "what breaks if I change X" | `atlas_what_breaks` |
| Root-cause analysis from a stack trace / failing test | `atlas_root_cause` |
| Repo summary, architecture, dependency graph, health | `atlas_repo_summary`, … |
| Export context for Claude / Cursor / Codex | `atlas_export_for_*` |

Full tool list and setup: [README_MCP.md](README_MCP.md) (18 tools).

---

## Install & connect (Windows)

1. Download and run the Windows installer (`Atlas_Setup.exe`). The app is not currently
   code-signed, so Windows SmartScreen may warn ("unknown publisher") — choose
   *More info → Run anyway* if you trust the download source.
2. Connect your agent — see [README_MCP.md](README_MCP.md) and
   [docs/MCP_CLIENT_SETUP.md](docs/MCP_CLIENT_SETUP.md).
3. In your agent, scan a repository, then ask:
   > "Where is authentication handled, and what breaks if I change it?"

First scan on a very large monorepo can take up to a minute; results are cached afterward.

---

## Current limitations (honest)

- **Windows only** — macOS/Linux are not supported yet.
- The installer is **unsigned** — SmartScreen will warn until it is code-signed.
- **Payments are not enabled.**
- **No third-party security certification** (e.g., SOC 2).
- End-to-end task-outcome improvement (vs better retrieval) has **not** been measured yet.
- The full web → desktop → MCP path has not been independently verified on a clean machine.

---

## Documentation

- [README_MCP.md](README_MCP.md) — MCP server setup (18 tools)
- [docs/MCP_CLIENT_SETUP.md](docs/MCP_CLIENT_SETUP.md) — per-client config
- [docs/LOCAL_FIRST.md](docs/LOCAL_FIRST.md) — security & local-first design
- [docs/DIFFERENTIATION.md](docs/DIFFERENTIATION.md) — how Atlas differs
- [SECURITY.md](SECURITY.md) · [PRIVACY.md](PRIVACY.md) · [TERMS.md](TERMS.md)
- [README_ARCHITECTURE.md](README_ARCHITECTURE.md) — architecture overview

---

## License

Proprietary. See [LICENSE](LICENSE).
