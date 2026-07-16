# Atlas intelligence quality benchmark

This is a deterministic benchmark contract for Atlas repository intelligence.
It deliberately separates a **scoreable expected outcome** from a claimed
Atlas run. `score.py` only scores a supplied observation JSON; it never calls a
model or writes a passing result on its own.

## Coverage

The fixtures cover Python, TypeScript, mixed frontend/backend source, nested
modules, direct and reverse dependencies, a cycle, an unresolved import, a
dynamic import, generated-file exclusion, tests, and configuration files. The
cross-repository case uses deliberately similar names to detect leakage.

## Running a real evaluation

1. Scan each fixture in a fresh Atlas process and export the relevant Files,
   Graph, Impact, Ask, Debug, and Plan evidence to an observation JSON.
2. Include only file paths, dependency edges, impact candidates, citation
   paths, and boolean stale/isolation outcomes. Do not place source, prompts,
   repository paths outside the fixture-relative paths, or generated answers in
   the observation.
3. Run `py -3 score.py observations.json` from this directory.

The output includes file relevance precision/recall, dependency
precision/recall, citation validity, stale-context detection,
cross-repository isolation, and impact false-positive/false-negative rates.
It is a launch gate only when the observations come from a recorded Atlas run.
