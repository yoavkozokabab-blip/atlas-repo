"""Atlas CLI.

Usage:
    python -m atlas context --repo <path> --task "..." --target codex
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from jarvis_desktop import agent_integrations


def _context(args: argparse.Namespace) -> int:
    result = agent_integrations.export_for_repo(
        args.repo,
        target=args.target,
        task=args.task,
        max_files=args.max_files,
    )
    if args.json:
        print(json.dumps(result, indent=2, default=str))
    elif result.get("ok"):
        text = str(result.get("text") or "")
        if args.output:
            out = Path(args.output)
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(text, encoding="utf-8")
            print(f"WROTE {out}")
        else:
            print(text, end="")
    else:
        print(result.get("error") or "Atlas context export failed", file=sys.stderr)
    return 0 if result.get("ok") else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="atlas", description="Atlas local repository intelligence CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    context = sub.add_parser("context", help="Generate task-scoped context for an AI coding agent")
    context.add_argument("--repo", required=True, help="Local repository path")
    context.add_argument("--task", required=True, help="Natural-language coding task")
    context.add_argument("--target", choices=["claude", "cursor", "codex"], default="codex")
    context.add_argument("--max-files", type=int, default=12)
    context.add_argument("--output", default="", help="Optional output markdown path")
    context.add_argument("--json", action="store_true", help="Print structured JSON instead of markdown")
    context.set_defaults(func=_context)

    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
