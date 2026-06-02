"""Phase 95D interactive review helper CLI."""

from __future__ import annotations

import argparse
import sys
from typing import List, Optional

from . import review_tool as RT


def build_parser() -> argparse.ArgumentParser:
    parent = argparse.ArgumentParser(add_help=False)
    parent.add_argument(
        "--run-dir",
        required=True,
        help="Phase 95C artifact directory (contains reviewer_a_packets.json).",
    )

    parser = argparse.ArgumentParser(
        prog="builder-core-review",
        description="Phase 95D helper for blinded real-repository finding review.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    validate = sub.add_parser(
        "validate",
        parents=[parent],
        help="Validate packets, reviews, and decision files.",
    )
    validate.add_argument("--slot", default="reviewer_a", choices=sorted(RT.REVIEW_SLOTS))

    listing = sub.add_parser(
        "list",
        parents=[parent],
        help="List pending and reviewed record ids.",
    )
    listing.add_argument("--slot", default="reviewer_a", choices=sorted(RT.REVIEW_SLOTS))

    show = sub.add_parser(
        "show",
        parents=[parent],
        help="Show one candidate with metadata and source window.",
    )
    show.add_argument("--slot", default="reviewer_a", choices=sorted(RT.REVIEW_SLOTS))
    group = show.add_mutually_exclusive_group(required=True)
    group.add_argument("--record-id", help="Specific record id to display.")
    group.add_argument("--next", action="store_true", help="Show the next pending item.")

    decide = sub.add_parser(
        "decide",
        parents=[parent],
        help="Record a reviewer decision.",
    )
    decide.add_argument("--record-id", required=True)
    decide.add_argument(
        "--label",
        required=True,
        choices=sorted(RT.DECISION_LABELS),
    )
    decide.add_argument("--reviewer", required=True)
    decide.add_argument("--slot", default="reviewer_a", choices=sorted(RT.REVIEW_SLOTS))
    decide.add_argument("--notes", default="")
    decide.add_argument("--fp-reason", default="", help="Required context for false positives.")
    decide.add_argument("--review-minutes", type=float, default=None)
    decide.add_argument(
        "--edit",
        action="store_true",
        help="Overwrite an existing decision for this record.",
    )

    resume = sub.add_parser(
        "resume",
        parents=[parent],
        help="Show the next unanswered item (same as show --next).",
    )
    resume.add_argument("--slot", default="reviewer_a", choices=sorted(RT.REVIEW_SLOTS))

    report = sub.add_parser(
        "report",
        parents=[parent],
        help="Summarize review progress and estimates.",
    )
    report.add_argument("--slot", default="reviewer_a", choices=sorted(RT.REVIEW_SLOTS))

    export_csv = sub.add_parser(
        "export-csv",
        parents=[parent],
        help="Write deterministic decisions CSV.",
    )
    export_csv.add_argument("--slot", default="reviewer_a", choices=sorted(RT.REVIEW_SLOTS))
    export_csv.add_argument(
        "--output",
        default="",
        help="CSV path (default: <run-dir>/review_decisions.<slot>.csv).",
    )

    return parser


def main(argv: Optional[List[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        context = RT.load_run_context(args.run_dir)
    except (OSError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    slot = getattr(args, "slot", "reviewer_a")

    try:
        if args.command == "validate":
            issues = RT.validate_run_context(context, slot=slot)
            if issues:
                for issue in issues:
                    print(f"ISSUE: {issue}")
                return 1
            print("OK: run directory is ready for review.")
            return 0

        if args.command == "list":
            summary = RT.list_summary(context, slot)
            print(f"PENDING ({len(summary['pending'])})")
            for record_id in summary["pending"]:
                print(record_id)
            print(f"\nREVIEWED ({len(summary['reviewed'])})")
            for record_id in summary["reviewed"]:
                print(record_id)
            if summary["next"]:
                print(f"\nNEXT: {summary['next']}")
            return 0

        if args.command in {"show", "resume"}:
            record_id = args.record_id if args.command == "show" and not args.next else None
            if record_id is None:
                record_id = RT.next_pending_record_id(context, slot)
                if record_id is None:
                    print("All items reviewed for this slot.")
                    return 0
            print(RT.format_candidate(context, record_id, slot=slot))
            return 0

        if args.command == "decide":
            decision = RT.apply_decision(
                context,
                args.record_id,
                args.label,
                reviewer=args.reviewer,
                slot=slot,
                notes=args.notes,
                fp_reason=args.fp_reason,
                review_minutes=args.review_minutes,
                edit=args.edit,
            )
            print(f"Saved {args.record_id} -> {decision['label']} ({decision['harness_label']})")
            nxt = RT.next_pending_record_id(context, slot)
            if nxt:
                print(f"NEXT: {nxt}")
            else:
                print("Review complete for this slot.")
            return 0

        if args.command == "report":
            progress = RT.estimate_progress(context, slot)
            print(RT.format_progress_report(progress), end="")
            return 0

        if args.command == "export-csv":
            output = args.output or str(
                RT.decisions_path(context.run_dir, slot).with_suffix(".csv")
            )
            RT.write_decisions_csv(context, slot, output)
            print(f"Wrote {output}")
            return 0

    except (KeyError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    print(f"ERROR: unknown command {args.command}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
