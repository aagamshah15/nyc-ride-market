"""Run metrics defined in sql/metrics/ over the aggregate tables.

Each metric is one SQL file; this module registers data/agg/*.parquet as views and runs
a named metric with parameters. Pages and publish.py read these outputs and never
recompute from trips.

Lane L09 · SPEC §6 · docs/lanes/L09-metrics.md
"""

from __future__ import annotations

import argparse

import pyarrow as pa

from pipeline.common import not_implemented

STUB_LANE = "L09"  # remove when the lane implements this module


def run(name: str, **params: object) -> pa.Table:
    """Run ``sql/metrics/{name}.sql`` with named parameters."""
    raise NotImplementedError(f"metrics.run (lane {STUB_LANE})")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m pipeline.metrics", description=__doc__)
    target = parser.add_mutually_exclusive_group(required=True)
    target.add_argument("name", nargs="?", help="metric file name without .sql")
    target.add_argument("--all", action="store_true", help="run every metric")
    parser.add_argument("--param", action="append", default=[], metavar="KEY=VALUE",
                        help="named parameter; repeatable")
    return parser


def main(argv: list[str] | None = None) -> None:
    build_parser().parse_args(argv)
    not_implemented(STUB_LANE, "metrics")


if __name__ == "__main__":
    main()
