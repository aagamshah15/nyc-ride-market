"""Clean trips for one month → that month's rows in every aggregate table (runs sql/agg/*.sql).

Deletes and rewrites only that month's rows in data/agg/{table}.parquet.

Lane L07 · SPEC §5 · decisions D7–D10 · docs/lanes/L07-aggregate.md
"""

from __future__ import annotations

import argparse

from pipeline.common import month_arg, not_implemented

STUB_LANE = "L07"  # remove when the lane implements this module


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m pipeline.aggregate", description=__doc__)
    parser.add_argument("--month", type=month_arg, metavar="YYYY-MM", required=True)
    return parser


def main(argv: list[str] | None = None) -> None:
    build_parser().parse_args(argv)
    not_implemented(STUB_LANE, "aggregate")


if __name__ == "__main__":
    main()
