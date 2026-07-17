"""Focused regression tests for Atlas v1.0.3 final human polish."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from atlas_desktop import product_info

STATIC = Path(__file__).resolve().parents[1] / "static"
REPO_STATE = STATIC / "atlas_repository_state.js"
SHELL = STATIC / "desktop-shell.js"
WORKBENCH = STATIC / "workbench-v3.js"
INDEX = STATIC / "index.html"


def _run_node(script: str) -> dict:
    import subprocess
    import tempfile

    node = shutil.which("node")
    if not node:
        pytest.skip("Node.js is required for deterministic frontend polish tests")
    with tempfile.NamedTemporaryFile("w", suffix=".cjs", delete=False, encoding="utf-8") as handle:
        handle.write(script)
        path = handle.name
    try:
        proc = subprocess.run(
            [node, path],
            capture_output=True,
            text=True,
            check=False,
            timeout=30,
        )
    finally:
        Path(path).unlink(missing_ok=True)
    if proc.returncode != 0:
        pytest.fail(proc.stderr or proc.stdout or "node script failed")
    return json.loads(proc.stdout.strip())


def test_product_version_is_104():
    assert product_info.PRODUCT_VERSION == "1.0.5"
    assert product_info.LAUNCH_BUILD_LABEL == "Atlas v1.0.5"


def test_index_footer_and_assets():
    html = INDEX.read_text(encoding="utf-8")
    assert "Atlas 1.0.5" in html
    assert "Report a bug" in html
    assert "Suggest a feature" in html
    assert "atlas_repository_state.js" in html
    assert "ui-polish-v103.css" in html
    assert "Runtime timed out" not in html
    assert "Repository grounded" not in html
    assert "Plan the change before editing code." in html
    assert "Trace a failure through the repository." in html
    assert "See what depends on a file before changing it." in html
    assert "Check connections" in html


def test_shell_does_not_surface_runtime_timeout_copy():
    source = SHELL.read_text(encoding="utf-8")
    assert "Runtime timed out" not in source
    assert "Atlas stopped responding. Your repository was not changed." in source


def test_repository_state_model_states():
    script = f"""
const vm = require("vm");
const source = {json.dumps(REPO_STATE.read_text(encoding="utf-8"))};
const context = {{ STATE: {{ summary: {{ ok: true, repo_name: "Atlas Demo", file_count: 18, module_count: 17, dependency_edges: 22 }} }} }};
context.window = context;
context.document = {{ dispatchEvent() {{}} }};
vm.createContext(context);
vm.runInContext(source, context);
const ready = context.AtlasRepositoryState.compute({{ trust: {{ fresh: true, user_trust_label: "Fresh" }} }});
const empty = context.AtlasRepositoryState.compute({{ summary: {{ ok: false }} }});
process.stdout.write(JSON.stringify({{ ready, empty }}));
"""
    result = _run_node(script)
    assert result["ready"]["state"] == "REPOSITORY_READY"
    assert result["ready"]["name"] == "Atlas Demo"
    assert result["ready"]["moduleCount"] == 17
    assert result["empty"]["state"] == "NO_REPOSITORY"


def test_optional_timeout_does_not_create_global_runtime_failure():
    shell_source = SHELL.read_text(encoding="utf-8")
    script = f"""
const vm = require("vm");
const source = {json.dumps(shell_source)};
const readiness = {{ dataset: {{}} }};
const label = {{ textContent: "Starting" }};
const document = {{
  readyState: "loading",
  getElementById(id) {{ return id === "globalReadiness" ? readiness : id === "globalReadinessLabel" ? label : null; }},
  addEventListener() {{}},
  querySelectorAll() {{ return []; }},
  body: {{ classList: {{ contains() {{ return false; }} }} }},
}};
const context = {{
  document,
  location: {{ origin: "http://127.0.0.1:8778" }},
  URL,
  STATE: {{ summary: {{ ok: true, repo_name: "Atlas Demo", module_count: 17 }} }},
  AtlasRepositoryState: {{ publish() {{ return {{ hasRepo: true }}; }} }},
  MutationObserver: class MutationObserver {{ observe() {{}} }},
  api: async (path) => {{
    if (path === "/api/health") return {{ ok: true, product: "ATLAS", persistence: {{ resume_card: {{ freshness_status: "fresh", validation_status: "valid" }} }} }};
    throw Object.assign(new Error("timeout"), {{ kind: "timeout" }});
  }},
  setTimeout() {{ return 1; }},
  clearTimeout() {{}},
}};
context.window = context;
vm.createContext(context);
vm.runInContext(source, context);
(async () => {{
  await context.atlasDesktopShell.updateGlobalStatus();
  process.stdout.write(JSON.stringify({{ label: label.textContent, state: readiness.dataset.state }}));
}})();
"""
    result = _run_node(script)
    assert "timed out" not in result["label"].lower()
    assert result["state"] != "error"


def test_successful_health_clears_prior_unavailable_state():
    shell_source = SHELL.read_text(encoding="utf-8")
    script = f"""
const vm = require("vm");
const source = {json.dumps(shell_source)};
const readiness = {{ dataset: {{}} }};
const label = {{ textContent: "Starting" }};
let healthy = false;
const document = {{
  readyState: "loading",
  getElementById(id) {{ return id === "globalReadiness" ? readiness : id === "globalReadinessLabel" ? label : null; }},
  addEventListener() {{}},
  querySelectorAll() {{ return []; }},
  body: {{ classList: {{ contains() {{ return false; }} }} }},
}};
const context = {{
  document,
  location: {{ origin: "http://127.0.0.1:8778" }},
  URL,
  STATE: {{ summary: null }},
  AtlasRepositoryState: {{ publish() {{ return {{ hasRepo: false }}; }} }},
  MutationObserver: class MutationObserver {{ observe() {{}} }},
  api: async (path) => {{
    if (path === "/api/health") return healthy ? {{ ok: true, product: "ATLAS" }} : null;
    if (path === "/api/repositories/current/summary") return null;
    return null;
  }},
  setTimeout() {{ return 1; }},
  clearTimeout() {{}},
}};
context.window = context;
vm.createContext(context);
vm.runInContext(source, context);
(async () => {{
  await context.atlasDesktopShell.updateGlobalStatus();
  const first = {{ label: label.textContent, state: readiness.dataset.state }};
  healthy = true;
  await context.atlasDesktopShell.updateGlobalStatus();
  process.stdout.write(JSON.stringify({{ first, second: {{ label: label.textContent, state: readiness.dataset.state }} }}));
}})();
"""
    result = _run_node(script)
    assert result["first"]["label"] == "Atlas stopped responding. Your repository was not changed."
    assert result["second"]["label"] == "No repository loaded"
    assert result["second"]["state"] == "idle"


def test_backend_health_failure_creates_banner():
    shell_source = SHELL.read_text(encoding="utf-8")
    script = f"""
const vm = require("vm");
const source = {json.dumps(shell_source)};
const readiness = {{ dataset: {{}} }};
const label = {{ textContent: "Starting" }};
const document = {{
  readyState: "loading",
  getElementById(id) {{ return id === "globalReadiness" ? readiness : id === "globalReadinessLabel" ? label : null; }},
  addEventListener() {{}},
  querySelectorAll() {{ return []; }},
  body: {{ classList: {{ contains() {{ return false; }} }} }},
}};
const context = {{
  document,
  location: {{ origin: "http://127.0.0.1:8778" }},
  URL,
  STATE: {{ summary: {{ ok: true, repo_name: "Demo" }} }},
  MutationObserver: class MutationObserver {{ observe() {{}} }},
  api: async () => null,
  setTimeout() {{ return 1; }},
  clearTimeout() {{}},
  go() {{}},
}};
context.window = context;
vm.createContext(context);
vm.runInContext(source, context);
(async () => {{
  await context.atlasDesktopShell.updateGlobalStatus();
  process.stdout.write(JSON.stringify({{ label: label.textContent, state: readiness.dataset.state }}));
}})();
"""
    result = _run_node(script)
    assert result["label"] == "Atlas stopped responding. Your repository was not changed."
    assert result["state"] == "error"


def test_agents_configured_vs_verified_semantics():
    workbench_source = WORKBENCH.read_text(encoding="utf-8")
    assert "agentVerificationState" in workbench_source
    assert "Configuration verified" not in workbench_source
    assert 'return "connected"' in workbench_source
    shell = SHELL.read_text(encoding="utf-8")
    assert "Connected clients" in shell
    assert "Configured clients" in shell
    assert "Verified clients" not in shell


def test_diagnostics_uses_repository_summary_not_zero_modules():
    source = SHELL.read_text(encoding="utf-8")
    assert "activeRepositorySummary" in source
    assert "repoSummary?.module_count" in source
    assert "4 component" not in source


def test_copy_review_table_exists():
    report = Path(__file__).resolve().parents[3] / "reports" / "final-human-polish-v103" / "copy-review.md"
    assert report.exists()
    text = report.read_text(encoding="utf-8")
    assert "Plan the change before editing code." in text
