/**
 * facts.ts — the ONLY place real Atlas product numbers/claims live.
 * Every marketing page and the 3D scene import from here so no number can drift
 * or be invented ad hoc. Everything below is verifiable in-repo (see
 * docs/design/content-plan.md). Do not add a claim here without evidence.
 */

export const AGENTS = ["Claude Code", "Cursor", "Codex"] as const;

export const facts = {
  mcpTools: 18,
  restoreMsLabel: "8–11ms",
  coldScanLabel: "~2–4s",
  // sample / demo repo
  sampleFiles: 18,
  sampleModules: 17,
  sampleIndexLabel: "~4s",
  askLatencyLabel: "1–30ms",
  // 50-scenario retrieval suite (feature / bug / impact)
  recall: { feature: 0.95, bug: 0.98, impact: 0.97 },
  precision: { feature: 0.8, bug: 0.3, impact: 0.88 },
  suiteScenarios: 50,
  suiteMeanScore: 86.3,
  // impact engine (separate suite)
  impactPrecision: 1.0,
  impactRecall: 0.93,
  impactRepos: 20,
  impactQuestions: 100,
  // distribution
  version: "1.0.2",
  platform: "Windows",
} as const;

/** Honest limitations — publish these; they build trust. */
export const limitations = [
  "Numbers are self-measured on one Windows development machine; your hardware will differ.",
  "The 50-scenario suite runs against a reference repository we built, not a random sample of OSS projects.",
  "Large monorepo indexing is slower and is an active work item.",
  "Retrieval quality is not the same as end-to-end task success with a coding agent.",
  "Windows only today. The installer is currently unsigned (SmartScreen warning).",
] as const;

/** Home copy deck (kept beside the facts so tone + numbers stay consistent). */
export const copy = {
  h1: "Your codebase, remembered.",
  support:
    "Atlas maps your repository into a persistent memory and serves cited context to Claude Code, Cursor and Codex — locally, across every session.",
  heroNote: "No signup required · Local-first · Your code stays on your machine",
  acts: {
    problem: "Every AI session starts from zero.",
    scan: "Atlas maps your repository.",
    memory: "Memory that survives across sessions.",
    agent: "Your agent asks; Atlas answers with citations.",
    converge: "Give your coding agent a persistent understanding of your project.",
  },
} as const;
