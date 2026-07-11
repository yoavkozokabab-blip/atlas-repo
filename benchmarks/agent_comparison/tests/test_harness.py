"""Tests for agent comparison benchmark harness."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
BENCH = ROOT / "benchmarks" / "agent_comparison"
SCRIPTS = BENCH / "scripts"


def test_pilot_tasks_and_gold_exist():
    tasks = sorted((BENCH / "tasks").glob("pilot_*.json"))
    assert len(tasks) == 6
    for task_path in tasks:
        raw = json.loads(task_path.read_text(encoding="utf-8"))
        gold = BENCH / raw["gold_file"]
        assert gold.is_file(), raw["task_id"]


def test_run_benchmark_validate_passes():
    proc = subprocess.run(
        [sys.executable, str(SCRIPTS / "run_benchmark.py"), "validate"],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr


def test_pilot_manifest_exists_after_run():
    manifest = BENCH / "runs" / "pilot_manifest.json"
    assert manifest.is_file()
    data = json.loads(manifest.read_text(encoding="utf-8"))
    assert data["run_count"] == 24
    assert data["execution_backend"] == "automated_stand_in"


def test_atlas_mcp_setup_uses_write_config():
    js = (ROOT / "atlas_desktop" / "static" / "atlas_mcp_setup.js").read_text(encoding="utf-8")
    connect = js[js.find("async function connectCodex") : js.find("function resetToolDetails")]
    assert "/api/integrations/codex/write-config" in connect
