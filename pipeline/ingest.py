"""Download one month of trip files, or the lookup files, each with a manifest entry.

Lane L02 · SPEC §3.1, §3.2 · docs/lanes/L02-ingest.md
"""

from __future__ import annotations

import argparse

from pipeline.common import month_arg, not_implemented

STUB_LANE = "L02"  # remove when the lane implements this module


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m pipeline.ingest", description=__doc__)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--month", type=month_arg, metavar="YYYY-MM",
                        help="download fhvhv, yellow and green for this month")
    action.add_argument("--ref", action="store_true",
                        help="download the zone lookup, zone shapefile and indicators CSV")
    action.add_argument("--check", type=month_arg, metavar="YYYY-MM",
                        help="HEAD all three datasets; exit 0 if all are posted, 1 if not")
    action.add_argument("--delete-raw", type=month_arg, metavar="YYYY-MM",
                        help="delete this month's raw trip files")
    parser.add_argument("--force", action="store_true",
                        help="download again even when the manifest matches")
    return parser


def main(argv: list[str] | None = None) -> None:
    build_parser().parse_args(argv)
    not_implemented(STUB_LANE, "ingest")


if __name__ == "__main__":
    main()
