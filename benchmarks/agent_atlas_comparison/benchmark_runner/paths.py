"""Common benchmark paths."""

from __future__ import annotations

from pathlib import Path

BENCHMARK_ROOT = Path(__file__).resolve().parents[1]
TASKS_DIR = BENCHMARK_ROOT / "tasks"
GOLD_DIR = BENCHMARK_ROOT / "gold"
RUNS_DIR = BENCHMARK_ROOT / "runs"
RESULTS_DIR = BENCHMARK_ROOT / "results"
REPORTS_DIR = BENCHMARK_ROOT / "reports"
SCORES_DIR = BENCHMARK_ROOT / "scores"
REPOSITORIES_PATH = BENCHMARK_ROOT / "repositories.json"
