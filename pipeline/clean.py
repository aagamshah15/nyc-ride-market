"""Raw trips for one month → unified, enriched, flagged trips (runs sql/clean/*.sql).

Writes data/clean/mode={mode}/month={YYYY-MM}/part-0.parquet. Flags rows; never drops them.

Lane L06 · SPEC §4, §4.1, §4.2 · docs/lanes/L06-clean.md
"""

from __future__ import annotations

import argparse

from pipeline.common import month_arg, not_implemented

STUB_LANE = "L06"  # remove when the lane implements this module


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m pipeline.clean", description=__doc__)
    parser.add_argument("--month", type=month_arg, metavar="YYYY-MM", required=True)
    return parser


def main(argv: list[str] | None = None) -> None:
    build_parser().parse_args(argv)
    not_implemented(STUB_LANE, "clean")


if __name__ == "__main__":
    main()
