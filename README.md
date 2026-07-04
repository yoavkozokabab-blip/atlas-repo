# Atlas

**Know what breaks before your AI changes it.**

Atlas is a local, agent-agnostic code-context engine for AI coding agents.

It parses your repository into a real dependency graph and symbol index, then gives Claude Desktop, Cursor, Codex and any MCP-compatible agent the exact files, symbols and blast radius needed for a task.

Your AI writes code fast. Atlas helps it understand what it is about to touch.

> Status: **1.0.0, Windows only.**

---

## The problem

AI coding agents are powerful, but on large or unfamiliar codebases they often:

- open the wrong files,
- miss hidden dependencies,
- forget project structure between sessions,
- burn tokens rediscovering context,
- edit code without knowing what else might break.

Atlas gives them a continuously scanned map of your repo instead of a guess.

---

## What Atlas does

| Capability | Tool |
|---|---|
| Scan a repo into a dependency graph + symbol index | `atlas_scan_repo` |
| Build a compact, evidence-ranked context pack | `atlas_build_context_pack` |
| Find task-relevant files with reasons + confidence | `atlas_find_relevant_files` |
| Impact analysis — “what breaks if I change X?” | `atlas_what_breaks` |
| Root-cause analysis from stack traces / failing tests | `atlas_root_cause` |
| Repo summary, architecture, dependency graph, health | `atlas_repo_summary`, … |
| Export context for Claude / Cursor / Codex | `atlas_export_for_*` |

Full tool list and setup: [README_MCP.md](README_MCP.md) — 18 tools.

---

## Example

Ask your agent:

> “Where is authentication handled, and what breaks if I change it?”

Atlas can return:

- the files most likely involved,
- the symbols that matter,
- why each file was selected,
- related dependencies,
- likely blast radius,
- tests or areas that may fail,
- confidence scores and evidence.

Instead of forcing the agent to search blindly, Atlas gives it the relevant map first.

---

## Why not just use memory?

Most AI memory tools store conversations, preferences or previous decisions.

Atlas parses the codebase itself.

That means Atlas is not just trying to remember what you said before. It builds structured repository knowledge from source code: files, symbols, dependencies, references and change impact.

Memory helps an agent remember.  
Atlas helps an agent understand the code it is about to change.

---

## Why Atlas

On a large codebase, an AI agent usually has two bad options:

1. burn context opening too many files;
2. rely on a hand-maintained `CLAUDE.md` / `AGENTS.md` that slowly drifts from reality.

Atlas gives the agent a precise, continuously scanned code map.

In an independent retrieval benchmark  
(gold = where a symbol is actually defined, resolved by grep, independent of Atlas; 62 tasks across 11 repos):

| Metric | Atlas | Baseline |
|---|---:|---:|
| Hit@1 | **0.55** | 0.27–0.32 keyword / BM25 |
| MRR | **0.68** | — |
| Recall@5 | **0.77** | — |
| Fabricated files | **0** | — |
| Token reduction | **~90–97% fewer tokens** | vs opening naive search top files |

Honest scope: this measures **retrieval quality**, not full end-to-end task outcomes. The advantage is largest on big or complex repos and on behavioural queries where there may be no exact symbol name. It is decisive versus BM25, but not statistically significant versus naive grep on top-5 hit. On small repos, your IDE’s built-in search may be enough.

See [Differentiation](docs/DIFFERENTIATION.md).

---

## Local-first security

Your code stays on your machine.

Atlas runs locally over stdio through MCP. Tool output is secret-redacted, and **no source code is uploaded to Atlas servers** to provide the product.

See [Security & Local-First](docs/LOCAL_FIRST.md).

---

## Install & connect

### Windows

1. Download and run `Atlas_Setup.exe`.

   The app is not currently code-signed, so Windows SmartScreen may warn:  
   “unknown publisher”.

   Choose **More info → Run anyway** if you trust the download source.

2. Connect your agent:

   - [README_MCP.md](README_MCP.md)
   - [docs/MCP_CLIENT_SETUP.md](docs/MCP_CLIENT_SETUP.md)

3. In Claude, Cursor or another MCP-compatible agent, scan a repo and ask:

   > “What breaks if I change this function?”

First scan on a very large monorepo can take up to a minute. Results are cached afterward.

---

## Current limitations

- **Windows only** — macOS/Linux are not supported yet.
- The installer is **unsigned** — SmartScreen will warn until Atlas is code-signed.
- **Payments are not enabled.**
- **No third-party security certification** yet, such as SOC 2.
- End-to-end task-outcome improvement has **not** been measured yet.
- The full web → desktop → MCP path has not been independently verified on a clean machine.

---

## Documentation

- [README_MCP.md](README_MCP.md) — MCP server setup and 18 tools
- [docs/MCP_CLIENT_SETUP.md](docs/MCP_CLIENT_SETUP.md) — per-client configuration
- [docs/LOCAL_FIRST.md](docs/LOCAL_FIRST.md) — security and local-first design
- [docs/DIFFERENTIATION.md](docs/DIFFERENTIATION.md) — how Atlas differs
- [SECURITY.md](SECURITY.md)
- [PRIVACY.md](PRIVACY.md)
- [TERMS.md](TERMS.md)
- [README_ARCHITECTURE.md](README_ARCHITECTURE.md) — architecture overview

---

## License

Proprietary. See [LICENSE](LICENSE).
