"""Smoke test for the Phase 89 value-flow + taint/security core.

Builds a throwaway synthetic repo with (1) a deliberately vulnerable file and
(2) a clean, safe file. Drives the real CLI:
    - security-scan over the repo
    - analyze-file on the vulnerable file and on the safe file
and asserts that the vulnerable file is flagged and the safe file is not.

Read-only on everything outside its temp dir; never executes the analyzed code;
no network.

Run:
    py -3 builder_core/scripts/smoke_phase89_value_dataflow_taint.py
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import textwrap

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _write(path: str, content: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(textwrap.dedent(content))


def _build_repo(root: str) -> None:
    _write(os.path.join(root, "vulnerable.py"), '''
        import os, subprocess, pickle, hashlib

        def run_cmd(user_cmd):
            # command injection: shell=True with untrusted input
            subprocess.call(user_cmd, shell=True)

        def lookup(name, cursor):
            # sql injection: string built from untrusted input
            q = "SELECT * FROM users WHERE name = '" + name + "'"
            cursor.execute(q)

        def load_config(path):
            # path traversal + unsafe deserialization of untrusted bytes
            with open(path, 'rb') as fh:
                return pickle.load(fh)

        def evaluate(expr):
            # code injection
            return eval(expr)

        def fingerprint(data):
            # weak crypto
            return hashlib.md5(data).hexdigest()
    ''')
    _write(os.path.join(root, "safe.py"), '''
        import hashlib

        def add(a, b):
            total = a + b
            return total

        def lookup(name, cursor):
            # parameterized query -> safe
            cursor.execute("SELECT * FROM users WHERE name = ?", (name,))

        def digest(data):
            # strong hash -> not flagged
            return hashlib.sha256(data).hexdigest()
    ''')


def _run(root: str, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "builder_core.cli", *args],
        cwd=REPO_ROOT, capture_output=True, text=True,
    )


def _section(title: str) -> None:
    print("\n" + "=" * 72)
    print(title)
    print("=" * 72)


def main() -> int:
    failures = []
    with tempfile.TemporaryDirectory(prefix="phase89_smoke_") as tmp:
        root = os.path.join(tmp, "repo")
        os.makedirs(root)
        _build_repo(root)
        print(f"Synthetic repo: {root}")

        _section("security-scan (whole repo)")
        res = _run(root, "security-scan", "--project", root, "--top", "20")
        print(res.stdout.strip())
        out = res.stdout
        for token in ("SECURITY SCAN", "SUMMARY", "FINDINGS", "EVIDENCE", "SOURCES",
                      "NEXT VERIFICATION STEPS"):
            if token not in out:
                failures.append(f"security-scan missing section {token}")
        for cat in ("command_injection", "sql_injection", "code_injection",
                    "unsafe_deserialization", "weak_crypto"):
            if cat not in out:
                failures.append(f"security-scan missing category {cat}")
        if "safe.py" in out:
            failures.append("security-scan flagged the safe file")

        _section("analyze-file vulnerable.py")
        res = _run(root, "analyze-file", "--project", root, "vulnerable.py")
        print(res.stdout.strip())
        for token in ("SUMMARY", "FINDINGS", "EVIDENCE", "SOURCES", "NEXT VERIFICATION STEPS"):
            if token not in res.stdout:
                failures.append(f"analyze-file missing section {token}")

        _section("analyze-file safe.py")
        res = _run(root, "analyze-file", "--project", root, "safe.py")
        print(res.stdout.strip())
        if "code_injection" in res.stdout or "command_injection" in res.stdout:
            failures.append("analyze-file flagged the safe file for injection")

    _section("RESULT")
    if failures:
        print("SMOKE FAILED:")
        for f in failures:
            print(f"  - {f}")
        return 1
    print("SMOKE PASSED — vulnerable file flagged across categories; safe file clean.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
