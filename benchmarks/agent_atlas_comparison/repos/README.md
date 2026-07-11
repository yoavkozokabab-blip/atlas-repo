# Benchmark Repository Checkouts

This directory is reserved for local benchmark checkouts if the operator wants
to keep pinned external repositories beside the benchmark harness.

The canonical repository metadata is `../repositories.json`. Do not change repo
commits during a paired run. If a repository is checked out here, use the exact
SHA from `repositories.json`.
