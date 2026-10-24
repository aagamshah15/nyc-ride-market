"""DESCRIBE every trip file in scope and write reports/schema_discovery.md.

``--check`` is the SPEC §8 schema check: exit non-zero if any file has a column that
``config/schema_map.yaml`` neither maps nor ignores.

Lane L03 · SPEC §4, §8 · decision D11 · docs/lanes/L03-schema.md
"""

from __future__ import annotations

import argparse

from pipeline.common import month_arg, not_implemented

STUB_LANE = "L03"  # remove when the lane implements this module


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m pipeline.discover", description=__doc__)
    parser.add_argument("--month", type=month_arg, metavar="YYYY-MM",
                        help="limit to one month (default: every month in config/sources.yaml)")
    parser.add_argument("--check", action="store_true",
                        help="run the schema check instead of writing the report")
    return parser


def main(argv: list[str] | None = None) -> None:
    build_parser().parse_args(argv)
    not_implemented(STUB_LANE, "discover")


if __name__ == "__main__":
    main()
