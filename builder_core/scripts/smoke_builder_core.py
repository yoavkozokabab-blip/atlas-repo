"""End-to-end smoke test for builder_core against a throwaway fake repo.

Creates a temporary repository (optionally a real git repo if git is present),
then drives the actual CLI via ``python -m builder_core.cli`` for each of the
four commands, asserting the output looks right. Writes nothing outside the
temp dir.

Run:
    py -3 builder_core/scripts/smoke_builder_core.py
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile

# Make the repo root importable / runnable regardless of CWD.
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _write(path: str, content: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(content)


def _build_fake_repo(root: str) -> None:
    _write(
        os.path.join(root, "README.md"),
        "# Demo Service\n\n"
        "A small service that handles user authentication with JWT tokens.\n\n"
        "## Architecture\n\n"
        "An API layer reads and writes a Postgres database through a "
        "repository layer.\n",
    )
    _write(
        os.path.join(root, "src", "auth.py"),
        '"""Authentication using JWT tokens."""\n\n'
        "def login(user, password):\n"
        "    # TODO: add brute-force protection\n"
        "    return True\n",
    )
    _write(
        os.path.join(root, "src", "billing.py"),
        '"""Billing module — charges customers."""\n\n'
        "def charge(amount):\n"
        "    return amount\n" + ("# placeholder\n" * 220),
    )
    _write(
        os.path.join(root, "tests", "test_auth.py"),
        "from src.auth import login\n\n"
        "def test_login():\n"
        "    assert login('u', 'p')\n",
    )


def _try_git_init(root: str) -> bool:
    env = dict(
        os.environ,
        GIT_AUTHOR_NAME="smoke",
        GIT_AUTHOR_EMAIL="smoke@example.com",
        GIT_COMMITTER_NAME="smoke",
        GIT_COMMITTER_EMAIL="smoke@example.com",
    )
    try:
        for args in (["init"], ["add", "-A"], ["commit", "-m", "initial"]):
            res = subprocess.run(
                ["git", *args], cwd=root, env=env,
                capture_output=True, text=True,
            )
            if res.returncode != 0:
                return False
        return True
    except (OSError, subprocess.SubprocessError):
        return False


def _run_cli(root: str, *cli_args: str) -> subprocess.CompletedProcess:
    cmd = [sys.executable, "-m", "builder_core.cli", *cli_args]
    return subprocess.run(
        cmd, cwd=REPO_ROOT, capture_output=True, text=True,
    )


def _section(title: str) -> None:
    print("\n" + "=" * 70)
    print(title)
    print("=" * 70)


def main() -> int:
    failures = []

    with tempfile.TemporaryDirectory(prefix="builder_core_smoke_") as tmp:
        root = os.path.join(tmp, "demo_repo")
        os.makedirs(root)
        _build_fake_repo(root)
        has_git = _try_git_init(root)
        print(f"Fake repo: {root}")
        print(f"git repo:  {has_git}")

        # 1) init
        _section("init")
        res = _run_cli(root, "init", "--project", root)
        print(res.stdout.strip())
        if res.returncode != 0 or "Indexed project" not in res.stdout:
            failures.append("init")
        index_path = os.path.join(root, ".jarvis_builder", "index.json")
        if not os.path.exists(index_path):
            failures.append("index.json missing")

        # 2) ask (risk)
        _section('ask "what are the biggest risks in this codebase?"')
        res = _run_cli(root, "ask", "--project", root,
                       "what are the biggest risks in this codebase?")
        print(res.stdout.strip())
        if not all(tok in res.stdout for tok in ("ANSWER", "EVIDENCE", "SOURCES")):
            failures.append("ask risk format")
        if "billing.py" not in res.stdout:
            failures.append("ask risk did not surface billing.py")

        # 2b) ask (retrieval)
        _section('ask "how does authentication work?"')
        res = _run_cli(root, "ask", "--project", root,
                       "how does authentication work?")
        print(res.stdout.strip())
        if "ANSWER" not in res.stdout:
            failures.append("ask retrieval format")

        # 3) remember
        _section('remember "we chose Postgres because of PostGIS"')
        res = _run_cli(root, "remember", "--project", root,
                       "we chose Postgres because of PostGIS support")
        print(res.stdout.strip())
        if "Decision stored" not in res.stdout:
            failures.append("remember")
        decisions_path = os.path.join(root, ".jarvis_builder", "decisions.jsonl")
        if not os.path.exists(decisions_path):
            failures.append("decisions.jsonl missing")

        # 4) decisions
        _section("decisions")
        res = _run_cli(root, "decisions", "--project", root)
        print(res.stdout.strip())
        if "Postgres" not in res.stdout:
            failures.append("decisions list")

    _section("RESULT")
    if failures:
        print("SMOKE FAILED:")
        for f in failures:
            print(f"  - {f}")
        return 1
    print("SMOKE PASSED — all four commands behaved correctly.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
