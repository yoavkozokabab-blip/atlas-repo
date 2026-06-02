"""CLI for the Phase 99D historical bug replay harness."""

from __future__ import annotations

import argparse
import sys
from typing import List, Optional

from . import harness


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="builder-core-historical-replay",
        description="Replay buggy/fixed revisions through the confirmed-defect pipeline.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    run = sub.add_parser("run", help="Replay cases from a JSON manifest.")
    run.add_argument("--manifest", required=True, help="Path to replay manifest JSON.")
    run.add_argument("--output", required=True, help="Directory for replay artifacts.")
    run.add_argument(
        "--enable",
        action="store_true",
        help="Run even when HISTORICAL_BUG_REPLAY_ENABLED is False.",
    )
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        manifest = harness.load_json(args.manifest)
        harness.run_replay(
            manifest,
            args.output,
            enabled=args.enable or harness.HISTORICAL_BUG_REPLAY_ENABLED,
        )
        print(f"Replay artifacts written to {args.output}")
        return 0
    except (OSError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
