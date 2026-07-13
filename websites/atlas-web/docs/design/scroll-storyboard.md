# Scroll Storyboard — one cinematic timeline

The home page is one continuous descent through Atlas's understanding of a project. A single
master timeline maps scroll progress `p` (0→1) to the scene states in `threejs-scene-plan.md`
and to DOM content reveals. Lenis smooth-scroll; GSAP ScrollTrigger scrubs `p`. Content is
pinned in "acts"; between acts the camera and graph transform.

## Acts (each ≈ one viewport of scroll, `scrub`, snap between acts)

**Act 0 — Hero (p≈0, not scrubbed; idle Memory state).**
Copy: *Your codebase, remembered.* + support line + Download / See how it works.
Behind: constellation in Memory state, drifting. On load: crystallize intro.
Bottom: tiny "scroll" affordance in mono.

**Act 1 — The problem (p 0→0.18) → Raw state.**
Graph scatters to noise as you enter. Left-aligned, large:
*Every AI session starts from zero.* Sub: agents re-explore the same repo every session; context
you hand-maintain (CLAUDE.md, wikis, RAG) drifts. Composition: text lower-left, void upper-right.

**Act 2 — Atlas scans (p 0.18→0.42) → Scan state.**
Scan plane sweeps; nodes light; clusters form; first mono labels fade in.
*Atlas maps files, symbols, concepts — and the relationships between them.* Right-aligned block;
a mono list of what's being resolved streams in (real kinds: files, symbols, imports, callers).

**Act 3 — Persistent memory (p 0.42→0.62) → Memory state.**
Graph fully resolved around the core. *Structured memory that survives across sessions.*
Inline proof chips (real): `restore 8–11ms` · `dependency graph + evidence store` · `local`.

**Act 4 — Agent retrieval (p 0.62→0.78) → Agent state.**
Retrieval path lights core→nodes. *Your agent asks; Atlas returns cited context.* Not a fake
chat: a technical request/response rendered as a routed path + a real cited-file evidence card
(path + relevance + reason). Named agents: Claude Code, Cursor, Codex (MCP).

**Act 5 — Product (p 0.78, un-pin; content-led).**
Canvas recedes (dims, blurs to bg). Real product surface integrated into the composition (not a
browser frame): Ask Atlas answer with citations, Impact list, Debug path. Uses real screens.

**Act 6 — Proof (content-led).**
Slow, quiet, dense. Real numbers only: sample repo 18 files, index ~4s, ask 1–30ms; 50-scenario
recall 0.95/0.98/0.97; harness ships in-repo + reproduce commands; local-first guarantees;
platform = Windows; MCP 18 tools. Link to /benchmarks with the honest limitations.

**Act 7 — Converge + CTA (p→1) → Converge state.**
Canvas returns; nodes gather into the Atlas mark. *Give your coding agent a persistent
understanding of your project.* Download Atlas · View on GitHub. Footer with a restrained
continuation of the graph.

## Rules

- One ScrollTrigger timeline owns `p`; no scattered scroll handlers. Section reveals are child
  tweens keyed off `p`, not independent listeners.
- `scrub` where the user should *drive* the transformation (graph morphs); discrete/snap where a
  state should complete decisively (act-to-act).
- No scroll hijacking that traps the user; Lenis stays close to native velocity; wheel/keys/space
  all work; anchor links jump correctly.
- Reduced-motion: timeline collapses to stable per-act states (no camera travel, no morph);
  all copy + proof remain, revealed by short opacity only.
