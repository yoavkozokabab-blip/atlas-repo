/**
 * Shared scroll-progress store for the home narrative. Decouples the GSAP/Lenis
 * scroll controller (writer) from the vanilla-three scene (reader) — the scene
 * reads `sceneProgress.p` every frame; the controller sets it from scroll.
 *
 * p = 0 .. 1 across the narrative section:
 *   0.00  hero          — resolved memory, graph in the right column
 *   ~0.10 enter         — graph slides to centre
 *   0.10–0.32 scan      — a scan plane sweeps the graph
 *   0.32–0.55 memory    — resolved around the core, bridges bright
 *   0.55–0.78 retrieval — a path lights from core to cited nodes
 *   0.78–1.00 converge  — nodes gather into the core / Atlas mark
 */
export const sceneProgress = { p: 0 };
