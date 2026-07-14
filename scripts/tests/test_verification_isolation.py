from __future__ import annotations

import os
import json
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

from scripts.verification_isolation import (
    _assert_isolated,
    activate_isolated_atlas_data,
    isolated_atlas_environment,
)


def _temporary_test_root() -> Path:
    # Do not depend on pytest's tmp_path fixture: some constrained Windows
    # runners make its default 0700 base inaccessible to subsequent workers.
    return Path(tempfile.mkdtemp(prefix="atlas-isolation-helper-test-"))


def _profile_environment(profile: Path) -> dict[str, str]:
    return {"USERPROFILE" if os.name == "nt" else "HOME": str(profile)}


def test_each_verification_run_gets_a_unique_test_root() -> None:
    test_root = _temporary_test_root()
    base = _profile_environment(test_root / "profile")
    base["JARVIS_DESKTOP_DATA"] = "legacy"

    first_root, first_env = isolated_atlas_environment("proof", environ=base)
    second_root, second_env = isolated_atlas_environment("proof", environ=base)

    assert first_root != second_root
    for root, env in ((first_root, first_env), (second_root, second_env)):
        probe = root / "write-probe"
        probe.write_text("ok", encoding="utf-8")
        assert probe.read_text(encoding="utf-8") == "ok"
        assert env["ATLAS_DESKTOP_DATA"] == str(root)
        assert env["ATLAS_TEST_MODE"] == "1"
        assert env["ATLAS_TEST_PROTECTED_DATA_ROOT"] == str(
            (test_root / "profile" / ".atlas_desktop").resolve()
        )
        assert "JARVIS_DESKTOP_DATA" not in env


def test_guard_rejects_canonical_root_and_descendants() -> None:
    protected = _temporary_test_root() / ".atlas_desktop"

    with pytest.raises(RuntimeError, match="canonical user-data tree"):
        _assert_isolated(protected, protected)
    with pytest.raises(RuntimeError, match="canonical user-data tree"):
        _assert_isolated(protected / "scans", protected)


def test_activation_updates_environment_for_child_inheritance() -> None:
    test_root = _temporary_test_root()
    env = _profile_environment(test_root / "profile")
    env["JARVIS_DESKTOP_DATA"] = "legacy"

    root = activate_isolated_atlas_data("child-proof", environ=env)

    assert env["ATLAS_DESKTOP_DATA"] == str(root)
    assert env["ATLAS_TEST_MODE"] == "1"
    assert "JARVIS_DESKTOP_DATA" not in env
    child = subprocess.check_output(
        [
            sys.executable,
            "-c",
            (
                "import json, os; print(json.dumps({"
                "'root': os.environ.get('ATLAS_DESKTOP_DATA'), "
                "'mode': os.environ.get('ATLAS_TEST_MODE'), "
                "'protected': os.environ.get('ATLAS_TEST_PROTECTED_DATA_ROOT')}))"
            ),
        ],
        env=env,
        text=True,
    )
    inherited = json.loads(child)
    assert inherited["root"] == str(root)
    assert inherited["mode"] == "1"


def test_activation_is_idempotent_within_one_verification_process() -> None:
    test_root = _temporary_test_root()
    env = _profile_environment(test_root / "profile")

    first = activate_isolated_atlas_data("parent-proof", environ=env)
    second = activate_isolated_atlas_data("imported-helper", environ=env)

    assert first == second


DIRECT_SCAN_SCRIPTS = (
    "ab_benchmark.py",
    "atlas_value_benchmark.py",
    "bench_audit4_retrieval.py",
    "bench_production_aware_ranking.py",
    "bench_symbol_slicing.py",
    "impact_benchmark.py",
    "phase116g_collect_metrics.py",
    "phase119_smoke.py",
    "phase121b_visual_metrics.py",
    "phase121c_trace_graph_pipeline.py",
)

ATLAS_IMPORT_SCRIPTS = DIRECT_SCAN_SCRIPTS + (
    "_phase116e_analytics_worker.py",
    "desktop_web_auth_smoke.py",
    "phase185_claude_demo_proof.py",
)

ATLAS_CHILD_SCRIPTS = (
    "e2e_beta_proof.py",
    "phase116e_analytics_write_probe.py",
    "phase185_claude_demo_proof.py",
)


@pytest.mark.parametrize("script_name", DIRECT_SCAN_SCRIPTS)
def test_direct_scan_scripts_activate_isolation_before_atlas_import(script_name: str) -> None:
    source = (Path(__file__).parents[1] / script_name).read_text(encoding="utf-8")

    activation = source.index("activate_isolated_atlas_data(")
    atlas_import = source.index("from atlas_desktop import api")
    first_scan = source.index("api.scan_repository(")
    assert activation < atlas_import < first_scan


@pytest.mark.parametrize("script_name", ATLAS_IMPORT_SCRIPTS)
def test_atlas_import_scripts_activate_isolation_first(script_name: str) -> None:
    source = (Path(__file__).parents[1] / script_name).read_text(encoding="utf-8")

    assert source.index("activate_isolated_atlas_data(") < source.index(
        "from atlas_desktop"
    )


@pytest.mark.parametrize("script_name", ATLAS_CHILD_SCRIPTS)
def test_atlas_child_scripts_activate_isolation_before_spawn(script_name: str) -> None:
    source = (Path(__file__).parents[1] / script_name).read_text(encoding="utf-8")

    assert source.index("activate_isolated_atlas_data(") < source.index(
        "subprocess.Popen("
    )
