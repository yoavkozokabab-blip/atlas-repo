# How Atlas differs (developer-honest)

Atlas is a **local, agent-agnostic code-context engine** over MCP. It scans a repo into a
real import/symbol graph and serves any AI agent evidence-ranked files + symbols, impact
analysis (`what_breaks`), and root-cause — with confidence, locally.

Benchmark context (independent retrieval benchmark, gold = symbol-definition file resolved
by grep, 62 tasks / 11 repos): Hit@1 **0.55** vs ~0.27–0.32 for keyword/BM25, MRR **0.68**,
**0 fabricated files**, **~90–97% fewer tokens**. Honest scope: this is *retrieval
quality*, not end-to-end task outcomes; the advantage is largest on big/complex repos and
behavioural ("no symbol named") queries, and decisive vs BM25 but **not** statistically
significant vs naive grep on top-5 hit. On small repos your IDE's search may be enough.

| Compared to | What they do well | How Atlas differs | Honest caveat |
|---|---|---|---|
| Dependency-graph tools | Precise graph for humans | Atlas makes the graph task-scoped + agent-consumable + adds `what_breaks` | Their raw precision can exceed Atlas on some languages |
| Repo-map tools (Aider) | Compact whole-repo map | Atlas ranks per-task with reasons/confidence + symbol slicing | Aider is mature, OSS, loved |
| Token-reduction tools | Trim/compress context | Atlas reduces tokens via better *selection*, not blind truncation | Fewer tokens ≠ better outcome (not claimed) |
| RAG over code (embeddings) | Semantic similarity | Atlas is graph + evidence: deterministic, explainable, 0 fabrications in benchmark | Embeddings can win pure-paraphrase recall |
| Cursor indexing | Best-in-class in-IDE retrieval | Atlas is agent-neutral (one engine for Claude/Codex/Gemini) and local/private | Cursor's UX + data flywheel are ahead |
| Claude Projects | Persistent project context for Claude | Atlas is cross-vendor and code-structure-aware | Projects is zero-setup inside Claude |
| Repo Prompt | Manual file curation to paste | Atlas auto-selects with graph evidence + impact | Repo Prompt gives fine manual control |
| Sourcegraph / Cody | Enterprise code intel | Atlas is local-first, agent-neutral, lighter-weight | Sourcegraph wins enterprise breadth/scale |
| Aider | Agentic CLI coding + repo-map | Atlas is a context *layer* for any agent, not an agent | Aider is a complete workflow |
| Continue.dev | OSS in-IDE assistant + context | Atlas focuses on graph-evidence retrieval + impact via MCP | Continue is broader / IDE-integrated |

**One line:** everyone returns files; Atlas returns the right files with auditable reasons,
blast radius, and confidence — to any agent, locally.

**Current limitations:** Windows only; the app is not currently code-signed; outcome
(vs retrieval) value not yet measured.
