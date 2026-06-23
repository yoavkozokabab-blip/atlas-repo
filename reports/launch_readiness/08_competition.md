# 08 — Competitive Analysis

**Date:** 2026-06-20. **Framing that matters:** Atlas is **not** an editor or an agent — it's a **context/memory layer that feeds the agents you already use** (Claude/Cursor/Codex) via MCP. So most "competitors" are partners or adjacent, not head-to-head. Compete on *context quality + token efficiency + repo understanding*, not on editing.

| Tool | Category | Memory | Context | Repo understanding | Token efficiency | Workflow | vs Atlas |
|---|---|---|---|---|---|---|---|
| **Cursor** | AI IDE | proprietary index | strong in-editor | embeddings index | opaque | edits inline | **Partner** — Atlas can feed Cursor via MCP; Cursor's index is a "good-enough" threat |
| **Claude Code / Desktop** | agent/CLI | manual (CLAUDE.md) | tool-driven | greps/reads on demand | no | agentic edits | **Primary host** — Atlas plugs in via MCP; this is the wedge |
| **Codex** | agent | thin | thin | limited | no | agentic | **Host** — same MCP value |
| **Aider** | CLI pair-programmer | repo map | repo-map + you pick files | tree-sitter repo map | medium | edits | Closest philosophically; Aider's repo-map is the nearest analog, but in-tool only, not MCP-portable |
| **Sourcegraph (Cody)** | code search/intelligence | indexes | strong, precise | best-in-class graph | medium | search/chat | Strongest on raw code intelligence; enterprise/hosted, heavier; Atlas is local-first + agent-fed |
| **Continue** | IDE assistant | context providers | configurable | basic | medium | in-IDE | Overlap on "context providers"; Atlas is deeper repo understanding + MCP |
| **OpenMemory / mem0** | memory layer | ★ general memory | conversational memory | not repo-specific | n/a | memory API | Direct "memory" competitor in name, but it's *conversational* memory, not *repository* memory — different axis |
| **Graphite** | code review/stacking | n/a | PR-centric | PR graph | n/a | review workflow | Adjacent (review), not context-for-agents |
| **Devin** | autonomous agent | internal | internal | internal | n/a | full autonomy | Different tier (full agent); not a context layer |

## Strongest advantage
**Evidence-centric, impact-aware, token-efficient repository context delivered over MCP to *any* agent, local-first.** Measured edge vs naive search: right file in top-3 ~3× more often, ~40× fewer tokens, **0 fabrications**, and grep collapses on big repos where Atlas still works. No competitor offers "portable, evidence-backed repo memory + impact analysis as an MCP server you point any agent at."

## Weakest point
- **Windows-only, unsigned** (vs polished cross-platform incumbents).
- **Read-only** (doesn't edit — by design, but users may expect it).
- **Answer-quality not yet proven** (only retrieval). 
- **Single active scan** (multi-repo/monorepo-at-once is weak).

## Biggest threat
**Cursor/Claude adding "good-enough" native repo memory/index** — if the host tools make their own context 80% as good, the marginal value of a separate MCP shrinks. Secondary: **mem0/OpenMemory** owning the "memory" narrative even though it's a different (conversational) axis. **Mitigation:** be the *best* repo-context layer (impact analysis, what-breaks, evidence) and stay agent-agnostic (work with all of them) so you're not betting on one host.
