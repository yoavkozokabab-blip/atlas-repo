"""Command-line entry point for the Phase 95A validation harness."""

from __future__ import annotations

import argparse
import sys
from typing import List, Optional

from . import harness


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="builder-core-validation",
        description="Read-only real-repository validation harness for Builder Core.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    run = sub.add_parser("run", help="Scan repositories from a preregistered manifest.")
    run.add_argument("--manifest", required=True, help="Path to the JSON repository manifest.")
    run.add_argument("--output", required=True, help="Artifact directory outside target repos.")

    report = sub.add_parser("report", help="Regenerate metrics and report after human review.")
    report.add_argument("--run-dir", required=True, help="Existing Phase 95A artifact directory.")
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "run":
            manifest = harness.load_manifest(args.manifest)
            harness.run_to_directory(manifest, args.output)
            print(f"Validation artifacts written to {args.output}")
            return 0
        harness.write_report_from_directory(args.run_dir)
        print(f"Validation report refreshed in {args.run_dir}")
        return 0
    except (OSError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
